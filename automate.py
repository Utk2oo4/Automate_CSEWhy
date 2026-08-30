import os
import json
import base64
import traceback
from io import BytesIO
from datetime import datetime, timedelta

from dotenv import load_dotenv
from google import genai
from google.genai import types

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from sheets import append_to_sheet
from mailer import send_email
# health import removed — PTB webhook server handles the HTTP port directly

# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")


# --------------------------------------------------
# GEMINI CLIENT
# --------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)


# --------------------------------------------------
# SESSION STORE
# --------------------------------------------------

SESSION_TIMEOUT_MINUTES = 30

# { user_id: {"data": {field: value, ...}, "updated_at": datetime} }
user_sessions: dict[int, dict] = {}


def get_session(user_id: int) -> dict:
    """Return the user's pending partial record, or empty dict if expired/absent."""
    session = user_sessions.get(user_id)
    if session:
        age = datetime.now() - session["updated_at"]
        if age < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            return session["data"]
        else:
            del user_sessions[user_id]
    return {}


def save_session(user_id: int, data: dict):
    """Persist a partial record for the user."""
    user_sessions[user_id] = {
        "data": data,
        "updated_at": datetime.now()
    }


def clear_session(user_id: int):
    """Remove the user's pending session."""
    user_sessions.pop(user_id, None)


def merge_person(existing: dict, new: dict) -> dict:
    """
    Merge new fields into existing partial record.
    Only fills in fields that are currently missing (None / absent).
    """
    merged = dict(existing)
    for field in ("name", "phone", "email", "batch"):
        if not merged.get(field) and new.get(field):
            merged[field] = new[field]
    return merged


def missing_fields(person: dict) -> list[str]:
    """Return list of required fields that are still missing."""
    missing = []
    for field in ("phone", "email", "batch"):
        if not person.get(field):
            missing.append(field)
    return missing


def process_extracted(user_id: int, data: dict) -> str:
    """
    Given raw Gemini output for a user, merge with their session,
    return the final reply string, and update / clear the session.
    """
    people = data.get("people", [])

    if not people:
        return "\u274c No enrollment information found."

    # If multiple people are found in one message, process all independently.
    if len(people) > 1:
        valid, incomplete = validate_people(data)
        reply = format_results(valid, incomplete)

        # Append each valid record to sheet and send email
        sheet_lines = []
        for person in valid:
            ok, msg = append_to_sheet(person)
            sheet_lines.append(msg)
            email_ok, email_msg = send_email(person)
            sheet_lines.append(email_msg)

        if sheet_lines:
            reply += "\n" + "\n".join(sheet_lines)

        return reply

    new_person = people[0]
    existing = get_session(user_id)
    merged = merge_person(existing, new_person)

    still_missing = missing_fields(merged)

    if still_missing:
        # Save and ask for remaining fields
        save_session(user_id, merged)
        name = merged.get("name") or "Record"
        fields_str = ", ".join(still_missing)
        return (
            f"\u23f3 Partial record saved for *{name}*.\n"
            f"Still missing: `{fields_str}`\n\n"
            f"Send the missing info and I'll complete the record.\n"
            f"_(Type /clear to start over)_"
        )
    else:
        # Complete! Clear session, write to sheet, send email, return result.
        clear_session(user_id)
        valid, incomplete = validate_people({"people": [merged]})
        reply = format_results(valid, incomplete)

        if valid:
            ok, sheet_msg = append_to_sheet(valid[0])
            reply += f"\n{sheet_msg}"
            email_ok, email_msg = send_email(valid[0])
            reply += f"\n{email_msg}"

        return reply


# --------------------------------------------------
# EXTRACTION SCHEMA
# --------------------------------------------------

PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "nullable": True,
            "description": "Person's name. Optional."
        },
        "phone": {
            "type": "string",
            "nullable": True,
            "description": "Phone number. Required."
        },
        "email": {
            "type": "string",
            "nullable": True,
            "description": "Email address. Required."
        },
        "batch": {
            "type": "string",
            "nullable": True,
            "description": "Batch name. Required."
        }
    },
    "required": [
        "name",
        "phone",
        "email",
        "batch"
    ]
}


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": PERSON_SCHEMA
        }
    },
    "required": ["people"]
}


# --------------------------------------------------
# EXTRACTION PROMPT
# --------------------------------------------------

EXTRACTION_PROMPT = """
You are an enrollment-data extraction system.

Extract enrollment information from the provided text and/or image.

For every person, extract:

1. name
2. phone
3. email
4. batch

IMPORTANT RULES:

- Name is OPTIONAL.
- Phone is REQUIRED.
- Email is REQUIRED.
- Batch is REQUIRED.
- There may be multiple people in the same message or image.
- Create a separate object for EVERY person.
- Never combine two different people.
- Never invent missing information.
- If a field cannot be confidently identified, return null.
- Preserve the batch name as written.
- Normalize email addresses to lowercase.
- Keep phone numbers as strings so leading zeros are not lost.
- Ignore unrelated text.
"""


# --------------------------------------------------
# GEMINI TEXT EXTRACTION
# --------------------------------------------------

def extract_from_text(text: str):

    response = client.models.generate_content(
        model="gemini-2.0-flash",

        contents=[
            EXTRACTION_PROMPT,
            f"""
Here is the Telegram message:

{text}
"""
        ],

        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    )

    return json.loads(response.text)


# --------------------------------------------------
# GEMINI IMAGE EXTRACTION
# --------------------------------------------------

