import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from faster_whisper import WhisperModel
import os
import json
from email_service.provider import send_email_and_get_thread
from gemini_service import email_assistant_team, EmailTeamResponse
from agent import personal_assistant_team, just_chat_with_company_info_agent

logger = logging.getLogger(__name__)

model = WhisperModel("tiny", device="cpu", compute_type="int8")
chat_histories = {}

async def handle_text_message(update: Update, context: CallbackContext) -> None:
    #Show typing...
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    if update.message and update.message.text:
        user_id = update.effective_user.id
        logger.info(f"Received message: '{update.message.text}' from user {user_id}")

        # Retrieve or initialize chat history
        if user_id not in chat_histories:
            chat_histories[user_id] = []

        # Add user message to history
        chat_histories[user_id].append({"role": "user", "content": update.message.text})

        # Get response from personal assistant team, passing the history
        # Assuming personal_assistant_team can take a 'history' argument
        response = just_chat_with_company_info_agent(update.message.text, history=chat_histories[user_id])
        
        # Add assistant response to history
        if response: # Ensure there is a response to add
            chat_histories[user_id].append({"role": "assistant", "content": response})
            
        await update.message.reply_text(response)

async def handle_audio_message(update: Update, context: CallbackContext) -> None:
    if update.message and (update.message.audio or update.message.voice):
        user_id = update.effective_user.id
        audio_type = "audio" if update.message.audio else "voice"
        audio_file_obj = update.message.audio or update.message.voice

        if not audio_file_obj:
            logger.warning("No audio or voice object found despite earlier check.")
            await update.message.reply_text("Sorry, I could not process the audio.")
            return

        temp_audio_path = "" # Initialize to ensure it's defined in finally block
        try:
            
            #Typing Animation
            
            tg_file = await audio_file_obj.get_file()
            temp_audio_path = f"temp_{tg_file.file_id}.{audio_file_obj.mime_type.split('/')[-1]}"
            
            await tg_file.download_to_drive(temp_audio_path)
            logger.info(f"Audio file downloaded to {temp_audio_path}")

            segments, info = model.transcribe(temp_audio_path, beam_size=5)

            logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")
            transcription = "".join(segment.text for segment in segments)

            if transcription:
                logger.info(f"Transcription: '{transcription}' from user {user_id}")
                # Retrieve or initialize chat history
                if user_id not in chat_histories:
                    chat_histories[user_id] = []

                # Add user message (transcription) to history
                chat_histories[user_id].append({"role": "user", "content": transcription})
                
                # Get response from personal assistant team, passing the history
                # Assuming personal_assistant_team can take a 'history' argument
                response = personal_assistant_team(transcription, history=chat_histories[user_id])

                # Add assistant response to history
                if response: # Ensure there is a response to add
                    chat_histories[user_id].append({"role": "assistant", "content": response})

                await update.message.reply_text(response)
                # try:
                #     # Email Assistant
                #     team_run_response = email_assistant_team(transcription) # This is the TeamRunResponse
                #     # Access the actual Pydantic model, assuming it's in the .output attribute
                #     if isinstance(team_run_response, EmailTeamResponse):
                #         actual_email_data: EmailTeamResponse = team_run_response.content
                #         print("============\n\n")
                #         print(f"TeamRunResponse object: {team_run_response}")
                #         print(f"Actual Email Data (from .output): {actual_email_data}")
                #         print("\n\n============\n\n")

                #         email_sent_successfully = send_email_and_get_thread(
                #             subject=actual_email_data.subject,
                #             body=actual_email_data.body, 
                #             to_email=actual_email_data.user_email # Corrected keyword to 'to_email'
                #         )

                #         if email_sent_successfully:
                #             await update.message.reply_text(
                #                 f"✅ Email sent successfully to {actual_email_data.user_name}\n\n"
                #                 f"Subject: {actual_email_data.subject}\n\n"
                #                 f"Body:\n{actual_email_data.body}"
                #             )
                #         else:
                #             logger.error("Failed to send email")
                #             await update.message.reply_text(
                #                 "❌ Sorry, there was an error sending the email. Please try again."
                #             )
                #     else:
                #         actual_email_data = team_run_response

                # except Exception as e:
                #     logger.error(f"Error in email processing: {e}", exc_info=True)
                #     await update.message.reply_text(
                #         "❌ An unexpected error occurred while processing your request."
                #     )
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
