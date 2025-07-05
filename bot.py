import os
import logging
import httpx
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import random
import json

# === ENV ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
USERS_FILE = "users.json"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Admins ===
ADMINS = set([OWNER_ID])

# === Personality ===
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a 16-year-old sweet, kind, emotionally intelligent girl. You speak only English, like a real person, emotionally connected as a best friend."
}

# === Models ===
FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "intel/neural-chat-7b",
]

# === Greeting Pool ===
GREETINGS = [
    "Hey there! How can I help you?",
    "Hi dear 🌸 What's up?",
    "Hello love 💖 I'm here for you!",
    "Hey sweetie, tell me what's on your mind.",
    "Hi 🌷 Need anything from me?"
]

def random_greeting():
    return random.choice(GREETINGS)

# === Load & Save Users ===
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

# === AI Generator ===
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
    return "I'm feeling a little tired right now. Please try again in a bit 💭💤"

# === Start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if update.effective_chat.type == "private":
        users = load_users()
        if chat_id not in users:
            users.append(chat_id)
            save_users(users)

    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "HEY, I'M CINDRELLA 🌹🕯️. JOIN FOR BOT UPDATE AND GIVE US YOUR OPENION @animalin_tm_empire🌹🕯️.BTW WHAT'S GOING ON DEAR 🌹🕯️🕯️..??",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Admin Panel ===
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# === Button Callback ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    if query.data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text("Send me the broadcast message.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text("👮 Admins:\n" + "\n".join(str(a) for a in ADMINS))

# === Message Handler ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    text = update.message.text or ""
    is_mentioned = f"@{context.bot.username.lower()}" in text.lower()
    is_replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    # Save users
    if chat.type == "private":
        users = load_users()
        if chat.id not in users:
            users.append(chat.id)
            save_users(users)

    # Admin actions
    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            users = load_users()
            count = 0
            for chat_id in users:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                    count += 1
                except: pass
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
                else:
                    await update.message.reply_text("❌ ID not in admin list.")
            except:
                await update.message.reply_text("❌ Invalid ID.")
        return

    # Forwarding
    if chat.type == "private" or is_mentioned or is_replied:
        for admin_id in ADMINS:
            try:
                if chat.type == "private":
                    await context.bot.forward_message(admin_id, chat.id, update.message.message_id)
                else:
                    msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
                    await context.bot.send_message(admin_id, f"📨 In group @{chat.username or 'unknown'} by @{update.effective_user.username or 'user'}:\n{msg_link}")
            except: pass

    # Reply logic
    if chat.type in ["group", "supergroup"]:
        if text.lower() in ["hi", "hello", "hey", "heyy", "sup", "good morning", "good night"]:
            await update.message.reply_text(random_greeting(), reply_to_message_id=update.message.message_id)
        elif is_mentioned or is_replied:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    elif chat.type == "private":
        reply = await generate_reply(text)
        await update.message.reply_text(reply)

# === Run Bot ===
if __name__ == "__main__":
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
)
