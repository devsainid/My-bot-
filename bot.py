import os
import logging
import httpx
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from telegram.constants import ChatAction

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

admins = set()
user_chats = set()
group_chats = set()
WAITING_FOR_BROADCAST, ADD_ADMIN, REMOVE_ADMIN = range(3)

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

logging.basicConfig(level=logging.INFO)

async def ai_reply(text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openchat/openchat-3.5",
        "messages": [SYSTEM_PROMPT, {"role": "user", "content": text}],
    }
    async with httpx.AsyncClient() as client:
        res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        return res.json()["choices"][0]["message"]["content"].strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_chats.add(update.effective_chat.id)
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in admins:
        return await update.message.reply_text("Only admin can access this.")
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "broadcast":
        await query.message.reply_text("Send the broadcast message now.")
        return WAITING_FOR_BROADCAST
    if user_id != OWNER_ID:
        return
    if query.data == "add_admin":
        await query.message.reply_text("Send user ID to add as admin.")
        return ADD_ADMIN
    if query.data == "remove_admin":
        await query.message.reply_text("Send user ID to remove from admin.")
        return REMOVE_ADMIN
    if query.data == "list_admins":
        if not admins:
            await query.message.reply_text("No admins added yet.")
        else:
            text = "\n".join([f"ID: {admin} | Username: @{(await context.bot.get_chat(admin)).username or 'N/A'}" for admin in admins])
            await query.message.reply_text(text)
    return ConversationHandler.END

async def handle_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admin_id = int(update.message.text.strip())
        admins.add(admin_id)
        await update.message.reply_text("✅ Admin added.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def handle_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admin_id = int(update.message.text.strip())
        admins.discard(admin_id)
        await update.message.reply_text("✅ Admin removed.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    success = 0
    for cid in list(user_chats.union(group_chats)):
        try:
            await context.bot.send_message(cid, msg)
            success += 1
        except:
            continue
    await update.message.reply_text(f"✅ Broadcast sent to {success} chats.")
    return ConversationHandler.END

async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    is_mention = context.bot.username.lower() in msg.text.lower() if msg.text else False
    is_reply_to_bot = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id
    if not (is_mention or is_reply_to_bot):
        return

    sender = update.effective_user
    info = f"👤 From: @{sender.username or 'NoUsername'} | ID: {sender.id}"
    link = f"https://t.me/c/{str(update.effective_chat.id)[4:]}/{update.message.message_id}" if update.effective_chat.type != "private" else ""
    for admin in [OWNER_ID] + list(admins):
        try:
            await context.bot.send_message(admin, info + (f"\n🔗 {link}" if link else ""))
            await msg.copy_to(admin)
        except:
            continue
    if update.effective_chat.type == "private":
        user_chats.add(update.effective_chat.id)
    else:
        group_chats.add(update.effective_chat.id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    greetings = ['hi', 'hello', 'hey', 'hii', 'sup']
    text_lower = msg.text.lower()
    is_mention = context.bot.username.lower() in text_lower
    is_reply_to_bot = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id
    is_greeting = text_lower.strip() in greetings

    if is_mention or is_reply_to_bot or is_greeting:
        await msg.reply_chat_action(ChatAction.TYPING)
        try:
            reply = await ai_reply(msg.text)
            await msg.reply_text(reply)
        except:
            await msg.reply_text("Oops! AI error.")

async def is_group_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    chat_admins = await update.effective_chat.get_administrators()
    return user_id == OWNER_ID or user_id in admins or any(admin.user.id == user_id for admin in chat_admins)

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("✅ User banned.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, permissions=perms)
        await update.message.reply_text("🔇 User muted.")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
        await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, permissions=perms)
        await update.message.reply_text("🔊 User unmuted.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_manage_chat=True, can_delete_messages=True)
        await update.message.reply_text("⬆️ Promoted.")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id,
            can_change_info=False, can_post_messages=False, can_edit_messages=False, can_delete_messages=False,
            can_invite_users=False, can_restrict_members=False, can_pin_messages=False, can_promote_members=False)
        await update.message.reply_text("⬇️ Demoted.")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_group_admin(update):
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Message pinned.")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Type /start to chat with me!")

app = Flask(__name__)
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(panel_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
application.add_handler(MessageHandler(filters.ALL, forward_all))
application.add_handler(CommandHandler("ban", ban))
application.add_handler(CommandHandler("mute", mute))
application.add_handler(CommandHandler("unmute", unmute))
application.add_handler(CommandHandler("promote", promote))
application.add_handler(CommandHandler("demote", demote))
application.add_handler(CommandHandler("pin", pin))
application.add_handler(CommandHandler("setwelcome", setwelcome))
application.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(panel_callback)],
    states={
        WAITING_FOR_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
        ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_admin)],
        REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_admin)],
    },
    fallbacks=[],
))
application.run_webhook(listen="0.0.0.0", port=10000, webhook_url=WEBHOOK_URL)
