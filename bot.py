import os
import logging
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

# Load config
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OWNER_ID = 6559745280  # Replace with your real owner ID

admins = {OWNER_ID}
user_chats = set()
group_chats = set()

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# Set up Flask app
flask_app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Send message using OpenRouter
async def ask_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5",
        "messages": [
            SYSTEM_PROMPT,
            {"role": "user", "content": prompt}
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=30
            )
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Something went wrong! {e}"

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_chats.add(user.id)
    await update.message.reply_text("Hi, I'm CINDRELLA 🌸. Let's talk!")

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return await update.message.reply_text("You are not authorized.")
    
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

# Handle button clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in admins:
        return await query.edit_message_text("You are not authorized.")

    data = query.data

    if data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.edit_message_text("Send the message to broadcast.")

    elif data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add_admin"
        await query.edit_message_text("Send the user ID to add as admin.")

    elif data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove_admin"
        await query.edit_message_text("Send the user ID to remove from admins.")

    elif data == "list_admins" and user_id == OWNER_ID:
        await query.edit_message_text(f"Admins:\n" + "\n".join(str(a) for a in admins))

# Handle text
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Save private or group chat
    if update.message.chat.type == "private":
        user_chats.add(update.message.chat.id)
    elif update.message.chat.type in ["group", "supergroup"]:
        group_chats.add(update.message.chat.id)

    # Owner/admin actions
    if user_id in admins and "action" in context.user_data:
        action = context.user_data.pop("action")

        if action == "broadcast":
            for uid in user_chats:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except:
                    pass
            for gid in group_chats:
                try:
                    await context.bot.send_message(chat_id=gid, text=text)
                except:
                    pass
            return await update.message.reply_text("✅ Broadcast sent.")

        elif action == "add_admin":
            admins.add(int(text))
            return await update.message.reply_text("✅ Admin added.")

        elif action == "remove_admin":
            admins.discard(int(text))
            return await update.message.reply_text("✅ Admin removed.")

    # Forward message to owner/admins
    for admin_id in admins:
        try:
            msg_link = f"https://t.me/c/{str(update.message.chat.id)[4:]}/{update.message.message_id}" if update.message.chat.type != "private" else ""
            await context.bot.send_message(chat_id=admin_id,
                                           text=f"📩 From {update.effective_user.username or update.effective_user.first_name}:\n{text}\n{msg_link}")
        except:
            pass

    # Chatbot reply
    reply = await ask_openrouter(text)
    await update.message.reply_text(reply)

# Create the application
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# Flask webhook route
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Set webhook
async def set_webhook():
    await application.bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    application.run_polling()  # Also starts the internal updater for webhook
