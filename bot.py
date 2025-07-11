
import os
import logging
import httpx
import json
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", "8080"))

app = ApplicationBuilder().token(BOT_TOKEN).build()

admins = [OWNER_ID]
known_chats = set()
try:
    with open("known_chats.txt") as f:
        known_chats = set(map(int, filter(None, f.read().splitlines())))
except:
    pass

# SYSTEM PROMPT
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

# AI Chat
async def chat_with_ai(message):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "openchat/openchat-3.5",
                    "messages": [SYSTEM_PROMPT, {"role": "user", "content": message}],
                },
            )
            return res.json()["choices"][0]["message"]["content"]
    except:
        return "Sorry, I'm down right now."

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")]]
    )
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=button)

# ADMIN PANEL
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in admins:
        return
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
    ]
    if uid == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")],
        ]
    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

# CALLBACKS
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    if uid not in admins:
        return
    if query.data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text("Send broadcast message:")
    elif query.data == "add_admin" and uid == OWNER_ID:
        context.user_data["action"] = "add_admin"
        await query.message.reply_text("Send user ID to add as admin:")
    elif query.data == "remove_admin" and uid == OWNER_ID:
        context.user_data["action"] = "remove_admin"
        await query.message.reply_text("Send user ID to remove from admin:")
    elif query.data == "list_admins" and uid == OWNER_ID:
        msg = "\n".join([f"{aid} (@{(await context.bot.get_chat(aid)).username})" for aid in admins if aid != OWNER_ID])
        await query.message.reply_text("Admins:\n" + (msg or "No admins added"))

# MESSAGE HANDLER
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat = update.effective_chat
    msg = update.message
    known_chats.add(chat.id)
    with open("known_chats.txt", "w") as f:
        f.write("\n".join(map(str, known_chats)))

    if "action" in context.user_data:
        action = context.user_data.pop("action")
        if action == "broadcast":
            for cid in known_chats:
                try:
                    await context.bot.send_message(cid, msg.text)
                except:
                    pass
        elif action == "add_admin":
            admins.append(int(msg.text))
            await msg.reply_text("Admin added.")
        elif action == "remove_admin":
            admins.remove(int(msg.text))
            await msg.reply_text("Admin removed.")
        return

    if msg.text and msg.text.lower() in ["hi", "hello", "hey", "sup", "yo"]:
        await msg.reply_text("Hey there 🌸")
    elif msg.text:
        reply = await chat_with_ai(msg.text)
        await msg.reply_text(reply)

    # Forward system
    fwd_text = f"👤 From: {uid} (@{msg.from_user.username or 'N/A'})\n"
    if msg.chat.type != "private":
        fwd_text += f"👥 Group: {chat.title}\n🔗 Message: https://t.me/c/{str(chat.id)[4:]}/{msg.message_id}"
    await context.bot.send_message(OWNER_ID, fwd_text)
    await context.bot.copy_message(OWNER_ID, chat.id, msg.message_id)

# GROUP JOIN
async def group_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"Welcome {member.full_name} 🌟")

# COMMANDS
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if update.message.reply_to_message:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text("User banned.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if update.message.reply_to_message:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("User muted.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if update.message.reply_to_message:
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_promote_members=False,
        )
        await update.message.reply_text("User promoted.")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    if update.message.reply_to_message:
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_promote_members=False,
            can_change_info=False
        )
        await update.message.reply_text("User demoted.")

# ROUTES
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    app.update_queue.put_nowait(update)
    return 'ok'

# HANDLERS
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("promote", promote))
app.add_handler(CommandHandler("demote", demote))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.MY_CHAT_MEMBER, group_join))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

# RUN
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL + "/webhook"
    )
