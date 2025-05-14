import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from faster_whisper import WhisperModel
import os
from email_provider import send_email
from gemini_service import gemini_email_writer, email_verifier



logger = logging.getLogger(__name__)


model = WhisperModel("tiny", device="cpu", compute_type="int8")

async def echo_message(update: Update, context: CallbackContext) -> None:
    if update.message and update.message.text:
        logger.info(f"Received message: '{update.message.text}' from user {update.effective_user.id}")
        await update.message.reply_text(update.message.text)

async def handle_audio_message(update: Update, context: CallbackContext) -> None:
    if update.message and (update.message.audio or update.message.voice):
        audio_type = "audio" if update.message.audio else "voice"
        audio_file_obj = update.message.audio or update.message.voice

        if not audio_file_obj:
            logger.warning("No audio or voice object found despite earlier check.")
            await update.message.reply_text("Sorry, I could not process the audio.")
            return

        try:
            await update.message.reply_text(f"Okay, just a second buddy...")
            tg_file = await audio_file_obj.get_file()
            temp_audio_path = f"temp_{tg_file.file_id}.{audio_file_obj.mime_type.split('/')[-1]}"
            
            await tg_file.download_to_drive(temp_audio_path)
            logger.info(f"Audio file downloaded to {temp_audio_path}")

            segments, info = model.transcribe(temp_audio_path, beam_size=5)

            logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")
            transcription = "".join(segment.text for segment in segments)

            if transcription:
                try:
                    # Email Verifier
                    email_exists = email_verifier(transcription, [
                        {
                            "name": "Sam", 
                            "email": "sam@gmail.com",
                        }, {
                            "name": "Aaditya",
                            "email": "aadityajagdale.21@gmail.com", 
                        }, {
                            "name": "John",
                            "email": "john@gmail.com",
                        }]
                    )

                    if not email_exists["email_exists"]:
                        await update.message.reply_text("No valid email recipient found in the message.")
                        return

                    # Generate email content
                    email_message = gemini_email_writer(
                        f"Write an email based on this transcription: {transcription}\n"
                        f"Recievers name MUST be: {email_exists['email']['name']} "
                    )

                    print("================\n\n")
                    print(email_message)
                    print("\n\n================")
                    
                    receiver_email = email_exists["email"]["email"]
                    email_sent_successfully = send_email(
                        email_message["subject"],
                        email_message["body"], 
                        receiver_email
                    )

                    if email_sent_successfully:
                        await update.message.reply_text(
                            f"✅ Email sent successfully to {email_exists['email']['name']}\n\n"
                            f"Subject: {email_message['subject']}\n\n"
                            f"Body:\n{email_message['body']}"
                        )
                    else:
                        logger.error("Failed to send email")
                        await update.message.reply_text(
                            "❌ Sorry, there was an error sending the email. Please try again."
                        )

                except Exception as e:
                    logger.error(f"Error in email processing: {e}", exc_info=True)
                    await update.message.reply_text(
                        "❌ An unexpected error occurred while processing your request."
                    )
            else:
                await update.message.reply_text("Could not transcribe the audio or it was empty.")

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            await update.message.reply_text("Sorry, an error occurred while processing your audio.")
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                logger.info(f"Temporary file {temp_audio_path} removed.")
                
    else:
        logger.warning("handle_audio_message called but no audio or voice found in message.")
