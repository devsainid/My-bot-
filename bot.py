import os
import logging
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.ext import AIORateLimiter
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

ADMIN_IDS = set([OWNER_ID])
pending_action = {}

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# SYSTEM PROMPT FOR CINDRELLA
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ========== HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey, I'm CINDRELLA 🕯️🕯️. your virtual  friend. how can i assist you today dear 🌹🕯️!")

async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text("You're not allowed to access this.")

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    await update.message.reply_text("Welcome to Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in ADMIN_IDS:
        return await query.edit_message_text("Access denied.")

    if query.data == "broadcast":
        pending_action[user_id] = "broadcast"
        await query.edit_message_text("Send me the message to broadcast.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        pending_action[user_id] = "add_admin"
        await query.edit_message_text("Send the user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        pending_action[user_id] = "remove_admin"
        await query.edit_message_text("Send the user ID to remove from admin.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        admin_list = "\n".join(str(i) for i in ADMIN_IDS)
        await query.edit_message_text(f"Admins:\n{admin_list}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Admin command handler
    if user_id in pending_action:
        action = pending_action.pop(user_id)
        if action == "broadcast":
            for chat_id in context.bot_data.get("chats", set()):
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                except:
                    pass
            await update.message.reply_text("Broadcast sent.")
        elif action == "add_admin":
            try:
                new_admin = int(text.strip())
                ADMIN_IDS.add(new_admin)
                await update.message.reply_text("Admin added.")
            except:
                await update.message.reply_text("Invalid user ID.")
        elif action == "remove_admin":
            try:
                remove_id = int(text.strip())
                if remove_id != OWNER_ID:
                    ADMIN_IDS.discard(remove_id)
                    await update.message.reply_text("Admin removed.")
                else:
                    await update.message.reply_text("You can't remove owner.")
            except:
                await update.message.reply_text("Invalid user ID.")
        return

    # Store chat IDs for broadcast
    context.bot_data.setdefault("chats", set()).add(update.effective_chat.id)

    # AI Chat
    reply = await get_ai_reply(text)
    await update.message.reply_text(reply)

    # Copy forward to owner/admins
    await forward_to_admins(update)

async def forward_to_admins(update: Update):
    sender = update.effective_user
    chat = update.effective_chat

    user_info = f"👤 @{sender.username or sender.first_name} ({sender.id})"
    chat_info = f"💬 Group: {chat.title} ({chat.id})" if chat.type != "private" else "💬 Private Chat"
    link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if chat.type != "private" else ""

    text = f"{user_info}\n{chat_info}\n\nMessage: {update.message.text}\n{link}"

    for admin_id in ADMIN_IDS:
        if admin_id != sender.id:
            try:
                await update.message.copy(chat_id=admin_id)
                await context.bot.send_message(chat_id=admin_id, text=text)
            except:
                pass

# ========== AI Integration ==========

async def get_ai_reply(msg):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": [
                    SYSTEM_PROMPT,
                    {"role": "user", "content": msg}
                ]
            }
        )
        return res.json()["choices"][0]["message"]["content"]
    except:
        return "I'm ofline  right now my dear sir ."

# ========== Webhook Setup ==========

@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot.bot)
    bot.update_queue.put_nowait(update)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is running"

# ========== Bot Init ==========

bot = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()
bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("admin", handle_admin))
bot.add_handler(CallbackQueryHandler(handle_callback))
bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

# Set Webhook on start
async def set_webhook():
    await bot.bot.set_webhook(url=WEBHOOK_URL)

bot.initialize()
bot.post_init = set_webhook
bot.run_polling = None  # disable polling

# ========== Final Start ==========

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
