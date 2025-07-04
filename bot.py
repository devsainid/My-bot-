import os import logging import requests from flask import Flask, request from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import ( Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, AIORateLimiter )

ENV

BOT_TOKEN = os.getenv("BOT_TOKEN") OWNER_ID = int(os.getenv("OWNER_ID")) OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") WEBHOOK_URL = os.getenv("WEBHOOK_URL")

Logging

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

App

app = Flask(name)

Admins

admins = set([OWNER_ID])

Application

bot = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

System prompt

system_prompt = { "role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend." }

AI

async def ask_openrouter(message: str) -> str: headers = { "Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json" } payload = { "model": "openchat/openchat-3.5", "messages": [system_prompt, {"role": "user", "content": message}] } response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers) return response.json()['choices'][0]['message']['content']

/start

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Hey! I'm CINDRELLA 🌹🕯️. add me in your group to more informative chats👩‍🦰👩‍🦰. how can i assist you today 🌹🕯️")

/admin

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id if user_id not in admins: return await update.message.reply_text("You are not authorized.")

keyboard = [
    [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
]
if user_id == OWNER_ID:
    keyboard.extend([
        [
            InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")
        ],
        [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
    ])
await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))

Button callbacks

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() user_id = query.from_user.id

if query.data == "broadcast":
    if user_id in admins:
        context.user_data['awaiting_broadcast'] = True
        await query.message.reply_text("Send message to broadcast:")
elif query.data == "add_admin" and user_id == OWNER_ID:
    context.user_data['awaiting_add_admin'] = True
    await query.message.reply_text("Send user ID to add as admin:")
elif query.data == "remove_admin" and user_id == OWNER_ID:
    context.user_data['awaiting_remove_admin'] = True
    await query.message.reply_text("Send user ID to remove:")
elif query.data == "list_admins" and user_id == OWNER_ID:
    admin_list = '\n'.join([str(a) for a in admins])
    await query.message.reply_text(f"Admins:\n{admin_list}")

Broadcast and admin updates

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id text = update.message.text

if context.user_data.get('awaiting_broadcast'):
    context.user_data['awaiting_broadcast'] = False
    for chat in context.bot_data.get("chats", set()):
        try:
            await context.bot.send_message(chat_id=chat, text=text)
        except:
            continue
    return await update.message.reply_text("Broadcast sent!")

if context.user_data.get('awaiting_add_admin'):
    context.user_data['awaiting_add_admin'] = False
    try:
        new_admin = int(text)
        admins.add(new_admin)
        return await update.message.reply_text(f"Added admin: {new_admin}")
    except:
        return await update.message.reply_text("Invalid ID")

if context.user_data.get('awaiting_remove_admin'):
    context.user_data['awaiting_remove_admin'] = False
    try:
        rm_admin = int(text)
        admins.discard(rm_admin)
        return await update.message.reply_text(f"Removed admin: {rm_admin}")
    except:
        return await update.message.reply_text("Invalid ID")

reply = await ask_openrouter(text)
await update.message.reply_text(reply)

# Forward message
for admin_id in admins:
    try:
        await context.bot.copy_message(chat_id=admin_id, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except:
        continue

# Save chat
chats = context.bot_data.setdefault("chats", set())
chats.add(update.effective_chat.id)

Webhook

@app.route('/', methods=['POST']) def webhook(): update = Update.de_json(request.get_json(force=True), bot.bot) bot.update_queue.put_nowait(update) return 'ok'

@app.route('/', methods=['GET', 'HEAD']) def index(): return 'Bot is alive!'

Run

if name == 'main': import asyncio asyncio.run(bot.initialize()) bot.add_handler(CommandHandler('start', start)) bot.add_handler(CommandHandler('admin', admin)) bot.add_handler(CallbackQueryHandler(button_handler)) bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input)) bot.run_webhook(listen="0.0.0.0", port=10000, webhook_url=WEBHOOK_URL)
