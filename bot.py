# bot.py - CINDRELLA final (Solo Leveling RPG + Admin Groups + OP Mode Fixed)
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------- STATE -----------------
usage_count = {"date": str(date.today()), "count": 0}
seen_members = defaultdict(dict)
couples_db = {}

# Moderation State
warnings_db = defaultdict(lambda: defaultdict(int)) 
afk_db = {} 
blacklist_db = defaultdict(set) 
filters_db = defaultdict(dict) 
rules_db = {} 
spam_tracker = defaultdict(lambda: defaultdict(list)) 

# RPG & Global Group State
known_groups = {} # chat_id -> title
chat_members_db = defaultdict(set) # chat_id -> set of user_ids
hunter_db = {} # user_id -> {"name": str, "username": str, "exp": int, "last_hunt": float, "last_daily": str}

WELCOME_MESSAGES = [
    "Welcome {name}! ✨ Glad you're here — have fun!",
    "Hey {name} 👋 — nice to see you! Introduce yourself 😄",
    "A lovely hello to {name} 🌸 — welcome to the fam!",
    "Oye {name} 😍 — welcome! Ready to vibe?",
    "Welcome, {name}! Make yourself at home 💖"
]
WELCOME_BG_URL = "https://images.unsplash.com/photo-1519608487953-e999c86e7455?w=1200"

# ---------- Helpers ----------
def _display_name(user):
    name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or getattr(user, "username", None) or "User"
    return str(name)

