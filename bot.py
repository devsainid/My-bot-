import os
import logging
import random
import httpx
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler
)

# ✅ Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "YOUR_CINDRELLABOT").lower()

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ADMINS = set([OWNER_ID])

# ✅ System Prompt
CINDRELLA_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ✅ Gentle greetings
GREETINGS = [
    "Hi there... I'm here for you 🤍",
    "Hey... how are you doing today?",
    "Hello dear... what's on your heart?",
    "Yes, I'm listening with care 🕊️",
    "Hi... let's talk if you're feeling something",
    "Hello... I’m all ears and warmth 💫"
]

# ✅ AI
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
        logger.error(f"❌ AI reply error: {e}")
        return "IM OFFLINE RIGHT NOW DEAR 😥💔"

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("HEY, I'M CINDRELLA 🌹🕯️. JOIN @lazy_guys_here FOR BOT UPDATE🌹🕯️.  HOW CAN I ASSIST YOU TODAY .?", reply_markup=InlineKeyboardMarkup(keyboard))

# ✅ /admin
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

# ✅ Buttons
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

# ✅ Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    text = update.message.text or ""
    is_mentioned = f"@{BOT_USERNAME}" in text.lower()
    is_replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_greeting = text.lower() in ["hi", "hello", "hey", "heyy", "sup"]

    # 🛠️ Admin actions
    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        try:
            if action == "broadcast":
                for chat_id in context.application.chat_data.keys():
                    try: await context.bot.send_message(chat_id, text)
                    except: pass
                await update.message.reply_text("📢 Broadcast sent.")
            elif action == "add_admin":
                ADMINS.add(int(text.strip()))
                await update.message.reply_text(f"✅ Admin {text} added.")
            elif action == "remove_admin":
                ADMINS.discard(int(text.strip()))
                await update.message.reply_text(f"✅ Admin {text} removed.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        return

    # 🔁 Private chat: forward every message
    if chat.type == "private":
        for admin_id in ADMINS:
            try:
                await context.bot.forward_message(admin_id, chat.id, update.message.message_id)
            except: pass

    # 🔁 Group chat: forward if mentioned or replied
    if chat.type in ["group", "supergroup"] and (is_mentioned or is_replied):
        msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if str(chat.id).startswith("-100") else "Group message"
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(admin_id, f"👤 @{update.effective_user.username or update.effective_user.first_name}\n🔗 {msg_link}\n💬 {text}")
            except: pass

    # 🤖 AI Reply
    if chat.type == "private" or is_greeting or is_mentioned or is_replied:
        if is_greeting and not (is_mentioned or is_replied):
            reply = random.choice(GREETINGS)
        else:
            reply = await generate_reply(text)
        await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)

# ✅ Keep Alive for Render
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get(WEBHOOK_URL)
        except: pass
        await asyncio.sleep(1500)  # every 25 minutes

# ✅ Start Bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_once(lambda _: asyncio.create_task(keep_alive()), when=1)

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
            )