def extract_from_image(image_bytes: bytes, mime_type: str, caption: str = None):

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    )

    contents = [EXTRACTION_PROMPT, image_part]

    if caption:
        contents.append(f"\nCaption from the message: {caption}")

    response = client.models.generate_content(
        model="gemini-2.0-flash",

        contents=contents,

        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    )

    return json.loads(response.text)


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

def validate_people(data):

    valid = []
    incomplete = []

    for person in data.get("people", []):

        name = person.get("name")
        phone = person.get("phone")
        email = person.get("email")
        batch = person.get("batch")

        missing = []

        if not phone:
            missing.append("phone")

        if not email:
            missing.append("email")

        if not batch:
            missing.append("batch")

        if missing:

            incomplete.append({
                "person": person,
                "missing": missing
            })

        else:

            valid.append(person)

    return valid, incomplete


# --------------------------------------------------
# FORMAT TELEGRAM RESPONSE
# --------------------------------------------------

def format_results(valid, incomplete):

    message = ""

    if valid:

        message += f"✅ Found {len(valid)} valid record(s)\n\n"

        for i, person in enumerate(valid, 1):

            name = person.get("name") or "Name not provided"

            message += (
                f"{i}. {name}\n"
                f"📱 {person['phone']}\n"
                f"📧 {person['email']}\n"
                f"🎓 {person['batch']}\n\n"
            )

    if incomplete:

        message += "⚠️ Incomplete record(s)\n\n"

        for i, item in enumerate(incomplete, 1):

            person = item["person"]

            name = person.get("name") or "Unknown person"

            missing = ", ".join(item["missing"])

            message += (
                f"{i}. {name}\n"
                f"Missing: {missing}\n\n"
            )

    if not message:

        message = "❌ No enrollment information found."

    return message


# --------------------------------------------------
# HANDLE TEXT
# --------------------------------------------------

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text
    user_id = update.effective_user.id

    await update.message.reply_text(
        "🔍 Reading the message..."
    )

    try:

        data = extract_from_text(text)

        print("\nGEMINI RESULT:")
        print(json.dumps(data, indent=2))

        message = process_extracted(user_id, data)

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR:", tb)
        short = tb[-800:]  # last 800 chars fits in Telegram
        await update.message.reply_text(
            f"❌ Error (text):\n```\n{short}\n```",
            parse_mode="Markdown"
        )


# --------------------------------------------------
# CLEAR COMMAND
# --------------------------------------------------

async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    clear_session(user_id)
    await update.message.reply_text(
        "🗑️ Session cleared. Send a new message to start fresh."
    )


# --------------------------------------------------
# HANDLE IMAGE
# --------------------------------------------------

async def handle_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🖼️ Reading the image..."
    )

    try:

        user_id = update.effective_user.id
        photo = update.message.photo[-1]
        caption = update.message.caption

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        image_bytes = BytesIO()

        await telegram_file.download_to_memory(
            image_bytes
        )

        image_bytes.seek(0)

        data = extract_from_image(
            image_bytes.read(),
            "image/jpeg",
            caption=caption
        )

        print("\nGEMINI RESULT:")
        print(json.dumps(data, indent=2))

        message = process_extracted(user_id, data)

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR:", tb)
        short = tb[-800:]
        await update.message.reply_text(
            f"❌ Error (image):\n```\n{short}\n```",
            parse_mode="Markdown"
        )


# --------------------------------------------------
# HANDLE DOCUMENT (image sent as file)
# --------------------------------------------------

SUPPORTED_IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"
}

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    doc = update.message.document
    mime_type = doc.mime_type or "image/jpeg"

    if mime_type not in SUPPORTED_IMAGE_MIMES:
        await update.message.reply_text(
            "⚠️ Please send a supported image type (JPEG, PNG, WEBP, GIF, HEIC)."
        )
        return

    await update.message.reply_text(
        "🖼️ Reading the image file..."
    )

    try:

        user_id = update.effective_user.id
        caption = update.message.caption

        telegram_file = await context.bot.get_file(doc.file_id)

        image_bytes = BytesIO()
        await telegram_file.download_to_memory(image_bytes)
        image_bytes.seek(0)

        data = extract_from_image(
            image_bytes.read(),
            mime_type,
            caption=caption
        )

        print("\nGEMINI RESULT:")
        print(json.dumps(data, indent=2))

        message = process_extracted(user_id, data)

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR:", tb)
        short = tb[-800:]
        await update.message.reply_text(
            f"❌ Error (doc):\n```\n{short}\n```",
            parse_mode="Markdown"
        )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    # --------------------------------------------------
    # WEBHOOK MODE (required for Render)
    # Render sets PORT and RENDER_EXTERNAL_URL automatically.
    # run_polling() does NOT work on Render free tier (errno 101).
    # --------------------------------------------------

    port = int(os.environ.get("PORT", 8080))
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # /clear command
    application.add_handler(
        CommandHandler("clear", clear_command)
    )

    # Text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # Images (compressed)
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_image
        )
    )

    # Images sent as files/documents
    application.add_handler(
        MessageHandler(
            filters.Document.IMAGE,
            handle_document
        )
    )

    print("🤖 Telegram bot is running...")

    if render_url:
        # --- Hosted on Render: use webhook ---
        webhook_url = f"{render_url}/{TELEGRAM_BOT_TOKEN}"
        print(f"🌐 Webhook mode: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=webhook_url,
        )
    else:
        # --- Local development: use polling ---
        print("🔄 Polling mode (local)")
        application.run_polling()


# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":
    main()