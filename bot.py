import os
import logging
import httpx
import json
from flask import Flask, request
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

ADMINS = [OWNER_ID]  # Add other admin IDs here
known_chats = set()
if os.path.exists("chats.txt"):
    with open("chats.txt", "r") as f:
        known_chats = set(filter(None, map(str.strip, f.readlines())))

app = ApplicationBuilder().token(BOT_TOKEN).build()
logging.basicConfig(level=logging.INFO)
flask_app = Flask(__name__)

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are CINDRELLA, a 16-year-old girl. You are sweet, kind, emotionally intelligent and speak only English. You talk like a real person and connect emotionally like a best friend."
}

async def generate_reply(user_input):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openchat/openchat-3.5-1210",
        "messages": [SYSTEM_PROMPT, {"role": "user", "content": user_input}]
    }
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "Oops, something went wrong."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = InlineKeyboardButton("➕ Add me to your group", url="https://t.me/YOUR_CINDRELLABOT?startgroup=true")
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🕯️🕯️. How you found me dear 🌹🕯️🕯️..?",
        reply_markup=InlineKeyboardMarkup([[button]])
    )

def save_chat_id(chat_id):
    if str(chat_id) not in known_chats:
        known_chats.add(str(chat_id))
        with open("chats.txt", "a") as f:
            f.write(f"{chat_id}\n")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Action received.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await update.message.reply_text("Unauthorized")

    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if user_id == OWNER_ID:
        buttons.append([InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")])
        buttons.append([InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")])
        buttons.append([InlineKeyboardButton("📋 List Admins", callback_data="list_admins")])

    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))

async def broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send message to broadcast:")
    context.user_data["awaiting_broadcast"] = True

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = msg.chat
    user = msg.from_user

    if user.id != OWNER_ID:
        forward_text = f"📩 Message from @{user.username or user.first_name} (ID: {user.id})\n"
        if chat.type in ["group", "supergroup"]:
            chat_link = f"https://t.me/{chat.username}" if chat.username else "Private group"
            msg_link = f"https://t.me/c/{str(chat.id)[4:]}/{msg.message_id}" if str(chat.id).startswith("-100") else "N/A"
            forward_text += f"👥 Group: {chat.title}\n🔗 Group Link: {chat_link}\n🔗 Message Link: {msg_link}\n"
        else:
            forward_text += "🧑‍💻 Chat Type: Private\n"

        forward_text += f"\n💬 Message:\n{msg.text}"
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(admin_id, forward_text)
            except:
                pass

    lowered = msg.text.lower()
    if any(x in lowered for x in ["cat pic", "send me cat", "pic of cat"]):
        await msg.reply_photo("https://cataas.com/cat")
    else:
        reply = await generate_reply(msg.text)
        await msg.reply_text(reply)

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        try:
            await update.effective_chat.promote_member(
                update.message.reply_to_message.from_user.id,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True,
            )
            await update.message.reply_text("User promoted ✅")
        except Exception as e:
            await update.message.reply_text(f"Failed to promote: {e}")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        try:
            await update.effective_chat.promote_member(
                update.message.reply_to_message.from_user.id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                is_anonymous=False,
            )
            await update.message.reply_text("User demoted ❌")
        except Exception as e:
            await update.message.reply_text(f"Failed to demote: {e}")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                update.message.reply_to_message.from_user.id,
                ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text("User muted 🔇")
        except Exception as e:
            await update.message.reply_text(f"Failed to mute: {e}")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMINS and update.message.reply_to_message:
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                update.message.reply_to_message.from_user.id,
                ChatPermissions(can_send_messages=True)
            )
            await update.message.reply_text("User unmuted 🔊")
        except Exception as e:
            await update.message.reply_text(f"Failed to unmute: {e}")

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CommandHandler("promote", promote))
app.add_handler(CommandHandler("demote", demote))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply_to_user))

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    app.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=f"{WEBHOOK_URL}/webhook"
        )
