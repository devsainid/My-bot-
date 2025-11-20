# bot.py - CINDRELLA final
import os
import logging
import json
import random
import re
import datetime
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
from datetime import date, datetime as dt, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

# ----------------- CONFIG -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))

admins_db = ADMIN_IDS.union({OWNER_ID})
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ----------------- STATE -----------------
usage_count = {"date": str(date.today()), "count": 0}

# seen members pool per chat (id -> {name, is_bot})
seen_members = defaultdict(dict)

# couple per-chat store
couples_db = {}
# couples_db[chat_id] = {"date": "YYYY-MM-DD", "pair": ((id1,name1),(id2,name2))}

# random welcome messages
WELCOME_MESSAGES = [
    "Welcome {name}! ✨ Glad you're here — have fun!",
    "Hey {name} 👋 — nice to see you! Introduce yourself 😄",
    "A lovely hello to {name} 🌸 — welcome to the fam!",
    "Oye {name} 😍 — welcome! Ready to vibe?",
    "Yay! {name} joined — bring snacks 🍪 and good mood 😏",
    "Welcome, {name}! Make yourself at home 💖",
    "What's up {name}? Get ready for chaos and cuddles 😂",
    "Oh hello {name} — you're in the best group now 😎",
    "Shoutout to {name} for joining! 🎉 Stay fun and kind.",
    "{name} has arrived — time to make memories 🥳"
]

# ---------- Helpers ----------
def _display_name(user):
    # prefer full name or first_name or username
    name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or getattr(user, "username", None) or "User"
    return str(name)

def mention_html(user_id: int, name: str) -> str:
    safe = (name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f'<a href="tg://user?id={user_id}">{safe}</a>'

# ------------- Admin checks --------------
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

# ------------- Start ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹🕯️—your power-packed AI & group management assistant! Promote me or chat anytime 💕",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------- Welcome (auto) -------------
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        # register member into seen pool
        seen_members[chat_id][member.id] = {
            "name": _display_name(member),
            "is_bot": getattr(member, "is_bot", False)
        }
        # pick random welcome and send
        name = _display_name(member)
        msg = random.choice(WELCOME_MESSAGES).format(name=name)
        try:
            await update.message.reply_text(msg)
        except Exception:
            # fallback plain reply
            await update.message.reply_text(f"Welcome {name}!")

# ------------- OpenRouter AI reply -------------
openrouter_models = [
    "cyberagent/cyberalpha-7b",
    "mistralai/mixtral-8x7b",
    "meta-llama/llama-3-8b-instruct",
    "gryphe/mythomax-l2-13b",
    "openchat/openchat-3.5",
    "mistralai/mistral-7b-instruct",
    "openrouter/cinematika-7b",
    "undi95/toppy-m-7b",
    "intel/neural-chat-7b",
    "nousresearch/nous-capybara-7b"
]

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    user_lang = update.message.from_user.language_code or "en"

    today = str(date.today())
    if usage_count["date"] != today:
        usage_count["date"] = today
        usage_count["count"] = 0

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are CINDRELLA — a bold, sassy, flirty, and smart Gen-Z girl persona. "
        "Reply in the same language as the user, keep replies short (1-2 lines), helpful, and give a next-step suggestion. "
        "Do not say you're an AI or ChatGPT. Always be playful but respectful."
    )

    for model in openrouter_models:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text}
                ]
            }
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    resp_json = res.json()
                    # defensive: locate content
                    reply = ""
                    try:
                        reply = resp_json["choices"][0]["message"]["content"]
                    except:
                        # fallback to simple text extraction
                        reply = resp_json.get("choices", [{}])[0].get("text", "") or "..."
                    usage_count["count"] += 1
                    return await update.message.reply_text(reply[:4096])
                else:
                    logging.warning(f"{model} failed: {res.status_code} — {res.text}")
        except Exception as e:
            logging.warning(f"Model {model} error: {e}")
            continue

    await update.message.reply_text("I'm being upgraded, try again shortly 💖")

# ------------- Admin commands & panel -------------
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    if not (await is_admin(update) or update.effective_user.id in admins_db):
        return
    user_id = await get_user_id(update, context)
    if not user_id:
        return await update.message.reply_text("Reply to a user or provide a valid username/ID.")

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
                can_send_other_messages=True, can_add_web_page_previews=True))
        elif action == "pin" and update.message.reply_to_message:
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            await context.bot.unpin_chat_message(chat_id)
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
                can_promote_members=False, is_anonymous=False)
        elif action == "purge" and update.message.reply_to_message:
            for msg_id in range(update.message.reply_to_message.message_id, update.message.message_id):
                try:
                    await context.bot.delete_message(chat_id, msg_id)
                except:
                    pass

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

# ------------- Couple of the Day feature -------------
async def pick_two_random(chat_id: int):
    pool = [
        (uid, info["name"])
        for uid, info in seen_members[chat_id].items()
        if not info.get("is_bot", False)
    ]
    if len(pool) < 2:
        return None
    pair = random.sample(pool, 2)
    return (pair[0], pair[1])

