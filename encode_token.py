"""
Run this script ONCE locally to get the base64 value of your token.json.
Paste the output as GOOGLE_TOKEN_B64 in Render's environment variables.
"""
import base64, os

token_path = os.path.join(os.path.dirname(__file__), "token.json")

if not os.path.exists(token_path):
    print("❌ token.json not found. Run the bot locally first to generate it.")
else:
    with open(token_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    print("\n✅ Copy this value into Render as GOOGLE_TOKEN_B64:\n")
    print(encoded)