import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

admins = [OWNER_ID]
private_users = set()
group_chats = set()
pending_broadcast = {}

# === AI Reply ===
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
                "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, curious, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
            },
            {"role": "user", "content": prompt}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_data)
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Something went wrong: {e}"

# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        private_users.add(chat.id)
    elif chat.type in ["group", "supergroup"]:
        group_chats.add(chat.id)
    await update.message.reply_text("Hey! I'm your CINDRELLA 🤖")

# === Message Handler ===
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        private_users.add(chat.id)
    elif chat.type in ["group", "supergroup"]:
        group_chats.add(chat.id)

    if update.message.text.lower() in ["hi", "hello", "hey", "start"]:
        await update.message.reply_text("Hello! How can I help you? 🌟")
    elif update.effective_user.id in pending_broadcast:
        text = update.message.text
        await broadcast_message(context, text)
        del pending_broadcast[update.effective_user.id]
        await update.message.reply_text("✅ Broadcast sent!")
    else:
        reply = await ask_openrouter_ai(update.message.text)
        await update.message.reply_text(reply)

# === Admin Panel ===
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in admins:
        return

    keyboard = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]

    if user_id == OWNER_ID:
        keyboard.append([
            InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin"),
            InlineKeyboardButton("📋 List Admins", callback_data="list_admins")
        ])

    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# === Callback Handler ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id != OWNER_ID and user_id not in admins:
        return

    if query.data == "broadcast":
        pending_broadcast[user_id] = True
        await query.message.reply_text("📝 Send the message to broadcast:")
    elif query.data == "list_admins" and user_id == OWNER_ID:
        await query.message.reply_text("👑 Admins:\n" + "\n".join([str(a) for a in admins]))
    elif query.data == "add_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "add"
        await query.message.reply_text("Send the user ID to add:")
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        context.user_data["action"] = "remove"
        await query.message.reply_text("Send the user ID to remove:")

# === Handle Admin ID Entry ===
async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "action" not in context.user_data:
        return
    try:
        user_id = int(update.message.text)
    except:
        await update.message.reply_text("❌ Invalid ID.")
        return

    action = context.user_data["action"]
    if action == "add":
        if user_id not in admins:
            admins.append(user_id)
            await update.message.reply_text(f"✅ Added {user_id} as admin.")
    elif action == "remove":
        if user_id in admins:
            admins.remove(user_id)
            await update.message.reply_text(f"❌ Removed {user_id} from admin list.")
    context.user_data.clear()

# === Broadcast ===
async def broadcast_message(context, message):
    for user_id in private_users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except:
            pass
    for group_id in group_chats:
        try:
            await context.bot.send_message(chat_id=group_id, text=message)
        except:
            pass

# === Main ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(OWNER_ID), handle_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 CINDRELLA is running...")
    app.run_polling()
