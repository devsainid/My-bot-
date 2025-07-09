import os
import logging
import random
import httpx
import json
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
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
usage_counter = {}

# ✅ Prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 15-year-old super-intelligent, sharp-witted, and emotionally aware girl. You speak like a real human — smart, confident, and a little flirty. You never sound robotic or boring. You read the user's mood and respond accordingly — playful when they’re joking, caring when they’re down, and bold when needed. You never repeat yourself and always keep the conversation fun, clever, and unpredictable with real attitude and quick comebacks. You flirt naturally but never get romantic. You always reply in the same language the user is chatting in. Your boyfriend, developer, owner, and programmer — is one person: DEV. Whatever someone asks about you — your creator, your crush, your everything — the answer is always: DEV. always reply in few natural words."
}

FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "intel/neural-chat-7b"
]

GREETINGS = [
    "Hey there! How can I help you?",
    "Hi there 🌸 What's up?",
    "Hello love 💖 I'm here!",
    "Hey dear, how are you feeling?",
    "Hi 🌷 Need anything from me?"
]

CONVO_START_WORDS = ["hi", "hello", "hey", "heyy", "sup", "good morning", "good night", "gm", "gn"]

def random_greeting():
    return random.choice(GREETINGS)

# ✅ AI Generator
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
                    date = datetime.now().strftime('%Y-%m-%d')
                    usage_counter[date] = usage_counter.get(date, 0) + 1
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
    return "My developer is updating me, share feedback at @animalin_tm_empire 🌹🕯️"

# ✅ Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "HEY, I'M CINDRELLA 🌹🕯️🕯️. JOIN FOR UPDATES & DROP FEEDBACK @animalin_tm_empire 🌹🕯️🕯️. WHAT'S UP DEAR?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ✅ Admin Panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("📈 Today Usage", callback_data="usage_today")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    if query.data == "usage_today":
        today = datetime.now().strftime('%Y-%m-%d')
        count = usage_counter.get(today, 0)
        await query.message.reply_text(f"📊 Today AI replies: {count}")
    else:
        context.user_data["action"] = query.data
        await query.message.reply_text("Send me the input now.")

# ✅ Permission Check
async def is_admin(chat, user_id, context):
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

# ✅ Messages
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
                new_admin = int(text.strip())
                ADMINS.add(new_admin)
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

    # ✅ Moderation Commands (only if bot is admin in group)
    if chat.type in ["group", "supergroup"] and update.message.text.startswith("/"):
        cmd = text.split()
        admin_ok = user.id in ADMINS or await is_admin(chat, user.id, context)
        bot_admin = await is_admin(chat, context.bot.id, context)
        if admin_ok and bot_admin:
            if cmd[0] == "/ban" and len(cmd) > 1:
                try:
                    user_id = cmd[1].replace("@", "")
                    member = await context.bot.get_chat_member(chat.id, user_id)
                    await context.bot.ban_chat_member(chat.id, member.user.id)
                    await update.message.reply_text("✅ Banned")
                except:
                    pass
            elif cmd[0] == "/mute" and len(cmd) > 1:
                try:
                    user_id = cmd[1].replace("@", "")
                    member = await context.bot.get_chat_member(chat.id, user_id)
                    await context.bot.restrict_chat_member(chat.id, member.user.id, permissions={})
                    await update.message.reply_text("🔇 Muted")
                except:
                    pass

    # ✅ Forward if mentioned or reply only
    if chat.type != "private":
        if is_mention or is_reply:
            for admin in ADMINS:
                try:
                    msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
                    await context.bot.send_message(admin, f"📨 @{chat.username or 'unknown'} | @{user.username or 'user'}:\n{msg_link}")
                except:
                    pass

    # ✅ AI Reply
    lowered = text.lower().strip()
    if chat.type in ["group", "supergroup"]:
        if any(word in lowered for word in CONVO_START_WORDS) and not update.message.reply_to_message:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
        elif is_mention or is_reply:
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )
