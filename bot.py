import os
import json
import logging
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

admins_file = "admins.json"
if not os.path.exists(admins_file):
    with open(admins_file, "w") as f:
        json.dump([OWNER_ID], f)

with open(admins_file, "r") as f:
    ADMINS = json.load(f)

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Set webhook on startup
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Bot running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! I’m CINDRELLA. YOUR super intelligence virtual AI friend 🌼 so how can i  assist you today !")

def is_admin(user_id):
    return user_id in ADMINS or user_id == OWNER_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
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
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

broadcasting = {}

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "broadcast" and is_admin(user_id):
        await query.message.reply_text("📝 Send me the message to broadcast.")
        broadcasting[user_id] = "pending"

    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add as admin:")
        context.user_data["admin_action"] = "add"

    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove from admin:")
        context.user_data["admin_action"] = "remove"

    elif query.data == "list_admins" and user_id == OWNER_ID:
        admin_list = "\n".join([f"`{aid}`" for aid in ADMINS])
        await query.message.reply_text(f"👑 Admins:\n{admin_list}", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Admin input handling
    if user_id in broadcasting and broadcasting[user_id] == "pending":
        await broadcast_message(text, context)
        await update.message.reply_text("✅ Message broadcasted.")
        del broadcasting[user_id]
        return

    if "admin_action" in context.user_data and user_id == OWNER_ID:
        action = context.user_data.pop("admin_action")
        try:
            target_id = int(text)
            if action == "add" and target_id not in ADMINS:
                ADMINS.append(target_id)
                with open(admins_file, "w") as f:
                    json.dump(ADMINS, f)
                await update.message.reply_text("✅ Admin added.")
            elif action == "remove" and target_id in ADMINS:
                ADMINS.remove(target_id)
                with open(admins_file, "w") as f:
                    json.dump(ADMINS, f)
                await update.message.reply_text("✅ Admin removed.")
            else:
                await update.message.reply_text("⚠️ Invalid action.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        return

    # Forward message
    await forward_to_owner(update)

    # AI Reply
    reply = await ask_cindrella(text)
    await update.message.reply_text(reply)

async def ask_cindrella(user_msg):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-1210",
        "messages": [
            {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
            {"role": "user", "content": user_msg}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        return result["choices"][0]["message"]["content"]

async def forward_to_owner(update: Update):
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text or "<non-text message>"
    sender_info = f"👤 From: {user.full_name} (@{user.username or 'no username'}) [ID: {user.id}]"
    message_link = ""

    if chat.type != "private":
        try:
            message_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
        except:
            message_link = ""

    for admin_id in ADMINS:
        await context.bot.send_message(admin_id, f"{sender_info}\n\n{text}\n\n🔗 {message_link}")

async def broadcast_message(text, context):
    for chat_id in ADMINS:
        try:
            await context.bot.send_message(chat_id, text)
        except:
            continue

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(handle_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

if __name__ == "__main__":
    import asyncio
    import threading
    import requests

    def set_webhook():
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url": f"{WEBHOOK_URL}"})

    threading.Thread(target=set_webhook).start()
    app.run(host="0.0.0.0", port=10000)
