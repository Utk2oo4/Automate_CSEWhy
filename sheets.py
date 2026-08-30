import os
import difflib
import base64
import json

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --------------------------------------------------
# SCOPES
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

# --------------------------------------------------
# AUTHENTICATE
# --------------------------------------------------

def authenticate() -> gspread.Client:
    """
    OAuth2 flow.
    - On Render (hosted): reads token from GOOGLE_TOKEN_B64 env var.
    - Locally: opens browser on first run, caches token in token.json.
    """
    creds = None

    # --- Hosted: load token from base64 env var ---
    token_b64 = os.environ.get("GOOGLE_TOKEN_B64")
    if token_b64:
        token_data = base64.b64decode(token_b64).decode("utf-8")
        creds = Credentials.from_authorized_user_info(
            json.loads(token_data), SCOPES
        )

    # --- Local: load token from file ---
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token back to file (local only)
            if not token_b64 and os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
        else:
            # Browser login — only works locally
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

    return gspread.authorize(creds)


# --------------------------------------------------
# FUZZY TAB MATCHING
# --------------------------------------------------

# When a batch keyword matches multiple tabs, prefer the tab containing this fragment.
# Key = substring of batch name (lowercase), Value = substring of preferred tab name (lowercase)
TAB_OVERRIDES = {
    "masterclass": "12 sep",
}


def find_tab(spreadsheet: gspread.Spreadsheet, batch_name: str) -> gspread.Worksheet | None:
    """
    Match batch_name to a sheet tab.
    - First checks TAB_OVERRIDES for explicit preferences on ambiguous tabs.
    - Falls back to fuzzy matching against all tab titles.
    Returns the matching worksheet, or None if no good match found.
    """
    if not batch_name:
        return None

    worksheets = spreadsheet.worksheets()
    tab_titles = [ws.title for ws in worksheets]
    batch_lower = batch_name.lower()
    titles_lower = [t.lower() for t in tab_titles]

    # Check if any override key appears in the batch name
    for keyword, preferred_fragment in TAB_OVERRIDES.items():
        if keyword in batch_lower:
            # Filter to only tabs that contain the preferred fragment
            filtered = [
                (i, t) for i, t in enumerate(titles_lower)
                if preferred_fragment in t
            ]
            if filtered:
                best_index, _ = filtered[0]
                return worksheets[best_index]

    # Default: fuzzy match against all tabs
    matches = difflib.get_close_matches(
        batch_lower,
        titles_lower,
        n=1,
        cutoff=0.3
    )

    if not matches:
        return None

    best_index = titles_lower.index(matches[0])
    return worksheets[best_index]


# --------------------------------------------------
# APPEND ROW
# --------------------------------------------------

def append_to_sheet(person: dict) -> tuple[bool, str]:
    """
    Append a person record to the correct tab based on their batch.

    Returns:
        (success: bool, message: str)
    """
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        return False, "GOOGLE_SHEET_ID is not set in .env"

    try:
        gc = authenticate()
        spreadsheet = gc.open_by_key(sheet_id)
    except Exception as e:
        return False, f"Could not open spreadsheet: {e}"

    batch = person.get("batch") or ""
    worksheet = find_tab(spreadsheet, batch)

    if worksheet is None:
        return False, (
            f"⚠️ Could not match batch \"{batch}\" to any sheet tab.\n"
            f"Please check the batch name."
        )

    # Find the next row (last filled row + 1)
    all_values = worksheet.get_all_values()

    # Determine next serial number from column A (skip header row 1)
    data_rows = [r for r in all_values[1:] if any(r)]  # skip blank rows
    next_sn = len(data_rows) + 1
    next_row = len(data_rows) + 2  # +1 for header, +1 for next

    name = person.get("name") or "Not Found"
    phone = person.get("phone") or ""
    email = person.get("email") or ""

    row_data = [next_sn, name, phone, email, batch]

    worksheet.insert_row(row_data, index=next_row)

    return True, (
        f"📊 Added to *{worksheet.title}*\n"
        f"Row {next_row} — Sn.No. {next_sn}"
    )
