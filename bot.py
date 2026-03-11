# bot.py - CINDRELLA final (No Purgeall + DB Couple Fix + Pro Admin Panel + RANDOM DUNGEONS)
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
from pymongo import MongoClient
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
MONGO_URI = os.environ.get("MONGO_URI") 

ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))
admins_db = ADMIN_IDS.union({OWNER_ID})

app = Flask(__name__)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------- STATE -----------------
usage_count = {"date": str(date.today()), "count": 0}
couples_db = {}
warnings_db = defaultdict(lambda: defaultdict(int)) 
afk_db = {} 
blacklist_db = defaultdict(set) 
filters_db = defaultdict(dict) 
rules_db = {} 
spam_tracker = defaultdict(lambda: defaultdict(list)) 

# RPG & Global Group State
known_groups = {} 
chat_members_db = defaultdict(set) 
hunter_db = {} 

# --- NEW: DUNGEON SYSTEM STATE ---
group_msg_counts = defaultdict(int)
active_dungeons = {}

DUNGEON_RANKS = {
    "E": {"video": "https://files.catbox.moe/ne4vk6.mp4", "reward": 50, "penalty": 10, "hp": 100, "name": "Goblin Outpost"},
    "D": {"video": "https://files.catbox.moe/ne4vk6.mp4", "reward": 80, "penalty": 20, "hp": 200, "name": "Direwolf Den"},
    "C": {"video": "https://files.catbox.moe/nyvaoy.mp4", "reward": 150, "penalty": 40, "hp": 400, "name": "High Orc Lair"},
    "B": {"video": "https://files.catbox.moe/nyvaoy.mp4", "reward": 250, "penalty": 60, "hp": 600, "name": "Assassin Guild"},
    "A": {"video": "https://files.catbox.moe/k5doyt.mp4", "reward": 400, "penalty": 100, "hp": 1000, "name": "A/B-Class Boss Room"},
    "S": {"video": "https://files.catbox.moe/k5doyt.mp4", "reward": 800, "penalty": 200, "hp": 2000, "name": "Ant King Nest"},
    "RED": {"video": "https://files.catbox.moe/8dxlw3.mp4", "reward": 1500, "penalty": 400, "hp": 3000, "name": "Blood-Red Igris"}
}
DUNGEON_WORDS = ["ARISE", "SMASH", "KILL", "WAKE UP", "FIGHT", "DEFEND"]

WELCOME_MESSAGES = [
    "Welcome {name}! ✨ Glad you're here — have fun!",
    "Hey {name} 👋 — nice to see you! Introduce yourself 😄",
    "A lovely hello to {name} 🌸 — welcome to the fam!"
]
WELCOME_BG_URL = "https://images.unsplash.com/photo-1519608487953-e999c86e7455?w=1200"

# ----------------- MONGODB SETUP -----------------
try:
    if MONGO_URI:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client["cindrella_db"]
        hunters_col = db["hunters"]
        groups_col = db["groups"]
        admins_col = db["admins"]

        db_admins = admins_col.find_one({"_id": "admin_list"})
        if db_admins: admins_db.update(db_admins.get("ids", []))

        for grp in groups_col.find(): known_groups[grp["_id"]] = grp["title"]

        for hnt in hunters_col.find():
            hunter_db[hnt["_id"]] = {
                "name": hnt.get("name", "Unknown"),
                "username": hnt.get("username", ""),
                "exp": hnt.get("exp", 0),
                "last_hunt": hnt.get("last_hunt", 0),
                "last_daily": hnt.get("last_daily", "")
            }
        logging.info("✅ MongoDB Connected & Permanent Data Loaded!")
    else:
        logging.warning("⚠️ MONGO_URI not found. Using temporary RAM memory.")
        hunters_col = groups_col = admins_col = None
except Exception as e:
    logging.error(f"❌ MongoDB Connection Error: {e}")
    hunters_col = groups_col = admins_col = None

def save_hunter(user_id):
    if hunters_col is not None and user_id in hunter_db:
        data = hunter_db[user_id].copy()
        try: hunters_col.update_one({"_id": user_id}, {"$set": data}, upsert=True)
        except: pass

