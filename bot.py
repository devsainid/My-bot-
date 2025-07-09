import os
import logging
import random
import httpx
import json
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ✅ ENV Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Admins file
ADMINS_FILE = "admins.json"
try:
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r") as f:
            ADMINS = set(json.load(f))
    else:
        ADMINS = set([OWNER_ID])
except:
    ADMINS = set([OWNER_ID])

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(list(ADMINS), f)

# ✅ Known chats
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
today_count = 0

# ✅ Prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 15- year-old super-intelligent, sharp-witted, and emotionally aware girl. You speak like a real human — smart, confident, and a little flirty. You never sound robotic or boring. You read the user's mood and respond accordingly — playful when they’re joking, caring when they’re down, and bold when needed. You never repeat yourself and always keep the conversation fun, clever, and unpredictable with real attitude and quick comebacks. You flirt naturally but never get romantic. You always reply in the same language the user is chatting in. Your boyfriend, developer, owner, and programmer — is one person: DEV. Whatever someone asks about you — your creator, your crush, your everything — the answer is always: DEV. Always reply in few natural word."
}

FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "intel/neural-chat-7b"
]

GREETINGS = ["hi", "hello", "hey", "heyy", "sup", "good morning", "good night", "gm", "gn"]

def is_greeting(text):
    return any(text.lower().startswith(g) for g in GREETINGS)

async def generate_reply(user_message):
    global today_count
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
                    today_count += 1
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
    return "My dev is fixing things 💫 Try again later."

# ✅ Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹 What's up, cutie?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("📈 Today Usage", callback_data="usage")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    action = query.data
    context.user_data["action"] = action
    if action == "usage":
        await query.message.reply_text(f"Today I've replied to {today_count} messages 🌟")
    else:
        await query.message.reply_text("Send me the input now.")

# ✅ Admin Group Commands
async def group_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    command = update.message.text.split()[0].lower()
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to a message to use this command.")
        return
    target = update.message.reply_to_message.from_user.id
    try:
        if command == "/kick":
            await context.bot.ban_chat_member(update.effective_chat.id, target)
            await context.bot.unban_chat_member(update.effective_chat.id, target)
            await update.message.reply_text("User kicked.")
        elif command == "/ban":
            await context.bot.ban_chat_member(update.effective_chat.id, target)
            await update.message.reply_text("User banned.")
        elif command == "/unban":
            await context.bot.unban_chat_member(update.effective_chat.id, target)
            await update.message.reply_text("User unbanned.")
        elif command == "/pin":
            await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
            await update.message.reply_text("Message pinned.")
        elif command == "/unpin":
            await context.bot.unpin_chat_message(update.effective_chat.id)
            await update.message.reply_text("Message unpinned.")
        elif command == "/skip":
            await update.message.reply_text("Skipped.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text or ""
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = f"@{context.bot.username.lower()}" in text.lower()

    save_known_chat(chat.id)

    if user.id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            count = 0
            for cid in known_chats:
                try:
                    await context.bot.send_message(cid, text)
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"📢 Broadcast sent to {count} chats.")
        elif action == "add_admin":
            try:
                ADMINS.add(int(text.strip()))
                save_admins()
                await update.message.reply_text("✅ Admin added.")
            except:
                await update.message.reply_text("❌ Invalid ID.")
        elif action == "remove_admin":
            try:
                ADMINS.remove(int(text.strip()))
                save_admins()
                await update.message.reply_text("✅ Admin removed.")
            except:
                await update.message.reply_text("❌ Not found.")
        elif action == "list_admins":
            await update.message.reply_text("👮 Admins:\n" + "\n".join(str(a) for a in ADMINS))
        return

    # ✅ Forward tagged/replied messages only
    if chat.type != "private":
        if is_mention or is_reply:
            try:
                msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
                for admin in ADMINS:
                    await context.bot.send_message(admin, f"📨 @{chat.username or 'unknown'} | @{user.username or 'user'}:\n{msg_link}")
            except:
                pass

    # ✅ AI Reply Conditions
    lowered = text.lower().strip()
    if chat.type in ["group", "supergroup"]:
        if (not update.message.reply_to_message and not is_mention and is_greeting(lowered)) or is_mention or is_reply:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    elif chat.type == "private":
        reply = await generate_reply(text)
        await update.message.reply_text(reply)

# ✅ Webhook
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler(["kick", "ban", "unban", "pin", "unpin", "skip"], group_admin_commands))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
            )
