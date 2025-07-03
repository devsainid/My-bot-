import os
import json
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Env vars
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Globals
ADMIN_IDS = [OWNER_ID]  # This can be extended later
application = Application.builder().token(BOT_TOKEN).build()
bot = Bot(BOT_TOKEN)
app = Flask(__name__)

# AI REPLY
async def ai_reply(message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openchat/openchat-3.5",
        "messages": [
            {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
            {"role": "user", "content": message}
        ]
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"]

# HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! I'm CINDRELLA ✨. your super intelligent virtual friend 🌹🌹. how can i assist you today !")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("Send the broadcast message.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "add_admin"
        await query.message.reply_text("Send the ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "remove_admin"
        await query.message.reply_text("Send the ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text(f"Admins: {ADMIN_IDS}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Handle admin actions
    mode = context.user_data.get("mode")
    if mode == "broadcast" and user_id in ADMIN_IDS:
        for chat in context.bot_data.get("chats", []):
            try:
                await bot.send_message(chat_id=chat, text=text)
            except:
                pass
        context.user_data["mode"] = None
        await update.message.reply_text("✅ Broadcast sent.")
        return

    if mode == "add_admin" and user_id == OWNER_ID:
        try:
            new_admin = int(text)
            if new_admin not in ADMIN_IDS:
                ADMIN_IDS.append(new_admin)
                await update.message.reply_text("✅ Admin added.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        context.user_data["mode"] = None
        return

    if mode == "remove_admin" and user_id == OWNER_ID:
        try:
            remove_id = int(text)
            if remove_id in ADMIN_IDS and remove_id != OWNER_ID:
                ADMIN_IDS.remove(remove_id)
                await update.message.reply_text("✅ Admin removed.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        context.user_data["mode"] = None
        return

    # AI chat
    if text:
        reply = await ai_reply(text)
        await update.message.reply_text(reply)

    # Track chat ID for future broadcasts
    chat_id = update.effective_chat.id
    chats = context.bot_data.setdefault("chats", set())
    chats.add(chat_id)

    # Forward message to owner and admins
    for admin in ADMIN_IDS:
        if user_id != admin:
            fwd_msg = f"From: [{update.effective_user.first_name}](tg://user?id={user_id})\nMessage: {text}"
            try:
                await bot.send_message(chat_id=admin, text=fwd_msg, parse_mode=ParseMode.MARKDOWN)
            except:
                pass

# ROUTE
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

# Telegram Webhook Set
@app.route("/", methods=["GET"])
def home():
    return "CINDRELLA bot running 💖"

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
