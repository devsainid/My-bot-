# Final Fixed Version of CINDRELLA Bot with Mention/Reply Check + OpenRouter 10 Free Models

import os, logging, json, random
import httpx
from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner
)
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

def is_bot_admin(chat_member):
    return isinstance(chat_member, ChatMemberAdministrator) or isinstance(chat_member, ChatMemberOwner)

async def is_admin(update: Update) -> bool:
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return is_bot_admin(member)
    except:
        return False

async def send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in admins_db:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🔯. How you found me dear 🌹🔯..?", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
            await update.message.reply_text(
                welcome_messages[chat_id].replace("{name}", member.mention_html()), parse_mode="HTML"
            )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    if not (await is_admin(update) or update.effective_user.id in admins_db):
        return
    if not context.args and not update.message.reply_to_message:
        return await update.message.reply_text("Reply to a user or provide a user ID.")
    try:
        user_id = int(context.args[0]) if context.args else update.message.reply_to_message.from_user.id
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
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True
            ))
        elif action == "pin" and update.message.reply_to_message:
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            await context.bot.unpin_chat_message(chat_id)
        elif action == "promote":
            await context.bot.promote_chat_member(chat_id, user_id, can_manage_chat=True, can_change_info=True,
                                                  can_delete_messages=True, can_invite_users=True,
                                                  can_restrict_members=True, can_pin_messages=True,
                                                  can_promote_members=True)
        elif action == "demote":
            await context.bot.promote_chat_member(chat_id, user_id, can_manage_chat=False, can_change_info=False,
                                                  can_delete_messages=False, can_invite_users=False,
                                                  can_restrict_members=False, can_pin_messages=False,
                                                  can_promote_members=False)
        elif action == "purge" and update.message.reply_to_message:
            for msg_id in range(update.message.reply_to_message.message_id, update.message.message_id):
                try: await context.bot.delete_message(chat_id, msg_id)
                except: pass
        await update.message.reply_text(f"✅ Action '{action}' done.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins_db:
        return
    keyboard = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        keyboard += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
    await update.message.reply_text("Welcome to Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in admins_db:
        return

    if query.data == "broadcast":
        await query.message.reply_text("📢 Send me the broadcast message:")
        context.user_data["awaiting_broadcast"] = True
    elif query.data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add as admin:")
        context.user_data["awaiting_add_admin"] = True
    elif query.data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove from admins:")
        context.user_data["awaiting_remove_admin"] = True
    elif query.data == "list_admins":
        await query.message.reply_text(f"Current Admins:\n{json.dumps(list(admins_db), indent=2)}")

openrouter_models = [
    "openchat/openchat-3.5", "gryphe/mythomax-l2-13b",
    "undi95/toppy-m-7b", "mistralai/mixtral-8x7b",
    "nousresearch/nous-capybara-7b", "nousresearch/nous-hermes-2-mixtral",
    "meta-llama/llama-3-8b-instruct", "intel/neural-chat-7b",
    "mistralai/mistral-7b-instruct", "openrouter/cinematika-7b"
]

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        model = random.choice(openrouter_models)
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are CINDRELLA, a 16-year-old sweet, kind, emotionally intelligent best friend. Respond in realistic English."},
                {"role": "user", "content": update.message.text}
            ]
        }
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            reply = res.json()["choices"][0]["message"]["content"]
            await update.message.reply_text(reply[:4096])
    except:
        await update.message.reply_text("I'm feeling off right now, try again later 💔")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    msg = message.text.lower()
    bot_username = context.bot.username.lower()

    if context.user_data.get("awaiting_broadcast"):
        context.user_data.pop("awaiting_broadcast")
        for admin_id in admins_db:
            try: await context.bot.send_message(chat_id=admin_id, text=f"📢 Broadcast:\n{message.text}")
            except: pass
        await message.reply_text("✅ Broadcast sent.")
        return

    if context.user_data.get("awaiting_add_admin"):
        context.user_data.pop("awaiting_add_admin")
        try:
            admins_db.add(int(message.text.strip()))
            await message.reply_text("✅ Admin added.")
        except:
            await message.reply_text("❌ Invalid ID.")
        return

    if context.user_data.get("awaiting_remove_admin"):
        context.user_data.pop("awaiting_remove_admin")
        try:
            rem_id = int(message.text.strip())
            if rem_id != OWNER_ID:
                admins_db.discard(rem_id)
                await message.reply_text("✅ Admin removed.")
            else:
                await message.reply_text("❌ Cannot remove owner.")
        except:
            await message.reply_text("❌ Invalid ID.")
        return

    mentioned = message.entities and any(e.type == "mention" and bot_username in message.text.lower() for e in message.entities)
    replied_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id

    greetings = ["hi", "hello", "hey", "yo", "sup", "hii", "heyy", "heya"]
    replies = ["Hey cutie 🥺💖", "Hi love 💕", "Hello darling 🌸", "Yo! how’s your day going? ☀️", "Hiiiii bestie 💖", "Hey sunshine 🌼", "Hi there 👋", "Sup sweetie 🍬"]

    if msg in greetings and not message.entities and not message.reply_to_message:
        await message.reply_text(random.choice(replies))
    elif mentioned or replied_to_bot:
        await ai_reply(update, context)

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    bot_username = context.bot.username.lower()

    if chat.type == "private":
        for admin_id in admins_db:
            await context.bot.send_message(admin_id, f"📩 Private msg from @{user.username or user.first_name}\n\n{message.text}")
    elif chat.type in ["group", "supergroup"]:
        mentioned = message.entities and any(e.type == "mention" and bot_username in message.text.lower() for e in message.entities)
        replied_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id
        if mentioned or replied_to_bot:
            link = f"https://t.me/{chat.username}/{message.message_id}" if chat.username else ""
            for admin_id in admins_db:
                await context.bot.send_message(admin_id, f"📨 Group: @{chat.username or chat.title}\n👤 User: @{user.username or user.first_name}\n🔗 {link}\n\n{message.text}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn't get that, love 💋")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setwelcome", set_welcome))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler))
    for cmd in ["ban", "unban", "kick", "mute", "unmute", "pin", "unpin", "promote", "demote", "purge"]:
        application.add_handler(CommandHandler(cmd, lambda u, c, cmd=cmd: admin_command(u, c, cmd)))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
