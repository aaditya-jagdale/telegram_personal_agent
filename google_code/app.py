import os
import base64
import json
import time
from email.mime.text import MIMEText
import re

from flask import Flask, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import pubsub_v1

# --- Configuration ---
# Fill these in with your details
PATH_TO_CREDENTIALS = 'credentials.json'  # Path to your OAuth 2.0 credentials
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/pubsub']
# IMPORTANT: Set this to the email address of the account you want to monitor AND
# the account you will use to authenticate the application via the browser popup.
YOUR_EMAIL_ADDRESS = 'aadi.lf21r@gmail.com'  # e.g., 'aadi.21r@gmail.com'
# IMPORTANT: This email address will receive the initial email that starts the tracked thread.
RECIPIENT_EMAIL = 'aadityajagdale.21@gmail.com' 
GCP_PROJECT_ID = 'market-simplified' # Your Google Cloud Project ID
PUBSUB_TOPIC_ID = 'gmail-updates' # Just the ID of your Pub/Sub topic

# Global variable to store the Gmail service object
gmail_service = None
# Global variable to store the dynamically obtained thread ID to track
TRACKED_THREAD_ID = None 
# Global variable to store the last processed history ID
LAST_PROCESSED_HISTORY_ID = None
# In-memory set to track processed message IDs to avoid duplicates
PROCESSED_MESSAGE_IDS = set()

app = Flask(__name__)

# --- Gmail Authentication and Service ---
def get_gmail_service():
    """Authenticates and returns a Gmail API service object.
    Manages token creation and refresh.
    """
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

# --- Email Sending Function ---
def create_message(sender, to, subject, message_text, thread_id=None):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw_message}
    if thread_id:
        body['threadId'] = thread_id
    return body

def get_latest_reply_text(full_text_body):
    """
    Attempts to extract only the latest reply from an email body,
    stripping away common quoted text headers.
    """
    # Regex for common Gmail-style reply headers
    # e.g., "On Mon, May 13, 2024 at 10:30 AM John Doe <john.doe@example.com> wrote:"
    # Covers English, Spanish ("El ... escribió:"), French ("Le ... a écrit :")
    # and some date/day variations.
    gmail_quote_header_pattern = re.compile(
        r"^\s*(On|Am|El|Le)\s+"
        r"([A-Za-zÀ-ÖØ-öø-ÿ]+[,.]?\s+)?\d{1,2}\s+[A-Za-zÀ-ÖØ-öø-ÿ]+[,.]?\s+\d{4}([,.]?\s+(at|à)|,)\s+\d{1,2}:\d{2}(\s+(AM|PM))?[,.]?"
        r".*(wrote|écrit|escribió)\s*:\s*$",
        re.IGNORECASE | re.MULTILINE
    )

    match = gmail_quote_header_pattern.search(full_text_body)
    if match:
        # Return the text before the detected quote header
        return full_text_body[:match.start()].strip()
    else:
        # Fallback: try to remove lines starting with "> " (common for plain text quotes)
        # This is more basic and might not cover all cases or could be too aggressive.
        lines = full_text_body.splitlines()
        latest_reply_lines = []
        for line in lines:
            if line.strip().startswith(">"):
                # If we find a line starting with '>', assume it's the start of quoted text
                # and stop collecting lines for the latest reply.
                break
            latest_reply_lines.append(line)

        if latest_reply_lines and len(latest_reply_lines) < len(lines):
            return "\n".join(latest_reply_lines).strip()
        else:
            # If no quote patterns are found, return the full body as a fallback.
            # This means it's likely a new email or a format we don't recognize.
            return full_text_body.strip()