def mention_html(user_id: int, name: str) -> str:
    safe = (name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f'<a href="tg://user?id={user_id}">{safe}</a>'

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

async def check_rights(update: Update, action: str) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if user.id in admins_db: return True
    if chat.type == "private": return False
    try:
        member = await chat.get_member(user.id)
        if isinstance(member, ChatMemberOwner): return True
        if isinstance(member, ChatMemberAdministrator):
            if action in ["ban", "kick", "mute", "unban", "unmute", "warn", "unwarn"]:
                return member.can_restrict_members
            if action in ["pin", "unpin"]: return member.can_pin_messages
            if action in ["purge", "purgeall", "purgegroup", "filter", "blacklist", "rules"]:
                return member.can_delete_messages
            if action in ["promote", "demote"]: return member.can_promote_members
        return False
    except: return False

def ensure_user_registered(update: Update):
    """Ensures user is in the hunter_db and group database even if they only use commands."""
    user = update.effective_user
    chat = update.effective_chat
    if not user: return
    
    username = f"@{user.username}" if user.username else ""
    if user.id not in hunter_db:
        hunter_db[user.id] = {"name": _display_name(user), "username": username, "exp": 0, "last_hunt": 0, "last_daily": ""}
    
    hunter_db[user.id]["name"] = _display_name(user)
    hunter_db[user.id]["username"] = username
    
    if user.id == OWNER_ID:
        hunter_db[user.id]["exp"] = 9999999 # Unlimited EXP for Owner
        
    if chat and chat.type in ["group", "supergroup"]:
        chat_members_db[chat.id].add(user.id)
        if chat.title: known_groups[chat.id] = chat.title

# ------------- SOLO LEVELING RPG SYSTEM -------------
def get_hunter_stats(exp, user_id=None):
    if user_id == OWNER_ID: return "MAX", "🌍 National Level Hunter"
    level = (exp // 100) + 1
    if level <= 10: rank = "🪵 E-Rank"
    elif level <= 20: rank = "🪨 D-Rank"
    elif level <= 30: rank = "🥉 C-Rank"
    elif level <= 40: rank = "🥈 B-Rank"
    elif level <= 50: rank = "🥇 A-Rank"
    else: rank = "👑 S-Rank"
    return level, rank

async def hunter_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    data = hunter_db[user.id]
    level, rank = get_hunter_stats(data["exp"], user.id)
    uname_display = f" ({data['username']})" if data['username'] else ""
    
    text = f"🪪 **HUNTER LICENSE**\n\n👤 **Name:** {data['name']}{uname_display}\n🎖 **Rank:** {rank}\n📊 **Level:** {level}\n⚡ **EXP:** {data['exp'] if level != 'MAX' else '∞'}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    now = time.time()
    data = hunter_db[user.id]
    
    # 1 Hour Cooldown for everyone (including owner to prevent spam)
    if now - data["last_hunt"] < 3600: 
        wait = int(3600 - (now - data["last_hunt"]))
        m, s = divmod(wait, 60)
        return await update.message.reply_text(f"⏳ Dungeon portal closed! Wait {m}m {s}s to hunt again.")
    
    data["last_hunt"] = now
    events = [
        ("🟢 E-Rank Gate: Defeated 5 Goblins!", 25),
        ("🟢 D-Rank Gate: Killed giant slimes.", 40),
        ("🟡 C-Rank Gate: Fought High Orcs.", 70),
        ("🔴 Boss Encounter! Barely escaped with your life.", -10),
        ("🌟 Double Dungeon! You found a secret reward!", 120),
        ("❌ Ambushed by another hunter! Lost some EXP.", -20)
    ]
    event, exp_gain = random.choice(events)
    
    if user.id != OWNER_ID:
        data["exp"] += exp_gain
        if data["exp"] < 0: data["exp"] = 0
    
    level, rank = get_hunter_stats(data["exp"], user.id)
    await update.message.reply_text(f"⛩️ **Dungeon Raid Results:**\n\n{event}\n⚡ **Total EXP:** {data['exp'] if level != 'MAX' else '∞'} | **Level:** {level}")

async def daily_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    
    # Reset at 1:00 AM IST
    now_ist = dt.now(ZoneInfo("Asia/Kolkata"))
    reset_day = str(now_ist.date() if now_ist.hour >= 1 else (now_ist - timedelta(days=1)).date())
    
    data = hunter_db[user.id]
    if data["last_daily"] == reset_day:
        return await update.message.reply_text("⏳ System: Daily Quest already completed! Next quest unlocks at 1:00 AM IST.")
        
    data["last_daily"] = reset_day
    if user.id != OWNER_ID: data["exp"] += 150
    
    level, rank = get_hunter_stats(data["exp"], user.id)
    await update.message.reply_text(f"🏋️‍♂️ **Daily Quest Completed!**\n100 Pushups, 100 Situps, 10km Run!\n\n🌟 +150 EXP Gained!\n📊 Current Level: {level}")

async def top_hunter_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat_id = update.effective_chat.id
    if chat_id not in chat_members_db or not chat_members_db[chat_id]:
        return await update.message.reply_text("No hunters found in this guild yet.")
        
    members = chat_members_db[chat_id]
    local_hunters = [uid for uid in members if uid in hunter_db]
    sorted_hunters = sorted(local_hunters, key=lambda x: hunter_db[x]["exp"], reverse=True)[:10]
    
    if not sorted_hunters:
        return await update.message.reply_text("No active hunters in this guild.")
        
    text = "🏆 **TOP 10 GUILD HUNTERS** 🏆\n\n"
    for i, uid in enumerate(sorted_hunters, 1):
        h = hunter_db[uid]
        level, rank = get_hunter_stats(h["exp"], uid)
        uname = f" {h.get('username', '')}" if h.get("username") else ""
        text += f"**{i}.** {h['name']}{uname} - Lvl {level} ({rank})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def world_top_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sorted_hunters = sorted(hunter_db.values(), key=lambda x: x["exp"], reverse=True)[:10]
    if not sorted_hunters:
        return await update.message.reply_text("The world is empty. No hunters found.")
        
    text = "🌍 **WORLD TOP 10 S-RANK HUNTERS** 🌍\n\n"
    for i, h in enumerate(sorted_hunters, 1):
        uid = next((k for k, v in hunter_db.items() if v == h), None)
        level, rank = get_hunter_stats(h["exp"], uid)
        uname = f" {h.get('username', '')}" if h.get("username") else ""
        text += f"**{i}.** {h['name']}{uname} - Lvl {level} ({rank})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

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
            await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=False))
            await update.message.reply_text(f"🔇 Muted {target_id}.")
        elif action == "unmute":
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, 
                    can_add_web_page_previews=True
                )
            )
            await update.message.reply_text(f"🔊 Unmuted {target_id}.")
        elif action == "pin":
            if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to a message to pin.")
            await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            if update.message.reply_to_message: await context.bot.unpin_chat_message(chat_id, update.message.reply_to_message.message_id)
            else: await context.bot.unpin_chat_message(chat_id)
            await update.message.reply_text("✅ Unpinned.")
        elif action == "promote":
            await context.bot.promote_chat_member(
                chat_id, target_id, can_manage_chat=True, can_delete_messages=True,
                can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False, 
                can_change_info=True, can_invite_users=True, can_pin_messages=True
            )
            await update.message.reply_text(f"🌟 Promoted {target_id} to Admin.")
    except BadRequest as e: await update.message.reply_text(f"❌ Error: {e.message}")
    except Exception as e: await update.message.reply_text(f"❌ System Error: {e}")

