import os
import logging
import json
import httpx
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, ChatPermissions, MessageEntity
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters)

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
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        ADMINS = set(json.load(f))
else:
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

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 17-year-old super-intelligent, sharp-witted, and emotionally aware girl. You reply like a real human — smart, confident, flirty. Always use user's mood and reply in same language."
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
    return "My dev is fixing things 💫 Try again later."

# ✅ Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹 What's up, cutie?", reply_markup=InlineKeyboardMarkup(keyboard))

async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup"]:
        link = f"https://t.me/{update.effective_chat.username}/{update.message.message_id}" if update.effective_chat.username else "(no link)"
        for admin in ADMINS:
            try:
                await context.bot.send_message(admin, f"From group: {update.effective_chat.title}\nUser: @{update.effective_user.username}\nLink: {link}\nText: {update.message.text}")
            except: pass
    elif update.effective_chat.type == "private":
        for admin in ADMINS:
            try:
                await context.bot.forward_message(admin, update.effective_chat.id, update.message.message_id)
            except: pass
    if is_greeting(update.message.text):
        reply = await generate_reply(update.message.text)
        await update.message.reply_text(reply)

# ✅ Admin Panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return
    keyboard = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        keyboard += [[InlineKeyboardButton("➕ Add Admin", callback_data="addadmin"), InlineKeyboardButton("➖ Remove Admin", callback_data="removeadmin")]]
        keyboard += [[InlineKeyboardButton("📋 List Admins", callback_data="listadmins")]]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMINS: return

    if query.data == "broadcast":
        await query.message.reply_text("Send broadcast message:")
        context.user_data["mode"] = "broadcast"
    elif query.data == "addadmin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add as admin:")
        context.user_data["mode"] = "addadmin"
    elif query.data == "removeadmin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove:")
        context.user_data["mode"] = "removeadmin"
    elif query.data == "listadmins" and user_id == OWNER_ID:
        text = "👑 Admins List:\n"
        for uid in ADMINS:
            try:
                user = await context.bot.get_chat(uid)
                text += f"• {user.first_name} (@{user.username}) — `{uid}`\n"
            except:
                text += f"• `{uid}`\n"
        await query.message.reply_text(text, parse_mode="Markdown")

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode: return
    context.user_data["mode"] = None
    if mode == "broadcast":
        for cid in known_chats:
            try: await context.bot.send_message(cid, update.message.text)
            except: pass
    elif mode == "addadmin":
        ADMINS.add(int(update.message.text))
        save_admins()
        await update.message.reply_text("✅ Admin added.")
    elif mode == "removeadmin":
        ADMINS.discard(int(update.message.text))
        save_admins()
        await update.message.reply_text("❌ Admin removed.")

# ✅ Group Events
async def group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_known_chat(update.effective_chat.id)

# ✅ Promote/Demote/Mute
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS: return
    if not update.message.reply_to_message: return
    await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id,
        can_manage_chat=True, can_delete_messages=True, can_restrict_members=True, can_promote_members=True)
    await update.message.reply_text("✅ Promoted")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS: return
    if not update.message.reply_to_message: return
    await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id,
        can_manage_chat=False, can_delete_messages=False, can_restrict_members=False, can_promote_members=False)
    await update.message.reply_text("❌ Demoted")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS: return
    if not update.message.reply_to_message: return
    await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions())
    await update.message.reply_text("🔇 Muted")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS: return
    if not update.message.reply_to_message: return
    await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=True))
    await update.message.reply_text("🔊 Unmuted")

# ✅ Webhook start
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("demote", demote))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(MessageHandler(filters.ALL, forward_messages))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT, handle_reply))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.MY_CHAT_MEMBER, group_join))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
            )
