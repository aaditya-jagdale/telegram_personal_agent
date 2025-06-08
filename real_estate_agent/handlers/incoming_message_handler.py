from telegram import Update
from telegram.ext import CallbackContext
from agno.agent import Agent, AgentKnowledge
from agno.models.google import Gemini
import os
import dotenv
from agno.vectordb.chroma import ChromaDb
from agno.knowledge.json import JSONKnowledgeBase
from agno.vectordb.pgvector import PgVector
from real_estate_agent.handlers.agents import get_real_estate_agent, RealEstateAgentOutput, PropertyModel
from telegram.constants import ParseMode
from telegram import File

dotenv.load_dotenv()
MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def handle_text_message(update: Update, context: CallbackContext) -> None:
    print("="*100 + "\n\n")
    print("💬 Text message received: ", update.message.text)
    print( "\n\n" + "="*100)
    response = get_real_estate_agent(update.message.text)
    # Extract the structured output from the response
    output: RealEstateAgentOutput = response
    print("Output: ", output)
    
    if output.properties is None or len(output.properties) == 0:
        await update.message.reply_text(output.message, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"I found {len(output.properties)} properties for you", parse_mode=ParseMode.MARKDOWN)
        for property in output.properties:
            caption = f"""*{property.title}* 🏠
📍 Location: {property.location}
💰 Price: ${property.price_usd:,}
📐 Area: {property.area_sqft:,} sq.ft
🛏️ Bedrooms: {property.bedrooms}
🚿 Bathrooms: {property.bathrooms} 
🏘️ Type: {property.property_type}"""
            try:
                await update.message.reply_photo(photo=property.image_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                print(f"Failed to send photo for property {property.id}: {str(e)}")
                placeholder_image = "https://img.freepik.com/free-vector/illustration-gallery-icon_53876-27002.jpg"
                await update.message.reply_photo(photo=placeholder_image, caption=f"{caption}\n\n*Image not available*", parse_mode=ParseMode.MARKDOWN)
                continue


async def handle_audio_message(update: Update, context: CallbackContext) -> None:
    print("="*100 + "\n\n")
    print("🎤 Audio message received: ", update.message.audio)
    print("="*100 + "\n\n")

    await update.message.reply_text("Hello, world! I am now using polling. I am a real estate agent.")


