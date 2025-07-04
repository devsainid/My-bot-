import os
import logging
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', 10000))  # Render default port

app = Flask(__name__)
admins = set()
pending_action = {}

logging.basicConfig(level=logging.INFO)

# ========== AI ==========
async def ai_chat(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openchat/openchat-3.5-0106",
        "messages": [
            {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
            {"role": "user", "content": prompt}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']

# ========== HANDLERS ==========
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
            await query.message.reply_text("\n".join(str(i) for i in admins))
        else:
            await query.message.reply_text("No admins added.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in pending_action:
        action = pending_action.pop(user_id)
        if action == "broadcast":
            for chat_id in context.application.chat_data:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                except:
                    pass
            await update.message.reply_text("✅ Broadcast sent.")
        elif action == "add_admin":
            admins.add(int(text))
            await update.message.reply_text("✅ Admin added.")
        elif action == "remove_admin":
            admins.discard(int(text))
            await update.message.reply_text("✅ Admin removed.")
        return

    if update.message.chat.type != "private" and text.lower() in ["hi", "hello", "hey", "yo", "sup guys"]:
        reply = await ai_chat(text)
        await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    elif update.message.chat.type == "private":
        reply = await ai_chat(text)
        await update.message.reply_text(reply)

    # Forwarding
    sender = update.effective_user
    chat = update.effective_chat
    for admin_id in [OWNER_ID] | admins:
        try:
            info = f"👤 {sender.full_name} (@{sender.username})\n📍 Chat: {chat.title or 'Private'}\n💬 {text}"
            await context.bot.send_message(chat_id=admin_id, text=info)
        except:
            pass

# ========== SETUP ==========
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ========== FLASK ROUTE ==========
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK"

# ========== RUN ==========
if __name__ == "__main__":
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        )
