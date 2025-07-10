import os
import logging
import json
import httpx
from flask import Flask, request
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
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
ADMINS = set([OWNER_ID])
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        ADMINS.update(json.load(f))

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(list(ADMINS), f)

# ✅ Known chats
KNOWN_CHATS_FILE = "known_chats.txt"
known_chats = set()
if os.path.exists(KNOWN_CHATS_FILE):
    with open(KNOWN_CHATS_FILE, "r") as f:
        known_chats = set(map(int, f.read().splitlines()))

def save_known_chat(chat_id):
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        with open(KNOWN_CHATS_FILE, "a") as f:
            f.write(str(chat_id) + "\n")

# ✅ Models
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

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 17-year-old super-intelligent, sharp-witted, and emotionally aware girl. You reply like a real human — smart, confident, and a little flirty. Keep replies short, natural, and emotionally intelligent."
}

today_count = 0
GREETINGS = ["hi", "hello", "hey", "gm", "gn", "sup"]

def is_greeting(text):
    return any(text.lower().startswith(g) for g in GREETINGS)

async def generate_reply(text):
    global today_count
    for model in FREE_MODELS:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
                        "X-Title": "CINDRELLA"
                    },
                    json={"model": model, "messages": [SYSTEM_PROMPT, {"role": "user", "content": text}]}
                )
                if "choices" in res.json():
                    today_count += 1
                    return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
    return "My dev is fixing it 💫 Try again later."

# ✅ Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    btn = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹 What's up, cutie?", reply_markup=InlineKeyboardMarkup(btn))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("👥 Total Users", callback_data="usage")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    if uid not in ADMINS:
        return
    action = query.data
    context.user_data["action"] = action
    if action == "usage":
        await query.message.reply_text(f"Total users: {len(known_chats)}\nToday's replies: {today_count}")
    else:
        await query.message.reply_text("Send the input now.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text or ""
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
                await update.message.reply_text("❌ Invalid ID")
        elif action == "remove_admin":
            try:
                ADMINS.remove(int(text.strip()))
                save_admins()
                await update.message.reply_text("✅ Admin removed.")
            except:
                await update.message.reply_text("❌ ID not found")
        elif action == "list_admins":
            msg = "👮 Admins:\n" + "\n".join([f"{a}" for a in ADMINS])
            await update.message.reply_text(msg)
        return

    if chat.type == "private":
        reply = await generate_reply(text)
        await update.message.reply_text(reply)
    elif chat.type in ["group", "supergroup"]:
        if is_greeting(text) or update.message.reply_to_message:
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)

async def group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.chat_member
    if member.new_chat_member.status in ["member", "administrator"]:
        save_known_chat(member.chat.id)

async def manage_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    command = update.message.text.lower().split()[0]
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to use this command.")
        return
    user_id = update.message.reply_to_message.from_user.id
    try:
        if command == "/ban":
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text("Banned ✅")
        elif command == "/unban":
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text("Unbanned ✅")
        elif command == "/kick":
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text("Kicked ✅")
        elif command == "/mute":
            await context.bot.restrict_chat_member(update.effective_chat.id, user_id, ChatPermissions())
            await update.message.reply_text("Muted ✅")
        elif command == "/unmute":
            await context.bot.restrict_chat_member(update.effective_chat.id, user_id, ChatPermissions(can_send_messages=True))
            await update.message.reply_text("Unmuted ✅")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ✅ Webhook
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler(["ban", "unban", "kick", "mute", "unmute"], manage_group))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ChatMemberUpdated.ALL, group_join))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
        )
