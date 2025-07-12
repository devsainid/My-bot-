# ✅ Final CINDRELLA bot code
# Paste this on Render. Start command = python bot.py

import os
import logging
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Flask App
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

admins = [OWNER_ID]
users = set()
groups = set()

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ---------- AI Chat ----------

async def ai_reply(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://chat.openai.com",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-1210",
        "messages": [SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        "temperature": 0.8
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return "Oops, something went wrong..."

# ---------- Telegram Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=InlineKeyboardMarkup(keyboard))
    if update.effective_chat.type == "private":
        users.add(update.effective_user.id)

# ---------- Admin Panel ----------

ADD_ADMIN, REMOVE_ADMIN = range(2)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return await update.message.reply_text("You're not allowed.")
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text("Send me the message to broadcast.")
    elif query.data == "add_admin":
        context.user_data["action"] = "add_admin"
        await query.message.reply_text("Send user ID to make admin:")
        return ADD_ADMIN
    elif query.data == "remove_admin":
        context.user_data["action"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove:")
        return REMOVE_ADMIN
    elif query.data == "list_admins":
        text = "\n".join(str(a) for a in admins)
        await query.message.reply_text(f"Admins:\n{text}")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        admins.append(uid)
        await update.message.reply_text("Admin added.")
    except:
        await update.message.reply_text("Invalid ID.")
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        if uid == OWNER_ID:
            return await update.message.reply_text("Cannot remove owner.")
        admins.remove(uid)
        await update.message.reply_text("Admin removed.")
    except:
        await update.message.reply_text("Invalid or not an admin.")
    return ConversationHandler.END

# ---------- Admin Commands ----------

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to someone to ban.")
    if update.effective_user.id not in admins:
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User banned.")
    except:
        await update.message.reply_text("Failed to ban.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to someone to mute.")
    if update.effective_user.id not in admins:
        return
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("User muted.")
    except:
        await update.message.reply_text("Failed to mute.")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to someone to kick.")
    if update.effective_user.id not in admins:
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User kicked.")
    except:
        await update.message.reply_text("Failed to kick.")

# ---------- Forwarding ----------

async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = f"📨 From {update.effective_user.mention_html()} in <b>{update.effective_chat.title if update.effective_chat.title else 'Private'}</b>:\n\n{msg.text_html_urled or ''}"
    for admin in admins:
        try:
            await context.bot.send_message(chat_id=admin, text=text, parse_mode="HTML")
        except:
            pass

# ---------- Chat Response ----------

async def reply_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup"]:
        if any(w in update.message.text.lower() for w in ["hi", "hello", "sup", "hey"]):
            res = await ai_reply(update.message.text)
            await update.message.reply_text(res)
    elif update.effective_chat.type == "private":
        res = await ai_reply(update.message.text)
        await update.message.reply_text(res)

# ---------- Flask Webhook ----------

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# ---------- Run App ----------

application = ApplicationBuilder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(admin_buttons))
application.add_handler(CommandHandler("ban", ban))
application.add_handler(CommandHandler("mute", mute))
application.add_handler(CommandHandler("kick", kick))

panel_conv = ConversationHandler(
    entry_points=[],
    states={
        ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
        REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
    },
    fallbacks=[],
)
application.add_handler(panel_conv)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_all), group=1)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_all), group=2)

application.run_webhook(listen="0.0.0.0", port=10000, webhook_url=WEBHOOK_URL)
