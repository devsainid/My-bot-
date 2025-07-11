import os
import logging
import random
import httpx
import telegram
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner, ChatMemberMember
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
    CallbackQueryHandler, ConversationHandler
)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))

# Init
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
ADMINS = set([OWNER_ID])

# Personality & Model
BOT_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent girl. You reply like a real best friend."
}
OPENROUTER_MODELS = [
    "openchat/openchat-3.5-0106",
    "mistralai/mixtral-8x7b",
    "gryphe/mythomax-l2-13b",
    "openrouter/cinematika-7b",
    "nousresearch/nous-capybara-7b",
    "google/gemma-7b-it"
]

# Store
USAGE_COUNT = 0
WELCOME_MESSAGES = {}
ADMIN_PANEL, ADDING_ADMIN, REMOVING_ADMIN = range(3)

# Utils
async def ai_reply(prompt):
    global USAGE_COUNT
    USAGE_COUNT += 1
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "Content-Type": "application/json"
    }
    payload = {
        "model": random.choice(OPENROUTER_MODELS),
        "messages": [BOT_SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
            data = res.json()
            return data['choices'][0]['message']['content'].strip()
    except:
        return "Oops! AI error."

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")
    )
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🕯️. How you found me dear 🌹🔯🕯️..?", reply_markup=btn)
    
# Command: /admin
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await update.message.reply_text("You aren't allowed here.")
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
            [InlineKeyboardButton("📊 Today Usage", callback_data="usage")]
        ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_PANEL

# Callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "broadcast":
        context.user_data['action'] = 'broadcast'
        await query.message.reply_text("Send the message to broadcast:")
        return ADMIN_PANEL
    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add as admin:")
        return ADDING_ADMIN
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove:")
        return REMOVING_ADMIN
    elif query.data == "list_admins" and user_id == OWNER_ID:
        out = "\n".join([f"ID: {uid}" for uid in ADMINS])
        await query.message.reply_text(f"Admins:\n{out}")
    elif query.data == "usage" and user_id == OWNER_ID:
        await query.message.reply_text(f"Total replies today: {USAGE_COUNT}")
    return ADMIN_PANEL

# Text messages
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    # Forward
    for admin_id in ADMINS:
        if msg.chat.type != 'private':
            await context.bot.forward_message(admin_id, msg.chat.id, msg.message_id)
    # Handle broadcast
    if msg.from_user.id == OWNER_ID and context.user_data.get('action') == 'broadcast':
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(admin_id, msg.text)
            except:
                pass
        await msg.reply_text("✅ Broadcast sent.")
        context.user_data.clear()
    # AI reply or greetings
    elif msg.text.lower() in ["hi", "hello", "hey", "sup", "yo"]:
        await msg.reply_text(random.choice(["Heyy", "Hii love", "Yo!", "Sweet hello", "Cutee hii 💖"]))
    else:
        reply = await ai_reply(msg.text)
        await msg.reply_text(reply[:300])

# Admin controls
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text)
        ADMINS.add(new_id)
        await update.message.reply_text("✅ Admin added.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rem_id = int(update.message.text)
        ADMINS.discard(rem_id)
        await update.message.reply_text("✅ Admin removed.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

# Group admin commands
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"Banned {user.full_name}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if context.args:
        await context.bot.unban_chat_member(update.effective_chat.id, int(context.args[0]))
        await update.message.reply_text("Unbanned successfully.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, ChatPermissions())
        await update.message.reply_text(f"Muted {user.full_name}")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_manage_chat=True, can_delete_messages=True, can_invite_users=True)
        await update.message.reply_text(f"Promoted {user.full_name}")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_manage_chat=False, can_delete_messages=False, can_invite_users=False)
        await update.message.reply_text(f"Demoted {user.full_name}")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    WELCOME_MESSAGES[update.effective_chat.id] = update.message.text.split(" ", 1)[1]
    await update.message.reply_text("✅ Welcome message set.")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        msg = WELCOME_MESSAGES.get(update.effective_chat.id)
        if msg:
            for member in update.message.new_chat_members:
                await update.message.reply_text(msg.replace("{name}", member.full_name))

async def is_admin(update: Update):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    member = await update.effective_chat.get_member(user_id)
    return member.status in ['administrator', 'creator'] or user_id in ADMINS

# Handler wiring
panel_conv = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_panel)],
    states={
        ADMIN_PANEL: [CallbackQueryHandler(button_handler)],
        ADDING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
        REMOVING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(panel_conv)
telegram_app.add_handler(CommandHandler("ban", ban))
telegram_app.add_handler(CommandHandler("unban", unban))
telegram_app.add_handler(CommandHandler("mute", mute))
telegram_app.add_handler(CommandHandler("promote", promote))
telegram_app.add_handler(CommandHandler("demote", demote))
telegram_app.add_handler(CommandHandler("setwelcome", setwelcome))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# Run
if __name__ == '__main__':
    telegram_app.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook"
  )
