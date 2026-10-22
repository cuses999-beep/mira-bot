
import os
import logging
import threading
from flask import Flask
from google import genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Retrieve API keys from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Default System Persona for Mira
DEFAULT_PERSONA = (
    "You are Mira, a friendly, intelligent, and cheerful AI assistant. "
    "You communicate in a warm, concise, and helpful manner on Telegram."
)

# User session history
user_sessions = {}

def get_user_session(user_id: int):
    """Retrieves or initializes a user's session data."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "persona": DEFAULT_PERSONA,
            "history": []
        }
    return user_sessions[user_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    user = update.effective_user
    user_id = user.id
    get_user_session(user_id)

    welcome_message = (
        f"Hi {user.first_name}! 👋 I am **Mira**, your personal AI companion on Telegram.\n\n"
        "Here is what you can do with me:\n"
        "• Just send me any message to start chatting!\n"
        "• `/clear` - Reset our conversation history.\n"
        "• `/persona <instructions>` - Customize my personality or role.\n\n"
        "How can I help you today?"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler to reset conversation history."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)
    session["history"] = []
    
    await update.message.reply_text("✨ Conversation history cleared! We have a fresh start.")

async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler to set custom system persona for the bot."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if not context.args:
        current_persona = session["persona"]
        await update.message.reply_text(
            f"Current persona:\n\n_{current_persona}_\n\n"
            "To change it, send: `/persona <your prompt instructions>`",
            parse_mode="Markdown"
        )
        return

    new_persona = " ".join(context.args)
    session["persona"] = new_persona
    session["history"] = []
    
    await update.message.reply_text(
        f"✅ Persona updated! Here is how I will act now:\n\n_{new_persona}_",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user text messages and generates AI response via Gemini."""
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    session = get_user_session(user_id)
    session_history = session["history"]
    persona = session["persona"]

    session_history.append({"role": "user", "parts": [{"text": user_text}]})

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=session_history,
            config={
                "system_instruction": persona
            }
        )

        bot_reply = response.text if response.text else "Sorry, I couldn't process that request."
        session_history.append({"role": "model", "parts": [{"text": bot_reply}]})

        await update.message.reply_text(bot_reply)

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        if session_history and session_history[-1]["role"] == "user":
            session_history.pop()

        await update.message.reply_text(
            "⚠️ Sorry, I encountered an error connecting to the AI model. Please try again in a moment."
        )

# --- Web Server to Keep Render Alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Mira Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable is missing.")
        return

    # Start dummy web server in background thread for Render health check
    threading.Thread(target=run_web_server, daemon=True).start()

    # Build python-telegram-bot application
    bot_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("clear", clear_command))
    bot_app.add_handler(CommandHandler("persona", persona_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Mira Telegram Bot is running on Render...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
```