def save_group(chat_id, title):
    if groups_col is not None:
        try: groups_col.update_one({"_id": chat_id}, {"$set": {"title": title}}, upsert=True)
        except: pass

def save_admins():
    if admins_col is not None:
        try: admins_col.update_one({"_id": "admin_list"}, {"$set": {"ids": list(admins_db)}}, upsert=True)
        except: pass

# ---------- Helpers ----------
def _display_name(user):
    return str(getattr(user, "first_name", None) or getattr(user, "username", None) or "User")

def mention_html(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</a>'

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    if update.message.reply_to_message: return update.message.reply_to_message.from_user.id
    if context.args:
        arg = context.args[0]
        if re.fullmatch(r"@\w{5,}", arg):
            try: return (await context.bot.get_chat(arg)).id
            except: return None
        try: return int(arg)
        except: return None
    return None

async def check_rights(update: Update, action: str) -> bool:
    user, chat = update.effective_user, update.effective_chat
    if user.id in admins_db: return True
    if chat.type == "private": return False
    try:
        member = await chat.get_member(user.id)
        if isinstance(member, ChatMemberOwner): return True
        if isinstance(member, ChatMemberAdministrator):
            if action in ["ban", "kick", "mute", "unban", "unmute", "warn", "unwarn"]: return member.can_restrict_members
            if action in ["pin", "unpin"]: return member.can_pin_messages
            if action in ["purge", "purgegroup", "filter", "blacklist", "rules"]: return member.can_delete_messages
            if action in ["promote", "demote"]: return member.can_promote_members
        return False
    except: return False

def ensure_user_registered(update: Update):
    user, chat = update.effective_user, update.effective_chat
    if not user: return
    username = f"@{user.username}" if user.username else ""
    if user.id not in hunter_db:
        hunter_db[user.id] = {"name": _display_name(user), "username": username, "exp": 0, "last_hunt": 0, "last_daily": ""}
    
    hunter_db[user.id]["name"] = _display_name(user)
    hunter_db[user.id]["username"] = username
    if user.id == OWNER_ID: hunter_db[user.id]["exp"] = 9999999
        
    if chat and chat.type in ["group", "supergroup"]:
        chat_members_db[chat.id].add(user.id)
        if chat.title and (chat.id not in known_groups or known_groups[chat.id] != chat.title):
            known_groups[chat.id] = chat.title
            save_group(chat.id, chat.title)

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
    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    username = f"@{target_user.username}" if target_user.username else ""
    if target_user.id not in hunter_db:
        hunter_db[target_user.id] = {"name": _display_name(target_user), "username": username, "exp": 0, "last_hunt": 0, "last_daily": ""}
    if target_user.id == OWNER_ID: hunter_db[target_user.id]["exp"] = 9999999

    data = hunter_db[target_user.id]
    level, rank = get_hunter_stats(data["exp"], target_user.id)
    uname_display = f" ({data['username']})" if data['username'] else ""
    safe_name = str(data['name']).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    text = f"🪪 <b>HUNTER LICENSE</b>\n\n👤 <b>Name:</b> {safe_name}{uname_display}\n🎖 <b>Rank:</b> {rank}\n📊 <b>Level:</b> {level}\n⚡ <b>EXP:</b> {data['exp'] if level != 'MAX' else '∞'}"
    await update.message.reply_text(text, parse_mode="HTML")

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user, now = update.effective_user, time.time()
    data = hunter_db[user.id]
    
    if now - data["last_hunt"] < 3600: 
        m, s = divmod(int(3600 - (now - data["last_hunt"])), 60)
        return await update.message.reply_text(f"⏳ Dungeon portal closed! Wait {m}m {s}s to hunt again.")
    
    data["last_hunt"] = now
    events = [
        ("🟢 E-Rank Gate: Defeated 5 Goblins!", 25), ("🟢 D-Rank Gate: Killed giant slimes.", 40),
        ("🟡 C-Rank Gate: Fought High Orcs.", 70), ("🔴 Boss Encounter! Barely escaped with your life.", -10),
        ("🌟 Double Dungeon! You found a secret reward!", 120), ("❌ Ambushed by another hunter! Lost some EXP.", -20)
    ]
    event, exp_gain = random.choice(events)
    if user.id != OWNER_ID: data["exp"] = max(0, data["exp"] + exp_gain)
    
    save_hunter(user.id)
    level, rank = get_hunter_stats(data["exp"], user.id)
    await update.message.reply_text(f"⛩️ **Dungeon Raid Results:**\n\n{event}\n⚡ **Total EXP:** {data['exp'] if level != 'MAX' else '∞'} | **Level:** {level}")

async def daily_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    now_ist = dt.now(ZoneInfo("Asia/Kolkata"))
    reset_day = str(now_ist.date() if now_ist.hour >= 1 else (now_ist - timedelta(days=1)).date())
    
    data = hunter_db[user.id]
    if data["last_daily"] == reset_day:
        return await update.message.reply_text("⏳ System: Daily Quest already completed! Next quest unlocks at 1:00 AM IST.")
        
    data["last_daily"] = reset_day
    if user.id != OWNER_ID: data["exp"] += 150
    
    save_hunter(user.id)
    level, rank = get_hunter_stats(data["exp"], user.id)
    await update.message.reply_text(f"🏋️‍♂️ **Daily Quest Completed!**\n100 Pushups, 100 Situps, 10km Run!\n\n🌟 +150 EXP Gained!\n📊 Current Level: {level}")

async def give_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sender = update.effective_user
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Jisko EXP dena hai, uske message ka reply karke `/give <amount>` likho.")
    target = update.message.reply_to_message.from_user
    if sender.id == target.id: return await update.message.reply_text("❌ Khud ko EXP nahi de sakte!")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text("❌ Sahi format: `/give <amount>`")
        
    amount = int(context.args[0])
    if amount <= 0: return await update.message.reply_text("❌ Amount 0 se zyada hona chahiye.")
        
    if target.id not in hunter_db:
        hunter_db[target.id] = {"name": _display_name(target), "username": f"@{target.username}" if target.username else "", "exp": 0, "last_hunt": 0, "last_daily": ""}
        
    sender_data, target_data = hunter_db[sender.id], hunter_db[target.id]
    if sender.id != OWNER_ID:
        if sender_data["exp"] < amount: return await update.message.reply_text(f"❌ Tumhare paas itni EXP nahi hai! (Current: {sender_data['exp']})")
        sender_data["exp"] -= amount
        
    target_data["exp"] += amount
    save_hunter(sender.id); save_hunter(target.id)
    
    await update.message.reply_text(f"💸 <b>EXP Transferred!</b>\n\n<b>{str(sender_data['name']).replace('<','&lt;')}</b> gave <b>{amount} EXP</b> to <b>{str(target_data['name']).replace('<','&lt;')}</b> ⚡", parse_mode="HTML")

async def top_hunter_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat_id = update.effective_chat.id
    members = chat_members_db.get(chat_id, set())
    sorted_hunters = sorted([uid for uid in members if uid in hunter_db], key=lambda x: hunter_db[x]["exp"], reverse=True)[:10]
    if not sorted_hunters: return await update.message.reply_text("No active hunters in this guild.")
        
    text = "🏆 <b>TOP 10 GUILD HUNTERS</b> 🏆\n\n"
    for i, uid in enumerate(sorted_hunters, 1):
        h = hunter_db[uid]
        level, rank = get_hunter_stats(h["exp"], uid)
        text += f"<b>{i}.</b> {str(h['name']).replace('<','&lt;')}{' '+h.get('username') if h.get('username') else ''} - Lvl {level} ({rank})\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def world_top_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sorted_hunters = sorted(hunter_db.items(), key=lambda x: x[1]["exp"], reverse=True)[:10]
    if not sorted_hunters: return await update.message.reply_text("The world is empty. No hunters found.")
        
    text = "🌍 <b>WORLD TOP 10 S-RANK HUNTERS</b> 🌍\n\n"
    for i, (uid, h) in enumerate(sorted_hunters, 1):
        level, rank = get_hunter_stats(h["exp"], uid)
        text += f"<b>{i}.</b> {str(h['name']).replace('<','&lt;')}{' '+h.get('username') if h.get('username') else ''} - Lvl {level} ({rank})\n"
    await update.message.reply_text(text, parse_mode="HTML")

# ------------- MODERATION COMMANDS -------------
async def mod_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    action = update.message.text.split()[0][1:].split('@')[0].lower()
    if not await check_rights(update, action): return await update.message.reply_text("❌ You don't have Admin rights to do this.")
    target_id = await get_user_id(update, context)
    if not target_id and action not in ["unpin"]: return await update.message.reply_text("❌ Reply to a user or provide an ID/Username.")
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
            await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True, can_add_web_page_previews=True))
            await update.message.reply_text(f"🔊 Unmuted {target_id}.")
        elif action == "pin":
            if update.message.reply_to_message: await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        elif action == "unpin":
            if update.message.reply_to_message: await context.bot.unpin_chat_message(chat_id, update.message.reply_to_message.message_id)
            else: await context.bot.unpin_chat_message(chat_id)
            await update.message.reply_text("✅ Unpinned.")
        elif action == "promote":
            await context.bot.promote_chat_member(chat_id, target_id, can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False, can_change_info=True, can_invite_users=True, can_pin_messages=True)
            await update.message.reply_text(f"🌟 Promoted {target_id} to Admin.")
    except BadRequest as e: await update.message.reply_text(f"❌ Error: {e.message}")
    except Exception as e: await update.message.reply_text(f"❌ System Error: {e}")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purge"): return await update.message.reply_text("❌ Admin rights required.")
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to the oldest message.")
    try:
        start_id, end_id, chat_id = update.message.reply_to_message.message_id, update.message.message_id, update.effective_chat.id
        msg_ids = list(range(start_id, end_id + 1))
        for i in range(0, len(msg_ids), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids[i:i+100])
            except: pass 
        ack = await context.bot.send_message(chat_id, "✅ Purge complete."); await asyncio.sleep(3); await ack.delete()
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def purge_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgegroup"): return await update.message.reply_text("❌ Admin rights required.")
    chat_id, curr = update.effective_chat.id, update.message.message_id
    try:
        await context.bot.delete_messages(chat_id, list(range(curr - 100, curr + 1)))
        ack = await context.bot.send_message(chat_id, "✅ Group cleanup (Last 100)."); await asyncio.sleep(5); await ack.delete()
    except: await update.message.reply_text("❌ Messages too old/already deleted.")