async def couple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user

    # register sender
    seen_members[chat_id][sender.id] = {
        "name": _display_name(sender),
        "is_bot": getattr(sender, "is_bot", False)
    }

    today_str = str(date.today())

    # if exists for today -> tag same pair & wishes
    existing = couples_db.get(chat_id)
    if existing and existing.get("date") == today_str and existing.get("pair"):
        (id1, name1), (id2, name2) = existing["pair"]
        text = (
            f"💞 Couple of the Day (still):\n"
            f"{mention_html(id1, name1)}\n"
            f"{mention_html(id2, name2)}\n\n"
            f"Lots of love and wishes! 😘🎉\n"
            f"May your day be full of smiles ❤️"
        )
        return await update.message.reply_text(text, parse_mode="HTML")

    # pick fresh pair
    picked = await pick_two_random(chat_id)
    if not picked:
        # fallback: add chat admins to pool and retry
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            for a in admins:
                u = a.user
                seen_members[chat_id][u.id] = {"name": _display_name(u), "is_bot": u.is_bot}
            picked = await pick_two_random(chat_id)
        except Exception:
            picked = None

    if not picked:
        return await update.message.reply_text("Not enough active members yet to make a couple. Wait for more people to chat ❤️")

    ((id1, name1), (id2, name2)) = picked
    couples_db[chat_id] = {"date": today_str, "pair": ((id1, name1), (id2, name2))}

    wishes = [
        "Awwww this is cute 😍",
        "May your chats be full of love 💖",
        "Couple vibes ON 🔥",
        "Tag each other and pose for the profile pic 😏",
        "Loads of kisses and good luck 😘",
        "Stay sweet and silly together 💫"
    ]
    wish_text = "\n".join(random.sample(wishes, k=min(3, len(wishes))))

    text = (
        f"💘 *Couple of the Day* 💘\n"
        f"{mention_html(id1, name1)}  +  {mention_html(id2, name2)}\n\n"
        f"{wish_text}\n\n"
        f"Use /couple again to shower them with love today! 🌹"
    )
    return await update.message.reply_text(text, parse_mode="HTML")

# daily reset job at 1:00 AM IST
async def couple_daily_reset(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Running daily couple reset (1:00 AM IST)")
    couples_db.clear()
    # keep seen_members to preserve pool
    # optionally you can prune old seen_members here

# ------------- Register senders helper (called in message handlers) -------------
def register_sender_from_update(update: Update):
    try:
        chat_id = update.effective_chat.id
        user = update.effective_user
        if user:
            seen_members[chat_id][user.id] = {
                "name": _display_name(user),
                "is_bot": getattr(user, "is_bot", False)
            }
    except Exception:
        pass

# ------------- Message handlers -------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # register sender for couple pool
    register_sender_from_update(update)

    msg = update.message.text.lower()
    bot_username = context.bot.username.lower()

    if context.user_data.pop("awaiting_broadcast", None):
        text = update.message.text
        for aid in admins_db:
            try:
                await context.bot.send_message(aid, f"📢 Broadcast:\n{text}")
            except:
                pass
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
    replies = ["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie","Hey sunshine","Hi there 👋","what’s up buddy","Sup sweetie 🍬"]

    mentioned = update.message.entities and any(
        e.type == "mention" and bot_username in update.message.text.lower()
        for e in update.message.entities
    )
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg in greetings and not mentioned and not replied:
        await update.message.reply_text(random.choice(replies))
    elif mentioned or replied:
        await ai_reply(update, context)

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # register sender for couple pool
    register_sender_from_update(update)

    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text or ""
    bot_username = context.bot.username.lower()

    if chat.type == "private":
        for aid in admins_db:
            try:
                await context.bot.send_message(aid, f"📩 Private from @{user.username or user.first_name}:\n{text}")
            except:
                pass

    elif chat.type in ["group", "supergroup"]:
        mentioned = update.message.entities and any(e.type=="mention" and bot_username in text.lower() for e in update.message.entities)
        replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

        if mentioned or replied:
            link = f"https://t.me/{chat.username}/{update.message.message_id}" if chat.username else ""
            for aid in admins_db:
                try:
                    await context.bot.send_message(
                        aid,
                        f"📨 @{chat.username or chat.title} by @{user.username or user.first_name}\n🔗{link}\n\n{text}"
                    )
                except:
                    pass

# ------------- MAIN & Dispatcher -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler))

    # moderation commands
    for cmd in ["ban","unban","kick","mute","unmute","pin","unpin","promote","demote","purge"]:
        application.add_handler(CommandHandler(cmd, partial(admin_command, action=cmd)))

    # couple command
    application.add_handler(CommandHandler("couple", couple_command))

    # message handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message), group=0)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), group=1)

    # Schedule daily reset at 1:00 AM IST
    ist = ZoneInfo("Asia/Kolkata")
    application.job_queue.run_daily(couple_daily_reset, time=dt_time(hour=1, minute=0, tzinfo=ist))

    # Run webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
