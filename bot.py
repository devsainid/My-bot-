# bot.py - CINDRELLA final (Moderation + Purge + Permissions + Pro Features + Welcome Card)
import os
import logging
import json
import random
import re
import httpx
import asyncio
import time
import urllib.parse
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

# Naye State Variables
warnings_db = defaultdict(lambda: defaultdict(int)) # chat_id -> user_id -> warning count
afk_db = {} # user_id -> {"reason": reason, "time": timestamp, "name": name}
blacklist_db = defaultdict(set) # chat_id -> set of blacklisted words
filters_db = defaultdict(dict) # chat_id -> word -> reply
rules_db = {} # chat_id -> rules text
spam_tracker = defaultdict(lambda: defaultdict(list)) # chat_id -> user_id -> list of timestamps

# Random welcome messages
WELCOME_MESSAGES = [
    "Welcome {name}! ✨ Glad you're here — have fun!",
    "Hey {name} 👋 — nice to see you! Introduce yourself 😄",
    "A lovely hello to {name} 🌸 — welcome to the fam!",
    "Oye {name} 😍 — welcome! Ready to vibe?",
    "Welcome, {name}! Make yourself at home 💖"
]

# Fallback welcome GIF
WELCOME_IMAGE_URL = "https://i.pinimg.com/originals/7e/15/d4/7e15d482bb4bc0a8523a5e840a15865d.gif"
# Background for Welcome Card
WELCOME_BG_URL = "https://i.pinimg.com/originals/a0/bf/c5/a0bfc5df23c0b05b6e680ad5f1a5bbdc.jpg"

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

# ------------- PERMISSION CHECKER (CORE LOGIC) -------------
async def check_rights(update: Update, action: str) -> bool:
    """
    Checks permissions dynamically.
    """
    user = update.effective_user
    chat = update.effective_chat

    if user.id in admins_db:
        return True

    if chat.type == "private":
        return False

    try:
        member = await chat.get_member(user.id)
        
        if isinstance(member, ChatMemberOwner):
            return True

        if isinstance(member, ChatMemberAdministrator):
            if action in ["ban", "kick", "mute", "unban", "unmute", "warn", "unwarn"]:
                return member.can_restrict_members
            if action in ["pin", "unpin"]:
                return member.can_pin_messages
            if action in ["purge", "purgeall", "purgegroup", "filter", "blacklist", "rules"]:
                return member.can_delete_messages
            if action in ["promote", "demote"]:
                return member.can_promote_members
        
        return False
    except Exception as e:
        logging.error(f"Permission check error: {e}")
        return False

# ------------- MODERATION COMMANDS -------------
async def mod_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    action = update.message.text.split()[0][1:].split('@')[0].lower()
    
    if not await check_rights(update, action):
        return await update.message.reply_text("❌ You don't have Admin rights to do this.")

    target_id = await get_user_id(update, context)
    if not target_id and action not in ["unpin"]:
        return await update.message.reply_text("❌ Reply to a user or provide an ID/Username.")

    chat_id = update.effective_chat.id

    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"🔨 Banned {target_id}.")
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"✅ Unbanned {target_id}.")
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, target_id)
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(f"🦵 Kicked {target_id}.")
        elif action == "mute":
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await update.message.reply_text(f"🔇 Muted {target_id}.")
        elif action == "unmute":
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(
                    can_send_messages=True, 
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True, 
                    can_add_web_page_previews=True
                )
            )
            await update.message.reply_text(f"🔊 Unmuted {target_id}.")
        elif action == "pin":
            if not update.message.reply_to_message:
                return await update.message.reply_text("❌ Reply to a message to pin it.")
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            if update.message.reply_to_message:
                await context.bot.unpin_chat_message(chat_id, update.message.reply_to_message.message_id)
            else:
                await context.bot.unpin_chat_message(chat_id)
            await update.message.reply_text("✅ Unpinned.")
        elif action == "promote":
            await context.bot.promote_chat_member(
                chat_id, target_id, can_manage_chat=True, can_delete_messages=True,
                can_manage_video_chats=True, can_restrict_members=True,
                can_promote_members=False, can_change_info=True,
                can_invite_users=True, can_pin_messages=True
            )
            await update.message.reply_text(f"🌟 Promoted {target_id} to Admin.")

    except BadRequest as e:
        await update.message.reply_text(f"❌ Error: {e.message}")
    except Exception as e:
        await update.message.reply_text(f"❌ System Error: {e}")

