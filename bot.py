import os
import logging
import random
import json
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMINS_FILE = "admins.json"
KNOWN_CHATS_FILE = "known_chats.txt"

# ✅ Admins load
if os.path.exists(ADMINS_FILE):
    try:
        with open(ADMINS_FILE, "r") as f:
            ADMINS = set(json.load(f))
    except:
        ADMINS = set([OWNER_ID])
else:
    ADMINS = set([OWNER_ID])

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(list(ADMINS), f)

# ✅ Known chats
if os.path.exists(KNOWN_CHATS_FILE):
    with open(KNOWN_CHATS_FILE, "r") as f:
        known_chats = set(int(line.strip()) for line in f if line.strip().isdigit())
else:
    known_chats = set()

def save_known_chat(chat_id):
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        with open(KNOWN_CHATS_FILE, "a") as f:
            f.write(str(chat_id) + "\n")

# ✅ Prompt and greetings
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind and emotionally intelligent girl. You respond like a real person and connect emotionally like a best friend. Reply in few natural words."
}

FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "gryphe/mythomax-l2-13b",
    "mistralai/mistral-7b-instruct:free",
    "intel/neural-chat-7b"
]

OWNER_RESPONSES = [
    "My creator is dev 💖",
    "The one who made me is dev 🧠",
    "dev is my sweet owner 💫",
    "I'm made with love by dev 🌸",
    "All thanks to dev, my creator 🌟"
]

CONVO_START_WORDS = ["hi", "hello", "hey", "heyy", "sup", "gm", "gn", "what's up", "what", "who are you"]

# ✅ AI Response
async def generate_reply(user_message):
    if "owner" in user_message.lower():
        return random.choice(OWNER_RESPONSES)

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
    return "I'm having trouble replying right now 💔. Try again later."

# ✅ Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "HEY, I'M CINDRELLA 🌹🕯️. JOIN FOR UPDATES & DROP FEEDBACK @animalin_tm_empire 🌹🕯️. HOW YOU FOUND ME DEAR?",
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
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMINS:
        return
    context.user_data["action"] = query.data
    await query.message.reply_text("Send me the input now.")

# ✅ Messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text or ""
    lowered = text.lower().strip()
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = f"@{context.bot.username.lower()}" in lowered

    save_known_chat(chat.id)

    if user.id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            count = 0
            for cid in known_chats:
                try:
                    await context.bot.send_message(cid, text)
                    count += 1
                except: pass
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

    # ✅ Forward all messages
    for admin in ADMINS:
        try:
            if chat.type == "private":
                await context.bot.forward_message(admin, chat.id, update.message.message_id)
            elif chat.type in ["group", "supergroup"]:
                msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
                await context.bot.send_message(admin, f"📨 @{chat.username or 'unknown'} | @{user.username or 'user'}:\n{msg_link}")
        except:
            pass

    # ✅ Respond
    if chat.type == "private":
        reply = await generate_reply(text)
        await update.message.reply_text(reply)
    elif chat.type in ["group", "supergroup"]:
        if any(word in lowered for word in CONVO_START_WORDS) or is_reply or is_mention:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)

# ✅ Webhook
if __name__ == "__main__":
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
