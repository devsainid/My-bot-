import os
import logging
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
    filters, CallbackQueryHandler
)
import httpx
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8443))

admins = set([OWNER_ID])
broadcast_mode = {}

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# AI Chat
async def generate_ai_reply(user_message):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
            "Content-Type": "application/json"
        }
        json_data = {
            "model": "openchat/openchat-3.5-0106",
            "messages": [
                SYSTEM_PROMPT,
                {"role": "user", "content": user_message}
            ]
        }
        async with httpx.AsyncClient() as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_data)
            return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return "Oops, something went wrong 😥"

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

# Admin Panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return await update.message.reply_text("You're not authorized.")
    
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]

    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("🔐 Admin Panel", reply_markup=reply_markup)

# Callback Button Actions
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in admins:
        return await query.message.reply_text("You’re not authorized.")

    if query.data == "broadcast":
        broadcast_mode[user_id] = "awaiting_message"
        await query.message.reply_text("Send the message to broadcast.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        broadcast_mode[user_id] = "add_admin"
        await query.message.reply_text("Send the user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        broadcast_mode[user_id] = "remove_admin"
        await query.message.reply_text("Send the user ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        admin_list = "\n".join([str(admin) for admin in admins])
        await query.message.reply_text(f"👮 Admins:\n{admin_list}")

# Handle Admin Input
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in broadcast_mode:
        return

    mode = broadcast_mode.pop(user_id)
    text = update.message.text

    if mode == "broadcast":
        for chat_id in context.bot_data.get("chats", []):
            try:
                await context.bot.send_message(chat_id, text)
            except:
                pass
        await update.message.reply_text("✅ Broadcast sent.")
    elif mode == "add_admin":
        try:
            admins.add(int(text))
            await update.message.reply_text(f"✅ Admin added: {text}")
        except:
            await update.message.reply_text("❌ Invalid user ID.")
    elif mode == "remove_admin":
        try:
            admins.remove(int(text))
            await update.message.reply_text(f"✅ Admin removed: {text}")
        except:
            await update.message.reply_text("❌ Could not remove admin.")

# Reply on "hi", "hello"
async def greet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()
    if any(word in msg for word in ["hi", "hello", "hey", "sup", "yo"]):
        reply = await generate_ai_reply(msg)
        await update.message.reply_text(reply)

# Forward all messages to owner & admins
async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    sender_info = f"👤 From: @{user.username or user.first_name} ({user.id})"

    for admin_id in admins:
        if admin_id != user.id:
            try:
                await context.bot.send_message(admin_id, f"{sender_info}\n\n{msg.text}")
            except:
                pass

    # Track chats
    context.bot_data.setdefault("chats", set()).add(update.effective_chat.id)

# Flask Webhook
@app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, context.bot)
    await context.application.process_update(update)
    return "OK"

# Run
async def run():
    global context
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    context = application

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(admins), handle_admin_input))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), greet_handler))
    application.add_handler(MessageHandler(filters.ALL, forward_messages))

    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("✅ Webhook set")

    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(run())
