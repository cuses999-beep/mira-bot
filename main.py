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

# Fetch API Keys safely from Render Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DEFAULT_PERSONA = (
    "You are Ani x, a friendly, intelligent, and cheerful AI assistant. "
    "You communicate in a warm, concise, and helpful manner on Telegram."
)

user_sessions = {}

def get_user_session(user_id: int):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "persona": DEFAULT_PERSONA,
            "history": []
        }
    return user_sessions[user_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)

    welcome_message = (
        f"Hi {user.first_name}! 👋 I am **Ani x**, your AI companion.\n\n"
        "• Send me a message to chat!\n"
        "• `/clear` - Reset history.\n"
        "• `/persona <instructions>` - Custom personality."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_user_session(update.effective_user.id)
    session["history"] = []
    await update.message.reply_text("✨ Conversation history cleared!")

async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_user_session(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(f"Current persona:\n\n_{session['persona']}_", parse_mode="Markdown")
        return

    new_persona = " ".join(context.args)
    session["persona"] = new_persona
    session["history"] = []
    await update.message.reply_text(f"✅ Persona updated to:\n_{new_persona}_", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    session = get_user_session(user_id)
    session_history = session["history"]

    session_history.append({"role": "user", "parts": [{"text": user_text}]})

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        # Using gemini-2.0-flash for high stability
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=session_history,
            config={
                "system_instruction": session["persona"]
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
            f"⚠️ AI Error: {e}"
        )

# Web server for keeping service alive on Render
app = Flask(__name__)

@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "Ani x Bot Status: Active", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot_app = ApplicationBuilder().token(token).build()

    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("clear", clear_command))
    bot_app.add_handler(CommandHandler("persona", persona_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
    