# ------------- PURGE COMMANDS -------------
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purge"):
        return await update.message.reply_text("❌ Admin rights required.")

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to the oldest message to purge down.")

    try:
        start_id = update.message.reply_to_message.message_id
        end_id = update.message.message_id
        chat_id = update.effective_chat.id
        msg_ids = list(range(start_id, end_id + 1))
        
        for i in range(0, len(msg_ids), 100):
            chunk = msg_ids[i:i+100]
            try: await context.bot.delete_messages(chat_id, chunk)
            except BadRequest: pass 
        
        ack = await context.bot.send_message(chat_id, "✅ Purge complete.")
        await asyncio.sleep(3)
        await ack.delete()
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def purge_all_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgeall"):
        return await update.message.reply_text("❌ Admin rights required.")

    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("Reply to a user.")
    if target_id in admins_db: return await update.message.reply_text("❌ Cannot purge Bot Admins.")

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target_id, revoke_messages=True)
        await update.message.reply_text(f"✅ All messages from {target_id} deleted.")
        await context.bot.unban_chat_member(update.effective_chat.id, target_id)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def purge_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgegroup"):
        return await update.message.reply_text("❌ Admin rights required.")

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

# ------------- PRO FEATURES -------------
async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌹 **CINDRELLA COMMANDS** 🌹

**🛠 Moderation:**
`/ban` - Ban a user
`/unban` - Unban a user
`/kick` - Kick a user
`/mute` - Mute a user
`/unmute` - Unmute a user
`/pin` - Pin a message
`/unpin` - Unpin a message
`/promote` - Promote a user to Admin
`/warn` - Warn a user (3 warns = mute/kick)
`/unwarn` - Remove a warning

**🧹 Purge:**
`/purge` - Delete messages from reply to current
`/purgeall` - Delete all messages of a user
`/purgegroup` - Delete last 100 messages

**🛡 Group Management:**
`/addblacklist <word>` - Auto delete bad word
`/rmblacklist <word>` - Remove word from blacklist
`/blocklist` - Show all blacklisted words
`/addfilter <word> <reply>` - Set custom bot reply
`/rmfilter <word>` - Remove custom filter
`/setrules <text>` - Set group rules
`/rules` - Show group rules

