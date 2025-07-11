import os
import logging
import random
import httpx
import telegram
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))

# App setup
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Admins & Settings
ADMINS = set([OWNER_ID])
USAGE_COUNT = 0
GREETING_WORDS = ["hi", "hello", "hey", "sup", "yo", "heya"]
BOT_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent girl. You reply like a real best friend in short, human-like sentences."
}
MODELS = [
    "openchat/openchat-3.5-0106", "mistralai/mixtral-8x7b",
    "gryphe/mythomax-l2-13b", "openrouter/chronos-hermes-13b",
    "google/gemma-7b-it", "mistralai/mistral-7b-instruct"
]
ADMIN_PANEL, ADDING_ADMIN, REMOVING_ADMIN = range(3)

# AI reply
async def ai_reply(prompt):
    global USAGE_COUNT
    USAGE_COUNT += 1
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "Content-Type": "application/json"
    }
    payload = {
        "model": random.choice(MODELS),
        "messages": [BOT_SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
            data = res.json()
            return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        return "Oops! AI error."

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")
    )
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?",
        reply_markup=btn
    )

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await update.message.reply_text("You aren't allowed here.")

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("📊 Usage", callback_data="usage")]
        ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_PANEL

# Handle admin buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "broadcast":
        context.user_data['action'] = 'broadcast'
        await query.message.reply_text("Send the message to broadcast:")
        return ADMIN_PANEL

    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add as admin:")
        return ADDING_ADMIN

    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove:")
        return REMOVING_ADMIN

    elif query.data == "list_admins" and user_id == OWNER_ID:
        out = "\n".join([f"ID: {uid}" for uid in ADMINS])
        await query.message.reply_text(f"Admins:\n{out}")

    elif query.data == "usage" and user_id == OWNER_ID:
        await query.message.reply_text(f"Total replies today: {USAGE_COUNT}")

    return ADMIN_PANEL

# Add/remove admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text)
        ADMINS.add(new_id)
        await update.message.reply_text("✅ Admin added.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rem_id = int(update.message.text)
        ADMINS.discard(rem_id)
        await update.message.reply_text("✅ Admin removed.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# Text handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id

    # Message forwarding
    for admin_id in ADMINS:
        if admin_id != user_id:
            try:
                forward_text = f"📩 From @{msg.from_user.username or user_id}:\n{msg.text}"
                await context.bot.send_message(admin_id, forward_text)
            except:
                pass

    # Admin broadcast
    if user_id == OWNER_ID:
        action = context.user_data.get('action')
        if action == 'broadcast':
            for admin in ADMINS:
                try:
                    await context.bot.send_message(admin, msg.text)
                except:
                    pass
            await msg.reply_text("✅ Broadcast sent.")
            context.user_data.clear()
            return

    # Greetings
    if msg.text.lower() in GREETING_WORDS:
        return await msg.reply_text(random.choice(["Heyy", "Hii love", "Yo!", "Sweet hello", "Cutee hii 💖"]))

    # AI reply
    reply = await ai_reply(msg.text)
    await msg.reply_text(reply[:300])

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

# Handlers
panel_conv = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_panel)],
    states={
        ADMIN_PANEL: [CallbackQueryHandler(button_handler)],
        ADDING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
        REMOVING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(panel_conv)
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# Start
if __name__ == '__main__':
    telegram_app.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook"
        )
