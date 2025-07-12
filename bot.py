import os, logging, random, httpx, telegram
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler, ConversationHandler
)

# ENV Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
logging.basicConfig(level=logging.INFO)

# Constants
ADMINS = set([OWNER_ID])
BOT_SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent girl. You reply like a real best friend in short, human-like sentences."
}
MODELS = [
    "openchat/openchat-3.5-0106", "mistralai/mixtral-8x7b",
    "gryphe/mythomax-l2-13b", "openrouter/cinematika-7b"
]
GREETING_WORDS = ["hi", "hello", "hey", "sup", "yo", "heya"]
USAGE_COUNT = 0
WELCOME_MESSAGE = "Welcome to the group!"

ADMIN_PANEL, ADDING_ADMIN, REMOVING_ADMIN = range(3)

# ========== AI Chat ==========
async def ai_reply(prompt):
    global USAGE_COUNT
    USAGE_COUNT += 1
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT",
        "Content-Type": "application/json"
    }
    payload = {
        "model": random.choice(MODELS),
        "messages": [BOT_SYSTEM_PROMPT, {"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
            return r.json()['choices'][0]['message']['content']
    except:
        return "Oops! AI error."

# ========== Handlers ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")
    )
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=btn)

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
            [InlineKeyboardButton("📊 Usage", callback_data="usage")]
        ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_PANEL

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if q.data == "broadcast":
        context.user_data['action'] = 'broadcast'
        await q.message.reply_text("Send message to broadcast:")
    elif q.data == "add_admin" and uid == OWNER_ID:
        await q.message.reply_text("Send user ID to add:")
        return ADDING_ADMIN
    elif q.data == "remove_admin" and uid == OWNER_ID:
        await q.message.reply_text("Send user ID to remove:")
        return REMOVING_ADMIN
    elif q.data == "list_admins" and uid == OWNER_ID:
        admins = "\n".join([str(uid) for uid in ADMINS])
        await q.message.reply_text(f"Admins:\n{admins}")
    elif q.data == "usage" and uid == OWNER_ID:
        await q.message.reply_text(f"Today's usage: {USAGE_COUNT}")
    return ADMIN_PANEL

# ========== Utilities ==========
async def is_admin(update: Update):
    user_id = update.effective_user.id
    member = await update.effective_chat.get_member(user_id)
    return user_id in ADMINS or isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))

# ========== Admin Commands ==========
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text("✅ Banned.")
    except: await update.message.reply_text("❌ Error.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text("✅ Unbanned.")
    except: await update.message.reply_text("❌ Error.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, ChatPermissions())
        await update.message.reply_text("✅ Muted.")
    except: await update.message.reply_text("❌ Error.")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text("✅ Kicked.")
    except: await update.message.reply_text("❌ Error.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_manage_chat=True, can_delete_messages=True)
        await update.message.reply_text("✅ Promoted.")
    except: await update.message.reply_text("❌ Error.")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.promote_chat_member(update.effective_chat.id, user.id, can_manage_chat=False, can_delete_messages=False)
        await update.message.reply_text("✅ Demoted.")
    except: await update.message.reply_text("❌ Error.")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        await update.message.pin()
        await update.message.reply_text("✅ Pinned.")
    except: await update.message.reply_text("❌ Error.")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    try:
        await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("✅ Unpinned.")
    except: await update.message.reply_text("❌ Error.")

# ========== Welcome, Sticker, AI, Text ==========
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        await update.message.reply_html(f"{WELCOME_MESSAGE}, {m.mention_html()}!")

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return
    global WELCOME_MESSAGE
    WELCOME_MESSAGE = update.message.text.split(' ', 1)[1]
    await update.message.reply_text("✅ Welcome message set.")

async def sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("That's cute! 💖")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = msg.text.lower()

    if msg.from_user.id == OWNER_ID and context.user_data.get('action') == 'broadcast':
        for uid in ADMINS:
            try: await context.bot.send_message(uid, msg.text)
            except: pass
        await msg.reply_text("✅ Broadcast sent.")
        context.user_data.clear()
        return

    if any(greet in txt for greet in GREETING_WORDS):
        return await msg.reply_text(random.choice(["Heyy", "Hii love", "Yo!", "Sweet hello", "Cutee hii 💖"]))

    if txt.startswith("give me") and "pic" in txt:
        keyword = txt.replace("give me", "").replace("pic", "").strip()
        return await msg.reply_photo(f"https://loremflickr.com/640/360/{keyword}")

    res = await ai_reply(msg.text)
    await msg.reply_text(res[:300])

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        ADMINS.add(uid)
        await update.message.reply_text("✅ Admin added.")
    except: await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        ADMINS.discard(uid)
        await update.message.reply_text("✅ Admin removed.")
    except: await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ========== Webhook ==========
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

# ========== Handlers ==========
panel_conv = ConversationHandler(
    entry_points=[CommandHandler("admin", admin_panel)],
    states={
        ADMIN_PANEL: [CallbackQueryHandler(button_handler)],
        ADDING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
        REMOVING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("ban", ban))
telegram_app.add_handler(CommandHandler("unban", unban))
telegram_app.add_handler(CommandHandler("kick", kick))
telegram_app.add_handler(CommandHandler("mute", mute))
telegram_app.add_handler(CommandHandler("promote", promote))
telegram_app.add_handler(CommandHandler("demote", demote))
telegram_app.add_handler(CommandHandler("pin", pin))
telegram_app.add_handler(CommandHandler("unpin", unpin))
telegram_app.add_handler(CommandHandler("setwelcome", set_welcome))
telegram_app.add_handler(panel_conv)
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
telegram_app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_reply))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# ========== Start Webhook ==========
if __name__ == '__main__':
    telegram_app.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook"
          )
