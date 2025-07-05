import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler
)
import httpx

# ✅ Basic config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Admins list
ADMINS = set([OWNER_ID])

# ✅ System prompt
CINDRELLA_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# ✅ AI reply
# ✅ AI reply
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
            logger.info(f"AI Response Raw: {data}")
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"❌ AI reply error: {e}")
        return "IM OFFLINE RIGHT NOW DEAR 😥💔"
        
# ✅ /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("HEY, I'M CINDRELLA 🌹🕯️. JOIN @lazy_guys_here FOR BOT UPDATE🌹🕯️.  HOW CAN I ASSIST YOU TODAY .?", reply_markup=InlineKeyboardMarkup(keyboard))

# ✅ /admin command
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

# ✅ Callback query handler
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

# ✅ Handle messages for broadcast/admin management/AI chat
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 🔐 Owner/Admin only actions
    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")

        if action == "broadcast":
            for chat_id in context.application.chat_data.keys():
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                except:
                    pass
            await update.message.reply_text("📢 Broadcast sent.")

        elif action == "add_admin":
            try:
                new_admin = int(text.strip())
                ADMINS.add(new_admin)
                await update.message.reply_text(f"✅ Admin {new_admin} added.")
            except:
                await update.message.reply_text("❌ Invalid ID.")

        elif action == "remove_admin":
            try:
                rem_admin = int(text.strip())
                if rem_admin in ADMINS:
                    ADMINS.remove(rem_admin)
                    await update.message.reply_text(f"✅ Admin {rem_admin} removed.")
                else:
                    await update.message.reply_text("❌ ID not in admin list.")
            except:
                await update.message.reply_text("❌ Invalid ID.")
        return

    # 📩 Forward message to OWNER + all admins
    sender = update.effective_user
    chat = update.effective_chat
    for admin_id in ADMINS:
        try:
            await context.bot.forward_message(chat_id=admin_id, from_chat_id=chat.id, message_id=update.message.message_id)
        except:
            pass

# 💬 AI reply in group or private
    if chat.type in ["group", "supergroup"]:
        if (
            text.lower() in ["hi", "hello", "sup", "hey", "heyy"] or
            update.message.reply_to_message or
            f"@{context.bot.username.lower()}" in text.lower()
        ):
            reply = await generate_reply(text)
            await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    else:
        reply = await generate_reply(text)
        await update.message.reply_text(reply)
# ✅ Main entry
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ✅ Run webhook (Render-compatible)
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
                )
