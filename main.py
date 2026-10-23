import os
import logging
import threading

from flask import Flask
from groq import AsyncGroq
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_PERSONA = (
    "You are Ani x, a friendly, intelligent, and cheerful AI assistant. "
    "Reply warmly, naturally, and helpfully. "
    "Keep answers clear and appropriate."
)

MODEL_ID = "openai/gpt-oss-120b"

groq_client = None
user_sessions = {}

app = Flask(__name__)


def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"history": []}
    return user_sessions[user_id]


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "Hi! 👋 I'm Ani x, your AI assistant powered by Groq.\n\n"
        "Send me a message to chat!\n"
        "/clear - Clear your chat history"
    )


async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"history": []}

    await update.effective_message.reply_text(
        "✨ Conversation history cleared!"
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    if message is None or not message.text:
        return

    user_id = update.effective_user.id
    session = get_user_session(user_id)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    messages = [
        {"role": "system", "content": DEFAULT_PERSONA}
    ]
    messages.extend(session["history"])
    messages.append({
        "role": "user",
        "content": message.text,
    })

    try:
        response = await groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            temperature=0.7,
            max_completion_tokens=1024,
        )

        reply = response.choices[0].message.content

        if not reply:
            reply = "Sorry, I couldn't generate a response."

        session["history"].extend([
            {"role": "user", "content": message.text},
            {"role": "assistant", "content": reply},
        ])

        # Keep the latest 6 conversation turns
        session["history"] = session["history"][-12:]

        # Telegram message length limit
        for i in range(0, len(reply), 4000):
            await message.reply_text(reply[i:i + 4000])

    except Exception:
        logger.exception("Groq API request failed")

        await message.reply_text(
            "⚠️ Ani x is having an AI connection problem. "
            "Please try again shortly."
        )


@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Ani x Bot Status: Active (Groq)", 200


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


def main():
    global groq_client

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not telegram_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")

    if not groq_api_key:
        raise RuntimeError("Missing GROQ_API_KEY environment variable")

    groq_client = AsyncGroq(api_key=groq_api_key)

    threading.Thread(
        target=run_web_server,
        daemon=True,
    ).start()

    bot_app = ApplicationBuilder().token(telegram_token).build()

    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("clear", clear_command))
    bot_app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    logger.info("Ani x bot starting...")
    bot_app.run_polling()


if __name__ == "__main__":
    main()
    
