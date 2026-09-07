"""
Run this script locally to re-authenticate with Google and generate a new token.
It will:
1. Open your browser to log into Google and grant permissions.
2. Save the fresh token to token.json.
3. Print the base64 string to update GOOGLE_TOKEN_B64 in Render.
"""
import os
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ credentials.json not found at: {CREDENTIALS_FILE}")
        return

    print("🌐 Opening browser for Google login...")
    print("👉 If a warning appears ('Google hasn't verified this app'), click 'Advanced' -> 'Go to automate-why (unsafe)' -> Continue.")
    
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print("✅ New token.json generated and saved!")

    with open(TOKEN_FILE, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    print("\n" + "=" * 60)
    print("📋 Copy this base64 string and update GOOGLE_TOKEN_B64 in Render:")
    print("=" * 60)
    print(encoded)
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
