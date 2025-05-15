import os
import time
import requests
import subprocess
from googleapiclient.discovery import build
import pickle

# Configs
TOKEN_FILE = "token.pkl"
NGROK_PORT = 8081
NGROK_API = "http://localhost:4040/api/tunnels"
PUBSUB_TOPIC = "projects/market-simplified/topics/gmail-updates"

def get_gmail_service():
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return build('gmail', 'v1', credentials=creds)

def start_ngrok(port):
    print("Starting ngrok...")
    subprocess.Popen(["ngrok", "http", str(port)])
    time.sleep(3)  # wait for ngrok to initialize

    try:
        res = requests.get(NGROK_API).json()
        for tunnel in res["tunnels"]:
            if tunnel["proto"] == "https":
                return tunnel["public_url"]
    except Exception as e:
        print("Failed to get ngrok tunnel:", e)
        return None

def register_gmail_watch(service, ngrok_url):
    watch_request = {
        "labelIds": ["INBOX"],
        "topicName": PUBSUB_TOPIC
    }

    try:
        response = service.users().watch(
            userId='me',
            body=watch_request
        ).execute()

        print(f"✅ Gmail watch started. Webhook will hit: {ngrok_url}/gmail/webhook")
        print("Response:", response)
    except Exception as e:
        print("Failed to start Gmail watch:", e)

if __name__ == "__main__":
    public_url = start_ngrok(NGROK_PORT)
    if not public_url:
        print("❌ ngrok tunnel not established. Exiting.")
        exit(1)

    webhook_url = f"{public_url}/gmail/webhook"
    print(f"📡 Webhook endpoint: {webhook_url}")

    service = get_gmail_service()
    register_gmail_watch(service, public_url)
