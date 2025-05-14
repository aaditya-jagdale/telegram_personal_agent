import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
import logging
from gemini_service import gemini_email_writer

load_dotenv()
logger = logging.getLogger(__name__)

sender_email = os.getenv("SENDER_EMAIL", "aadi.lf21r@gmail.com")
password = os.getenv("APP_PASSWORD")

def send_email(subject, body, receiver_email):
    if not password:
        logger.error("APP_PASSWORD not found in environment variables.")
        return False

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            
            # Then send the complete message object
            server.sendmail(sender_email, receiver_email, message.as_string())
            
        logger.info(f"Email sent successfully to {receiver_email} with subject: {subject}")
        return True
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending email: {e}", exc_info=True)
        return False
