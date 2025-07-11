import os
import logging
import random
import httpx
from flask import Flask, request
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions, InputFile)
from telegram.constants import ChatAction
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
PORT = int(os.environ.get("PORT", 8080))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Telegram bot
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Admin list
ADMINS = set([OWNER_ID])

# Bot stats
reply_counter = 0

# AI models
OPENROUTER_MODELS = [
    "openchat/openchat-3.5-0106", "mistralai/mixtral-8x7b", "gryphe/mythomax-l2-13b",
    "openrouter/cinematika-7b", "nousresearch/nous-capybara-7b", "google/gemma-7b-it",
    "gryphe/mythomist-7b", "openrouter/chronos-hermes-13b", "openrouter/nous-hermes-2-mixtral",
    "mistralai/mistral-7b-instruct"
]

# Role
BOT_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent girl. You reply in short, human-like sentences like a real best friend."
}

# Keywords
GREETING_WORDS = ["hi", "hello", "hey", "sup", "yo", "heya", "hii", "hola"]
pic_keywords = ["cat", "dog", "flower", "girl", "boy", "nature", "car", "moon", "sun", "anime"]
random_replies = ["Hehe cute 💖", "Aww okay 😊", "Hmm tell me more", "Alright love 😇", "Gotcha! 😎",
                  "Done sweetie", "Haha that’s funny!", "No worries 😌", "Yep yep!", "I’m here always 💬"]
sent_messages = set()

# AI reply
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
            data = res.json()
            return data['choices'][0]['message']['content'].strip()
    except:
        return "Oops! Something went wrong."

# Image
async def get_image(query):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"https://api.unsplash.com/photos/random?query={query}&client_id=YOUR_UNSPLASH_API_KEY")
        data = res.json()
        return data['urls']['regular'] if 'urls' in data else None

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global reply_counter
    msg = update.message
    if not msg.text: return
    text = msg.text.lower()

    if any(word in text.split() for word in GREETING_WORDS):
        reply = random.choice([r for r in random_replies if r not in sent_messages])
        sent_messages.add(reply)
        if len(sent_messages) >= len(random_replies):
            sent_messages.clear()
        await msg.reply_text(reply)
        return

    for word in pic_keywords:
        if word in text:
            await msg.chat.send_action(ChatAction.UPLOAD_PHOTO)
            url = await get_image(word)
            if url:
                await msg.reply_photo(url)
            else:
                await msg.reply_text("Couldn't find pic 🥺")
            return

    reply = await ai_reply(msg.text)
    reply_counter += 1
    await msg.reply_text(reply[:300])

# Sticker
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_sticker(update.message.sticker.file_id)

# Photo
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cute pic 💖")

# Forwarding
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.id in ADMINS: return
    user = msg.from_user
    chat = msg.chat
    fwd_text = f"📨 From: @{user.username or user.first_name}\n👥 Chat: {chat.title or user.first_name}"
    if chat.type != 'private':
        fwd_text += f"\n🔗 Message: https://t.me/c/{str(chat.id)[4:]}/{msg.message_id}"
    for admin_id in ADMINS:
        try:
            await context.bot.forward_message(admin_id, chat.id, msg.message_id)
            await context.bot.send_message(admin_id, fwd_text)
        except: pass

# Admin commands
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        try:
            await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=False))
            await update.message.reply_text("User muted 🚫")
        except:
            await update.message.reply_text("I need admin rights 😢")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
            await update.message.reply_text("User kicked 🦶")
        except:
            await update.message.reply_text("I need admin rights 😢")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        try:
            await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id,
                                                  can_change_info=True, can_delete_messages=True, can_invite_users=True,
                                                  can_restrict_members=True, can_pin_messages=True)
            await update.message.reply_text("User promoted 👑")
        except:
            await update.message.reply_text("I need admin rights 😢")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        try:
            await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id,
                                                  can_change_info=False, can_delete_messages=False, can_invite_users=False,
                                                  can_restrict_members=False, can_pin_messages=False)
            await update.message.reply_text("User demoted 🔽")
        except:
            await update.message.reply_text("I need admin rights 😢")

# /admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: return
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 Admin List", callback_data="list_admins")],
            [InlineKeyboardButton("📊 Today Usage", callback_data="usage")]
        ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

# Callback handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "broadcast":
        await query.message.reply_text("Send message to broadcast:")
        context.user_data['awaiting_broadcast'] = True

    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send ID to add as admin:")
        context.user_data['awaiting_add_admin'] = True

    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send ID to remove from admin:")
        context.user_data['awaiting_remove_admin'] = True

    elif query.data == "list_admins" and user_id == OWNER_ID:
        text = "👑 Admins:\n" + "\n".join([f"{aid}" for aid in ADMINS])
        await query.message.reply_text(text)

    elif query.data == "usage" and user_id == OWNER_ID:
        await query.message.reply_text(f"Replies today: {reply_counter}")

# Handle follow-up replies
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if context.user_data.get("awaiting_broadcast"):
        for admin in ADMINS:
            try:
                await context.bot.send_message(admin, text)
            except: pass
        context.user_data.clear()
        return await update.message.reply_text("Broadcast sent ✅")

    if context.user_data.get("awaiting_add_admin"):
        try:
            ADMINS.add(int(text))
            context.user_data.clear()
            return await update.message.reply_text("Admin added ✅")
        except: pass

    if context.user_data.get("awaiting_remove_admin"):
        try:
            ADMINS.remove(int(text))
            context.user_data.clear()
            return await update.message.reply_text("Admin removed ✅")
        except: pass

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup.from_button(InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true"))
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=btn)

# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

# Handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("admin", admin_panel))
telegram_app.add_handler(CallbackQueryHandler(handle_callback))
telegram_app.add_handler(CommandHandler("mute", mute))
telegram_app.add_handler(CommandHandler("kick", kick))
telegram_app.add_handler(CommandHandler("promote", promote))
telegram_app.add_handler(CommandHandler("demote", demote))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
telegram_app.add_handler(MessageHandler(filters.ALL, forward_message))
telegram_app.add_handler(MessageHandler(filters.TEXT, handle_admin_input))

# Run
if __name__ == '__main__':
    telegram_app.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook"
)