# ------------- PRO FEATURES -------------
async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌹 **CINDRELLA COMMANDS** 🌹

**⚔️ Solo Leveling (RPG):**
`/stats [reply]` - Check Hunter License
`/hunt` - Enter Dungeon & Kill Monsters
`/daily` - Daily System Quest (+150 EXP)
`/give <reply> <amount>` - Donate EXP
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
`/warn <reply> [reason]` - Warn user
`/unwarn <reply>` - Remove a warn

**🧹 Purge:**
`/purge <reply>` - Delete msgs from reply to current
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
`/admin` - Bot Admin Panel
    """
    await update.message.reply_text(text, parse_mode="Markdown")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "warn"): return await update.message.reply_text("❌ Admin rights required.")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ Reply to a user to warn.")
    chat_id = update.effective_chat.id
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_id in admins_db or target_member.status in ['administrator', 'creator']: return await update.message.reply_text("❌ Cannot warn an Admin.")
    except: pass

    warnings_db[chat_id][target_id] += 1
    count = warnings_db[chat_id][target_id]
    reason = " ".join(context.args) if context.args else "No reason given."
    if count >= 3:
        await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=False))
        warnings_db[chat_id][target_id] = 0
        await update.message.reply_text(f"🛑 User {target_id} reached 3 warnings and is now MUTED!")
    else: await update.message.reply_text(f"⚠️ Warned {target_id}! ({count}/3)\nReason: {reason}")

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
    blacklist_db[update.effective_chat.id].add(context.args[0].lower()); await update.message.reply_text(f"✅ Word '{context.args[0]}' added.")

async def rm_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    blacklist_db[update.effective_chat.id].discard(context.args[0].lower()); await update.message.reply_text(f"✅ Word '{context.args[0]}' removed.")

async def show_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text("❌ Admin rights required.")
    words = blacklist_db[update.effective_chat.id]
    if not words: return await update.message.reply_text("✅ Blocklist ekdum khali hai.")
    await update.message.reply_text("🚫 **Blocked Words:**\n" + "\n".join([f"- `{w}`" for w in words]), parse_mode="Markdown")

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text("❌ Admin rights required.")
    text = update.message.text.split(None, 2)
    if len(text) < 3: return await update.message.reply_text("❌ Format: /addfilter <word> <reply>")
    filters_db[update.effective_chat.id][text[1].lower()] = text[2]; await update.message.reply_text(f"✅ Filter added.")

async def rm_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text("❌ Admin rights required.")
    if not context.args: return await update.message.reply_text("❌ Provide a word.")
    filters_db[update.effective_chat.id].pop(context.args[0].lower(), None); await update.message.reply_text(f"✅ Filter removed.")

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
                await update.message.reply_text(f"🎬 **{anime['title']}**\n\n📊 Score: {anime.get('score', 'N/A')}\n🎞 Episodes: {anime.get('episodes', 'N/A')}\n🔄 Status: {anime.get('status', 'N/A')}\n\n🔗 [More Info]({anime['url']})", parse_mode="Markdown")
            else: await update.message.reply_text("❌ Anime not found!")
    except: await update.message.reply_text("❌ API error.")

# ------------- ADMIN PANEL (OWNER vs ADMIN) -------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins_db: 
        return await update.message.reply_text("❌ Only Bot Admins & Owner can use this.")
    
    if user_id == OWNER_ID:
        buttons = [
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🌐 List Groups", callback_data="list_groups")],
            [InlineKeyboardButton("➕ Add Bot Admin", callback_data="add_admin"), InlineKeyboardButton("➖ Remove Bot Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
        await update.message.reply_text(f"👑 **Owner Panel**\n📊 Replies Today: {usage_count['count']}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        buttons = [
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🌐 List Groups", callback_data="list_groups")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
        await update.message.reply_text(f"🛠 **Bot Admin Panel**\n📊 Replies Today: {usage_count['count']}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in admins_db: return await query.answer("❌ You are not a Bot Admin!", show_alert=True)
    await query.answer()

    if query.data == "broadcast":
        await query.message.reply_text("📢 Send me the broadcast message:")
        context.user_data["awaiting_broadcast"] = True
    elif query.data == "list_groups":
        if not known_groups: return await query.message.reply_text("Bot is not active in any groups yet.")
        await query.message.reply_text("Fetching group links... please wait. ⏳")
        text = "🌐 <b>Bot Groups & Links:</b>\n\n"
        for cid, title in list(known_groups.items()):
            safe_title = str(title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            try: link = await context.bot.export_chat_invite_link(cid); text += f"🔹 {safe_title}: <a href='{link}'>Invite Link</a>\n"
            except: text += f"🔹 {safe_title}: <i>(No Admin Rights)</i>\n"
        for i in range(0, len(text), 4000): await query.message.reply_text(text[i:i+4000], parse_mode="HTML", disable_web_page_preview=True)
    elif query.data == "add_admin":
        if user_id != OWNER_ID: return await query.message.reply_text("❌ Only the Owner can add admins.")
        await query.message.reply_text("Send user ID to add as Bot Admin:")
        context.user_data["awaiting_add_admin"] = True
    elif query.data == "remove_admin":
        if user_id != OWNER_ID: return await query.message.reply_text("❌ Only the Owner can remove admins.")
        await query.message.reply_text("Send user ID to remove from Bot Admins:")
        context.user_data["awaiting_remove_admin"] = True
    elif query.data == "list_admins":
        admin_text = "📋 **Current Bot Admins:**\n\n"
        for aid in admins_db:
            if aid == OWNER_ID:
                admin_text += f"👑 Owner (`{aid}`)\n"
            else:
                if aid in hunter_db:
                    h = hunter_db[aid]
                    uname = f" {h['username']}" if h.get("username") else ""
                    admin_text += f"🔹 {h['name']}{uname} (`{aid}`)\n"
                else:
                    admin_text += f"🔹 Unknown Hunter (`{aid}`)\n"
        await query.message.reply_text(admin_text, parse_mode="Markdown")

# ------------- AI & WELCOME & CORE TEXT HANDLER -------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹—your group manager & AI bestie!\nType /commands to see what I can do!", reply_markup=InlineKeyboardMarkup(keyboard))

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, chat = update.effective_chat.id, update.effective_chat
    try: member_count = await chat.get_member_count()
    except: member_count = "New"

    for member in update.message.new_chat_members:
        if not member.is_bot:
            username = f"@{member.username}" if member.username else "No Username"
            final_msg = random.choice(WELCOME_MESSAGES).format(name=_display_name(member)) + f"\n🆔 UserID: {member.id}\n👤 Username: {username}\n📜 Bio: System Hidden"
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
    models = ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free", "nvidia/nemotron-3-nano-30b-a3b:free", "stepfun/step-3.5-flash:free", "arcee-ai/trinity-large-preview:free"]
    
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
    today_str = str(date.today())
    if couples_db.get(chat_id, {}).get("date") == today_str:
        (id1, name1), (id2, name2) = couples_db[chat_id]["pair"]
        return await update.message.reply_text(f"💞 Couple of the Day:\n{mention_html(id1, name1)} + {mention_html(id2, name2)}", parse_mode="HTML")

    members = chat_members_db.get(chat_id, set())
    pool = [(uid, hunter_db[uid]["name"]) for uid in members if uid in hunter_db]
    if len(pool) < 2: return await update.message.reply_text("Not enough active members yet! (Thode aur logo ko ek message karne do pehle) ❤️")
        
    picked = random.sample(pool, 2)
    couples_db[chat_id] = {"date": today_str, "pair": picked}
    await update.message.reply_text(f"💘 *Couple of the Day* 💘\n{mention_html(picked[0][0], picked[0][1])} + {mention_html(picked[1][0], picked[1][1])}", parse_mode="HTML")

async def couple_daily_reset(context: ContextTypes.DEFAULT_TYPE): couples_db.clear()

# ------------- NEW: RANDOM DUNGEON SYSTEM -------------
async def gate_break(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    if chat_id in active_dungeons:
        dungeon = active_dungeons.pop(chat_id)
        penalty = dungeon['penalty']
        affected = 0
        for uid in chat_members_db.get(chat_id, set()):
            if uid in hunter_db and uid != OWNER_ID:
                hunter_db[uid]["exp"] = max(0, hunter_db[uid]["exp"] - penalty)
                save_hunter(uid)
                affected += 1
        
        try:
            await context.bot.delete_message(chat_id, dungeon["msg_id"])
        except: pass
        
        await context.bot.send_message(
            chat_id,
            f"💀 <b>GATE BREAK!!</b> 💀\n\nThe {dungeon['rank']}-Rank Boss escaped the dungeon and ravaged the Guild!\n📉 {affected} active Hunters lost {penalty} EXP!",
            parse_mode="HTML"
        )

async def clear_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, participants: list):
    dungeon = active_dungeons.pop(chat_id, None)
    if not dungeon: return
    
    if "job" in dungeon: dungeon["job"].schedule_removal()
    
    reward = dungeon["reward"]
    winners_text = ""
    for uid in participants:
        if uid in hunter_db and uid != OWNER_ID:
            hunter_db[uid]["exp"] += reward
            save_hunter(uid)
            winners_text += f"- {hunter_db[uid]['name']} (+{reward} EXP)\n"
            
    try: await context.bot.delete_message(chat_id, dungeon["msg_id"])
    except: pass
    
    await context.bot.send_message(
        chat_id,
        f"🎊 <b>DUNGEON CLEARED!</b> 🎊\n\nThe {dungeon['rank']}-Rank Gate has been successfully closed!\n\n🏅 <b>Rewards Distributed:</b>\n{winners_text}",
        parse_mode="HTML"
    )

async def spawn_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    ranks = ["E", "E", "D", "D", "C", "C", "B", "A", "S", "RED"]
    rank = random.choice(ranks)
    data = DUNGEON_RANKS[rank]
    
    dtype = random.choice([1, 2, 3]) # 1: Boss Smash, 2: Word Type, 3: Co-op Raid
    
    dungeon_info = {
        "rank": rank, "penalty": data["penalty"], "reward": data["reward"], 
        "hp": data["hp"], "max_hp": data["hp"], "type": dtype, "participants": set()
    }
    
    instructions = ""
    markup = None
    
    if dtype == 1:
        instructions = f"Boss HP is {data['hp']}! Mash the ATTACK button below to reduce it to 0!"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"⚔️ ATTACK (HP: {data['hp']})", callback_data="dungeon_attack")]])
    elif dtype == 2:
        word = random.choice(DUNGEON_WORDS)
        dungeon_info["word"] = word
        instructions = f"Quick! Reply to this message and type exactly: <code>{word}</code>"
    elif dtype == 3:
        instructions = "Heavy Boss! We need 3 different Hunters to click JOIN RAID!"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛡️ JOIN RAID (0/3)", callback_data="dungeon_join")]])

    caption = f"""🚨 <b>SYSTEM ALERT: A GATE HAS APPEARED!</b> 🚨

