import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
import asyncio # Keep for async handlers, not strictly needed for polling setup itself if handlers are sync
import dotenv
from message_handler import echo_message, handle_audio_message


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize Bot application
if BOT_TOKEN:
    custom_bot = ApplicationBuilder().token(BOT_TOKEN).build()
else:
    logger.critical("BOT_TOKEN environment variable not set. Exiting.")
    exit()

async def start_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Hello, world! I am now using polling.")


# Add handlers to the application
custom_bot.add_handler(CommandHandler("start", start_command))
custom_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))
custom_bot.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio_message))

if __name__ == "__main__":
    logger.info("Starting bot with polling...")
    custom_bot.run_polling()
    logger.info("Bot has stopped polling.")