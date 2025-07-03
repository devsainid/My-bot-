import os
import json
import httpx
import logging
import asyncio
from flask import Flask, request
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

logging.basicConfig(level=logging.INFO)

# ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

ADMINS_FILE = "admins.json"
admins = []

# Load admins from file
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        admins = json.load(f)

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in admins

# Flask app
flask_app = Flask(__name__)
bot = Bot(BOT_TOKEN)

# === Telegram Bot Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey, I'm CINDRELLA 💫 so what's in your mind !")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("You are not allowed.")

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👑 Admin Panel:", reply_markup=markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        return await query.message.reply_text("Not allowed.")

    data = query.data
    context.user_data["awaiting"] = data

    if data == "broadcast":
        await query.message.reply_text("📢 Send the message to broadcast:")
    elif data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Enter user ID to add as admin:")
    elif data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Enter admin ID to remove:")
    elif data == "list_admins" and user_id == OWNER_ID:
        if admins:
            await query.message.reply_text("👥 Admins:\n" + "\n".join(map(str, admins)))
        else:
            await query.message.reply_text("No admins yet.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Forward to owner + admins
    for admin_id in [OWNER_ID] + admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📨 From [{username}](tg://user?id={user_id}):\n{text}",
                parse_mode="Markdown"
            )
        except:
            pass

    # Handle awaiting actions
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
                    await update.message.reply_text("Already an admin.")
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
                    await update.message.reply_text("Admin not found.")
            except:
                await update.message.reply_text("Invalid ID.")
        context.user_data["awaiting"] = None
        return

    # AI Chat Reply
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
    except:
        reply = "Oops, I'm OFFLINE right now 😭😭"

    await update.message.reply_text(reply)

# === Webhook Route ===
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    flask_app.bot_app.update_queue.put_nowait(update)
    return "OK"

# === Main async setup ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    flask_app.bot_app = app

    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()  # Important: Required even with webhook for queue processing

    print("Bot running...")

# === Run Flask and Telegram Bot ===
if __name__ == "__main__":
    asyncio.get_event_loop().create_task(main())
    flask_app.run(host="0.0.0.0", port=PORT)
