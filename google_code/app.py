import os
import base64
import json
import time
from email.mime.text import MIMEText
import re
from email.utils import getaddresses # Added for parsing To/Cc headers

from flask import Flask, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import pubsub_v1

# --- Configuration ---
# Fill these in with your details
PATH_TO_CREDENTIALS = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/pubsub']
YOUR_EMAIL_ADDRESS = 'aadi.lf21r@gmail.com'  # The bot's email address
RECIPIENT_EMAIL = 'aadityajagdale.21@gmail.com' # Email to send the initial message to
GCP_PROJECT_ID = 'market-simplified'
PUBSUB_TOPIC_ID = 'gmail-updates'   

# Global variables
gmail_service = None
TRACKED_THREAD_ID = None
LAST_PROCESSED_HISTORY_ID = None
PROCESSED_MESSAGE_IDS = set()

app = Flask(__name__)

# --- Gmail Authentication and Service ---
def get_gmail_service():
    """Authenticates and returns a Gmail API service object."""
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except ValueError:
            print("Error loading token.json. It might be corrupted. Please delete it and re-authenticate.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("⏳ Refreshing expired token...")
                creds.refresh(Request())
                print("✅ Token refreshed successfully.")
            except Exception as e:
                print(f"❌ Failed to refresh token: {e}. Please re-authenticate.")
                if os.path.exists('token.json'):
                    os.remove('token.json')
                flow = InstalledAppFlow.from_client_secrets_file(PATH_TO_CREDENTIALS, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            print("ℹ️ No valid credentials found or token needs to be created. Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(PATH_TO_CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
        print("🔑 Authentication successful. Credentials saved to token.json.")
    return build('gmail', 'v1', credentials=creds)

# --- Email Helper Functions ---
def extract_emails_from_header(header_value):
    """Extracts email addresses from a header string (e.g., To, Cc), returns them in lowercase."""
    if not header_value:
        return []
    # getaddresses returns list of (realname, email_address) tuples
    return [addr.lower() for name, addr in getaddresses([header_value]) if addr]

# Modified create_message function
def create_message(sender, to, subject, message_text, thread_id=None, cc=None, in_reply_to=None, references=None):
    """Creates a MIMEText email message object for Gmail API.

    Args:
        sender: Email address of the sender.
        to: Email address of the primary recipient.
        subject: Subject of the email.
        message_text: Plain text body of the email.
        thread_id: Optional. ID of the thread to reply to.
        cc: Optional. Comma-separated string of CC email addresses.
        in_reply_to: Optional. Message-ID of the email being replied to.
        references: Optional. References header string.

    Returns:
        A dict containing the raw, base64url encoded email message, suitable for Gmail API.
    """
    message = MIMEText(message_text)
    message['to'] = to
    if cc: # Only add CC header if cc is not None or empty
        message['cc'] = cc
    message['from'] = sender
    message['subject'] = subject # Gmail usually handles "Re:" prefix for replies in a thread
    if in_reply_to:
        message['In-Reply-To'] = in_reply_to
    if references:
        message['References'] = references

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw_message}
    if thread_id:
        body['threadId'] = thread_id
    return body

def get_latest_reply_text(full_text_body):
    """Attempts to extract only the latest reply from an email body."""
    gmail_quote_header_pattern = re.compile(
        r"^\s*(On|Am|El|Le)\s+"
        r"([A-Za-zÀ-ÖØ-öø-ÿ]+[,.]?\s+)?\d{1,2}\s+[A-Za-zÀ-ÖØ-öø-ÿ]+[,.]?\s+\d{4}([,.]?\s+(at|à)|,)\s+\d{1,2}:\d{2}(\s+(AM|PM))?[,.]?"
        r".*(wrote|écrit|escribió)\s*:\s*$",
        re.IGNORECASE | re.MULTILINE
    )
    match = gmail_quote_header_pattern.search(full_text_body)
    if match:
        return full_text_body[:match.start()].strip()
    else:
        lines = full_text_body.splitlines()
        latest_reply_lines = []
        for line in lines:
            if line.strip().startswith(">"):
                break
            latest_reply_lines.append(line)
        if latest_reply_lines and len(latest_reply_lines) < len(lines):
            return "\n".join(latest_reply_lines).strip()
        else:
            return full_text_body.strip()

def send_message(service, user_id, message_body, is_initial_email=False):
    """Sends an email message."""
    try:
        message = service.users().messages().send(userId=user_id, body=message_body).execute()
        log_prefix = "🚀 Initial Tracked Email Sent." if is_initial_email else "✉️ Echo Message Sent."
        print(f"{log_prefix} ID: {message['id']}, Thread ID: {message.get('threadId')}")
        return message
    except HttpError as error:
        log_prefix = "initial" if is_initial_email else "echo"
        print(f'❌ An error occurred while sending {log_prefix} message: {error}')
        return None

# --- Gmail Watch Management ---
def start_gmail_watch(service, project_id, topic_id, user_id='me'):
    global LAST_PROCESSED_HISTORY_ID
    topic_name = f'projects/{project_id}/topics/{topic_id}'
    request_body = {
        'labelIds': ['INBOX'],
        'labelFilterBehavior': 'INCLUDE',
        'topicName': topic_name
    }
    try:
        response = service.users().watch(userId=user_id, body=request_body).execute()
        print(f"✅ Watch request successful for user '{user_id}'. Response: {response}")
        LAST_PROCESSED_HISTORY_ID = response.get('historyId')
        print(f"📜 Initial historyId set to: {LAST_PROCESSED_HISTORY_ID}")
        expiration_ms = response.get('expiration')
        if expiration_ms:
            print(f"⏳ Watch expires at: {time.ctime(int(expiration_ms)/1000)}")
        return response
    except HttpError as error:
        print(f"❌ An error occurred during watch request for user '{user_id}': {error}")
        return None

def stop_gmail_watch(service, user_id='me'):
    try:
        service.users().stop(userId=user_id).execute()
        print(f"🛑 Successfully stopped watching Gmail mailbox for user '{user_id}'.")
    except HttpError as error:
        print(f"❌ An error occurred while stopping watch for user '{user_id}': {error}")

# --- Webhook and Message Processing ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """Receives push notifications from Pub/Sub for Gmail updates."""
    global gmail_service, LAST_PROCESSED_HISTORY_ID, TRACKED_THREAD_ID, YOUR_EMAIL_ADDRESS, PROCESSED_MESSAGE_IDS

    print("\n--- 📬 WEBHOOK HIT ---")
    if not gmail_service:
        print("❌ Webhook: Gmail service not initialized.")
        return jsonify({'status': 'error', 'message': 'Gmail service not ready'}), 500
    if not TRACKED_THREAD_ID:
        print("❌ Webhook: TRACKED_THREAD_ID is not set.")
        return jsonify({'status': 'error', 'message': 'TRACKED_THREAD_ID not configured'}), 500

    envelope = request.get_json(silent=True)
    if not envelope:
        print('❌ Webhook: No Pub/Sub message received or not valid JSON.')
        if request.data: print(f"Request data (not JSON): {request.data}")
        return jsonify({'status': 'error', 'message': 'Bad request format'}), 400
    
    print(f"📦 Webhook: Received envelope: {json.dumps(envelope, indent=2)}")
    if not isinstance(envelope, dict) or 'message' not in envelope:
        print(f'❌ Webhook: Invalid Pub/Sub message format: {envelope}')
        return jsonify({'status': 'error', 'message': 'Invalid Pub/Sub message format'}), 400

    pubsub_message = envelope['message']
    if isinstance(pubsub_message, dict) and 'data' in pubsub_message:
        try:
            data_bytes = base64.b64decode(pubsub_message['data'])
            data_str = data_bytes.decode('utf-8')
            message_data = json.loads(data_str)
            print(f"📊 Webhook: Decoded Pub/Sub message data: {json.dumps(message_data, indent=2)}")

            email_address_from_notification = message_data.get('emailAddress')
            history_id_from_notification = message_data.get('historyId')

            print(f"📧 Webhook: Notification for email: {email_address_from_notification}, historyId: {history_id_from_notification}")

            if email_address_from_notification.lower() != YOUR_EMAIL_ADDRESS.lower():
                print(f"⚠️ Webhook: Notification for different email ({email_address_from_notification}), expected ({YOUR_EMAIL_ADDRESS}). Skipping.")
                return jsonify({'status': 'success', 'message': 'Notification for different user'}), 200

            if not history_id_from_notification:
                print("❌ Webhook: No historyId in notification payload.")
                return jsonify({'status': 'error', 'message': 'No historyId in notification'}), 400
            
            current_start_history_id = LAST_PROCESSED_HISTORY_ID
            if not current_start_history_id:
                print(f"⚠️ Webhook: LAST_PROCESSED_HISTORY_ID was not set. Using historyId from notification ({history_id_from_notification}) as start point.")
                current_start_history_id = history_id_from_notification
            
            print(f"⏳ Webhook: Processing Gmail history starting AFTER historyId: {current_start_history_id}")
            history_response = gmail_service.users().history().list(
                userId='me', startHistoryId=str(current_start_history_id), historyTypes=['messageAdded']
            ).execute()
            print(f"📜 Webhook: Gmail history.list API response: {json.dumps(history_response, indent=2)}")

            all_history_records = history_response.get('history', [])
            next_page_token = history_response.get('nextPageToken')
            while next_page_token:
                print(f"📑 Webhook: Fetching next page of history with token: {next_page_token}")
                history_response = gmail_service.users().history().list(
                    userId='me', startHistoryId=str(current_start_history_id),
                    historyTypes=['messageAdded'], pageToken=next_page_token
                ).execute()
                print(f"📜 Webhook: Gmail history.list API response (paginated): {json.dumps(history_response, indent=2)}")
                all_history_records.extend(history_response.get('history', []))
                next_page_token = history_response.get('nextPageToken')
            
            if not all_history_records: print("ℹ️ Webhook: No history records found since last processed ID.")

            new_messages_found_in_thread = False
            for history_record in all_history_records:
                messages_added = history_record.get('messagesAdded', [])
                for added_msg_info in messages_added:
                    msg_id = added_msg_info['message']['id']
                    msg_thread_id = added_msg_info['message']['threadId']
                    print(f"  📧 Webhook: Found added message. ID: {msg_id}, Thread ID: {msg_thread_id}")

                    if msg_id in PROCESSED_MESSAGE_IDS:
                        print(f"    ⏩ Webhook: Message {msg_id} already processed. Skipping.")
                        continue

                    if msg_thread_id == TRACKED_THREAD_ID:
                        print(f"    🎯 Webhook: Message {msg_id} IS in TRACKED thread {TRACKED_THREAD_ID}.")
                        new_messages_found_in_thread = True
                        
                        full_message = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                        payload = full_message.get('payload', {})
                        headers = payload.get('headers', [])
                        
                        sender_email_raw = "Unknown Sender"
                        original_subject = "Original Thread Subject"
                        incoming_message_id = None
                        incoming_references = None
                        incoming_to_emails = []
                        incoming_cc_emails = []

                        for header in headers:
                            name_lower = header['name'].lower()
                            if name_lower == 'from': sender_email_raw = header['value']
                            elif name_lower == 'subject': original_subject = header['value']
                            elif name_lower == 'message-id': incoming_message_id = header['value']
                            elif name_lower == 'references': incoming_references = header['value']
                            elif name_lower == 'to': incoming_to_emails = extract_emails_from_header(header['value'])
                            elif name_lower == 'cc': incoming_cc_emails = extract_emails_from_header(header['value'])
                        
                        parsed_sender_list = extract_emails_from_header(sender_email_raw) # Returns lowercase emails
                        sender_email = "" # Initialize sender_email
                        if parsed_sender_list:
                            sender_email = parsed_sender_list[0]
                        else: # Fallback for parsing From header
                            if '<' in sender_email_raw and '>' in sender_email_raw:
                                sender_email = sender_email_raw[sender_email_raw.find('<')+1:sender_email_raw.find('>')].lower()
                            else:
                                sender_email = sender_email_raw.strip().lower()
                            if not sender_email: # Final fallback
                                sender_email = "unknown.sender@example.com"


                        print(f"      👤 Webhook: Message {msg_id} From: {sender_email}, Subject: '{original_subject}'")
                        print(f"      ✉️ Headers - To: {incoming_to_emails}, Cc: {incoming_cc_emails}, MsgID: {incoming_message_id}, Refs: {incoming_references}")
                        
                        bot_actual_email_lower = YOUR_EMAIL_ADDRESS.lower()
                        if sender_email and sender_email != bot_actual_email_lower:
                            print(f"      ✅ Webhook: Reply from '{sender_email}' (not self) in thread {TRACKED_THREAD_ID}.")
                            
                            message_body_content_raw = "Could not extract reply content."
                            if 'parts' in payload:
                                for part in payload['parts']:
                                    if part['mimeType'] == 'text/plain' and part['body'].get('data'):
                                        message_body_content_raw = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                                        break
                            elif 'body' in payload and payload['body'].get('data'):
                                message_body_content_raw = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                            
                            message_body_content = get_latest_reply_text(message_body_content_raw)
                            print(f"      🗣️ Webhook: Processed latest reply: '{message_body_content[:100]}...'")

                            # Construct reply-all recipient list
                            reply_to_primary = sender_email # To: the person who sent the message
                            
                            all_other_recipients = set()
                            for email in incoming_to_emails: all_other_recipients.add(email) # Already lowercase
                            for email in incoming_cc_emails: all_other_recipients.add(email) # Already lowercase

                            if bot_actual_email_lower in all_other_recipients:
                                all_other_recipients.remove(bot_actual_email_lower)
                            if reply_to_primary.lower() in all_other_recipients: # reply_to_primary is already lowercase
                                all_other_recipients.remove(reply_to_primary.lower())
                            
                            cc_list_str = ', '.join(sorted(list(all_other_recipients)))

                            new_in_reply_to = incoming_message_id
                            new_references = (incoming_references + " " if incoming_references else "") + (incoming_message_id if incoming_message_id else "")
                            
                            echo_body_text = message_body_content

                            echo_message_body = create_message(
                                sender=YOUR_EMAIL_ADDRESS,
                                to=reply_to_primary,
                                cc=cc_list_str if cc_list_str else None,
                                subject=original_subject, # Use original subject for reply
                                message_text=echo_body_text,
                                thread_id=TRACKED_THREAD_ID,
                                in_reply_to=new_in_reply_to,
                                references=new_references.strip() # Ensure no leading/trailing space if one part was empty
                            )
                            print(f"      🚀 Webhook: Sending echo reply. To: '{reply_to_primary}', CC: '{cc_list_str if cc_list_str else 'None'}'...")
                            send_message(gmail_service, 'me', echo_message_body)
                            PROCESSED_MESSAGE_IDS.add(msg_id)
                        else:
                            print(f"      🤔 Webhook: Message {msg_id} is from self ({sender_email}) or sender could not be identified as external. No echo sent.")
                            PROCESSED_MESSAGE_IDS.add(msg_id)
                    else:
                        print(f"    🚫 Webhook: Message {msg_id} (Thread: {msg_thread_id}) is NOT in tracked thread ({TRACKED_THREAD_ID}).")
                        PROCESSED_MESSAGE_IDS.add(msg_id)

            new_history_id_from_api = history_response.get('historyId') # HistoryId from the last page of history.list
            if new_history_id_from_api:
                LAST_PROCESSED_HISTORY_ID = str(new_history_id_from_api)
                print(f"🔄 Webhook: Updated LAST_PROCESSED_HISTORY_ID to: {LAST_PROCESSED_HISTORY_ID} (from history.list API response)")
            else: # Fallback if API doesn't return historyId (e.g. no new history records)
                LAST_PROCESSED_HISTORY_ID = str(history_id_from_notification)
                print(f"🔄 Webhook: No new historyId from API. LAST_PROCESSED_HISTORY_ID updated to: {LAST_PROCESSED_HISTORY_ID} (from Pub/Sub notification)")

            if not new_messages_found_in_thread:
                print(f"ℹ️ Webhook: No new messages found *in the tracked thread* {TRACKED_THREAD_ID} within this history batch.")
            print("✅ Webhook: Notification processed successfully.")
            return jsonify({'status': 'success', 'message': 'Notification processed'}), 200

        except Exception as e:
            print(f'❌ Webhook: Error processing Pub/Sub message: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'Internal server error: {e}'}), 500
    else:
        print("❌ Webhook: Invalid message format in Pub/Sub payload.")
        return jsonify({'status': 'error', 'message': 'Invalid message format in Pub/Sub payload'}), 400

# --- Main Application Logic ---
if __name__ == '__main__':
    print("🚀 Initializing Gmail service...")
    gmail_service = get_gmail_service()
    if not gmail_service:
        print("❌ Failed to initialize Gmail service. Exiting.")
        exit()
    print("✅ Gmail service initialized successfully.")

    # Config validation
    placeholders = {
        'YOUR_EMAIL_ADDRESS': 'aadi.lf21r@gmail.com', # Example, ensure user changes this
        'RECIPIENT_EMAIL': 'aadityajagdale.21@gmail.com', # Example
        'GCP_PROJECT_ID': 'market-simplified', # Example
        'PUBSUB_TOPIC_ID': 'gmail-updates' # Example
    }
    config_error = False
    user_placeholders = ['your_bot_email@example.com', 'initial_recipient@example.com', 'your-gcp-project-id', 'gmail-updates-topic']
    for key, val_in_code in placeholders.items():
        # Check if the value in code is one of the generic placeholders often left by users
        if globals()[key] in user_placeholders or globals()[key] == val_in_code and key != "PUBSUB_TOPIC_ID" and key != "GCP_PROJECT_ID" and key != "YOUR_EMAIL_ADDRESS" and key != "RECIPIENT_EMAIL": # Be more specific with default check
             # This check needs refinement if default values ARE the actual values
             pass # Allow default values if they are not generic placeholders. User must verify them.
        if not globals()[key]:
            print(f"🚨 CONFIGURATION ERROR: Please set {key} at the top of the script. It's currently empty.")
            config_error = True
    if config_error:
        print("Exiting due to configuration errors.")
        exit()
    
    print(f"📬 Monitoring Email: {YOUR_EMAIL_ADDRESS}")
    print(f"📨 Initial Email Recipient: {RECIPIENT_EMAIL}")
    print(f"☁️ GCP Project: {GCP_PROJECT_ID}, Pub/Sub Topic: {PUBSUB_TOPIC_ID}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    initial_subject = f"Automated Tracking Email - {timestamp}"
    initial_body = (
        f"This is an automated email sent at {timestamp} to initiate a new tracked thread.\n"
        f"Please reply to this email to test the echo functionality.\n\n"
        f"Bot monitoring: {YOUR_EMAIL_ADDRESS}"
    )
    
    print(f"📧 Sending initial email to {RECIPIENT_EMAIL} to start tracking...")
    msg_to_send = create_message(YOUR_EMAIL_ADDRESS, RECIPIENT_EMAIL, initial_subject, initial_body)
    sent_message = send_message(gmail_service, 'me', msg_to_send, is_initial_email=True)
    
    if sent_message and sent_message.get('threadId'):
        TRACKED_THREAD_ID = sent_message['threadId']
        print(f"🧵 Successfully obtained new Thread ID for tracking: {TRACKED_THREAD_ID}")
    else:
        print("❌ Failed to send initial email or retrieve its threadId. Exiting.")
        exit()
    
    print("📡 Attempting to start Gmail watch...")
    watch_response = start_gmail_watch(gmail_service, GCP_PROJECT_ID, PUBSUB_TOPIC_ID)
    if not watch_response or not LAST_PROCESSED_HISTORY_ID:
        print("⚠️ Failed to start Gmail watch or obtain initial history ID. Webhook might not function correctly.")
    else:
        print(f"👍 Gmail watch started/confirmed. Current history ID for watch: {LAST_PROCESSED_HISTORY_ID}")

    print(f"🌐 Starting Flask server for webhook on port 8080...")
    print(f"   NGROK: Ensure ngrok is running and Pub/Sub push endpoint is: https://<your-ngrok-id>.ngrok.io/webhook")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)