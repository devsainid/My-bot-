import os
import logging
import random
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler, Application
)
import httpx

# ✅ Configs
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

GREETINGS = [
    "Hey there 🌸", "Hi dear 🌟", "Hello cutie 😇", "Hey! How's it going? 💫",
    "Hi sweet soul 🌼", "What's up? 😊", "Heyy, how can I help you love 💖",
    "I'm here for you! 🌷"
]

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
                    "messages": [CINDRELLA_SYSTEM_PROMPT, {"role": "user", "content": user_message}]
                }
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"❌ AI error: {e}")
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

# ✅ Callback button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMINS:
        return
    action_map = {
        "broadcast": "broadcast",
        "add_admin": "add_admin",
        "remove_admin": "remove_admin",
        "list_admins": "list_admins"
    }
    action = action_map.get(query.data)
    if action:
        context.user_data["action"] = action
        if action == "list_admins":
            return await query.message.reply_text(f"👮 Admins:\n" + "\n".join(str(a) for a in ADMINS))
        await query.message.reply_text(f"Send user ID/message for: {action.replace('_', ' ').title()}")

# ✅ Message handling
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    text = update.message.text or ""
    is_mentioned = f"@{context.bot.username.lower()}" in text.lower()
    is_replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if user_id in ADMINS and "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            for chat_id in context.application.chat_data.keys():
                try: await context.bot.send_message(chat_id, text)
                except: pass
            return await update.message.reply_text("📢 Broadcast sent.")
        try:
            target = int(text.strip())
            if action == "add_admin":
                ADMINS.add(target)
                return await update.message.reply_text(f"✅ Admin {target} added.")
            elif action == "remove_admin":
                if target in ADMINS:
                    ADMINS.remove(target)
                    return await update.message.reply_text(f"✅ Admin {target} removed.")
                else:
                    return await update.message.reply_text("❌ Not an admin.")
        except:
            return await update.message.reply_text("❌ Invalid ID.")
        return

    # ✅ Forward Logic
    if chat.type == "private":
        for admin_id in ADMINS:
            try: await context.bot.forward_message(admin_id, chat.id, update.message.message_id)
            except: pass
    elif is_mentioned or is_replied:
        for admin_id in ADMINS:
            try:
                username = f"@{update.effective_user.username}" if update.effective_user.username else f"[User](tg://user?id={user_id})"
                link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if str(chat.id).startswith("-100") else "Message link unavailable"
                await context.bot.send_message(admin_id, f"👤 {username}\n🔗 [Message Link]({link})", parse_mode="Markdown", disable_web_page_preview=True)
            except: pass

    # ✅ AI Reply
    if chat.type in ["group", "supergroup"]:
        if text.lower() in ["hi", "hello", "sup", "hey", "heyy"] or is_mentioned or is_replied:
            prompt = random.choice(GREETINGS) if text.lower() in ["hi", "hello", "sup", "hey", "heyy"] else text
            reply = await generate_reply(prompt)
            return await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    else:
        reply = await generate_reply(text)
        return await update.message.reply_text(reply)

# ✅ Keep alive ping
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get(WEBHOOK_URL)
        except:
            pass
        await asyncio.sleep(900)

# ✅ Final run app
async def main():
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.create_task(keep_alive())
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