⛩️ <b>Rank:</b> {rank}-Rank Dungeon
👹 <b>Boss:</b> {data['name']}

⚔️ <b>HOW TO CLEAR:</b>
{instructions}

⏳ <i>Time limit: 5 Minutes before GATE BREAK!</i>"""

    try:
        msg = await context.bot.send_video(
            chat_id=chat_id, video=data["video"], caption=caption, 
            parse_mode="HTML", reply_markup=markup
        )
        dungeon_info["msg_id"] = msg.message_id
        dungeon_info["job"] = context.job_queue.run_once(gate_break, 300, data=chat_id)
        active_dungeons[chat_id] = dungeon_info
    except Exception as e:
        logging.error(f"Dungeon Spawn Error: {e}")

async def dungeon_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    ensure_user_registered(update)
    
    if chat_id not in active_dungeons: return await query.answer("Dungeon is already closed or broken!", show_alert=True)
    dungeon = active_dungeons[chat_id]
    
    if query.data == "dungeon_attack" and dungeon["type"] == 1:
        dungeon["participants"].add(user_id)
        dmg = random.randint(10, max(15, dungeon["max_hp"] // 10))
        dungeon["hp"] -= dmg
        
        if dungeon["hp"] <= 0:
            await query.answer("Boss Defeated! 🩸", show_alert=True)
            await clear_dungeon(update, context, chat_id, list(dungeon["participants"]))
        else:
            try:
                await query.answer(f"Dealt {dmg} DMG! ⚔️")
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"⚔️ ATTACK (HP: {dungeon['hp']})", callback_data="dungeon_attack")]])
                await query.edit_message_reply_markup(reply_markup=markup)
            except: pass
            
    elif query.data == "dungeon_join" and dungeon["type"] == 3:
        if user_id in dungeon["participants"]: return await query.answer("You already joined the raid!", show_alert=True)
        dungeon["participants"].add(user_id)
        count = len(dungeon["participants"])
        
        if count >= 3:
            await query.answer("Raid Full! Boss Defeated! 🛡️", show_alert=True)
            await clear_dungeon(update, context, chat_id, list(dungeon["participants"]))
        else:
            try:
                await query.answer("You joined the raid! 🛡️")
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"🛡️ JOIN RAID ({count}/3)", callback_data="dungeon_join")]])
                await query.edit_message_reply_markup(reply_markup=markup)
            except: pass

# ------------- CORE TEXT HANDLER (MODIFIED FOR DUNGEONS) -------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id, user, msg_lower = update.effective_chat.id, update.effective_user, update.message.text.lower()
    
    ensure_user_registered(update)
    
# ⚔️ NEW: DUNGEON TYPING MECHANIC
    if chat_id in active_dungeons and active_dungeons[chat_id]["type"] == 2:
        if update.message.reply_to_message and update.message.reply_to_message.message_id == active_dungeons[chat_id]["msg_id"]:
            if msg_lower == active_dungeons[chat_id]["word"].lower():
                await clear_dungeon(update, context, chat_id, [user.id])
                return 

    # ⚔️ NEW: DUNGEON TRIGGER COUNTER
    if update.effective_chat.type in ["group", "supergroup"]:
        group_msg_counts[chat_id] += 1
        if group_msg_counts[chat_id] >= 30:
            group_msg_counts[chat_id] = 0
            if chat_id not in active_dungeons:
                asyncio.create_task(spawn_dungeon(update, context, chat_id))

    if user.id != OWNER_ID:
        hunter_db[user.id]["exp"] += 1 
        if hunter_db[user.id]["exp"] % 5 == 0: save_hunter(user.id) # DB Save

    if user.id in admins_db:
        if context.user_data.pop("awaiting_broadcast", None):
            success = 0
            for cid in list(known_groups.keys()):
                try: 
                    await context.bot.send_message(cid, f"📢 **Broadcast Message:**\n\n{update.message.text}", parse_mode="Markdown")
                    success += 1
                except: pass
            return await update.message.reply_text(f"✅ Broadcast sent to {success} groups!")
            
        if user.id == OWNER_ID:
            if context.user_data.pop("awaiting_add_admin", None):
                try: admins_db.add(int(update.message.text.strip())); save_admins(); await update.message.reply_text("✅ Admin added.")
                except: await update.message.reply_text("❌ Invalid ID.")
                return
            if context.user_data.pop("awaiting_remove_admin", None):
                try: 
                    if int(update.message.text.strip()) != OWNER_ID: admins_db.discard(int(update.message.text.strip())); save_admins(); await update.message.reply_text("✅ Removed.")
                except: await update.message.reply_text("❌ Invalid ID.")
                return

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

    if user.id in afk_db:
        afk_db.pop(user.id); await update.message.reply_text(f"👋 Welcome back {_display_name(user)}, AFK removed!")
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id in afk_db:
        afk_user = afk_db[update.message.reply_to_message.from_user.id]
        await update.message.reply_text(f"💤 {afk_user['name']} is currently AFK: {afk_user['reason']}")

    if msg_lower in filters_db[chat_id]: return await update.message.reply_text(filters_db[chat_id][msg_lower])

    bot_un = context.bot.username.lower() if context.bot.username else ""
    mentioned = (update.message.entities and any(e.type == "mention" and bot_un in msg_lower for e in update.message.entities)) or any(f in msg_lower for f in filters_db[chat_id].keys())
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg_lower in ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","gn"] and not mentioned and not replied:
        await update.message.reply_text(random.choice(["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie"]))
    elif mentioned or replied:
        await ai_reply(update, context)

# ------------- MAIN -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # NEW: Button conflict fix using Regex patterns!
    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(broadcast|list_groups|add_admin|remove_admin|list_admins)$"))
    application.add_handler(CallbackQueryHandler(dungeon_button_handler, pattern="^dungeon_"))
    
    application.add_handler(CommandHandler("commands", commands_list))

    application.add_handler(CommandHandler("stats", hunter_profile))
    application.add_handler(CommandHandler("hunt", hunt))
    application.add_handler(CommandHandler("daily", daily_quest))
    application.add_handler(CommandHandler("give", give_exp))
    application.add_handler(CommandHandler("top_hunter", top_hunter_local))
    application.add_handler(CommandHandler("world_top", world_top_global))

    mod_cmds = ["ban", "unban", "kick", "mute", "unmute", "pin", "unpin", "promote"]
    application.add_handler(CommandHandler(mod_cmds, mod_action))
    
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

    application.add_handler(CommandHandler("purge", purge))
    application.add_handler(CommandHandler("purgegroup", purge_group))
    
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    if application.job_queue:
        ist = ZoneInfo("Asia/Kolkata")
        application.job_queue.run_daily(couple_daily_reset, time=dt_time(hour=1, minute=0, tzinfo=ist))

    logging.info("🤖 Bot starting...")
    application.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", 10000)), webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
