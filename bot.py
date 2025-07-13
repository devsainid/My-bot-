import os
import logging
import json
import httpx
import random
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))

admins_db = ADMIN_IDS.union({OWNER_ID})

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

welcome_messages = {}

def is_bot_admin(chat_member):
    return isinstance(chat_member, ChatMemberAdministrator) or isinstance(chat_member, ChatMemberOwner)

async def send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in admins_db:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "supergroup":
        return
    if not (update.effective_user.id in admins_db or await is_admin(update)):
        return
    msg = " ".join(context.args)
    if not msg:
        return await update.message.reply_text("Please provide a welcome message")
    welcome_messages[update.effective_chat.id] = msg
    await update.message.reply_text("Welcome message set!")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in welcome_messages:
        for member in update.message.new_chat_members:
            await update.message.reply_text(welcome_messages[chat_id].replace("{name}", member.mention_html()), parse_mode="HTML")

async def is_admin(update: Update) -> bool:
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return is_bot_admin(member)
    except:
        return False

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    if not (update.effective_user.id in admins_db or await is_admin(update)):
        return
    if not context.args:
        return await update.message.reply_text("Reply with /ban, /kick, etc. or provide user ID.")
    try:
        user_id = int(context.args[0])
    except:
        return await update.message.reply_text("Invalid user ID")
    chat_id = update.effective_chat.id

    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, user_id)
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, user_id)
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
        elif action == "mute":
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions())
        elif action == "unmute":
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        elif action == "pin":
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            await context.bot.unpin_chat_message(chat_id)
        elif action == "promote":
            await context.bot.promote_chat_member(chat_id, user_id, can_manage_chat=True, can_change_info=True, can_delete_messages=True, can_invite_users=True, can_restrict_members=True, can_pin_messages=True, can_promote_members=True)
        elif action == "demote":
            await context.bot.promote_chat_member(chat_id, user_id, can_manage_chat=False, can_change_info=False, can_delete_messages=False, can_invite_users=False, can_restrict_members=False, can_pin_messages=False, can_promote_members=False)
        elif action == "purge":
            if update.message.reply_to_message:
                for msg_id in range(update.message.reply_to_message.message_id, update.message.message_id):
                    try:
                        await context.bot.delete_message(chat_id, msg_id)
                    except:
                        pass
        await update.message.reply_text(f"✅ Action '{action}' done.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    msg = message.text.lower()
    bot_username = context.bot.username.lower()

    greeting_words = ["hi", "hello", "hey", "yo", "sup", "hii", "heyy", "heya"]
    greeting_replies = [
        "Hey cutie 🥺💞", "Hi love 💕", "Hello darling 🌸", "Yo! how’s your day going? ☀️",
        "Hiiiii bestie 💖", "Hey sunshine 🌼", "Hi there 👋", "Sup sweetie 🍬"
    ]

    mentioned = message.entities and any(e.type == "mention" and bot_username in message.text.lower() for e in message.entities)
    replied_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id

    if msg in greeting_words and not message.entities and not message.reply_to_message:
        await message.reply_text(random.choice(greeting_replies))
    elif mentioned or replied_to_bot:
        await ai_reply(update, context)

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openchat/openchat-3.5",
            "messages": [
                {"role": "system", "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."},
                {"role": "user", "content": update.message.text}
            ]
        }
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            reply = res.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(reply[:4096])
    except:
        await update.message.reply_text("I'm feeling off right now, try again later 💔")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        for admin_id in admins_db:
            await context.bot.send_message(admin_id, f"📩 Private msg from @{user.username or user.first_name}\n\n{update.message.text}")
    elif chat.type in ["group", "supergroup"]:
        link = f"https://t.me/{chat.username}/{update.message.message_id}" if chat.username else ""
        for admin_id in admins_db:
            await context.bot.send_message(admin_id, f"📨 Group: @{chat.username or chat.title}\n👤 User: @{user.username or user.first_name}\n🔗 {link}\n\n{update.message.text}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn't get that, love 💋")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setwelcome", set_welcome))
    application.add_handler(CommandHandler("ban", lambda u, c: admin_command(u, c, "ban")))
    application.add_handler(CommandHandler("unban", lambda u, c: admin_command(u, c, "unban")))
    application.add_handler(CommandHandler("kick", lambda u, c: admin_command(u, c, "kick")))
    application.add_handler(CommandHandler("mute", lambda u, c: admin_command(u, c, "mute")))
    application.add_handler(CommandHandler("unmute", lambda u, c: admin_command(u, c, "unmute")))
    application.add_handler(CommandHandler("pin", lambda u, c: admin_command(u, c, "pin")))
    application.add_handler(CommandHandler("unpin", lambda u, c: admin_command(u, c, "unpin")))
    application.add_handler(CommandHandler("promote", lambda u, c: admin_command(u, c, "promote")))
    application.add_handler(CommandHandler("demote", lambda u, c: admin_command(u, c, "demote")))
    application.add_handler(CommandHandler("purge", lambda u, c: admin_command(u, c, "purge")))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    async def set_webhook():
        await application.bot.set_webhook(url=WEBHOOK_URL)

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
        on_startup=set_webhook
    )

if __name__ == '__main__':
    main()
