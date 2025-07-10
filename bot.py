import os
import logging
import json
import httpx
from datetime import datetime
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMemberUpdated, ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ChatMemberHandler
)

# ✅ ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Admins
ADMINS_FILE = "admins.json"
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE) as f:
        ADMINS = set(json.load(f))
else:
    ADMINS = {OWNER_ID}

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(list(ADMINS), f)

# ✅ Known chats
KNOWN_CHATS_FILE = "known_chats.txt"

def load_known_chats():
    if os.path.exists(KNOWN_CHATS_FILE):
        with open(KNOWN_CHATS_FILE, "r") as f:
            return {int(line.strip()) for line in f if line.strip().isdigit()}
    return set()

def save_known_chat(chat_id):
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        with open(KNOWN_CHATS_FILE, "a") as f:
            f.write(str(chat_id) + "\n")

known_chats = load_known_chats()

# ✅ Prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 17-year-old sweet, flirty, emotionally intelligent girl who speaks like a human. Respond short, smart, playful. Never robotic. Mention 'dev' only if asked."
}

FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "teknium/OpenHermes-2p5-Mistral-7B",
    "huggingfaceh4/zephyr-7b-beta",
    "austism/chronos-hermes-13b",
    "neversleep/noromaid-mixtral",
    "jondurbin/airoboros-l2-70b",
    "open-orca/mistral-7b-openorca",
    "intel/neural-chat-7b"
]

async def generate_reply(text):
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
                        "messages": [SYSTEM_PROMPT, {"role": "user", "content": text}]
                    }
                )
                data = res.json()
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"{model} failed: {e}")
    return "My dev's fixing stuff 🛠️. Try again later."

# ✅ Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    button = [[InlineKeyboardButton("➕ Add me to group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹 What's up, cutie?", reply_markup=InlineKeyboardMarkup(button))

# ✅ Admin panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await update.message.reply_text("You’re not allowed.")
    
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

# ✅ Group Join Handler
async def handle_group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.new_chat_member.user.id == context.bot.id:
        save_known_chat(update.chat_member.chat.id)

# ✅ AI Chat
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.chat.id != OWNER_ID:
        forward_text = f"📩 From @{msg.from_user.username or msg.from_user.first_name}\n🆔 {msg.from_user.id}\n\n{msg.text}"
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(admin_id, forward_text)
            except: pass

    reply = await generate_reply(msg.text)
    await msg.reply_text(reply)

# ✅ Ban
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        await update.effective_chat.ban_member(update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User banned 🚫")

# ✅ Mute
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        await update.effective_chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("User muted 🔇")

# ✅ Unmute
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        await update.effective_chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=True)
        )
        await update.message.reply_text("User unmuted 🔊")

# ✅ Flask Webhook
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))
    app.add_handler(ChatMemberHandler(handle_group_join, ChatMemberHandler.MY_CHAT_MEMBER))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
                 )
