import os
import threading
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/")
def root():
    return jsonify({"status": "ok", "service": "telegram-bot"}), 200

def start_health_server():
    """Start Flask health server in a background daemon thread."""
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_in_thread():
    thread = threading.Thread(target=start_health_server, daemon=True)
    thread.start()
