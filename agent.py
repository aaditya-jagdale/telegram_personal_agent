from email_service.provider import send_email_and_get_thread
from email_service.listener import listen_to_thread
import os

if __name__ == "__main__":
    subject = "Test Thread Email"
    body = "This is the initial message."
    receiver = "aadityajagdale.21@gmail.com"

    thread_id = send_email_and_get_thread(subject, body, receiver)
    listen_to_thread(thread_id, "aadi.21r@gmail.com")
