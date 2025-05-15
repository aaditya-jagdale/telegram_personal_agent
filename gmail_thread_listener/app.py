from flask import Flask, request, jsonify
from email_service.provider import send_email_and_get_thread
from email_service.listener import get_service, get_latest_message_in_thread
import os
import json
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# In-memory storage for mapping thread IDs (for demo; use Redis/DB in prod)
active_threads = {}

@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json()
    subject = data.get("subject")
    body = data.get("body")
    receiver = data.get("receiver")

    if not all([subject, body, receiver]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        thread_id = send_email_and_get_thread(subject, body, receiver)
        active_threads[thread_id] = receiver

        return jsonify({
            "message": "Email sent",
            "thread_id": thread_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/gmail/webhook", methods=["POST"])
def gmail_webhook():
    try:
        envelope = request.get_json(force=True, silent=True)

        if not envelope or "message" not in envelope:
            print("⚠️ No 'message' in the request body.")
            return "No content", 204

        encoded_data = envelope["message"].get("data")

        if not encoded_data:
            print("⚠️ No 'data' field inside 'message'.")
            return "Missing data", 204

        # Decode base64 data payload from Pub/Sub
        decoded_data = base64.urlsafe_b64decode(encoded_data + '==').decode("utf-8")
        print(f"📨 Push notification received: {decoded_data}")

        # Try parsing decoded data to JSON
        history = json.loads(decoded_data)
        history_id = history.get("historyId")
        if not history_id:
            print("⚠️ No 'historyId' found in decoded data.")
            return "No history ID", 204

        print(f"📩 Gmail historyId received: {history_id}")

        # Fetch reply message using Gmail API
        service = get_service()
        for thread_id, receiver in active_threads.items():
            reply = get_latest_message_in_thread(service, thread_id, receiver)
            if reply:
                print(f"\n✅ New reply detected:")
                print(f"From: {reply['from']}")
                print(f"Date: {reply['timestamp']}")
                print(f"Content: {reply['snippet']}\n")

        return "", 204

    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        return "Webhook error", 500


if __name__ == "__main__":
    app.run(port=8081)