def send_message(service, user_id, message_body, is_initial_email=False):
    """Sends an email message. is_initial_email flag is for logging purposes."""
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
    
    if not TRACKED_THREAD_ID: # This should be set by the main thread on startup
        print("❌ Webhook: TRACKED_THREAD_ID is not set. Cannot process messages. This is unexpected if startup was successful.")
        return jsonify({'status': 'error', 'message': 'TRACKED_THREAD_ID not configured'}), 500

    envelope = request.get_json(silent=True) 
    if not envelope:
        print('❌ Webhook: No Pub/Sub message received or not valid JSON.')
        if request.data:
            print(f"Request data (not JSON): {request.data}")
        return jsonify({'status': 'error', 'message': 'Bad request format: No JSON payload or invalid JSON'}), 400
    
    print(f"📦 Webhook: Received envelope: {json.dumps(envelope, indent=2)}")

    if not isinstance(envelope, dict) or 'message' not in envelope:
        print(f'❌ Webhook: Invalid Pub/Sub message format (missing "message" key): {envelope}')
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

            if email_address_from_notification != YOUR_EMAIL_ADDRESS:
                print(f"⚠️ Webhook: Notification for different email ({email_address_from_notification}), expected ({YOUR_EMAIL_ADDRESS}). Skipping.")
                return jsonify({'status': 'success', 'message': 'Notification for different user'}), 200

            if not history_id_from_notification:
                print("❌ Webhook: No historyId in notification payload.")
                return jsonify({'status': 'error', 'message': 'No historyId in notification'}), 400
            
            current_start_history_id = LAST_PROCESSED_HISTORY_ID
            if not current_start_history_id:
                print(f"⚠️ Webhook: LAST_PROCESSED_HISTORY_ID was not set. Using historyId from notification ({history_id_from_notification}) as start point. This might re-process or miss history if script restarted.")
                current_start_history_id = history_id_from_notification
            
            print(f"⏳ Webhook: Processing Gmail history for user: {email_address_from_notification}, starting AFTER historyId: {current_start_history_id}")
            
            history_response = gmail_service.users().history().list(
                userId='me', 
                startHistoryId=str(current_start_history_id), 
                historyTypes=['messageAdded'] 
            ).execute()

            print(f"📜 Webhook: Gmail history.list API response: {json.dumps(history_response, indent=2)}")

            all_history_records = history_response.get('history', [])
            next_page_token = history_response.get('nextPageToken')

            while next_page_token:
                print(f"📑 Webhook: Fetching next page of history with token: {next_page_token}")
                history_response = gmail_service.users().history().list(
                    userId='me',
                    startHistoryId=str(current_start_history_id),
                    historyTypes=['messageAdded'],
                    pageToken=next_page_token
                ).execute()
                print(f"📜 Webhook: Gmail history.list API response (paginated): {json.dumps(history_response, indent=2)}")
                all_history_records.extend(history_response.get('history', []))
                next_page_token = history_response.get('nextPageToken')
            
            if not all_history_records:
                print("ℹ️ Webhook: No history records found since last processed ID.")

            new_messages_found_in_thread = False
            for history_record_index, history_record in enumerate(all_history_records):
                print(f"🔍 Webhook: Examining history record #{history_record_index + 1}, ID: {history_record.get('id')}")
                messages_added = history_record.get('messagesAdded', [])
                if not messages_added:
                    print(f"  No 'messagesAdded' in history record #{history_record_index + 1}.")
                    continue

                for added_msg_info_index, added_msg_info in enumerate(messages_added):
                    msg_id = added_msg_info['message']['id']
                    msg_thread_id = added_msg_info['message']['threadId']
                    print(f"  📧 Webhook: Found added message. ID: {msg_id}, Thread ID: {msg_thread_id} (Record #{history_record_index + 1}, MsgInfo #{added_msg_info_index + 1})")


                    if msg_id in PROCESSED_MESSAGE_IDS:
                        print(f"    ⏩ Webhook: Message {msg_id} already processed in this session. Skipping.")
                        continue

                    if msg_thread_id == TRACKED_THREAD_ID:
                        print(f"    🎯 Webhook: Message {msg_id} IS in TRACKED thread {TRACKED_THREAD_ID}.")
                        new_messages_found_in_thread = True
                        
                        full_message = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                        
                        payload = full_message.get('payload', {})
                        headers = payload.get('headers', [])
                        
                        sender_email = "Unknown Sender"
                        original_subject = "Original Thread Subject" 
                        for header in headers:
                            if header['name'].lower() == 'from':
                                sender_email = header['value']
                                if '<' in sender_email and '>' in sender_email:
                                    sender_email = sender_email[sender_email.find('<')+1:sender_email.find('>')]
                            if header['name'].lower() == 'subject':
                                original_subject = header['value']
                        
                        print(f"      👤 Webhook: Message {msg_id} from: {sender_email}, Subject: '{original_subject}'")

                        if sender_email and YOUR_EMAIL_ADDRESS.lower() not in sender_email.lower():
                            print(f"      ✅ Webhook: Reply from '{sender_email}' (not self) detected in thread {TRACKED_THREAD_ID}.")
                            
                            message_body_content_raw = "Could not extract reply content." # Default
                            if 'parts' in payload:
                                for part in payload['parts']:
                                    if part['mimeType'] == 'text/plain':
                                        body_data = part['body'].get('data')
                                        if body_data:
                                            message_body_content_raw = base64.urlsafe_b64decode(body_data).decode('utf-8')
                                            print(f"      💬 Webhook: Extracted raw text/plain part for message {msg_id}.")
                                            break
                            elif 'body' in payload and payload['body'].get('data'): 
                                body_data = payload['body'].get('data')
                                message_body_content = base64.urlsafe_b64decode(body_data).decode('utf-8')
                                print(f"      💬 Webhook: Extracted body data for message {msg_id} (non-multipart).")
                            else:
                                print(f"      ⚠️ Webhook: Could not find text/plain body for message {msg_id}.")

                            message_body_content = get_latest_reply_text(message_body_content_raw)
                            print(f"      🗣️ Webhook: Processed latest reply content for message {msg_id}: '{message_body_content[:100]}...'")

                            echo_subject = f"Echo: Reply in '{original_subject}'"
                            echo_body_text = (
                                f"A new reply was received in thread '{original_subject}'.\n\n"
                                f"From: {sender_email}\n\n"
                                f"--- Latest Reply Content ---\n{message_body_content}\n--- End of Reply ---\n\n" #Changed to "Latest Reply"
                                f"Tracked Thread ID: {TRACKED_THREAD_ID}\n"
                                f"Original Message ID of reply: {msg_id}"
                            )

                            echo_message_body = create_message(
                                sender=YOUR_EMAIL_ADDRESS, 
                                to=YOUR_EMAIL_ADDRESS,     
                                subject=echo_subject,
                                message_text=echo_body_text,
                                thread_id=TRACKED_THREAD_ID
                            )
                            print(f"      🚀 Webhook: Sending echo email to {RECIPIENT_EMAIL} for message {msg_id}...")
                            send_message(gmail_service, 'me', echo_message_body)
                            PROCESSED_MESSAGE_IDS.add(msg_id) 
                        else:
                            print(f"      🤔 Webhook: Message {msg_id} is from self ({sender_email}) or sender could not be reliably identified as external. No echo sent.")
                            PROCESSED_MESSAGE_IDS.add(msg_id) 
                    else:
                        print(f"    🚫 Webhook: Message {msg_id} (Thread: {msg_thread_id}) is NOT in the tracked thread ({TRACKED_THREAD_ID}).")
                        PROCESSED_MESSAGE_IDS.add(msg_id) 

            new_history_id_from_list_response = history_response.get('historyId') 
            if new_history_id_from_list_response:
                LAST_PROCESSED_HISTORY_ID = str(new_history_id_from_list_response) 
                print(f"🔄 Webhook: Updated LAST_PROCESSED_HISTORY_ID to: {LAST_PROCESSED_HISTORY_ID} (from history.list response's historyId)")
            else:
                LAST_PROCESSED_HISTORY_ID = str(history_id_from_notification)
                print(f"🔄 Webhook: No new historyId from history.list response. LAST_PROCESSED_HISTORY_ID updated to: {LAST_PROCESSED_HISTORY_ID} (from Pub/Sub notification's historyId)")


            if not new_messages_found_in_thread:
                print(f"ℹ️ Webhook: No new messages found *in the tracked thread* {TRACKED_THREAD_ID} within the processed history.")

            print("✅ Webhook: Notification processed successfully.")
            return jsonify({'status': 'success', 'message': 'Notification processed'}), 200

        except Exception as e:
            print(f'❌ Webhook: Error processing Pub/Sub message: {e}')
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'Internal server error: {e}'}), 500
    else:
        print("❌ Webhook: Invalid message format in Pub/Sub payload (missing 'data' or not a dict).")
        return jsonify({'status': 'error', 'message': 'Invalid message format in Pub/Sub payload'}), 400


