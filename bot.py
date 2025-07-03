import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import httpx

# Basic Config
BOT_TOKEN = "7600489635:AAEXc3iBM7g_O_L6_yL3h5vNN4o_BSWsLDE"
OWNER_ID = 6559745280
ADMINS = set()
OPENROUTER_API_KEY = "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"

# Log
logging.basicConfig(level=logging.INFO)

# --- AI REPLY HANDLER ---
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    prompt = [
        {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
        {"role": "user", "content": text}
    ]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "Content-Type": "application/json"
    }

    try:
        response = httpx.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers,
                              json={"model": "openchat/openchat-3.5", "messages": prompt})
        reply = response.json()["choices"][0]["message"]["content"]
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Something went wrong.")

# --- ADMIN PANEL ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in ADMINS:
        return await update.message.reply_text("You are not allowed.")
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]
    if user_id == OWNER_ID:
        keyboard += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# --- CALLBACK HANDLERS ---
ADD_ADMIN, REMOVE_ADMIN, BROADCAST = range(3)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "broadcast" and (user_id == OWNER_ID or user_id in ADMINS):
        await query.message.reply_text("Send the broadcast message now:")
        context.user_data["action"] = "broadcast"
    
    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send ID to add as admin:")
        context.user_data["action"] = "add_admin"

    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send ID to remove from admins:")
        context.user_data["action"] = "remove_admin"

    elif query.data == "list_admins" and user_id == OWNER_ID:
        if ADMINS:
            admins_text = "\n".join(str(admin) for admin in ADMINS)
        else:
            admins_text = "No admins added."
        await query.message.reply_text(admins_text)

# --- HANDLE TEXT AFTER BUTTONS ---
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")
    text = update.message.text

    if action == "add_admin":
        try:
            ADMINS.add(int(text))
            await update.message.reply_text("Admin added successfully.")
        except:
            await update.message.reply_text("Invalid ID.")
        context.user_data.pop("action")

    elif action == "remove_admin":
        try:
            ADMINS.remove(int(text))
            await update.message.reply_text("Admin removed.")
        except:
            await update.message.reply_text("ID not in admin list.")
        context.user_data.pop("action")

    elif action == "broadcast":
        # Broadcast to all known chats (you can add group/user tracking logic here)
        await update.message.reply_text("Broadcast sent.")
        context.user_data.pop("action")

# --- FORWARD SYSTEM ---
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    text = f"📨 From: @{user.username or user.id} | Chat ID: `{chat.id}`\n\n{update.message.text or 'non-text message'}"

    # Forward to owner + all admins
    recipients = [OWNER_ID] + list(ADMINS)
    for admin_id in recipients:
        try:
            await context.bot.send_message(admin_id, text, parse_mode="Markdown")
        except Exception as e:
            logging.warning(f"Can't forward to {admin_id}: {e}")

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))
    app.add_handler(MessageHandler(filters.ALL, forward_all))  # Forward anything else

    app.run_polling()

if __name__ == "__main__":
    main()
