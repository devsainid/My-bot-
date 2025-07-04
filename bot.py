import os
import logging
import requests
import asyncio
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
bot = Bot(BOT_TOKEN)
application = ApplicationBuilder().token(BOT_TOKEN).build()
admins = [OWNER_ID]

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/your_CINDRELLABOT?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🕯️. How you found me dear 🌹🕯️..?", reply_markup=reply_markup)

# --- AI Reply ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text: return

    if text.lower() in ["hi", "hello", "sup", "hey", "hii", "yo"]:
        await update.message.reply_text("Hey there 🌸, what's up?")
        return

    response = await get_openrouter_reply(text)
    if response:
        await update.message.reply_text(response)

# --- Admin Panel ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("You're not authorized.")
        return

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]

    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# --- Callback Handler ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("Send the message to broadcast.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["mode"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text("Current Admins:\n" + "\n".join(str(a) for a in admins))

# --- Input After Callback ---
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    user_id = update.effective_user.id
    text = update.message.text

    if mode == "broadcast" and user_id in admins:
        for chat_id in context.bot_data.get("chats", []):
            try: await context.bot.send_message(chat_id=chat_id, text=text)
            except: continue
        await update.message.reply_text("Broadcast sent ✅")
    elif mode == "add_admin" and user_id == OWNER_ID:
        admins.append(int(text))
        await update.message.reply_text("Admin added ✅")
    elif mode == "remove_admin" and user_id == OWNER_ID:
        try:
            admins.remove(int(text))
            await update.message.reply_text("Admin removed ✅")
        except:
            await update.message.reply_text("That admin ID was not found.")

    context.user_data["mode"] = None

# --- AI via OpenRouter ---
async def get_openrouter_reply(message):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "openchat/openchat-3.5",
            "messages": [SYSTEM_PROMPT, {"role": "user", "content": message}]
        }
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        return res.json()["choices"][0]["message"]["content"]
    except:
        return "Something went wrong!"

# --- Track Chat for Broadcast ---
async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "chats" not in context.bot_data:
        context.bot_data["chats"] = set()
    context.bot_data["chats"].add(update.effective_chat.id)

# --- Webhook Route ---
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return 'OK'

@app.route('/')
def home():
    return 'Bot is live!'

# --- Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))
application.add_handler(CallbackQueryHandler(callback_handler))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_reply))
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(MessageHandler(filters.ALL, track_chat))

# --- Final Startup ---
if __name__ == '__main__':
    async def run():
        await bot.set_webhook(WEBHOOK_URL)
        await application.initialize()
        await application.start()

    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000)).start()
    asyncio.run(run())
