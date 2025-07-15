import os, logging, json, random, re, datetime
import httpx
from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner, ChatMember
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from functools import partial

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))

admins_db = ADMIN_IDS.union({OWNER_ID})
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

welcome_messages = {}
usage_count = {"date": str(datetime.date.today()), "count": 0}

async def has_proper_admin_power(member: ChatMember) -> bool:
    return (
        isinstance(member, ChatMemberAdministrator) and
        member.can_restrict_members and
        member.can_manage_chat
    ) or isinstance(member, ChatMemberOwner)

async def is_admin(update: Update) -> bool:
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return await has_proper_admin_power(member)
    except:
        return False

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    if context.args:
        arg = context.args[0]
        if re.fullmatch(r"@\w{5,}", arg):
            try:
                user = await context.bot.get_chat(arg)
                return user.id
            except:
                return None
        try:
            return int(arg)
        except:
            return None
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🕯️—your power‑packed AI & group management assistant! Promote me or chat anytime 💕",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "supergroup": return
    if not (await is_admin(update) or update.effective_user.id in admins_db): return
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
                welcome_messages[chat_id].replace("{name}", member.mention_html()),
                parse_mode="HTML"
            )

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
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are CINDRELLA, a sweet, kind 15‑year‑old anime gamer. Always respond in user’s language like a real friend."},
                {"role": "user", "content": update.message.text}
            ]
        }
        async with httpx.AsyncClient() as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        reply = res.json()["choices"][0]["message"]["content"]

        today = str(datetime.date.today())
        if usage_count["date"] != today:
            usage_count["date"] = today
            usage_count["count"] = 0
        usage_count["count"] += 1

        await update.message.reply_text(reply[:4096])
    except Exception as e:
        logging.error("OpenRouter error", exc_info=e)
        await update.message.reply_text("I'm being upgraded, try again shortly 💖")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    if not (await is_admin(update) or update.effective_user.id in admins_db):
        return
    user_id = await get_user_id(update, context)
    if not user_id:
        return await update.message.reply_text("Reply to a user or provide a valid username/ID.")

    chat_id = update.effective_chat.id
    try:
        if action == "ban": await context.bot.ban_chat_member(chat_id, user_id)
        elif action == "unban": await context.bot.unban_chat_member(chat_id, user_id)
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
        elif action == "mute": await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions())
        elif action == "unmute":
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
        elif action == "pin" and update.message.reply_to_message:
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin": await context.bot.unpin_chat_message(chat_id)
        elif action == "promote":
            await context.bot.promote_chat_member(chat_id, user_id,
                can_manage_chat=True, can_change_info=True,
                can_delete_messages=True, can_invite_users=True,
                can_restrict_members=True, can_pin_messages=True,
                can_promote_members=False, is_anonymous=False)
        elif action == "demote":
            await context.bot.promote_chat_member(chat_id, user_id,
                can_manage_chat=False, can_change_info=False,
                can_delete_messages=False, can_invite_users=False,
                can_restrict_members=False, can_pin_messages=False,
                can_promote_members=False, is_anonymous=True)
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
    buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
        ]
    buttons.append([InlineKeyboardButton("📋 List Admins", callback_data="list_admins")])
    today = usage_count["date"]
    usage_info = f"\n📊 Replies Today: {usage_count['count']} (Date: {today})"
    await update.message.reply_text("Welcome to Admin Panel:" + usage_info,
                                    reply_markup=InlineKeyboardMarkup(buttons))

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
        info = []
        for aid in admins_db:
            try:
                user = await context.bot.get_chat(aid)
                uname = f"@{user.username}" if user.username else user.full_name
                info.append(f"{uname} — {aid}")
            except:
                info.append(f"ID: {aid} (username unavailable)")
        await query.message.reply_text("Current Bot Admins:\n\n" + "\n".join(info))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()
    bot_username = context.bot.username.lower()

    if context.user_data.pop("awaiting_broadcast", None):
        text = update.message.text
        for aid in admins_db:
            try:
                await context.bot.send_message(aid, f"📢 Broadcast:\n{text}")
            except: pass
        await update.message.reply_text("✅ Broadcast sent.")
        return

    if context.user_data.pop("awaiting_add_admin", None):
        try:
            uid = int(update.message.text.strip())
            admins_db.add(uid)
            await update.message.reply_text("✅ Admin added.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        return

    if context.user_data.pop("awaiting_remove_admin", None):
        try:
            uid = int(update.message.text.strip())
            if uid != OWNER_ID:
                admins_db.discard(uid)
                await update.message.reply_text("✅ Admin removed.")
            else:
                await update.message.reply_text("❌ Cannot remove owner.")
        except:
            await update.message.reply_text("❌ Invalid ID.")
        return

    greetings = ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","good morning","gn","good night"]
    replies = ["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie","Hey sunshine","Hi there 👋"," what’s up buddy","Sup sweetie 🍬"]
    mentioned = update.message.entities and any(e.type=="mention" and bot_username in update.message.text.lower() for e in update.message.entities)
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg in greetings and not mentioned and not replied:
        await update.message.reply_text(random.choice(replies))
    elif mentioned or replied:
        await ai_reply(update, context)

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    bot_username = context.bot.username.lower()

    if chat.type == "private":
        for aid in admins_db:
            await context.bot.send_message(aid, f"📩 Private from @{user.username or user.first_name}:\n{text}")
    elif chat.type in ["group","supergroup"]:
        mentioned = update.message.entities and any(e.type=="mention" and bot_username in text.lower() for e in update.message.entities)
        replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        if mentioned or replied:
            link = f"https://t.me/{chat.username}/{update.message.message_id}" if chat.username else ""
            for aid in admins_db:
                await context.bot.send_message(aid, f"📨 @{chat.username or chat.title} by @{user.username or user.first_name}\n🔗{link}\n\n{text}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn't get that")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwelcome", set_welcome))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    for cmd in ["ban","unban","kick","mute","unmute","pin","unpin","promote","demote","purge"]:
        app.add_handler(CommandHandler(cmd, partial(admin_command, action=cmd)))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), group=1)
    app.add_handler(MessageHandler(filters.COMMAND, unknown), group=2)

    app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT",10000)), webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
