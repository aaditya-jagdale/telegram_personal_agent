from email.utils import parseaddr
from googleapiclient.discovery import build
import pickle

TOKEN_FILE = 'token.pkl'

def get_service():
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return build('gmail', 'v1', credentials=creds)

def get_latest_message_in_thread(service, thread_id, sender_email):
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    messages = thread.get("messages", [])

    for msg in reversed(messages):  # Check newest first
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        from_email = parseaddr(headers.get("From", ""))[1]

        if from_email != sender_email:
            return {
                "from": from_email,
                "snippet": msg.get("snippet"),
                "timestamp": headers.get("Date")
            }

    return None