# ------------- PURGE COMMANDS -------------
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purge"): return await update.message.reply_text("❌ Admin rights required.")
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to the oldest message.")
    try:
        start_id = update.message.reply_to_message.message_id
        end_id = update.message.message_id
        chat_id = update.effective_chat.id
        msg_ids = list(range(start_id, end_id + 1))
        for i in range(0, len(msg_ids), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids[i:i+100])
            except: pass 
        ack = await context.bot.send_message(chat_id, "✅ Purge complete.")
        await asyncio.sleep(3); await ack.delete()
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def purge_all_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgeall"): return await update.message.reply_text("❌ Admin rights required.")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("Reply to a user.")
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target_id, revoke_messages=True)
        await update.message.reply_text(f"✅ All messages from {target_id} deleted.")
        await context.bot.unban_chat_member(update.effective_chat.id, target_id)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def purge_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgegroup"): return await update.message.reply_text("❌ Admin rights required.")
    chat_id = update.effective_chat.id
    curr = update.message.message_id
    try:
        await context.bot.delete_messages(chat_id, list(range(curr - 100, curr + 1)))
        ack = await context.bot.send_message(chat_id, "✅ Group cleanup (Last 100).")
        await asyncio.sleep(5); await ack.delete()
    except: await update.message.reply_text("❌ Messages too old/already deleted.")

# ------------- PRO FEATURES -------------
async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌹 **CINDRELLA COMMANDS** 🌹

**⚔️ Solo Leveling (RPG):**
`/stats` - Check Hunter License & Rank
`/hunt` - Enter Dungeon & Kill Monsters
`/daily` - Daily System Quest (+150 EXP)
`/top_hunter` - Top 10 Hunters in Group
`/world_top` - Global Top 10 S-Rank Hunters

**🛠 Moderation:**
`/ban <reply/id>` - Ban a user
`/unban <id>` - Unban a user
`/kick <reply/id>` - Kick a user
`/mute <reply/id>` - Mute a user
`/unmute <reply/id>` - Unmute a user
`/pin <reply>` - Pin a message
`/unpin <reply>` - Unpin a message
`/promote <reply/id>` - Promote user to Admin
`/warn <reply> [reason]` - Warn user (3 warns = mute)
`/unwarn <reply>` - Remove a warn

