# telegram_personal_agent

A personal Telegram bot built with [python-telegram-bot](https://python-telegram-bot.org/) for handling text and audio/voice messages. This bot uses polling to receive messages and can be easily extended with custom handlers.

## Features
- Responds to /start command
- Echoes text messages
- Handles audio and voice messages
- Modular handler structure for easy extension

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repo-url>
cd telegram_bot
```

### 2. Install dependencies
It is recommended to use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the project root with the following content:
```
BOT_TOKEN=your_telegram_bot_token_here
```

### 4. Run the bot
```bash
python app.py
```

## File Structure
- `app.py` - Main entry point, sets up the bot and handlers
- `message_handler.py` - Contains message handler functions
- `email_provider.py`, `gemini_service.py` - Additional services (customize as needed)
- `requirements.txt` - Python dependencies

## Environment Variables
- `BOT_TOKEN`: Your Telegram bot token (get it from BotFather)

## Usage
- Start a chat with your bot on Telegram
- Send `/start` to receive a welcome message
- Send text or audio/voice messages to interact
