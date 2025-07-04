import os
import logging
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# System prompt for OpenRouter
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# Main Bot Application
application = ApplicationBuilder().token(BOT_TOKEN).build()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

# AI chat function
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ['private', 'group', 'supergroup']:
        return
    if update.message.text.lower() in ["hi", "hello", "hey", "sup guys", "good morning", "good evening"]:
        messages = [SYSTEM_PROMPT, {"role": "user", "content": update.message.text}]
        try:
            response = await get_openrouter_reply(messages)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Oops, something went wrong...")

# OpenRouter AI call
async def get_openrouter_reply(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-1210",
        "messages": messages
    }
    async with httpx.AsyncClient() as client:
        res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]

# Set handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))

# Webhook route
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Run Flask + Bot webhook
if __name__ == "__main__":
    async def run():
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info("Webhook set successfully.")
        await application.initialize()
        await application.start()
        await application.updater.start_webhook()
    import asyncio
    asyncio.get_event_loop().run_until_complete(run())
    app.run(host="0.0.0.0", port=10000)
