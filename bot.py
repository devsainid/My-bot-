import os
import json
import httpx
import logging
import asyncio
from flask import Flask, request
from telegram import (
    Bot, Update, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

logging.basicConfig(level=logging.INFO)

# ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Data
ADMINS_FILE = "admins.json"
admins = []

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# Bot init
bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# Load admins
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        admins = json.load(f)
else:
    admins = []

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in admins

# === COMMANDS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey, I'm CINDRELLA 💫 so what's in your mind !")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("You are not allowed.")

    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]

    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👑 Admin Panel:", reply_markup=markup)

# === CALLBACKS ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        return await query.message.reply_text("Not allowed.")

    data = query.data

    if data == "broadcast":
        context.user_data["awaiting"] = "broadcast"
        await query.message.reply_text("📢 Send the message to broadcast:")

    elif data == "add_admin" and user_id == OWNER_ID:
        context.user_data["awaiting"] = "add_admin"
        await query.message.reply_text("Enter user ID to add as admin:")

    elif data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["awaiting"] = "remove_admin"
        await query.message.reply_text("Enter admin ID to remove:")

    elif data == "list_admins" and user_id == OWNER_ID:
        if admins:
            await query.message.reply_text("👥 Admins:\n" + "\n".join(map(str, admins)))
        else:
            await query.message.reply_text("No admins yet.")

# === TEXT HANDLING ===

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Forward to owner/admins
    for admin_id in [OWNER_ID] + admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📨 From [{username}](tg://user?id={user_id}):\n{text}",
                parse_mode="Markdown"
            )
        except:
            pass

    # Admin tasks
    awaiting = context.user_data.get("awaiting")
    if awaiting:
        if awaiting == "broadcast" and is_admin(user_id):
            for chat_id in [OWNER_ID] + admins:
                try:
                    await bot.send_message(chat_id=chat_id, text=f"📢 Broadcast:\n{text}")
                except:
                    pass
            await update.message.reply_text("✅ Broadcast sent!")
        elif awaiting == "add_admin" and user_id == OWNER_ID:
            try:
                new_id = int(text)
                if new_id not in admins:
                    admins.append(new_id)
                    save_admins()
                    await update.message.reply_text("✅ Admin added.")
                else:
                    await update.message.reply_text("Already admin.")
            except:
                await update.message.reply_text("Invalid ID.")
        elif awaiting == "remove_admin" and user_id == OWNER_ID:
            try:
                rem_id = int(text)
                if rem_id in admins:
                    admins.remove(rem_id)
                    save_admins()
                    await update.message.reply_text("✅ Admin removed.")
                else:
                    await update.message.reply_text("Not found in admins.")
            except:
                await update.message.reply_text("Invalid ID.")
        context.user_data["awaiting"] = None
        return

    # AI reply
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://openrouter.ai",
            "X-Title": "CINDRELLA Bot"
        }
        data = {
            "model": "openchat/openchat-3.5",
            "messages": [SYSTEM_PROMPT, {"role": "user", "content": text}]
        }
        response = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
        reply = response.json()["choices"][0]["message"]["content"]
    except Exception:
        reply = "Oops, I'm OFFLINE right now 😭😭"

    await update.message.reply_text(reply)

# === TELEGRAM APP SETUP ===

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

# === SET WEBHOOK + INIT ===

async def set_webhook():
    await application.initialize()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await application.start()

asyncio.run(set_webhook())

# === FLASK SERVER (for RENDER) ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
