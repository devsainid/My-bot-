import os
import logging
import json
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

admins = set([OWNER_ID])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

system_prompt = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

greetings = ["hi", "hello", "hey", "sup", "heya", "yo"]

async def ai_reply(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openchat/openchat-3.5",
        "messages": [system_prompt, {"role": "user", "content": text}]
    }
    res = httpx.post(url, headers=headers, json=data)
    try:
        return res.json()["choices"][0]["message"]["content"].strip()
    except:
        return "I'm having a little trouble replying right now. Try again later."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to your group", url="https://t.me/" + context.bot.username + "?startgroup=true")]
    ])
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=kb)

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

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.effective_user.id

    # Admin actions
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

    # Save chat
    if 'all_chats' not in context.bot_data:
        context.bot_data['all_chats'] = set()
    context.bot_data['all_chats'].add(update.effective_chat.id)

    # Picture & sticker
    if any(x in text for x in ["pic", "photo", "image"]):
        await update.message.reply_photo("https://picsum.photos/300/400")
        return

    # Greet or mention
    if any(greet in text for greet in greetings) or context.bot.username.lower() in text:
        reply = await ai_reply(update.message.text)
        await update.message.reply_text(reply)

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("That's a cute sticker 💖")

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

# Moderation commands
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user to kick.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("User kicked.")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user to ban.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("User banned.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user to unban.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("User unbanned.")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to pin.")
    await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
    await update.message.reply_text("Message pinned.")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    await context.bot.unpin_all_chat_messages(update.effective_chat.id)
    await update.message.reply_text("All messages unpinned.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user to promote.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.promote_chat_member(
        update.effective_chat.id,
        user_id,
        can_change_info=True,
        can_delete_messages=True,
        can_invite_users=True,
        can_restrict_members=True,
        can_pin_messages=True,
        can_promote_members=False
    )
    await update.message.reply_text("User promoted.")

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return 'ok'

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CallbackQueryHandler(admin_buttons))
    application.add_handler(CommandHandler('kick', kick))
    application.add_handler(CommandHandler('ban', ban))
    application.add_handler(CommandHandler('unban', unban))
    application.add_handler(CommandHandler('pin', pin))
    application.add_handler(CommandHandler('unpin', unpin))
    application.add_handler(CommandHandler('promote', promote))
    application.add_handler(MessageHandler(filters.ALL, forward_all))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 10000)),
        webhook_url=WEBHOOK_URL + "/webhook"
    )
