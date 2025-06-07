from telegram import Update
from telegram.ext import CallbackContext
from agno.agent import Agent, AgentKnowledge
from agno.models.google import Gemini
import os
import dotenv
from agno.vectordb.chroma import ChromaDb
from agno.knowledge.json import JSONKnowledgeBase
from agno.vectordb.pgvector import PgVector
from real_estate_agent.handlers.agents import real_estate_agent

dotenv.load_dotenv()
MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def handle_text_message(update: Update, context: CallbackContext) -> None:
    print("Text message received: ", update.message.text)
    response = real_estate_agent.run(update.message.text).content
    print("Response: ", response)
    await update.message.reply_text(response)


async def handle_audio_message(update: Update, context: CallbackContext) -> None:
    print("Audio message received: ", update.message.audio)
    await update.message.reply_text("Hello, world! I am now using polling. I am a real estate agent.")


