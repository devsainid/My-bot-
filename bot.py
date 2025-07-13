import os
import logging
import json
import httpx
from flask import Flask, request
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ChatPermissions)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

admins = set()
users = set()

system_prompt = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# --- Helper Functions ---

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id in admins or is_owner(user_id)

def get_image_from_unsplash(query):
    url = f"https://source.unsplash.com/800x600/?{query}"
    return url

def build_admin_keyboard():
    keyboard = []
    if is_owner(OWNER_ID):
        keyboard += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    keyboard.insert(0, [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")])
    return InlineKeyboardMarkup(keyboard)

# --- Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url="https://t.me/{}?startgroup=true".format(context.bot.username))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text("Admin Panel:", reply_markup=build_admin_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.message.reply_text("Send me the message to broadcast.")

    elif query.data == "add_admin" and is_owner(query.from_user.id):
        context.user_data["awaiting_add_admin"] = True
        await query.message.reply_text("Send user ID to add as admin.")

    elif query.data == "remove_admin" and is_owner(query.from_user.id):
        context.user_data["awaiting_remove_admin"] = True
        await query.message.reply_text("Send user ID to remove from admins.")

    elif query.data == "list_admins" and is_owner(query.from_user.id):
        admin_list = "\n".join([str(i) for i in admins]) or "No admins yet."
        await query.message.reply_text(f"Admins:\n{admin_list}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    # Broadcast handling
    if context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        for uid in users.union(admins):
            try:
                await context.bot.send_message(uid, text)
            except:
                continue
        await update.message.reply_text("Broadcast sent ✅")
        return

    # Add admin
    if context.user_data.get("awaiting_add_admin"):
        context.user_data["awaiting_add_admin"] = False
        try:
            admins.add(int(text))
            await update.message.reply_text("Admin added ✅")
        except:
            await update.message.reply_text("Failed to add admin ❌")
        return

    # Remove admin
    if context.user_data.get("awaiting_remove_admin"):
        context.user_data["awaiting_remove_admin"] = False
        try:
            admins.remove(int(text))
            await update.message.reply_text("Admin removed ✅")
        except:
            await update.message.reply_text("Failed to remove admin ❌")
        return

    # Check for image request
    if any(x in text.lower() for x in ["pic", "photo", "image"]):
        image_url = get_image_from_unsplash(text)
        await update.message.reply_photo(image_url)
        return

    # Normal message -> AI reply
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-0106",
        "messages": [system_prompt, {"role": "user", "content": text}]
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            reply = res.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(reply[:4096])
    except:
        await update.message.reply_text("Sorry, I couldn't respond right now.")

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Aww, nice sticker! 🧸")

async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    try:
        msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if chat.type != 'private' else ""
        for admin_id in [OWNER_ID] + list(admins):
            await context.bot.send_message(admin_id, f"Message from {user.mention_html()} ({user.id}):\n{update.message.text or 'Non-text message'}\n{msg_link}", parse_mode="HTML")
    except:
        pass

# --- Webhook Setup ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), context.bot)
    context.application.update_queue.put_nowait(update)
    return "ok"

if __name__ == '__main__':
    from telegram.ext import Application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.NEW_CHAT_MEMBERS, forward_all), group=0)
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )
