import os
import logging
import json
import httpx
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, ChatPermissions
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
    "content": "You are CINDRELLA, a 17-year-old super-intelligent, sharp-witted, and emotionally aware girl. You reply like a real human — smart, confident, and a little flirty. You read the user's mood and respond accordingly — playful, bold, or caring. Keep replies short, natural, and unpredictable. You never sound robotic, never repeat yourself, and avoid using long messages. Only mention your owner, DEV, when someone directly asks about your creator, owner, programmer, or boyfriend. You always reply in the same language the user uses."
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

async def handle_group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.new_chat_member.status in ["member", "administrator"]:
        save_known_chat(update.effective_chat.id)

# ✅ Admin Panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await update.message.reply_text("You are not authorized to use this panel.")

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [[
            InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")
        ], [
            InlineKeyboardButton("📋 List Admins", callback_data="list_admins")
        ]]

    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text("Send your broadcast message now ✉️")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin ➕")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admins ➖")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text("👑 Admins:\n" + "\n".join(map(str, ADMINS)))

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")
    if not action:
        return
    user_id = update.effective_user.id
    target = update.message.text.strip()

    if action == "broadcast" and user_id in ADMINS:
        for cid in known_chats:
            try:
                await context.bot.send_message(cid, target)
            except:
                pass
        await update.message.reply_text("Broadcast sent 💌")
    elif action == "add_admin" and user_id == OWNER_ID:
        ADMINS.add(int(target))
        save_admins()
        await update.message.reply_text(f"Added {target} as admin ✅")
    elif action == "remove_admin" and user_id == OWNER_ID:
        ADMINS.discard(int(target))
        save_admins()
        await update.message.reply_text(f"Removed {target} from admins ✅")
    context.user_data.clear()

# ✅ Message Forwarding
async def forward_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or "<no text>"
    chat = update.effective_chat
    link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if str(chat.id).startswith("-100") else ""
    forward_text = f"📥 From: @{user.username or user.first_name} ({user.id})\n📍 Chat: {chat.title or 'Private'}\n🔗 {link}\n\n{text}"
    for admin in ADMINS:
        try:
            await context.bot.send_message(admin, forward_text)
        except:
            pass

# ✅ AI Replies
async def reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    if is_greeting(update.message.text or "") or update.message.chat.type != "private":
        await update.message.chat.send_action(action=ChatAction.TYPING)
        reply = await generate_reply(update.message.text)
        await update.message.reply_text(reply)

# ✅ Ban, Mute Commands
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    if update.message.reply_to_message:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
            await update.message.reply_text("User banned ❌")
        except:
            await update.message.reply_text("Ban failed ❌")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    if update.message.reply_to_message:
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                update.message.reply_to_message.from_user.id,
                ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text("User muted 🔇")
        except:
            await update.message.reply_text("Mute failed ❌")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    if update.message.reply_to_message:
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                update.message.reply_to_message.from_user.id,
                ChatPermissions(can_send_messages=True)
            )
            await update.message.reply_text("User unmuted 🔊")
        except:
            await update.message.reply_text("Unmute failed ❌")

# ✅ Main
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_actions))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_message))
    app.add_handler(MessageHandler(filters.ALL, forward_to_owner))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatMemberUpdated.ALL, handle_group_join))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
)
