# bot.py - CINDRELLA final (Moderation + Purge + Permissions)
import os
import logging
import json
import random
import re
import httpx
import asyncio
from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner, ChatMember
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import BadRequest
from functools import partial
from datetime import date, datetime as dt, time as dt_time
from zoneinfo import ZoneInfo
from collections import defaultdict

# ----------------- CONFIG -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
# Bot Admins list from ENV
ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))

# Global Admins (Owner + Admin IDs)
admins_db = ADMIN_IDS.union({OWNER_ID})

app = Flask(__name__)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------- STATE -----------------
usage_count = {"date": str(date.today()), "count": 0}
seen_members = defaultdict(dict)
couples_db = {}

# Random welcome messages
WELCOME_MESSAGES = [
    "Welcome {name}! ✨ Glad you're here — have fun!",
    "Hey {name} 👋 — nice to see you! Introduce yourself 😄",
    "A lovely hello to {name} 🌸 — welcome to the fam!",
    "Oye {name} 😍 — welcome! Ready to vibe?",
    "Welcome, {name}! Make yourself at home 💖"
]

# ---------- Helpers ----------
def _display_name(user):
    name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or getattr(user, "username", None) or "User"
    return str(name)

def mention_html(user_id: int, name: str) -> str:
    safe = (name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f'<a href="tg://user?id={user_id}">{safe}</a>'

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Extract user ID from reply or arguments."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    if context.args:
        arg = context.args[0]
        # Check if username
        if re.fullmatch(r"@\w{5,}", arg):
            try:
                user = await context.bot.get_chat(arg)
                return user.id
            except:
                return None
        # Check if ID
        try:
            return int(arg)
        except:
            return None
    return None

# ------------- PERMISSION CHECKER (CORE LOGIC) -------------
async def check_rights(update: Update, action: str) -> bool:
    """
    Checks permissions dynamically.
    1. Bot Owner/Bot Admin -> Always True.
    2. Group Admin -> Checked against specific rights.
    """
    user = update.effective_user
    chat = update.effective_chat

    # 1. Global Bot Admin Bypass
    if user.id in admins_db:
        return True

    # 2. Private Chat (Admin commands usually don't work here but prevent crash)
    if chat.type == "private":
        return False

    # 3. Check Group Admin Rights
    try:
        member = await chat.get_member(user.id)
        
        # Owner always has rights
        if isinstance(member, ChatMemberOwner):
            return True

        # Admin specific checks
        if isinstance(member, ChatMemberAdministrator):
            if action in ["ban", "kick", "mute", "unban", "unmute"]:
                return member.can_restrict_members
            if action in ["pin", "unpin"]:
                return member.can_pin_messages
            if action in ["purge", "purgeall", "purgegroup"]:
                return member.can_delete_messages
            if action in ["promote", "demote"]:
                return member.can_promote_members
        
        return False # Regular member
    except Exception as e:
        logging.error(f"Permission check error: {e}")
        return False

# ------------- MODERATION COMMANDS -------------
async def mod_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    # 1. Check Permissions
    if not await check_rights(update, action):
        # Silent return mostly, or small warning
        return await update.message.reply_text("❌ You don't have rights to do this.")

    # 2. Get Target User
    target_id = await get_user_id(update, context)
    if not target_id and action not in ["unpin", "purge", "purgegroup"]:
        return await update.message.reply_text("❌ Reply to a user or provide an ID/Username.")

    chat_id = update.effective_chat.id

    # 3. Execute Action
    try:
        # --- BAN ---
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"🔨 Banned {target_id}.")
        
        # --- UNBAN ---
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"✅ Unbanned {target_id}.")

        # --- KICK (Ban + Unban) ---
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, target_id)
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"🦵 Kicked {target_id}.")

        # --- MUTE (Restrict) ---
        elif action == "mute":
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text(f"🔇 Muted {target_id}.")

        # --- UNMUTE ---
        elif action == "unmute":
            # Restore standard permissions
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await update.message.reply_text(f"🔊 Unmuted {target_id}.")

        # --- PIN ---
        elif action == "pin":
            if not update.message.reply_to_message:
                return await update.message.reply_text("❌ Reply to a message to pin it.")
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
            # Optional: notify
            # await update.message.reply_text("📌 Pinned.")

        # --- UNPIN ---
        elif action == "unpin":
            if update.message.reply_to_message:
                # Unpin specific message
                await context.bot.unpin_chat_message(chat_id, update.message.reply_to_message.message_id)
            else:
                # Unpin latest
                await context.bot.unpin_chat_message(chat_id)
            await update.message.reply_text("✅ Unpinned.")

    except BadRequest as e:
        await update.message.reply_text(f"❌ Error: {e.message}")
    except Exception as e:
        await update.message.reply_text(f"❌ System Error: {e}")

