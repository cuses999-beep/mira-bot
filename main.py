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

        response = client