# --- Main Application Logic ---
if __name__ == '__main__':
    print("🚀 Initializing Gmail service...")
    gmail_service = get_gmail_service()
    if not gmail_service:
        print("❌ Failed to initialize Gmail service. Please check credentials and OAuth flow. Exiting.")
        exit()
    print("✅ Gmail service initialized successfully.")
    
    # Ensure essential configurations are set
    if any(val is None or 'your_' in val or 'recipient_' in val for val in [YOUR_EMAIL_ADDRESS, RECIPIENT_EMAIL, GCP_PROJECT_ID, PUBSUB_TOPIC_ID]):
        print("🚨 CONFIGURATION ERROR: Please set YOUR_EMAIL_ADDRESS, RECIPIENT_EMAIL, GCP_PROJECT_ID, and PUBSUB_TOPIC_ID at the top of the script.")
        exit()
    
    print(f"📬 Monitoring Email: {YOUR_EMAIL_ADDRESS}")
    print(f"📨 Initial Email Recipient: {RECIPIENT_EMAIL}")
    print(f"☁️ GCP Project: {GCP_PROJECT_ID}, Pub/Sub Topic: {PUBSUB_TOPIC_ID}")

    # --- Send Initial Email to Start Tracking ---
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
        TRACKED_THREAD_ID = sent_message['threadId'] # Set the global variable
        print(f"🧵 Successfully obtained new Thread ID for tracking: {TRACKED_THREAD_ID}")
    else:
        print("❌ Failed to send initial email or retrieve its threadId. Cannot proceed with tracking.")
        exit()
    
    # --- Start Gmail Watch ---
    print("📡 Attempting to start Gmail watch...")
    watch_response = start_gmail_watch(gmail_service, GCP_PROJECT_ID, PUBSUB_TOPIC_ID) 
    
    if not watch_response or not LAST_PROCESSED_HISTORY_ID:
        print("⚠️ Failed to start Gmail watch or obtain initial history ID. Webhook might not function correctly.")
        print("   Ensure Pub/Sub topic exists, permissions are correct, and you authenticated as the correct user.")
        # Depending on the desired behavior, you might want to exit if watch fails.
        # For now, we'll let it continue so the Flask server starts, but webhook might not work.
    else:
        print(f"👍 Gmail watch started/confirmed. Current history ID for watch: {LAST_PROCESSED_HISTORY_ID}")

    print(f"🌐 Starting Flask server for webhook on port 8080...")
    print(f"   NGROK: Make sure ngrok is running and your Pub/Sub subscription push endpoint is: https://<your-ngrok-id>.ngrok.io/webhook")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)

