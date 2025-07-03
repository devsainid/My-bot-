import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

admins = [OWNER_ID]

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey! I'm your CINDRELLA 🤖")

# Respond to hi, hello etc.
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() in ["hi", "hello", "hey", "start"]:
        await update.message.reply_text("Hello! How can I help you? 🌟")
    else:
        reply = await ask_openrouter_ai(update.message.text)
        await update.message.reply_text(reply)

# Ask OpenRouter AI
async def ask_openrouter_ai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "X-Title": "CINDRELLA"
    }
    json_data = {
        "model": "openchat/openchat-3.5",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are CINDRELLA, a 16-year-old emotionally intelligent girl. "
                    "You talk in a warm, friendly, human-like way. Always respond only in English. "
                    "You're kind, realistic, smart, and emotionally supportive like a best friend."
                )
            },
            {"role": "user", "content": prompt}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_data)
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Something went wrong: {e}"

# Admin panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in admins:
        return

    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", url="https://t.me/YOUR_CHANNEL")],
    ]

    if user_id == OWNER_ID:
        keyboard.append([
            InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin"),
            InlineKeyboardButton("📋 List Admins", callback_data="list_admins")
        ])

    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# Callback handler
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != OWNER_ID:
        return

    if query.data == "list_admins":
        await query.message.reply_text("Current admins:\n" + "\n".join([str(a) for a in admins]))
    elif query.data == "add_admin":
        await query.message.reply_text("Send the user ID to add:")
        context.user_data["action"] = "add"
    elif query.data == "remove_admin":
        await query.message.reply_text("Send the user ID to remove:")
        context.user_data["action"] = "remove"

# Handle admin ID entry
async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "action" not in context.user_data:
        return

    try:
        user_id = int(update.message.text)
        action = context.user_data["action"]

        if action == "add":
            if user_id not in admins:
                admins.append(user_id)
                await update.message.reply_text(f"✅ Added {user_id} as admin.")
        elif action == "remove":
            if user_id in admins:
                admins.remove(user_id)
                await update.message.reply_text(f"❌ Removed {user_id} from admin list.")
    except:
        await update.message.reply_text("⚠️ Invalid ID. Please enter a valid number.")

    context.user_data.clear()

# Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(OWNER_ID), handle_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 CINDRELLA is running...")
    app.run_polling()
