import os
import pickle
import base64
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pkl'

def get_service():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
        creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def create_message(to, subject, body):
    msg = MIMEText(body)
    msg['to'] = to
    msg['from'] = os.getenv("SENDER_EMAIL")
    msg['subject'] = subject
    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {'raw': raw_msg}

def send_email_and_get_thread(subject, body, to_email):
    service = get_service()
    message = create_message(to_email, subject, body)
    sent_msg = service.users().messages().send(userId='me', body=message).execute()
    logger.info(f"Email sent to {to_email} with Thread ID: {sent_msg['threadId']}")
    return sent_msg['threadId']  # You’ll use this for listening
