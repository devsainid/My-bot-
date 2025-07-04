import os
import logging
import asyncio
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, AIORateLimiter, CommandHandler,
    MessageHandler, ContextTypes, filters, CallbackQueryHandler
)
from telegram.constants import ParseMode

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# --- FLASK ---
app = Flask(__name__)

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# --- GLOBAL ADMIN LIST ---
ADMINS = set()

# --- OPENROUTER AI CHAT FUNCTION ---
async def ai_reply(user_message):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": [
                    SYSTEM_PROMPT,
                    {"role": "user", "content": user_message}
                ]
            },
            timeout=15
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI ERROR: {e}")
        return "Sorry, something went wrong while thinking..."

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Heyy I'm CINDRELLA 🌹🕯️. add me in any group to use.! and how can i assist you today 🌹🕯️.?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    # Forward to owner
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📩 Message from [{user.first_name}](tg://user?id={user.id}):\n{text}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

    # AI Reply
    reply = await ai_reply(text)
    await update.message.reply_text(reply)

# --- ADMIN PANEL ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in ADMINS:
        return await update.message.reply_text("You are not authorized!")

    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]

    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]

    await update.message.reply_text("👑 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# --- CALLBACK HANDLERS ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "broadcast":
        if user_id == OWNER_ID or user_id in ADMINS:
            context.user_data["awaiting_broadcast"] = True
            await query.message.reply_text("Send the broadcast message now:")
    elif query.data == "add_admin":
        if user_id == OWNER_ID:
            context.user_data["awaiting_add_admin"] = True
            await query.message.reply_text("Send the user ID to add as admin:")
    elif query.data == "remove_admin":
        if user_id == OWNER_ID:
            context.user_data["awaiting_remove_admin"] = True
            await query.message.reply_text("Send the user ID to remove from admin:")
    elif query.data == "list_admins":
        if user_id == OWNER_ID:
            if not ADMINS:
                await query.message.reply_text("No admins added.")
            else:
                await query.message.reply_text("Current admins:\n" + "\n".join(map(str, ADMINS)))

# --- TEXT AFTER CALLBACK ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        # Broadcast message to all chats (simulate with owner only here)
        await context.bot.send_message(chat_id=OWNER_ID, text=f"📢 Broadcast:\n{text}")
        await update.message.reply_text("✅ Broadcast sent!")

    elif context.user_data.get("awaiting_add_admin"):
        context.user_data["awaiting_add_admin"] = False
        try:
            new_admin_id = int(text)
            ADMINS.add(new_admin_id)
            await update.message.reply_text("✅ Admin added!")
        except:
            await update.message.reply_text("Invalid ID!")

    elif context.user_data.get("awaiting_remove_admin"):
        context.user_data["awaiting_remove_admin"] = False
        try:
            ADMINS.remove(int(text))
            await update.message.reply_text("✅ Admin removed!")
        except:
            await update.message.reply_text("ID not found!")

    else:
        await handle_message(update, context)

# --- SETUP APPLICATION ---
bot = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("admin", admin_panel))
bot.add_handler(CallbackQueryHandler(callback_handler))
bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))

# --- WEBHOOK SETUP ---
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot.bot)
        asyncio.create_task(bot.process_update(update))
        return "OK"
    return "Running!"

# --- INITIALIZE AND SET WEBHOOK ---
async def main():
    await bot.initialize()
    await bot.bot.set_webhook(url=WEBHOOK_URL)
    await bot.start()
    print("Bot initialized with webhook!")

asyncio.run(main())

# --- RUN FLASK ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
