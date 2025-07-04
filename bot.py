import os
import asyncio
import logging
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, AIORateLimiter
)

# Basic Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

admins = [OWNER_ID]
users = set()
group_ids = set()

# App + Bot setup
app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

# Start Command
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")
    ]])
    msg = "Hey, I'm CINDRELLA 🌹🕯. How you found me dear 🌹🕯️..?"
    await update.message.reply_text(msg, reply_markup=keyboard)

# AI Chat Handler
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if update.message.chat.type in ['group', 'supergroup']:
        group_ids.add(chat_id)
    else:
        users.add(chat_id)

    # Forward to admins
    for admin_id in admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 From: @{update.effective_user.username or user_id}\n🗨️: {text}"
            )
        except:
            pass

    # OpenRouter AI response
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "openchat/openchat-3.5-0106",
            "messages": [
                {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
                {"role": "user", "content": text}
            ]
        }
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        reply = res.json()["choices"][0]["message"]["content"]
        await update.message.reply_text(reply[:4000])
    except Exception as e:
        await update.message.reply_text("Oops! I'm having a sleepy moment 💤")

# Webhook endpoint
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.update_queue.put_nowait(update)
    return "ok"

@app.route("/", methods=["GET"])
def root():
    return "Running."

# Admin Panel Setup
admin_buttons = InlineKeyboardMarkup([
    [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
    [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
     InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
    [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
])

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admins:
        await update.message.reply_text("👑 Admin Panel", reply_markup=admin_buttons)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in admins:
        await query.edit_message_text("❌ You are not allowed.")
        return

    data = query.data
    if data == "broadcast":
        context.user_data["admin_action"] = "broadcast"
        await query.edit_message_text("📨 Send me the message to broadcast:")
    elif data == "add_admin":
        context.user_data["admin_action"] = "add_admin"
        await query.edit_message_text("➕ Send ID to add as admin:")
    elif data == "remove_admin":
        context.user_data["admin_action"] = "remove_admin"
        await query.edit_message_text("➖ Send ID to remove from admin:")
    elif data == "list_admins":
        admin_list = "\n".join([str(a) for a in admins])
        await query.edit_message_text(f"📋 Current Admins:\n{admin_list}")

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("admin_action")
    if not action:
        return
    try:
        target_id = int(update.message.text.strip())
        if action == "add_admin":
            admins.append(target_id)
            await update.message.reply_text(f"✅ Added {target_id} as admin.")
        elif action == "remove_admin":
            admins.remove(target_id)
            await update.message.reply_text(f"❌ Removed {target_id} from admins.")
        elif action == "broadcast":
            text = update.message.text
            success = 0
            for uid in users.union(group_ids):
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    success += 1
                except:
                    pass
            await update.message.reply_text(f"📢 Broadcast sent to {success} chats.")
    except:
        await update.message.reply_text("⚠️ Invalid input or user not found.")
    context.user_data["admin_action"] = None

# Handlers
bot_app.add_handler(CommandHandler("start", start_cmd))
bot_app.add_handler(CommandHandler("admin", admin_panel))
bot_app.add_handler(CallbackQueryHandler(handle_callback))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
bot_app.add_handler(MessageHandler(filters.TEXT & filters.User(OWNER_ID), handle_admin_response))

# --- set webhook ---
async def set_webhook():
    await bot_app.bot.set_webhook(WEBHOOK_URL)

asyncio.run(set_webhook())

# --- Start bot properly ---
async def run_bot():
    await bot_app.initialize()
    await bot_app.start()

asyncio.run(run_bot())

# --- Run Flask server ---
app.run(host="0.0.0.0", port=10000)