# ------------- PURGE COMMANDS -------------
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes messages from reply to current."""
    if not await check_rights(update, "purge"):
        return

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the oldest message to purge down.")

    try:
        start_id = update.message.reply_to_message.message_id
        end_id = update.message.message_id
        chat_id = update.effective_chat.id
        
        # Telegram IDs are sequential. Batch delete.
        msg_ids = list(range(start_id, end_id + 1))
        
        # Delete in chunks of 100
        for i in range(0, len(msg_ids), 100):
            chunk = msg_ids[i:i+100]
            try:
                await context.bot.delete_messages(chat_id, chunk)
            except BadRequest:
                pass # Ignore "message not found" or "too old"
        
        ack = await context.bot.send_message(chat_id, "✅ Purge complete.")
        await asyncio.sleep(3)
        await ack.delete()

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def purge_all_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes ALL messages from a user (Kick method)."""
    if not await check_rights(update, "purgeall"):
        return

    target_id = await get_user_id(update, context)
    if not target_id:
        return await update.message.reply_text("Reply to a user.")
    
    # Safety: Don't purge admins
    if target_id in admins_db:
        return await update.message.reply_text("❌ Cannot purge Bot Admins.")

    try:
        # Revoke_messages=True wipes history
        await context.bot.ban_chat_member(update.effective_chat.id, target_id, revoke_messages=True)
        await update.message.reply_text(f"✅ All messages from {target_id} deleted.")
        await context.bot.unban_chat_member(update.effective_chat.id, target_id)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def purge_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes last 100 messages."""
    if not await check_rights(update, "purgegroup"):
        return

    chat_id = update.effective_chat.id
    curr = update.message.message_id
    msg_ids = list(range(curr - 100, curr + 1))
    
    try:
        await context.bot.delete_messages(chat_id, msg_ids)
        ack = await context.bot.send_message(chat_id, "✅ Group cleanup (Last 100).")
        await asyncio.sleep(5)
        await ack.delete()
    except BadRequest:
        await update.message.reply_text("❌ Messages too old/already deleted.")

# ------------- ADMIN PANEL (OWNER ONLY) -------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only Owner
    if update.effective_user.id != OWNER_ID:
        return 
        
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("➕ Add Bot Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Bot Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
    ]
    today = usage_count["date"]
    usage_info = f"\n📊 Replies Today: {usage_count['count']} (Date: {today})"
    await update.message.reply_text("🤖 **Bot Owner Panel**" + usage_info,
                                    reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != OWNER_ID:
        return

    if query.data == "broadcast":
        await query.message.reply_text("📢 Send me the broadcast message:")
        context.user_data["awaiting_broadcast"] = True
    elif query.data == "add_admin":
        await query.message.reply_text("Send user ID to add as Bot Admin:")
        context.user_data["awaiting_add_admin"] = True
    elif query.data == "remove_admin":
        await query.message.reply_text("Send user ID to remove from Bot Admins:")
        context.user_data["awaiting_remove_admin"] = True
    elif query.data == "list_admins":
        info = [str(aid) for aid in admins_db]
        await query.message.reply_text("Current Bot Admins IDs:\n" + "\n".join(info))

# ------------- COUPLE & AI (UNCHANGED) -------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹—your group manager & AI bestie! Use /admin if you are my owner.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        seen_members[chat_id][member.id] = {"name": _display_name(member), "is_bot": member.is_bot}
        if not member.is_bot:
            msg = random.choice(WELCOME_MESSAGES).format(name=_display_name(member))
            await update.message.reply_text(msg)

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    today = str(date.today())
    if usage_count["date"] != today:
        usage_count["date"] = today
        usage_count["count"] = 0

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "You are CINDRELLA — a bold, sassy, flirty, and smart Gen-Z girl persona. Reply shortly (1-2 lines)."

    # Using Mistral for reliability
    try:
        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": message_text}]
        }
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"]
                usage_count["count"] += 1
                return await update.message.reply_text(reply[:4096])
    except:
        pass

async def couple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    seen_members[chat_id][sender.id] = {"name": _display_name(sender), "is_bot": getattr(sender, "is_bot", False)}
    
    today_str = str(date.today())
    existing = couples_db.get(chat_id)
    if existing and existing.get("date") == today_str:
        (id1, name1), (id2, name2) = existing["pair"]
        return await update.message.reply_text(f"💞 Couple of the Day (still):\n{mention_html(id1, name1)} + {mention_html(id2, name2)}", parse_mode="HTML")

    pool = [(uid, info["name"]) for uid, info in seen_members[chat_id].items() if not info.get("is_bot", False)]
    if len(pool) < 2:
        return await update.message.reply_text("Not enough active members yet! ❤️")
    
    picked = random.sample(pool, 2)
    couples_db[chat_id] = {"date": today_str, "pair": picked}
    ((id1, name1), (id2, name2)) = picked
    return await update.message.reply_text(f"💘 *Couple of the Day* 💘\n{mention_html(id1, name1)} + {mention_html(id2, name2)}", parse_mode="HTML")

async def couple_daily_reset(context: ContextTypes.DEFAULT_TYPE):
    couples_db.clear()

# ------------- TEXT & OWNER PANEL HANDLERS -------------
def register_sender(update):
    try:
        chat_id = update.effective_chat.id
        user = update.effective_user
        if user: seen_members[chat_id][user.id] = {"name": _display_name(user), "is_bot": user.is_bot}
    except: pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_sender(update)
    if not update.message or not update.message.text: return

    # Owner Panel Input Handling
    if update.effective_user.id == OWNER_ID:
        if context.user_data.pop("awaiting_broadcast", None):
            text = update.message.text
            for aid in admins_db:
                try: await context.bot.send_message(aid, f"📢 Broadcast:\n{text}")
                except: pass
            return await update.message.reply_text("✅ Broadcast sent.")

        if context.user_data.pop("awaiting_add_admin", None):
            try:
                admins_db.add(int(update.message.text.strip()))
                await update.message.reply_text("✅ Admin added.")
            except: await update.message.reply_text("❌ Invalid ID.")
            return

        if context.user_data.pop("awaiting_remove_admin", None):
            try:
                uid = int(update.message.text.strip())
                if uid != OWNER_ID:
                    admins_db.discard(uid)
                    await update.message.reply_text("✅ Removed.")
                else: await update.message.reply_text("❌ Cannot remove Owner.")
            except: await update.message.reply_text("❌ Invalid ID.")
            return

    # AI Chat
    msg = update.message.text.lower()
    bot_username = context.bot.username.lower() if context.bot.username else ""
    
    greetings = ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","gn"]
    replies = ["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie"]

    mentioned = update.message.entities and any(e.type == "mention" and bot_username in update.message.text.lower() for e in update.message.entities)
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg in greetings and not mentioned and not replied:
        await update.message.reply_text(random.choice(replies))
    elif mentioned or replied:
        await ai_reply(update, context)

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_sender(update)
    # Basic logging/forwarding logic can remain here if needed, simplified for cleaner code
    pass

# ------------- MAIN -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Basic
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler))

    # Moderation
    for cmd in ["ban", "unban", "kick", "mute", "unmute", "pin", "unpin"]:
        application.add_handler(CommandHandler(cmd, partial(mod_action, action=cmd)))

    # Purge
    application.add_handler(CommandHandler("purge", purge))
    application.add_handler(CommandHandler("purgeall", purge_all_user))
    application.add_handler(CommandHandler("purgegroup", purge_group))

    # Fun
    application.add_handler(CommandHandler("couple", couple_command))

    # Handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Job Queue
    if application.job_queue:
        ist = ZoneInfo("Asia/Kolkata")
        application.job_queue.run_daily(couple_daily_reset, time=dt_time(hour=1, minute=0, tzinfo=ist))

    logging.info("🤖 Bot starting...")
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
