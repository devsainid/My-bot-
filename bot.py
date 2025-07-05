import os
import logging
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler
)
import httpx

# ✅ Configs
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMINS = set([OWNER_ID])

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ System Prompt
CINDRELLA_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ✅ Random Greetings
GREETINGS = [
    "Hey there, how can I help you today?",
    "Hello sweetie 🌸 What’s up?",
    "Hi love! Need something?",
    "Hey, I'm here for you 💫",
    "Yes dear? I'm listening 💖"
]

# ✅ AI Reply
async def generate_reply(user_message):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
                    "X-Title": "CINDRELLA-Telegram-Bot"
                },
                json={
                    "model": "openrouter/cypher-alpha:free",
                    "messages": [
                        CINDRELLA_SYSTEM_PROMPT,
                        {"role": "user", "content": user_message}
                    ]
                }
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return random.choice(GREETINGS)

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("HEY, I'M CINDRELLA 🌹🕯️. JOIN @lazy_guys_here FOR BOT UPDATE🌹🕯️.  HOW CAN I ASSIST YOU TODAY .?", reply_markup=InlineKeyboardMarkup(keyboard))

# ✅ /admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# ✅ Callback buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    if query.data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text("Send me the broadcast message.")
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin.")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admins.")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text(f"👮 Admins:\n" + "\n".join(str(a) for a in ADMINS))

# ✅ Handle all messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    text = message.text
    chat = update.effective_chat
    sender = update.effective_user

    # 📤 Owner/Admin commands
    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            for chat_id in context.application.chat_data.keys():
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                except:
                    pass
            await message.reply_text("📢 Broadcast sent.")
        elif action == "add_admin":
            try:
                new_admin = int(text.strip())
                ADMINS.add(new_admin)
                await message.reply_text(f"✅ Admin {new_admin} added.")
            except:
                await message.reply_text("❌ Invalid ID.")
        elif action == "remove_admin":
            try:
                rem_admin = int(text.strip())
                if rem_admin in ADMINS:
                    ADMINS.remove(rem_admin)
                    await message.reply_text(f"✅ Admin {rem_admin} removed.")
                else:
                    await message.reply_text("❌ ID not in admin list.")
            except:
                await message.reply_text("❌ Invalid ID.")
        return

    # 📩 Forward private messages to admins
    if chat.type == "private":
        for admin_id in ADMINS:
            try:
                await context.bot.forward_message(chat_id=admin_id, from_chat_id=chat.id, message_id=message.message_id)
            except:
                pass

    # 📩 Group: forward tagged/replied messages with username + link
    elif chat.type in ["group", "supergroup"]:
        if message.reply_to_message or f"@{context.bot.username.lower()}" in text.lower():
            for admin_id in ADMINS:
                try:
                    msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{message.message_id}"
                    info = f"👤 From: @{sender.username or sender.id}\n🔗 Message: {msg_link}"
                    await context.bot.send_message(chat_id=admin_id, text=info)
                except:
                    pass

    # 💬 AI replies
    if chat.type == "private":
        reply = await generate_reply(text)
        await message.reply_text(reply)
    elif chat.type in ["group", "supergroup"]:
        if message.reply_to_message or f"@{context.bot.username.lower()}" in text.lower() or text.lower() in ["hi", "hello", "hey", "heyy", "sup"]:
            reply = await generate_reply(text)
            await message.reply_text(reply, reply_to_message_id=message.message_id)

# ✅ Main entry
if __name__ == "__main__":
    from telegram.ext import Application
    from telegram.ext import JobQueue

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ✅ JobQueue Fix
    if not app.job_queue:
        app.job_queue = JobQueue()
        app.job_queue.set_application(app)
        app.job_queue.start()

    async def keep_alive():
        logger.info("✅ Keep alive ping...")

    app.job_queue.run_repeating(lambda _: asyncio.create_task(keep_alive()), interval=7200)

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )
