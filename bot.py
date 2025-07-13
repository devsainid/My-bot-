import os
import logging
import json
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ChatMemberAdministrator
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
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

async def send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in admins_db:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("\u2795 Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", reply_markup=reply_markup)

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "supergroup": return
    if not (update.effective_user.id in admins_db or await is_admin(update)): return
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
        return member.status in ("administrator", "creator")
    except:
        return False

# ==== Admin Commands ====

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return await update.message.reply_text("Reply to a user to ban.")
    await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
    await update.message.reply_text("User banned!")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not context.args: return await update.message.reply_text("Give user ID to unban.")
    await context.bot.unban_chat_member(update.effective_chat.id, int(context.args[0]))
    await update.message.reply_text("User unbanned!")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions())
    await update.message.reply_text("User muted!")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=True))
    await update.message.reply_text("User unmuted!")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
    await context.bot.unban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
    await update.message.reply_text("User kicked!")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_manage_chat=True, can_delete_messages=True, can_promote_members=False)
    await update.message.reply_text("User promoted!")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_manage_chat=False, can_delete_messages=False, can_promote_members=False)
    await update.message.reply_text("User demoted!")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if update.message.reply_to_message:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("Message pinned!")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    await context.bot.unpin_chat_message(update.effective_chat.id)
    await update.message.reply_text("Message unpinned!")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
    if not update.message.reply_to_message: return
    start = update.message.reply_to_message.message_id
    end = update.message.message_id
    for msg_id in range(start, end):
        try:
            await context.bot.delete_message(update.effective_chat.id, msg_id)
        except:
            pass

# ==== AI + Image/Sticker Request Handler ====

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()
    if msg in ["hi", "hello", "hey", "sup", "yo", "hii"]:
        await update.message.reply_text("Hey cutie 🥺💖")
    elif any(word in msg for word in ["pic of", "image of", "show me", "photo of"]):
        await update.message.reply_photo("https://source.unsplash.com/600x400/?" + msg.replace(" ", "_"))
    elif any(word in msg for word in ["sticker", "send sticker"]):
        await update.message.reply_sticker("CAACAgUAAxkBAAEBLZxkFz0AAUeBp-lHYJPTwDwVYHZQj_8AAu8DAAIBVm1V4v_Ev5x2fKc1BA")
    else:
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
            await context.bot.send_message(admin_id, f"💎 Private msg from @{user.username or user.first_name}\n\n{update.message.text}")
    elif chat.type in ["group", "supergroup"]:
        link = f"https://t.me/{chat.username}/{update.message.message_id}" if chat.username else "(no link)"
        for admin_id in admins_db:
            await context.bot.send_message(admin_id, f"📨 Group: @{chat.username or chat.title}\n👤 User: @{user.username or user.first_name}\n🔗 {link}\n\n{update.message.text}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn't get that, love 💋")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setwelcome", set_welcome))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("promote", promote))
    application.add_handler(CommandHandler("demote", demote))
    application.add_handler(CommandHandler("pin", pin))
    application.add_handler(CommandHandler("unpin", unpin))
    application.add_handler(CommandHandler("purge", purge))
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