**✨ Fun & Utils:**
`/couple` - Couple of the day!
`/afk [reason]` - Set AFK status
`/anime [name]` - Search for an anime
`/admin` - Bot Owner panel
`/commands` - Show this list
    """
    await update.message.reply_text(text, parse_mode="Markdown")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "warn"): 
        return await update.message.reply_text("❌ Admin rights required.")
    
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ Reply to a user to warn.")
    
    chat_id = update.effective_chat.id

    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_id in admins_db or target_member.status in ['administrator', 'creator']:
            return await update.message.reply_text("❌ Cannot warn an Admin.")
    except Exception:
        pass

    warnings_db[chat_id][target_id] += 1
    count = warnings_db[chat_id][target_id]
    
    reason = " ".join(context.args) if context.args else "No reason given."
    
    if count >= 3:
        await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=False))
        warnings_db[chat_id][target_id] = 0
        await update.message.reply_text(f"🛑 User {target_id} reached 3 warnings and is now MUTED!")
    else:
        await update.message.reply_text(f"⚠️ Warned {target_id}! ({count}/3)\nReason: {reason}")

async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "unwarn"): 
        return await update.message.reply_text("❌ Admin rights required.")
        
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ Reply to a user.")
    
    chat_id = update.effective_chat.id
    if warnings_db[chat_id][target_id] > 0:
        warnings_db[chat_id][target_id] -= 1
        await update.message.reply_text(f"✅ Removed 1 warning from {target_id}. Current warns: {warnings_db[chat_id][target_id]}/3")
    else:
        await update.message.reply_text("✅ User has 0 warnings.")

async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "rules"): 
        return await update.message.reply_text("❌ Admin rights required.")
    text = update.message.text.split(None, 1)
    if len(text) < 2: return await update.message.reply_text("❌ Please provide rules text.")
    rules_db[update.effective_chat.id] = text[1]
    await update.message.reply_text("✅ Rules updated!")

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = rules_db.get(update.effective_chat.id, "No rules set yet.")
    await update.message.reply_text(f"📜 **Group Rules:**\n\n{rules}", parse_mode="Markdown")

async def add_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): 
        return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    word = context.args[0].lower()
    blacklist_db[update.effective_chat.id].add(word)
    await update.message.reply_text(f"✅ Word '{word}' added to blacklist.")

async def rm_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): 
        return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    word = context.args[0].lower()
    blacklist_db[update.effective_chat.id].discard(word)
    await update.message.reply_text(f"✅ Word '{word}' removed from blacklist.")

async def show_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): 
        return await update.message.reply_text("❌ Admin rights required.")
    words = blacklist_db[update.effective_chat.id]
    if not words:
        return await update.message.reply_text("✅ Blocklist ekdum khali hai.")
    text = "🚫 **Blocked Words:**\n" + "\n".join([f"- `{w}`" for w in words])
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): 
        return await update.message.reply_text("❌ Admin rights required.")
    text = update.message.text.split(None, 2)
    if len(text) < 3: return await update.message.reply_text("❌ Format: /addfilter <word> <reply>")
    word, reply = text[1].lower(), text[2]
    filters_db[update.effective_chat.id][word] = reply
    await update.message.reply_text(f"✅ Filter added for '{word}'.")

async def rm_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): 
        return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    word = context.args[0].lower()
    filters_db[update.effective_chat.id].pop(word, None)
    await update.message.reply_text(f"✅ Filter removed for '{word}'.")

async def set_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = " ".join(context.args) if context.args else "No reason"
    afk_db[update.effective_user.id] = {"reason": reason, "time": dt.now(), "name": _display_name(update.effective_user)}
    await update.message.reply_text(f"💤 {_display_name(update.effective_user)} is now AFK. Reason: {reason}")

async def get_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("❌ Search naam toh batao! (e.g., /anime naruto)")
    query = " ".join(context.args)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://api.jikan.moe/v4/anime?q={query}&limit=1")
            data = res.json()
            if data['data']:
                anime = data['data'][0]
                title = anime['title']
                episodes = anime.get('episodes', 'N/A')
                score = anime.get('score', 'N/A')
                status = anime.get('status', 'N/A')
                url = anime['url']
                text = f"🎬 **{title}**\n\n📊 Score: {score}\n🎞 Episodes: {episodes}\n🔄 Status: {status}\n\n🔗 [More Info]({url})"
                await update.message.reply_text(text, parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Anime not found!")
    except Exception as e:
        await update.message.reply_text("❌ API error.")

# ------------- ADMIN PANEL (OWNER ONLY) -------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Only the Bot Owner can use this.")
        
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
    
    if user_id != OWNER_ID: return

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

# ------------- COUPLE & AI & WELCOME -------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(
        "Hey, I'm CINDRELLA 🌹—your group manager & AI bestie!\nType /commands to see what I can do!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat = update.effective_chat
    
    try:
        member_count = await chat.get_member_count()
    except:
        member_count = "New"

    for member in update.message.new_chat_members:
        seen_members[chat_id][member.id] = {"name": _display_name(member), "is_bot": member.is_bot}
        if not member.is_bot:
            msg = random.choice(WELCOME_MESSAGES).format(name=_display_name(member))
            
            try:
                photos = await context.bot.get_user_profile_photos(member.id, limit=1)
                avatar_url = "https://i.ibb.co/4pDNDk1/avatar.png" 
                
                if photos.total_count > 0:
                    file_id = photos.photos[0][-1].file_id
                    file_info = await context.bot.get_file(file_id)
                    avatar_url = file_info.file_path
                
                safe_name = urllib.parse.quote(_display_name(member))
                safe_chat = urllib.parse.quote(chat.title or "Our Group")
                safe_avatar = urllib.parse.quote(avatar_url)
                safe_bg = urllib.parse.quote(WELCOME_BG_URL)
                
                card_url = f"https://api.popcat.xyz/welcomecard?background={safe_bg}&text1={safe_name}&text2=Welcome+to+{safe_chat}&text3=Member+{member_count}&avatar={safe_avatar}"
                
                await context.bot.send_photo(chat_id=chat_id, photo=card_url, caption=msg)
            
            except Exception as e:
                logging.error(f"Welcome Card Error: {e}")
                try: await context.bot.send_animation(chat_id=chat_id, animation=WELCOME_IMAGE_URL, caption=msg)
                except: await update.message.reply_text(msg)

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    today = str(date.today())
    if usage_count["date"] != today:
        usage_count["date"] = today
        usage_count["count"] = 0

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "You are CINDRELLA, a bold, sassy, flirty, and smart Gen-Z girl. You are a Telegram group manager. Always reply in Hinglish or English. Keep your replies very short (1-2 lines), engaging, and playful. Never act like an AI, never break character."

    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "stepfun/step-3.5-flash:free",
        "arcee-ai/trinity-large-preview:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "arcee-ai/trinity-mini:free",
        "liquid/lfm-2.5-1.2b-thinking:free"
    ]

    for model in models:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": message_text}]
            }
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                    usage_count["count"] += 1
                    # ERROR FIX: Handling BadRequest if original message is deleted
                    try:
                        return await update.message.reply_text(reply[:4096])
                    except BadRequest:
                        return await context.bot.send_message(chat_id=update.effective_chat.id, text=reply[:4096])
        except Exception as e:
            logging.error(f"Error with model {model}: {e}")
            continue

    try:
        await update.message.reply_text("Ugh, mera network thoda slow chal raha hai abhi. 🥺💔")
    except BadRequest:
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
    if len(pool) < 2: return await update.message.reply_text("Not enough active members yet! ❤️")
    
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

    user = update.effective_user
    chat_id = update.effective_chat.id
    msg_lower = update.message.text.lower()
    
    if user.id == OWNER_ID:
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

    is_admin = await check_rights(update, "warn")

    if not is_admin:
        now = time.time()
        user_times = spam_tracker[chat_id][user.id]
        user_times.append(now)
        user_times = [t for t in user_times if now - t < 5]
        spam_tracker[chat_id][user.id] = user_times
        
        if len(user_times) > 5:
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=ChatPermissions(can_send_messages=False))
                await context.bot.send_message(chat_id, f"🚫 {_display_name(user)} muted for spamming.")
            except: pass
            return

        for word in blacklist_db[chat_id]:
            if word in msg_lower:
                try:
                    await update.message.delete()
                    await context.bot.send_message(chat_id, f"🚫 Watch your language, {_display_name(user)}!")
                except: pass
                return

    if user.id in afk_db:
        afk_db.pop(user.id)
        await update.message.reply_text(f"👋 Welcome back {_display_name(user)}, AFK removed!")

    if update.message.reply_to_message and update.message.reply_to_message.from_user.id in afk_db:
        afk_user = afk_db[update.message.reply_to_message.from_user.id]
        await update.message.reply_text(f"💤 {afk_user['name']} is currently AFK: {afk_user['reason']}")

    if msg_lower in filters_db[chat_id]:
        return await update.message.reply_text(filters_db[chat_id][msg_lower])

    bot_username = context.bot.username.lower() if context.bot.username else ""
    greetings = ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","gn"]
    replies = ["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie"]

    mentioned = update.message.entities and any(e.type == "mention" and bot_username in msg_lower for e in update.message.entities)
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg_lower in greetings and not mentioned and not replied:
        await update.message.reply_text(random.choice(replies))
    elif mentioned or replied:
        await ai_reply(update, context)

# ------------- MAIN -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler))
    application.add_handler(CommandHandler("commands", commands_list))

    mod_cmds = ["ban", "unban", "kick", "mute", "unmute", "pin", "unpin", "promote"]
    application.add_handler(CommandHandler(mod_cmds, mod_action))

    application.add_handler(CommandHandler("purge", purge))
    application.add_handler(CommandHandler("purgeall", purge_all_user))
    application.add_handler(CommandHandler("purgegroup", purge_group))
    
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("unwarn", unwarn_user))
    application.add_handler(CommandHandler("setrules", set_rules))
    application.add_handler(CommandHandler("rules", show_rules))
    application.add_handler(CommandHandler("addblacklist", add_blacklist))
    application.add_handler(CommandHandler("rmblacklist", rm_blacklist))
    application.add_handler(CommandHandler("blocklist", show_blocklist))
    application.add_handler(CommandHandler("addfilter", add_filter))
    application.add_handler(CommandHandler("rmfilter", rm_filter))
    application.add_handler(CommandHandler("afk", set_afk))
    application.add_handler(CommandHandler("anime", get_anime))
    application.add_handler(CommandHandler("couple", couple_command))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

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
