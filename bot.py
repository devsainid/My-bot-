import os
import logging
import httpx
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext import Dispatcher

# Logging
logging.basicConfig(level=logging.INFO)

# Load env variables
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Flask app
app = Flask(__name__)
bot = Bot(token=TOKEN)

# Create dispatcher
application = Application.builder().token(TOKEN).build()
dp: Dispatcher = application

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm alive. 🌸")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": [
                    {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
                    {"role": "user", "content": user_message}
                ]
            }
        )
        data = response.json()
        reply = data['choices'][0]['message']['content']
        await update.message.reply_text(reply)

# Add handlers
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

# --- Webhook Endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "ok", 200

# --- Root test route ---
@app.route("/", methods=["GET"])
def home():
    return "Bot is alive!", 200

# --- Webhook setter ---
@app.before_first_request
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    try:
        httpx.post(url)
        logging.info("Webhook set successfully.")
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")

# --- Run Flask ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
