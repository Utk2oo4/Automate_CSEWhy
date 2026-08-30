# 📋 CSEWhy Enrollment Automation Bot

A Telegram bot that automatically extracts student enrollment data from messages and images, saves it to Google Sheets, and sends confirmation emails — all without any manual work.

---

## ✨ Features

- 🔍 **Smart Extraction** — Uses Gemini AI to extract name, phone, email, and batch from any text or image
- 🧠 **Session Memory** — Handles split messages (e.g. name in one message, phone in another)
- 📊 **Google Sheets** — Auto-adds each student to the correct batch tab
- 📧 **Auto Email** — Sends a batch-specific confirmation email instantly
- 🖼️ **Image Support** — Works with screenshots, photos, and file uploads
- 🌐 **Health Check** — `/health` endpoint keeps the bot alive on Render

---

## 🗂️ Project Structure

```
automate/
├── automate.py        # Main bot — Telegram handlers & session logic
├── sheets.py          # Google Sheets integration (OAuth2)
├── mailer.py          # Email sending (Gmail SMTP)
├── health.py          # Flask health check server for Render
├── encode_token.py    # One-time utility to encode token.json for hosting
├── email_format.txt   # Reference email templates
├── requirements.txt   # Python dependencies
├── render.yaml        # Render deployment config
└── .gitignore
```

---

## ⚙️ Setup

### 1. Clone & create virtual environment

```bash
git clone <your-repo-url>
cd automate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
SENDER_EMAIL=your_gmail@gmail.com
SENDER_APP_PASSWORD=your_16_char_app_password
```

### 3. Set up Google Sheets OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Google Sheets API** and **Google Drive API**
3. Create **OAuth 2.0 credentials** → type: **Desktop app**
4. Download as `credentials.json` into the project folder
5. Add your Gmail as a test user in the OAuth consent screen
6. Run the bot once locally — a browser login prompt will appear
7. After login, `token.json` is generated automatically

### 4. Run locally

```bash
source venv/bin/activate
python3 automate.py
```

---

## 📊 Google Sheet Structure

Each batch has its own tab. Columns:

| A | B | C | D | E |
|---|---|---|---|---|
| Sn. No. | Name | Phone | Email | Batch |

**Tab matching** is fuzzy — `"Frontier"` → `"Frontiers | AI Fellowship"` automatically.

To override ambiguous matches, edit `TAB_OVERRIDES` in `sheets.py`:
```python
TAB_OVERRIDES = {
    "masterclass": "12 sep",  # Always pick the 12 Sep tab
}
```

---

## 📧 Email Templates

Templates are defined in `mailer.py` under `TEMPLATES`. Each template has:
- `match_keywords` — what batch names trigger this template
- `subject` — email subject line
- `cc` — CC address
- `body` — email body (supports `{name}` placeholder)

---

## 🤖 Bot Commands

| Command | Action |
|---------|--------|
| `/clear` | Reset your pending session (start over) |

---

## 🚀 Deploy to Render

### 1. Encode your token for the server

```bash
python3 encode_token.py
```

Copy the printed base64 string.

### 2. Push to GitHub

```bash
git add .
git commit -m "initial commit"
git push
```

### 3. Create Render Web Service

- Go to [render.com](https://render.com) → **New → Web Service**
- Connect your GitHub repo (Render auto-detects `render.yaml`)

### 4. Add environment variables in Render dashboard

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | your token |
| `GEMINI_API_KEY` | your key |
| `GOOGLE_SHEET_ID` | your sheet ID |
| `SENDER_EMAIL` | your Gmail |
| `SENDER_APP_PASSWORD` | 16-char app password |
| `GOOGLE_TOKEN_B64` | output from `encode_token.py` |

### 5. Keep alive with cron-job.org

- Go to [cron-job.org](https://cron-job.org) → create a free account
- Add job: `https://your-app.onrender.com/health` every **5 minutes**

---

## 🔑 Getting API Keys

| Key | Where to get |
|-----|-------------|
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) on Telegram |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `GOOGLE_SHEET_ID` | From your sheet URL: `.../spreadsheets/d/**ID**/edit` |
| `SENDER_APP_PASSWORD` | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |

---

## 📝 License

Internal tool — CSEWhy © 2026
