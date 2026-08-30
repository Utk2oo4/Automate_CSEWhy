import os
import smtplib
import difflib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid

# --------------------------------------------------
# EMAIL TEMPLATES
# Keyed by lowercase keywords used for fuzzy matching
# --------------------------------------------------

TEMPLATES = {
    "ai masterclass": {
        "match_keywords": ["masterclass", "ai masterclass"],
        "subject": "AI Masterclass Registration Confirmed – 12th September 2026",
        "cc": "whycse@gmail.com",
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
        "cc": "whycse@gmail.com",
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
}


# --------------------------------------------------
# FIND TEMPLATE BY BATCH NAME (fuzzy match)
# --------------------------------------------------

def find_template(batch_name: str) -> dict | None:
    """Fuzzy-match batch name to the best email template."""
    if not batch_name:
        return None

    batch_lower = batch_name.lower()

    # Collect all keywords with their template keys
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
# SEND EMAIL
# --------------------------------------------------

def send_email(person: dict) -> tuple[bool, str]:
    """
    Send a batch-specific confirmation email to the student.

    Returns:
        (success: bool, message: str)
    """
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        return False, "⚠️ SENDER_EMAIL or SENDER_APP_PASSWORD not set in .env"

    to_email = person.get("email")
    if not to_email:
        return False, "⚠️ No email address to send to"

    batch = person.get("batch") or ""
    name = person.get("name") or "Student"

    template = find_template(batch)

    if template is None:
        return False, f"⚠️ No email template found for batch: \"{batch}\""

    # Build email
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Cc"] = template["cc"]
    msg["Subject"] = template["subject"]
    msg["Message-ID"] = make_msgid()  # unique ID prevents Gmail threading

    body = template["body"].format(name=name)
    msg.attach(MIMEText(body, "plain"))

    recipients = [to_email, template["cc"]]

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        return True, f"📧 Email sent to {to_email}"

    except Exception as e:
        return False, f"❌ Email failed: {e}"
