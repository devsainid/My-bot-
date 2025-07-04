import os
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Load env variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Flask app
app = Flask(__name__)
bot = Bot(BOT_TOKEN)

# Telegram application
application = ApplicationBuilder().token(BOT_TOKEN).build()
admins = [OWNER_ID]

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

# General messages handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    if text in ["hi", "hello", "hii", "hey", "yo", "sup"]:
        await update.message.reply_text("Hey there 🌸, what's up?")
        return

    response = await get_openrouter_reply(update.message.text)
    if response:
        await update.message.reply_text(response)

# AI reply using OpenRouter API
async def get_openrouter_reply(message):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "openchat/openchat-3.5",
            "messages": [SYSTEM_PROMPT, {"role": "user", "content": message}]
        }
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        return res.json()["choices"][0]["message"]["content"]
    except:
        return "Oops, something went wrong!"

# Admin panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("You're not authorized.")
        return

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]

    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# Handle callback actions
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("Send the message to broadcast.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        admin_list = "\n".join(str(a) for a in admins)
        await query.message.reply_text(f"Current Admins:\n{admin_list}")

# Process admin replies
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if mode == "broadcast" and user_id in admins:
        for chat_id in context.bot_data.get("chats", set()):
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except:
                continue
        await update.message.reply_text("Broadcast sent ✅")
    elif mode == "add_admin" and user_id == OWNER_ID:
        try:
            new_admin = int(text)
            if new_admin not in admins:
                admins.append(new_admin)
                await update.message.reply_text("Admin added ✅")
            else:
                await update.message.reply_text("Already an admin.")
        except:
            await update.message.reply_text("Invalid ID.")
    elif mode == "remove_admin" and user_id == OWNER_ID:
        try:
            remove_id = int(text)
            if remove_id in admins:
                admins.remove(remove_id)
                await update.message.reply_text("Admin removed ✅")
            else:
                await update.message.reply_text("Not an admin.")
        except:
            await update.message.reply_text("Invalid ID.")
    context.user_data["mode"] = None

# Track all chats for broadcast
async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "chats" not in context.bot_data:
        context.bot_data["chats"] = set()
    context.bot_data["chats"].add(update.effective_chat.id)

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

# Root route
@app.route('/')
def home():
    return "Bot is live!"

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(callback_handler))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_reply))
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(MessageHandler(filters.ALL, track_chat))

# Run Flask + Telegram webhook
if __name__ == '__main__':
    import threading
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url=WEBHOOK_URL
)