**🧹 Purge:**
`/purge <reply>` - Delete msgs from reply to current
`/purgeall <reply>` - Delete all msgs of a user
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
    """
    await update.message.reply_text(text, parse_mode="Markdown")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "warn"): return await update.message.reply_text("❌ Admin rights required.")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ Reply to a user to warn.")
    chat_id = update.effective_chat.id
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_id in admins_db or target_member.status in ['administrator', 'creator']:
            return await update.message.reply_text("❌ Cannot warn an Admin.")
    except: pass

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
    if not await check_rights(update, "unwarn"): return await update.message.reply_text("❌ Admin rights required.")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ Reply to a user.")
    chat_id = update.effective_chat.id
    if warnings_db[chat_id][target_id] > 0:
        warnings_db[chat_id][target_id] -= 1
        await update.message.reply_text(f"✅ Removed 1 warning. Current warns: {warnings_db[chat_id][target_id]}/3")
    else: await update.message.reply_text("✅ User has 0 warnings.")

async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "rules"): return await update.message.reply_text("❌ Admin rights required.")
    text = update.message.text.split(None, 1)
    if len(text) < 2: return await update.message.reply_text("❌ Please provide rules text.")
    rules_db[update.effective_chat.id] = text[1]
    await update.message.reply_text("✅ Rules updated!")

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 **Group Rules:**\n\n{rules_db.get(update.effective_chat.id, 'No rules set yet.')}", parse_mode="Markdown")

async def add_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    word = context.args[0].lower()
    blacklist_db[update.effective_chat.id].add(word)
    await update.message.reply_text(f"✅ Word '{word}' added to blacklist.")

async def rm_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    word = context.args[0].lower()
    blacklist_db[update.effective_chat.id].discard(word)
    await update.message.reply_text(f"✅ Word '{word}' removed from blacklist.")

async def show_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text("❌ Admin rights required.")
    words = blacklist_db[update.effective_chat.id]
    if not words: return await update.message.reply_text("✅ Blocklist ekdum khali hai.")
    await update.message.reply_text("🚫 **Blocked Words:**\n" + "\n".join([f"- `{w}`" for w in words]), parse_mode="Markdown")

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text("❌ Admin rights required.")
    text = update.message.text.split(None, 2)
    if len(text) < 3: return await update.message.reply_text("❌ Format: /addfilter <word> <reply>")
    filters_db[update.effective_chat.id][text[1].lower()] = text[2]
    await update.message.reply_text(f"✅ Filter added for '{text[1].lower()}'.")

async def rm_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    filters_db[update.effective_chat.id].pop(context.args[0].lower(), None)
    await update.message.reply_text(f"✅ Filter removed for '{context.args[0].lower()}'.")

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
                text = f"🎬 **{anime['title']}**\n\n📊 Score: {anime.get('score', 'N/A')}\n🎞 Episodes: {anime.get('episodes', 'N/A')}\n🔄 Status: {anime.get('status', 'N/A')}\n\n🔗 [More Info]({anime['url']})"
                await update.message.reply_text(text, parse_mode="Markdown")
            else: await update.message.reply_text("❌ Anime not found!")
    except: await update.message.reply_text("❌ API error.")

# ------------- ADMIN PANEL (OWNER ONLY) -------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return await update.message.reply_text("❌ Only the Bot Owner can use this.")
    
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("🌐 List Groups", callback_data="list_groups")],
        [InlineKeyboardButton("➕ Add Bot Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Bot Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
    ]
    usage_info = f"\n📊 Replies Today: {usage_count['count']} (Date: {usage_count['date']})"
    await update.message.reply_text("🤖 **Bot Owner Panel**" + usage_info, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID: return await query.answer()
    await query.answer()

    if query.data == "broadcast":
        await query.message.reply_text("📢 Send me the broadcast message:")
        context.user_data["awaiting_broadcast"] = True
    elif query.data == "list_groups":
        if not known_groups: return await query.message.reply_text("Bot is not active in any groups yet.")
        await query.message.reply_text("Fetching group links... please wait. ⏳")
        text = "🌐 **Bot Groups & Links:**\n\n"
        for cid, title in list(known_groups.items()):
            try:
                link = await context.bot.export_chat_invite_link(cid)
                text += f"🔹 {title}: [Invite Link]({link})\n"
            except:
                text += f"🔹 {title}: *(No Admin Rights)*\n"
        for i in range(0, len(text), 4000):
            await query.message.reply_text(text[i:i+4000], parse_mode="Markdown", disable_web_page_preview=True)
    elif query.data == "add_admin":
        await query.message.reply_text("Send user ID to add as Bot Admin:")
        context.user_data["awaiting_add_admin"] = True
    elif query.data == "remove_admin":
        await query.message.reply_text("Send user ID to remove from Bot Admins:")
        context.user_data["awaiting_remove_admin"] = True
    elif query.data == "list_admins":
        await query.message.reply_text("Current Bot Admins IDs:\n" + "\n".join([str(aid) for aid in admins_db]))

# ------------- AI & WELCOME & CORE TEXT HANDLER -------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹—your group manager & AI bestie!\nType /commands to see what I can do!", reply_markup=InlineKeyboardMarkup(keyboard))

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat = update.effective_chat
    try: member_count = await chat.get_member_count()
    except: member_count = "New"

    for member in update.message.new_chat_members:
        seen_members[chat_id][member.id] = {"name": _display_name(member), "is_bot": member.is_bot}
        if not member.is_bot:
            username = f"@{member.username}" if member.username else "No Username"
            userDetails = f"\n🆔 UserID: {member.id}\n👤 Username: {username}\n📜 Bio: System Hidden"
            final_msg = random.choice(WELCOME_MESSAGES).format(name=_display_name(member)) + userDetails
            
            try:
                safe_name = urllib.parse.quote(_display_name(member))
                safe_chat = urllib.parse.quote(chat.title or "Our Group")
                safe_member_count = urllib.parse.quote(f"Member #{member_count}")
                photos = await context.bot.get_user_profile_photos(member.id, limit=1)
                avatar_url = "https://i.ibb.co/4pDNDk1/avatar.png" 
                if photos.total_count > 0: avatar_url = (await context.bot.get_file(photos.photos[0][-1].file_id)).file_path
                card_url = f"https://api.popcat.xyz/welcomecard?background={urllib.parse.quote(WELCOME_BG_URL)}&text1={safe_name}&text2=Welcome+to+{safe_chat}&text3={safe_member_count}&avatar={urllib.parse.quote(avatar_url)}"
                await context.bot.send_photo(chat_id=chat_id, photo=card_url, caption=final_msg)
            except: pass

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if usage_count["date"] != str(date.today()): usage_count.update({"date": str(date.today()), "count": 0})

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "You are CINDRELLA, a bold, sassy, flirty, and smart Gen-Z girl. You are a Telegram group manager. Always reply in Hinglish or English. Keep your replies very short (1-2 lines), engaging, and playful. Never act like an AI."
    models = ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free", "nvidia/nemotron-3-nano-30b-a3b:free", "stepfun/step-3.5-flash:free", "arcee-ai/trinity-large-preview:free", "meta-llama/llama-3.2-3b-instruct:free", "liquid/lfm-2.5-1.2b-thinking:free"]

    for model in models:
        try:
            payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": message_text}]}
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                    usage_count["count"] += 1
                    try: return await update.message.reply_text(reply[:4096])
                    except BadRequest: return await context.bot.send_message(chat_id=update.effective_chat.id, text=reply[:4096])
        except: continue
    try: await update.message.reply_text("Ugh, mera network thoda slow chal raha hai abhi. 🥺💔")
    except: pass

async def couple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    seen_members[chat_id][sender.id] = {"name": _display_name(sender), "is_bot": getattr(sender, "is_bot", False)}
    today_str = str(date.today())
    if couples_db.get(chat_id, {}).get("date") == today_str:
        (id1, name1), (id2, name2) = couples_db[chat_id]["pair"]
        return await update.message.reply_text(f"💞 Couple of the Day:\n{mention_html(id1, name1)} + {mention_html(id2, name2)}", parse_mode="HTML")

    pool = [(uid, info["name"]) for uid, info in seen_members[chat_id].items() if not info.get("is_bot", False)]
    if len(pool) < 2: return await update.message.reply_text("Not enough active members yet! ❤️")
    picked = random.sample(pool, 2)
    couples_db[chat_id] = {"date": today_str, "pair": picked}
    await update.message.reply_text(f"💘 *Couple of the Day* 💘\n{mention_html(picked[0][0], picked[0][1])} + {mention_html(picked[1][0], picked[1][1])}", parse_mode="HTML")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    user = update.effective_user
    msg_lower = update.message.text.lower()
    
    # 🌍 RPG & Tracking Updates properly handled through ensure_user_registered
    ensure_user_registered(update)
    
    if user.id != OWNER_ID: hunter_db[user.id]["exp"] += 1 

    # Owner commands processing
    if user.id == OWNER_ID:
        if context.user_data.pop("awaiting_broadcast", None):
            for aid in admins_db:
                try: await context.bot.send_message(aid, f"📢 Broadcast:\n{update.message.text}")
                except: pass
            return await update.message.reply_text("✅ Broadcast sent.")
        if context.user_data.pop("awaiting_add_admin", None):
            try: admins_db.add(int(update.message.text.strip())); await update.message.reply_text("✅ Admin added.")
            except: await update.message.reply_text("❌ Invalid ID.")
            return
        if context.user_data.pop("awaiting_remove_admin", None):
            try: 
                if int(update.message.text.strip()) != OWNER_ID: admins_db.discard(int(update.message.text.strip())); await update.message.reply_text("✅ Removed.")
            except: await update.message.reply_text("❌ Invalid ID.")
            return

    # Spam & Filter Checks
    if not await check_rights(update, "warn"):
        now = time.time()
        spam_tracker[chat_id][user.id] = [t for t in spam_tracker[chat_id][user.id] + [now] if now - t < 5]
        if len(spam_tracker[chat_id][user.id]) > 5:
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=ChatPermissions(can_send_messages=False))
                return await context.bot.send_message(chat_id, f"🚫 {_display_name(user)} muted for spamming.")
            except: pass
        
        if any(word in msg_lower for word in blacklist_db[chat_id]):
            try:
                await update.message.delete()
                return await context.bot.send_message(chat_id, f"🚫 Watch your language, {_display_name(user)}!")
            except: pass

    # AFK Logic
    if user.id in afk_db:
        afk_db.pop(user.id)
        await update.message.reply_text(f"👋 Welcome back {_display_name(user)}, AFK removed!")
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id in afk_db:
        afk_user = afk_db[update.message.reply_to_message.from_user.id]
        await update.message.reply_text(f"💤 {afk_user['name']} is currently AFK: {afk_user['reason']}")

    # Custom Filters
    if msg_lower in filters_db[chat_id]: return await update.message.reply_text(filters_db[chat_id][msg_lower])

    # AI Trigger Logic
    bot_un = context.bot.username.lower() if context.bot.username else ""
    mentioned = (update.message.entities and any(e.type == "mention" and bot_un in msg_lower for e in update.message.entities)) or any(f in msg_lower for f in filters_db[chat_id].keys())
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg_lower in ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","gn"] and not mentioned and not replied:
        await update.message.reply_text(random.choice(["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie"]))
    elif mentioned or replied:
        await ai_reply(update, context)

async def couple_daily_reset(context: ContextTypes.DEFAULT_TYPE): couples_db.clear()

# ------------- MAIN -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_button_handler))
    application.add_handler(CommandHandler("commands", commands_list))

    # SOLO LEVELING COMMANDS
    application.add_handler(CommandHandler("stats", hunter_profile))
    application.add_handler(CommandHandler("hunt", hunt))
    application.add_handler(CommandHandler("daily", daily_quest))
    application.add_handler(CommandHandler("top_hunter", top_hunter_local))
    application.add_handler(CommandHandler("world_top", world_top_global))

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
