import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import httpx

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
admins = set()

# ====== LOGGING ======
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== AI CHAT ======
async def ai_chat(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": "openchat/openchat-3.5-0106",
        "messages": [
            {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
            {"role": "user", "content": prompt}
        ]
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

# ====== COMMANDS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in admins:
        return

    buttons = []
    if user_id == OWNER_ID:
        buttons.extend([
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
        ])
    if user_id == OWNER_ID or user_id in admins:
        buttons.insert(0, [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")])

    await update.message.reply_text("🛡 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# ====== CALLBACKS ======
pending_action = {}

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "broadcast":
        pending_action[user_id] = "broadcast"
        await query.message.reply_text("Send the message you want to broadcast.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        pending_action[user_id] = "add_admin"
        await query.message.reply_text("Send the Telegram ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        pending_action[user_id] = "remove_admin"
        await query.message.reply_text("Send the Telegram ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        if admins:
            admin_list = "\n".join(str(a) for a in admins)
            await query.message.reply_text(f"Current Admins:\n{admin_list}")
        else:
            await query.message.reply_text("No admins added yet.")

# ====== HANDLE MESSAGES ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Admin actions
    if user_id in pending_action:
        action = pending_action.pop(user_id)
        if action == "broadcast":
            for chat_id in context.application.chat_data:
                try:
                    await context.bot.send_message(chat_id, text)
                except:
                    continue
            await update.message.reply_text("✅ Broadcast sent.")
        elif action == "add_admin":
            admins.add(int(text))
            await update.message.reply_text(f"✅ Admin {text} added.")
        elif action == "remove_admin":
            admins.discard(int(text))
            await update.message.reply_text(f"✅ Admin {text} removed.")
        return

    # AI Chat trigger
    if update.message.chat.type != "private" and text.lower() in ["hi", "hello", "hey", "sup guys", "yo"]:
        reply = await ai_chat(text)
        await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    elif update.message.chat.type == "private":
        reply = await ai_chat(text)
        await update.message.reply_text(reply)

    # Forward message to owner and admins
    sender = update.effective_user
    chat = update.effective_chat
    for admin_id in [OWNER_ID] | admins:
        try:
            msg_info = f"👤 From: {sender.full_name} (@{sender.username})\n💬 Chat: {chat.title or 'Private'}\n📝 Message:\n{text}"
            await context.bot.send_message(chat_id=admin_id, text=msg_info)
        except:
            continue

# ====== MAIN ======
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    print("✅ Webhook set.")
    await application.updater.start_polling()
    await application.updater.idle()

# ====== WEBHOOK ROUTE ======
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot.app.bot)
    asyncio.get_event_loop().create_task(bot.app.process_update(update))
    return "OK", 200

# ====== RUN ======
if __name__ == "__main__":
    bot = type("bot", (), {})()
    asyncio.run(main())
