import os
import logging
import random
import httpx
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ✅ Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Admins
ADMINS = set([OWNER_ID])

# ✅ Chat Memory File
KNOWN_CHATS_FILE = "known_chats.txt"

def load_known_chats():
    if os.path.exists(KNOWN_CHATS_FILE):
        with open(KNOWN_CHATS_FILE, "r") as f:
            return set(int(line.strip()) for line in f if line.strip().isdigit())
    return set()

def save_known_chat(chat_id):
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        with open(KNOWN_CHATS_FILE, "a") as f:
            f.write(str(chat_id) + "\n")

known_chats = load_known_chats()

# ✅ System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ✅ Free AI Models
FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "intel/neural-chat-7b",
]

# ✅ Greetings
GREETINGS = [
    "Hey there! How can I help you?",
    "Hi dear 🌸 What's up?",
    "Hello love 💖 I'm here for you!",
    "Hey sweetie, tell me what's on your mind.",
    "Hi 🌷 Need anything from me?"
]

CONVO_START_WORDS = ["hi", "hello", "hey", "heyy", "sup", "good morning", "good night", "gm", "gn"]

def random_greeting():
    return random.choice(GREETINGS)

# ✅ AI Chat
async def generate_reply(user_message):
    for model in FREE_MODELS:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
                        "X-Title": "CINDRELLA-Bot"
                    },
                    json={
                        "model": model,
                        "messages": [SYSTEM_PROMPT, {"role": "user", "content": user_message}]
                    }
                )
                data = res.json()
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
    return "MY DEVELOPER IS TRYING TO UPDATE ME IF U HAVE ANY OPENION SO REPORT US HERE ✨ @animalin_tm_empire"

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "HEY, I'M CINDRELLA 🌹🕯️🕯️. JOIN FOR BOT UPDATE AND GIVE US YOUR OPENION @animalin_tm_empire 🌹🕯️🕯️.BTW WHAT'S GOING ON DEAR 🌹🕯️🕯️..??",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ✅ /admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# ✅ Button Handling
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    context.user_data["action"] = query.data
    await query.message.reply_text("Send me the input now.")

# ✅ Message Handling
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user_id = update.effective_user.id
    text = update.message.text or ""
    is_mentioned = f"@{context.bot.username.lower()}" in text.lower()
    is_replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    save_known_chat(chat.id)

    # Admin actions
    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            count = 0
            for cid in known_chats:
                try:
                    await context.bot.send_message(chat_id=cid, text=text)
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"📢 Broadcast sent to {count} chats.")
        elif action == "add_admin":
            try:
                new_admin = int(text.strip())
                ADMINS.add(new_admin)
                await update.message.reply_text(f"✅ Admin {new_admin} added.")
            except:
                await update.message.reply_text("❌ Invalid ID.")
        elif action == "remove_admin":
            try:
                rem_admin = int(text.strip())
                if rem_admin in ADMINS:
                    ADMINS.remove(rem_admin)
                    await update.message.reply_text(f"✅ Admin {rem_admin} removed.")
            except:
                await update.message.reply_text("❌ Invalid ID.")
        elif action == "list_admins":
            await update.message.reply_text("👮 Admins:\n" + "\n".join(str(a) for a in ADMINS))
        return

    # Forward
    if chat.type == "private" or is_mentioned or is_replied:
        for admin_id in ADMINS:
            try:
                if chat.type == "private":
                    await context.bot.forward_message(admin_id, chat.id, update.message.message_id)
                else:
                    msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
                    await context.bot.send_message(admin_id, f"📨 In group @{chat.username or 'unknown'} by @{update.effective_user.username or 'user'}:\n{msg_link}")
            except:
                pass

    # Chat
    if chat.type in ["group", "supergroup"]:
        if any(word in text.lower() for word in CONVO_START_WORDS):
            await update.message.reply_text(random_greeting(), reply_to_message_id=update.message.message_id)
        elif is_mentioned or is_replied:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    elif chat.type == "private":
        reply = await generate_reply(text)
        await update.message.reply_text(reply)

# ✅ Start Bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
            )
