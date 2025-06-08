import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters
import asyncio
import dotenv
from handlers.incoming_message_handler import handle_text_message, handle_audio_message
from handlers.agents import meetings_kb, properties_kb

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
dotenv.load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8443))
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN")  # Your static ngrok domain
    
# Initialize Bot application
if BOT_TOKEN:
    custom_bot = ApplicationBuilder().token(BOT_TOKEN).build()
else:
    logger.critical("BOT_TOKEN environment variable not set. Exiting.")
    exit()

async def start_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Hello! I'm your real estate bot. Send me a message!")

# Add handlers to the application
custom_bot.add_handler(CommandHandler("start", start_command))
custom_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
custom_bot.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio_message))

if __name__ == "__main__":
    webhook_url = f"https://{NGROK_DOMAIN}/webhook"
    logger.info(f"Using webhook URL: {webhook_url}")
    meetings_kb.load(recreate=False)
    properties_kb.load(recreate=False)
    
    # Set webhook and start server
    custom_bot.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url,
        cert=None,
        drop_pending_updates=True,
        url_path="webhook"  # This is important - it tells the server to handle /webhook path
    )

