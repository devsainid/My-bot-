import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import requests

# Load from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

admins = [OWNER_ID]  # Add more admin IDs if needed
awaiting_broadcast = {}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SYSTEM PROMPT
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, curious, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! I'm your CINDRELLA how are u today..?")

# Handle admin command
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return

    keyboard = [
        [InlineKeyboardButton("\ud83d\udce2 Broadcast", callback_data="broadcast")]
    ]

    if user_id == OWNER_ID:
        keyboard.append([
            InlineKeyboardButton("\u2795 Add Admin", callback_data="add_admin"),
            InlineKeyboardButton("\u2796 Remove Admin", callback_data="remove_admin"),
            InlineKeyboardButton("\ud83d\udccb List Admins", callback_data="list_admins")
        ])

    await update.message.reply_text("\ud83d\udd10 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# Handle button callbacks
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in admins:
        return

    if query.data == "list_admins":
        await query.message.reply_text("Current admins:\n" + "\n".join([str(a) for a in admins]))
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add"
        await query.message.reply_text("Send the user ID to add:")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove"
        await query.message.reply_text("Send the user ID to remove:")
    elif query.data == "broadcast":
        awaiting_broadcast[user_id] = True
        await query.message.reply_text("Please send the broadcast message.")

# Handle admin ID input
async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "action" not in context.user_data:
        return
    try:
        new_id = int(update.message.text)
    except:
        return await update.message.reply_text("Invalid ID.")

    action = context.user_data["action"]
    if action == "add" and new_id not in admins:
        admins.append(new_id)
        await update.message.reply_text(f"✅ Added {new_id} as admin.")
    elif action == "remove" and new_id in admins:
        admins.remove(new_id)
        await update.message.reply_text(f"❌ Removed {new_id} from admin list.")
    context.user_data.clear()

# AI response
async def ask_openrouter_ai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "X-Title": "CINDRELLA"
    }
    data = {
        "model": "openchat/openchat-3.5",
        "messages": [
            SYSTEM_PROMPT,
            {"role": "user", "content": prompt}
        ]
    }
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Something went wrong: {e}"

# Broadcast handler
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in awaiting_broadcast:
        return

    text = update.message.text
    del awaiting_broadcast[user_id]

    # Send to all groups & private chats bot is in
    async for dialog in context.bot.get_dialogs():
        try:
            await context.bot.send_message(dialog.chat.id, text)
        except:
            continue

    await update.message.reply_text("✅ Broadcast sent.")

# Copy and forward all messages to owner/admins
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        sender = update.effective_user
        chat = update.effective_chat
        sender_name = sender.full_name
        msg_text = update.message.text or "[Non-text message]"
        link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}" if chat.type != Chat.PRIVATE else "(Private chat)"

        content = f"📩 Message from: {sender_name} (ID: {sender.id})\n"
        if chat.type != Chat.PRIVATE:
            content += f"Group: {chat.title}\n"
        content += f"Message: {msg_text}\nLink: {link}"

        for admin_id in admins:
            if admin_id != sender.id:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=content)
                except:
                    continue

# Message handler
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in awaiting_broadcast:
        return await handle_broadcast(update, context)

    # Forward messages first
    await forward_all(update, context)

    # Handle chat message
    if update.message.text.lower() in ["hi", "hello", "hey"]:
        await update.message.reply_text("Hello! How can I help you? 🌟")
    else:
        reply = await ask_openrouter_ai(update.message.text)
        await update.message.reply_text(reply)

# Run bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(OWNER_ID), handle_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 CINDRELLA is running...")
    app.run_polling()
