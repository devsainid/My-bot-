import os
import logging
import random
import httpx
import telegram
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatAction
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ContextTypes, ConversationHandler, filters)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
PORT = int(os.environ.get("PORT", 8080))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

ADMINS = set([OWNER_ID])
OPENROUTER_MODELS = [
    "openchat/openchat-3.5-0106", "mistralai/mixtral-8x7b", "gryphe/mythomax-l2-13b",
    "openrouter/cinematika-7b", "nousresearch/nous-capybara-7b", "google/gemma-7b-it",
    "gryphe/mythomist-7b", "openrouter/chronos-hermes-13b", "openrouter/nous-hermes-2-mixtral",
    "mistralai/mistral-7b-instruct"
]

BOT_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent girl. You reply like a real best friend in short, human-like sentences."
}

random_replies = [
    "Hehe cute 💖", "Aww okay 😊", "Hmm tell me more", "Alright love 😇", "Gotcha! 😎",
    "Done sweetie", "Haha that’s funny!", "No worries 😌", "Yep yep!", "I’m here always 💬"
]
sent_messages = set()
GREETING_WORDS = ["hi", "hello", "hey", "sup", "yo", "heya", "hii", "hola"]
pic_keywords = ["cat", "dog", "flower", "girl", "boy", "nature", "car", "moon", "sun", "anime"]
message_counter = 0

# AI Reply
async def ai_reply(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "Content-Type": "application/json"
    }
    payload = {
        "model": random.choice(OPENROUTER_MODELS),
        "messages": [BOT_SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
            return res.json()['choices'][0]['message']['content'].strip()
    except:
        return "Oops! Something went wrong."

async def get_image(query):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.unsplash.com/photos/random?query={query}&client_id=YOUR_UNSPLASH_API_KEY")
        d = r.json()
        return d['urls']['regular'] if 'urls' in d else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global message_counter
    msg = update.message
    text = msg.text.lower() if msg.text else ""
    if any(word in text.split() for word in GREETING_WORDS):
        reply = random.choice([r for r in random_replies if r not in sent_messages])
        sent_messages.add(reply)
        if len(sent_messages) >= len(random_replies):
            sent_messages.clear()
        await msg.reply_text(reply)
        message_counter += 1
        return
    for word in pic_keywords:
        if word in text:
            await msg.chat.send_action(ChatAction.UPLOAD_PHOTO)
            img_url = await get_image(word)
            if img_url:
                await msg.reply_photo(img_url)
            else:
                await msg.reply_text("Couldn't find pic 🥺")
            message_counter += 1
            return
    reply = await ai_reply(msg.text)
    await msg.reply_text(reply[:300])
    message_counter += 1

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.id == OWNER_ID: return
    info = f"📨 From: @{msg.from_user.username or msg.from_user.first_name}\n👥 Chat: {msg.chat.title or msg.from_user.first_name}"
    if msg.chat.type != 'private':
        info += f"\n🔗 https://t.me/c/{str(msg.chat.id)[4:]}/{msg.message_id}"
    for admin in ADMINS:
        try:
            await context.bot.forward_message(admin, msg.chat.id, msg.message_id)
            await context.bot.send_message(admin, info)
        except: pass

# Admin Commands
async def mute(update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"Muted {user.first_name} 🚫")

async def kick(update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"Kicked {user.first_name} 🦶")

async def promote(update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_change_info=True, can_delete_messages=True, can_invite_users=True, can_restrict_members=True, can_pin_messages=True)
        await update.message.reply_text(f"Promoted {user.first_name} 👑")

async def demote(update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_change_info=False, can_delete_messages=False, can_invite_users=False, can_restrict_members=False, can_pin_messages=False)
        await update.message.reply_text(f"Demoted {user.first_name} 🔽")

# Admin Panel (/admin)
ADMIN_WAITING = {}

async def admin_panel(update, context):
    uid = update.effective_user.id
    if uid not in ADMINS: return
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data='broadcast')],
    ]
    if uid == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data='add_admin')],
            [InlineKeyboardButton("➖ Remove Admin", callback_data='remove_admin')],
            [InlineKeyboardButton("📋 List Admins", callback_data='list_admins')],
            [InlineKeyboardButton("📊 Today Usage", callback_data='usage')]
        ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

async def admin_callback(update, context):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    if query.data == 'broadcast':
        ADMIN_WAITING[uid] = 'broadcast'
        await query.message.reply_text("Send the message to broadcast:")
    elif query.data == 'add_admin':
        ADMIN_WAITING[uid] = 'add_admin'
        await query.message.reply_text("Send ID to add as admin:")
    elif query.data == 'remove_admin':
        ADMIN_WAITING[uid] = 'remove_admin'
        await query.message.reply_text("Send ID to remove from admins:")
    elif query.data == 'list_admins':
        msg = "👑 Admins:\n" + "\n".join([f"`{aid}` - @{(await context.bot.get_chat(aid)).username}" for aid in ADMINS])
        await query.message.reply_text(msg, parse_mode='Markdown')
    elif query.data == 'usage':
        await query.message.reply_text(f"🤖 Messages handled today: {message_counter}")

async def admin_response(update, context):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if uid in ADMIN_WAITING:
        action = ADMIN_WAITING.pop(uid)
        if action == 'broadcast':
            for admin in ADMINS:
                try: await context.bot.send_message(admin, text)
                except: pass
            await update.message.reply_text("✅ Broadcast sent.")
        elif action == 'add_admin':
            ADMINS.add(int(text))
            await update.message.reply_text("✅ Admin added.")
        elif action == 'remove_admin':
            ADMINS.discard(int(text))
            await update.message.reply_text("✅ Admin removed.")

# Flask Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

# Handlers
telegram_app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?")))
telegram_app.add_handler(CommandHandler("admin", admin_panel))
telegram_app.add_handler(CallbackQueryHandler(admin_callback))
telegram_app.add_handler(CommandHandler("mute", mute))
telegram_app.add_handler(CommandHandler("kick", kick))
telegram_app.add_handler(CommandHandler("promote", promote))
telegram_app.add_handler(CommandHandler("demote", demote))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(MessageHandler(filters.TEXT, admin_response))
telegram_app.add_handler(MessageHandler(filters.ALL, forward_message))

# Start bot
if __name__ == '__main__':
    telegram_app.run_webhook(listen='0.0.0.0', port=PORT, webhook_url=f"{WEBHOOK_URL}/webhook")
