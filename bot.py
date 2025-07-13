import os
import logging
import json
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ChatMemberHandler, Application
)
from telegram.ext._application import RequestHandler

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# Admins
admins = set([OWNER_ID])

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Personality Prompt
system_prompt = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# Greeting keywords
greetings = ["hi", "hello", "hey", "sup", "heya", "yo"]

# AI Reply
async def ai_reply(text):
    try:
        res = await httpx.AsyncClient().post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": [system_prompt, {"role": "user", "content": text}]
            },
            timeout=15
        )
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("AI reply error:", e)
        return "I'm having a little trouble replying right now. Try again later."

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]
    ])
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=kb)

# /admin
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return await update.message.reply_text("You are not allowed here.")
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="addadmin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="removeadmin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="listadmins")]
        ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(buttons))

# Callback
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "broadcast":
        context.user_data['action'] = 'broadcast'
        await query.message.reply_text("Send the message to broadcast.")
    elif query.data == "addadmin":
        context.user_data['action'] = 'addadmin'
        await query.message.reply_text("Send user ID to add as admin.")
    elif query.data == "removeadmin":
        context.user_data['action'] = 'removeadmin'
        await query.message.reply_text("Send user ID to remove from admins.")
    elif query.data == "listadmins":
        await query.message.reply_text("Admins: " + ', '.join(map(str, admins)))

# Text messages
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.effective_user.id

    if user_id in admins and 'action' in context.user_data:
        action = context.user_data.pop('action')
        if action == 'broadcast':
            for chat_id in context.bot_data.get('all_chats', set()):
                try:
                    await context.bot.send_message(chat_id, update.message.text)
                except:
                    continue
            return await update.message.reply_text("Broadcast sent.")
        elif action == 'addadmin':
            try:
                admins.add(int(text))
                return await update.message.reply_text("Admin added.")
            except:
                return await update.message.reply_text("Invalid ID.")
        elif action == 'removeadmin':
            try:
                admins.discard(int(text))
                return await update.message.reply_text("Admin removed.")
            except:
                return await update.message.reply_text("Invalid ID.")

    if 'all_chats' not in context.bot_data:
        context.bot_data['all_chats'] = set()
    context.bot_data['all_chats'].add(update.effective_chat.id)

    if any(x in text for x in ["pic", "photo", "image"]):
        await update.message.reply_photo("https://picsum.photos/300/400")
        return

    if any(greet in text for greet in greetings) or context.bot.username.lower() in text:
        reply = await ai_reply(update.message.text)
        await update.message.reply_text(reply)

# Stickers
async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("That's a cute sticker 💖")

# Forward all
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text or msg.caption or ""
    if msg.chat.type in ["group", "supergroup"]:
        link = f"https://t.me/c/{str(msg.chat.id)[4:]}/{msg.message_id}" if str(msg.chat.id).startswith("-100") else None
        info = f"From Group: {msg.chat.title}\nUser: {msg.from_user.first_name} (@{msg.from_user.username})\nMsg: {text}"
    else:
        link = None
        info = f"From Private: {msg.from_user.first_name} (@{msg.from_user.username})\nMsg: {text}"
    for admin in admins:
        try:
            await context.bot.send_message(admin, info + (f"\n🔗 {link}" if link else ""))
        except:
            pass

# Admin check
async def is_admin(update):
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return member.status in ["administrator", "creator"] or update.effective_user.id in admins
    except:
        return False

# Group moderation
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User kicked.")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User banned.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        await context.bot.unban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User unbanned.")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("Message pinned.")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    await context.bot.unpin_all_chat_messages(update.effective_chat.id)
    await update.message.reply_text("All messages unpinned.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.promote_chat_member(
            update.effective_chat.id, user_id,
            can_change_info=True, can_delete_messages=True, can_invite_users=True,
            can_restrict_members=True, can_pin_messages=True, can_promote_members=False
        )
        await update.message.reply_text("User promoted.")

# Welcome
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.new_chat_member.status in ["member", "administrator"]:
        user = update.chat_member.new_chat_member.user
        await context.bot.send_message(update.chat_member.chat.id, f"🌸 Welcome {user.first_name} to {update.chat_member.chat.title}! 🌸")

# ✅ Flask App + Webhook route
flask_app = Flask(__name__)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

@flask_app.route("/webhook", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok", 200

# ✅ Register handlers
telegram_app.add_handler(CommandHandler('start', start))
telegram_app.add_handler(CommandHandler('admin', admin_panel))
telegram_app.add_handler(CallbackQueryHandler(admin_buttons))
telegram_app.add_handler(CommandHandler('kick', kick))
telegram_app.add_handler(CommandHandler('ban', ban))
telegram_app.add_handler(CommandHandler('unban', unban))
telegram_app.add_handler(CommandHandler('pin', pin))
telegram_app.add_handler(CommandHandler('unpin', unpin))
telegram_app.add_handler(CommandHandler('promote', promote))
telegram_app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
telegram_app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))

# ✅ Start app
if __name__ == '__main__':
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL + "/webhook"
    )
    flask_app.run(host="0.0.0.0", port=PORT)
