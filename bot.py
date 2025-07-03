import os
import json
import httpx
import logging
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
import asyncio

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

ADMINS_FILE = "admins.json"
admins = []
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        admins = json.load(f)

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in admins

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

# === Commands ===
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

# === Callback ===
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
        await query.message.reply_text("👥 Admins:\n" + "\n".join(map(str, admins)) if admins else "No admins yet.")

# === Messages ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    for admin_id in [OWNER_ID] + admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📨 From [{username}](tg://user?id={user_id}):\n{text}",
                parse_mode="Markdown"
            )
        except:
            pass

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

    # AI response
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
        res = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
        reply = res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        reply = "Oops, I'm OFFLINE right now 😭😭"

    await update.message.reply_text(reply)

# === Telegram Handlers ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Webhook Setup ===
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.get_event_loop().create_task(application.process_update(update))
    return "OK"

@app.route("/")
def index():
    return "CINDRELLA bot is live!"

async def set_webhook():
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
