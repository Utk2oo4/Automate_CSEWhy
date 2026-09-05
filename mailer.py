import os
import base64
import difflib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

# --------------------------------------------------
# EMAIL TEMPLATES
# Keyed by lowercase keywords used for fuzzy matching
# --------------------------------------------------

TEMPLATES = {
    "ai masterclass": {
        "match_keywords": ["masterclass", "ai masterclass"],
        "subject": "AI Masterclass Registration Confirmed – 12th September 2026",
        "cc": "whycse2@gmail.com",
        "body": """\
Dear Student,

Thank you for registering for the AI Masterclass with CSEWhy.

Your registration has been confirmed.

Date: 12th September 2026
Time: 5:00 PM
Mode: Live Online

WhatsApp Community: https://chat.whatsapp.com/GkqxHBpuAa2KDa7RP11BI4?s=sw&p=i&ilr=2

Please join the WhatsApp community for all updates regarding the masterclass. \
We'll also share the joining link and other details there before the session.

If you have any questions, feel free to reply to this email or contact us at 7011596808.

See you in the masterclass!


Team CSEWhy"""
    },

    "frontiers": {
        "match_keywords": ["frontiers", "frontier"],
        "subject": "AI Creator Fellowship- Frontiers Batch Update",
        "cc": "whycse2@gmail.com",
        "body": """\
Hello Student,

This is to inform you that your AI Creator Fellowship batch with CSEWhy will begin from mid-September 2026.

Batch Name: Frontiers

WhatsApp Group: https://chat.whatsapp.com/Di1BsET8zbcHc65z2BTWLy?mode=gi_t

Please ensure that all pending payments are cleared by 10th September 2026 to confirm your participation in the batch.

If you've joined any other AI Creator Fellowship WhatsApp groups, please exit them and stay in the Frontiers group only.

If you have any questions, feel free to reach out to us at 7011596808.

Thanks!
Team CSEWhy"""
    },

    "arjuna": {
        "match_keywords": ["arjuna", "arjuna batch", "ai for upsc"],
        "subject": "Update regarding AI for UPSC | Arjuna Batch",
        "cc": "whycse2@gmail.com",
        "body": """\
Hello Student,

This is to inform you that your AI for UPSC - Arjuna batch will begin from mid-September 2026.

Batch Name: Arjuna

WhatsApp Group: https://chat.whatsapp.com/KujS2edBFe8Anzg29TUk8X?mode=gi_t

You will be given access to the course portal and other study materials soon.

We’re excited to have you with us and look forward to being a part of your UPSC preparation journey. Wishing you a great and productive learning experience!

Best regards."""
    },

    "reformers": {
        "match_keywords": ["reformers", "reformer", "public policy"],
        "subject": "Public Policy Fellowship – Reformers Batch Update",
        "cc": "whycse2@gmail.com",
        "body": """\
Dear Student,

This is to inform you that your Public Policy Fellowship will begin in the last week of September 2026.

Whatsapp Group Link: https://chat.whatsapp.com/LlCwQFxb6yEINdppd2ZJGt?mode=gi_t

You will be given access to the course portal and other study materials soon. Further details regarding the batch schedule and sessions will be shared with you soon.

We’re excited to have you with us and look forward to being a part of your learning journey in public policy. Wishing you a great and productive learning experience!

If you have any questions, feel free to reach out to us at 7011596808.

Best regards,
Team CSEWhy"""
    },
}


# --------------------------------------------------
# SCOPES (must include Gmail send)
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


# --------------------------------------------------
# FIND TEMPLATE BY BATCH NAME (fuzzy match)
# --------------------------------------------------

def find_template(batch_name: str) -> dict | None:
    """Fuzzy-match batch name to the best email template."""
    if not batch_name:
        return None

    batch_lower = batch_name.lower()

    all_keywords = []
    keyword_to_template = {}
    for template_key, template in TEMPLATES.items():
        for kw in template["match_keywords"]:
            all_keywords.append(kw)
            keyword_to_template[kw] = template

    matches = difflib.get_close_matches(batch_lower, all_keywords, n=1, cutoff=0.4)
    if not matches:
        return None

    return keyword_to_template[matches[0]]


# --------------------------------------------------
# GET GMAIL CREDENTIALS
# --------------------------------------------------

def _get_creds() -> Credentials:
    """Load OAuth creds from env var (Render) or token.json (local)."""
    creds = None

    token_b64 = os.environ.get("GOOGLE_TOKEN_B64")
    if token_b64:
        token_data = json.loads(base64.b64decode(token_b64).decode("utf-8"))
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


# --------------------------------------------------
# SEND EMAIL via Gmail API (HTTPS — works on Render)
# --------------------------------------------------

def send_email(person: dict) -> tuple[bool, str]:
    """
    Send a batch-specific confirmation email to the student
    using the Gmail API over HTTPS (not SMTP).

    Returns:
        (success: bool, message: str)
    """
    to_email = person.get("email")
    if not to_email:
        return False, "⚠️ No email address to send to"

    batch = person.get("batch") or ""
    name = person.get("name") or "Student"

    template = find_template(batch)
    if template is None:
        return False, f"⚠️ No email template found for batch: \"{batch}\""

    try:
        creds = _get_creds()
        if not creds:
            return False, "❌ Gmail credentials not available"

        service = build("gmail", "v1", credentials=creds)

        # Build the email message
        msg = MIMEMultipart()
        msg["To"] = to_email
        msg["Cc"] = template["cc"]
        msg["Subject"] = template["subject"]
        msg["Message-ID"] = make_msgid()

        body = template["body"].format(name=name)
        msg.attach(MIMEText(body, "plain"))

        # Encode to base64url as required by Gmail API
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        return True, f"📧 Email sent to {to_email}"

    except HttpError as e:
        return False, f"❌ Gmail API error: {e}"
    except Exception as e:
        return False, f"❌ Email failed: {e}"
