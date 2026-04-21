# bot.py - CINDRELLA final (Emoji Syntax Error Fixed + Built-in Server + Memory)
import os
import logging
import json
import random
import re
import httpx
import asyncio
import time
import urllib.parse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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
from collections import defaultdict, deque

# ----------------- CONFIG -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI") 

ADMIN_IDS = set(json.loads(os.environ.get("ADMIN_IDS", "[]")))
admins_db = ADMIN_IDS.union({OWNER_ID})

# --- BUILT-IN DUMMY SERVER (NO FLASK) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        # ERROR FIXED HERE: Used .encode('utf-8') instead of b"..."
        self.wfile.write("🌸 CINDRELLA BOT IS AWAKE AND RUNNING! 🌸".encode('utf-8'))
    
    def log_message(self, format, *args):
        pass # Faltu logs hide karne ke liye

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def keep_alive():
    # Render URL ya Fallback URL
    url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL") or f"http://localhost:{os.environ.get('PORT', 10000)}"
    while True:
        time.sleep(300) # Har 5 minute mein ping
        try:
            httpx.get(url, timeout=5)
        except:
            pass
# ----------------------------------------

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

chat_history_db = defaultdict(list)
recent_messages_db = defaultdict(lambda: deque(maxlen=1000))
known_groups = {} 
chat_members_db = defaultdict(set) 
hunter_db = {} 

group_msg_counts = defaultdict(int)
active_dungeons = {}
arise_targets = {} 

ALL_SHADOWS = ["Goblin Chieftain", "Direwolf Alpha", "High Orc Kargal", "Assassin Kasaka", "Giant Iron Golem", "Tank", "Tusk", "Ant King Beru", "Blood-Red Igris", "Kamish", "Bellion"]

DUNGEON_RANKS = {
    "E": {"video": "https://files.catbox.moe/ne4vk6.mp4", "reward": 50, "crystals": 5, "penalty": 10, "hp": 100, "name": "Goblin Chieftain"},
    "D": {"video": "https://files.catbox.moe/ne4vk6.mp4", "reward": 80, "crystals": 10, "penalty": 20, "hp": 200, "name": "Direwolf Alpha"},
    "C": {"video": "https://files.catbox.moe/nyvaoy.mp4", "reward": 150, "crystals": 20, "penalty": 40, "hp": 400, "name": "High Orc Kargal"},
    "B": {"video": "https://files.catbox.moe/nyvaoy.mp4", "reward": 250, "crystals": 40, "penalty": 60, "hp": 600, "name": "Assassin Kasaka"},
    "A": {"video": "https://files.catbox.moe/k5doyt.mp4", "reward": 400, "crystals": 80, "penalty": 100, "hp": 1000, "name": "Giant Iron Golem"},
    "S": {"video": "https://files.catbox.moe/k5doyt.mp4", "reward": 800, "crystals": 150, "penalty": 200, "hp": 2000, "name": "Ant King Beru"},
    "RED": {"video": "https://files.catbox.moe/8dxlw3.mp4", "reward": 1500, "crystals": 300, "penalty": 400, "hp": 3000, "name": "Blood-Red Igris"}
}
DUNGEON_WORDS = ["ARISE", "SMASH", "KILL", "WAKE UP", "FIGHT", "DEFEND"]
active_pvps = {}

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
                "last_daily": hnt.get("last_daily", ""),
                "crystals": hnt.get("crystals", 0),
                "streak": hnt.get("streak", 0),
                "loot_boxes": hnt.get("loot_boxes", 0),
                "shadows": hnt.get("shadows", []),
                "title": hnt.get("title", "")
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

def _display_name(user):
    return str(getattr(user, "first_name", None) or getattr(user, "username", None) or "User")

def mention_html(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</a>'

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    if update.message.reply_to_message: 
        return update.message.reply_to_message.from_user.id
    if context.args:
        arg = context.args[0]
        if arg.isdigit() or (arg.startswith('-') and arg[1:].isdigit()):
            return int(arg)
        search_arg = arg if arg.startswith('@') else f"@{arg}"
        search_arg_lower = search_arg.lower()
        for uid, data in hunter_db.items():
            uname = data.get("username", "")
            if uname and uname.lower() == search_arg_lower:
                return uid
        try:
            admins = await context.bot.get_chat_administrators(update.effective_chat.id)
            for admin in admins:
                if admin.user.username and f"@{admin.user.username.lower()}" == search_arg_lower:
                    return admin.user.id
        except: pass
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == 'text_mention' and entity.user:
                    return entity.user.id
        try: 
            chat = await context.bot.get_chat(search_arg)
            return chat.id
        except: 
            return None
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
            if action in ["purge", "purgegroup", "purgeall", "filter", "blacklist", "rules"]: return member.can_delete_messages
            if action in ["promote", "demote"]: return member.can_promote_members
        return False
    except: return False

def ensure_user_registered(update: Update):
    user, chat = update.effective_user, update.effective_chat
    if not user: return
    username = f"@{user.username}" if user.username else ""
    if user.id not in hunter_db:
        hunter_db[user.id] = {"name": _display_name(user), "username": username, "exp": 0, "last_hunt": 0, "last_daily": "", "crystals": 0, "streak": 0, "loot_boxes": 0, "shadows": [], "title": ""}
    
    for key, val in [("crystals", 0), ("streak", 0), ("loot_boxes", 0), ("shadows", []), ("title", "")]:
        if key not in hunter_db[user.id]: hunter_db[user.id][key] = val

    hunter_db[user.id]["name"] = _display_name(user)
    hunter_db[user.id]["username"] = username
    
    if user.id == OWNER_ID: 
        hunter_db[user.id]["exp"] = 9999999
        hunter_db[user.id]["crystals"] = 9999999
        hunter_db[user.id]["loot_boxes"] = 9999
        hunter_db[user.id]["shadows"] = ALL_SHADOWS.copy()
        
    if chat and chat.type in ["group", "supergroup"]:
        chat_members_db[chat.id].add(user.id)
        if chat.title and (chat.id not in known_groups or known_groups[chat.id] != chat.title):
            known_groups[chat.id] = chat.title
            save_group(chat.id, chat.title)

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat = update.effective_chat
    sender = update.effective_user
    
    target_id = None
    target_user_obj = None

    if update.message.reply_to_message:
        target_user_obj = update.message.reply_to_message.from_user
        target_id = target_user_obj.id
    elif context.args:
        target_id = await get_user_id(update, context)
        if not target_id:
            return await update.message.reply_text("❌ System Error: User not found! Unhone group mein koi message nahi kiya hai, ya fir username galat hai.")
    else:
        target_id = sender.id
        target_user_obj = sender

    target_bio = "System Hidden"
    target_name = "Unknown Hunter"
    target_uname = "None"

    try:
        target_chat = await context.bot.get_chat(target_id)
        target_bio = target_chat.bio if target_chat.bio else "No bio set."
        target_name = target_chat.first_name + (f" {target_chat.last_name}" if target_chat.last_name else "")
        target_uname = f"@{target_chat.username}" if target_chat.username else "None"
    except:
        if target_user_obj:
            target_name = _display_name(target_user_obj)
            target_uname = f"@{target_user_obj.username}" if target_user_obj.username else "None"
        elif target_id in hunter_db:
            target_name = hunter_db[target_id]["name"]
            target_uname = hunter_db[target_id]["username"] or "None"

    group_bio = "No description available."
    group_uname = "None"
    group_title = chat.title if chat.type != 'private' else 'Private Chat'
    
    if chat.type != 'private':
        try:
            group_chat = await context.bot.get_chat(chat.id)
            group_bio = group_chat.description if group_chat.description else "No group bio set."
            group_uname = f"@{group_chat.username}" if group_chat.username else "None"
        except: pass
    
    dc_id = (target_id % 5) + 1 
    
    chat_id_str = f"<code>{chat.id}</code>"
    user_id_str = f"<code>{target_id}</code>"
    
    text = f"""🔍 <b>Chat Information</b>

<blockquote>👤 <b>Profile Details:</b>
├── <b>Name:</b> {target_name}
├── <b>ID:</b> {user_id_str}
├── <b>DC ID:</b> {dc_id}
└── <b>Username:</b> {target_uname}</blockquote>

<blockquote>💬 <b>Bio:</b> {target_bio} ❞</blockquote>

<blockquote>👥 <b>Group Information:</b>
├── <b>Title:</b> {group_title}
├── <b>ID:</b> {chat_id_str}
└── <b>Username:</b> {group_uname}</blockquote>

<blockquote>💬 <b>Bio:</b> {group_bio} ❞</blockquote>"""

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Profile", url=f"tg://user?id={target_id}")]
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

# ------------- RPG SYSTEM -------------
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
        hunter_db[target_user.id] = {"name": _display_name(target_user), "username": username, "exp": 0, "last_hunt": 0, "last_daily": "", "crystals": 0, "streak": 0, "loot_boxes": 0, "shadows": [], "title": ""}
    
    if target_user.id == OWNER_ID: 
        hunter_db[target_user.id]["exp"] = 9999999
        hunter_db[target_user.id]["crystals"] = 9999999
        hunter_db[target_user.id]["loot_boxes"] = 9999
        hunter_db[target_user.id]["shadows"] = ALL_SHADOWS.copy()

    data = hunter_db[target_user.id]
    level, rank = get_hunter_stats(data["exp"], target_user.id)
    uname_display = f" ({data['username']})" if data['username'] else ""
    safe_name = str(data['name']).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    title_disp = f"\n👑 <b>Title:</b> {data['title']}" if data.get("title") else ""
    
    shadow_list = data.get("shadows", [])
    shadows_count = len(shadow_list)
    shadow_names = ", ".join(set(shadow_list)) if shadows_count > 0 else "None"
    
    exp_disp = data['exp'] if level != 'MAX' else '∞'
    cryst_disp = data.get('crystals', 0) if level != 'MAX' else '∞'
    loot_disp = data.get('loot_boxes', 0) if level != 'MAX' else '∞'
    
    text = f"""🪪 <b>HUNTER LICENSE</b>

👤 <b>Name:</b> {safe_name}{uname_display}{title_disp}
🎖 <b>Rank:</b> {rank}
📊 <b>Level:</b> {level}
⚡ <b>EXP:</b> {exp_disp}
🔮 <b>Magic Crystals:</b> {cryst_disp}
👥 <b>Shadow Soldiers:</b> {shadows_count} <i>({shadow_names})</i>
🔥 <b>Daily Streak:</b> {data.get('streak', 0)} Days
🧰 <b>Loot Boxes:</b> {loot_disp}"""

    await update.message.reply_text(text, parse_mode="HTML")

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user, now = update.effective_user, time.time()
    data = hunter_db[user.id]
    
    if now - data["last_hunt"] < 3600: 
        m, s = divmod(int(3600 - (now - data["last_hunt"])), 60)
        return await update.message.reply_text(f"⏳ Dungeon portal closed! Wait {m}m {s}s to hunt again. (Use /shop to buy a Dungeon Key!)")
    
    data["last_hunt"] = now
    shadow_bonus = len(data.get("shadows", [])) * 5

    events = [
        ("🟢 E-Rank Gate: Defeated 5 Goblins!", 25, 2), 
        ("🟢 D-Rank Gate: Killed giant slimes.", 40, 4),
        ("🟡 C-Rank Gate: Fought High Orcs.", 70, 8), 
        ("🔴 Boss Encounter! Barely escaped with your life.", -10, 0),
        ("🌟 Double Dungeon! You found a secret reward!", 120, 15), 
        ("❌ Ambushed by another hunter! Lost some EXP.", -20, 0)
    ]
    event, exp_gain, cryst_gain = random.choice(events)
    
    if exp_gain > 0: exp_gain += shadow_bonus
    
    if user.id != OWNER_ID: 
        data["exp"] = max(0, data["exp"] + exp_gain)
        data["crystals"] += cryst_gain
    
    save_hunter(user.id)
    level, rank = get_hunter_stats(data["exp"], user.id)
    shadow_text = f" (Shadow Bonus: +{shadow_bonus})" if shadow_bonus > 0 and exp_gain > 0 else ""
    await update.message.reply_text(f"⛩️ **Dungeon Raid Results:**\n\n{event}\n⚡ **EXP:** {exp_gain}{shadow_text} | 🔮 **Crystals:** {cryst_gain}\n📊 **Total EXP:** {data['exp'] if level != 'MAX' else '∞'} | **Level:** {level}")

async def daily_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    now_ist = dt.now(ZoneInfo("Asia/Kolkata"))
    today = str(now_ist.date() if now_ist.hour >= 1 else (now_ist - timedelta(days=1)).date())
    yesterday = str((now_ist - timedelta(days=1)).date() if now_ist.hour >= 1 else (now_ist - timedelta(days=2)).date())
    
    data = hunter_db[user.id]
    if data["last_daily"] == today:
        return await update.message.reply_text("⏳ System: Daily Quest already completed! Next quest unlocks at 1:00 AM IST.")
        
    if data["last_daily"] == yesterday: data["streak"] = data.get("streak", 0) + 1
    else: data["streak"] = 1
        
    data["last_daily"] = today
    if user.id != OWNER_ID: 
        data["exp"] += 150
        data["crystals"] += 20
        
    streak_msg = f"🔥 Streak: Day {data['streak']}!"
    if data["streak"] % 7 == 0:
        data["loot_boxes"] += 1
        streak_msg += "\n🎁 **7-DAY REWARD: You received an S-Rank Loot Box! (Use /open_box)**"
    
    save_hunter(user.id)
    level, rank = get_hunter_stats(data["exp"], user.id)
    await update.message.reply_text(f"🏋️‍♂️ **Daily Quest Completed!**\n100 Pushups, 100 Situps, 10km Run!\n\n🌟 +150 EXP | 🔮 +20 Crystals\n{streak_msg}\n📊 Current Level: {level}")

async def open_loot_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    data = hunter_db[user.id]
    
    if data.get("loot_boxes", 0) <= 0 and user.id != OWNER_ID: 
        return await update.message.reply_text("❌ You don't have any S-Rank Loot Boxes. Complete a 7-day /daily streak to get one!")
        
    if user.id != OWNER_ID:
        data["loot_boxes"] -= 1
        
    exp_win = random.randint(500, 2000)
    cryst_win = random.randint(50, 200)
    
    if user.id != OWNER_ID:
        data["exp"] += exp_win
        data["crystals"] += cryst_win
    save_hunter(user.id)
    
    await update.message.reply_text(f"🧰 <b>Opening S-Rank Loot Box...</b>\n\n✨ <b>JACKPOT!</b> ✨\nYou found <b>{exp_win} EXP</b> and <b>{cryst_win} Magic Crystals</b> 🔮!", parse_mode="HTML")

async def give_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sender = update.effective_user
    
    if not update.message.reply_to_message: 
        return await update.message.reply_text("❌ Reply to a Hunter's message and type `/give` to send items.")
    target = update.message.reply_to_message.from_user
    if sender.id == target.id: 
        return await update.message.reply_text("❌ You cannot give items to yourself!")
        
    context.user_data["give_target_id"] = target.id
    context.user_data["give_target_name"] = _display_name(target)
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Give EXP", callback_data="give_exp"), InlineKeyboardButton("🔮 Give Crystals", callback_data="give_crystals")],
        [InlineKeyboardButton("🧰 Give Loot Box", callback_data="give_lootbox"), InlineKeyboardButton("👥 Give Shadow", callback_data="give_shadow")],
        [InlineKeyboardButton("❌ Cancel", callback_data="give_cancel")]
    ])
    await update.message.reply_text(f"🎁 What would you like to give to **{_display_name(target)}**?", parse_mode="Markdown", reply_markup=markup)

async def give_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    action = query.data.split("_")[1]
    
    if action == "cancel":
        context.user_data.pop("give_target_id", None)
        context.user_data.pop("give_item", None)
        context.user_data.pop("awaiting_give_amount", None)
        context.user_data.pop("awaiting_give_shadow", None)
        return await query.edit_message_text("❌ Transaction Cancelled.")
        
    target_id = context.user_data.get("give_target_id")
    if not target_id:
        return await query.answer("Session expired. Try /give again.", show_alert=True)
        
    target_name = context.user_data.get("give_target_name", "Hunter")
    
    if action == "shadow":
        s_shadows = hunter_db[user_id].get("shadows", [])
        if user_id == OWNER_ID: s_shadows = ALL_SHADOWS
        
        if not s_shadows:
            return await query.answer("You don't have any Shadow Soldiers to give!", show_alert=True)
            
        shadow_list = "\n".join([f"🌑 `{s}`" for s in set(s_shadows)])
        context.user_data["awaiting_give_shadow"] = True
        return await query.edit_message_text(f"👥 **Your Shadow Soldiers:**\n{shadow_list}\n\n*Type the EXACT name of the Shadow you want to give to {target_name}:*", parse_mode="Markdown")

    item_names = {"exp": "EXP ⚡", "crystals": "Magic Crystals 🔮", "lootbox": "S-Rank Loot Boxes 🧰"}
    context.user_data["give_item"] = action
    context.user_data["awaiting_give_amount"] = True
    
    await query.edit_message_text(f"🔢 How much **{item_names[action]}** do you want to give to {target_name}?\n\n*Type the number in the chat now:*", parse_mode="Markdown")

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

async def pvp_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    challenger = update.effective_user
    chat_id = update.effective_chat.id
    
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to the Hunter you want to duel with: `/pvp <amount>`")
    opponent = update.message.reply_to_message.from_user
    
    if challenger.id == opponent.id or opponent.is_bot: return await update.message.reply_text("❌ System error: Invalid target for duel.")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text("❌ Correct format: `/pvp <amount>`")
        
    bet = int(context.args[0])
    if bet < 10: return await update.message.reply_text("❌ Minimum bet is 10 EXP.")
    
    c_data = hunter_db[challenger.id]
    if c_data["exp"] < bet and challenger.id != OWNER_ID: return await update.message.reply_text(f"❌ You don't have enough EXP! (You have {c_data['exp']})")
        
    pvp_id = f"{chat_id}_{challenger.id}_{opponent.id}_{int(time.time())}"
    active_pvps[pvp_id] = {"c_id": challenger.id, "o_id": opponent.id, "bet": bet, "c_name": _display_name(challenger), "o_name": _display_name(opponent)}
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ ACCEPT", callback_data=f"pvp_accept_{pvp_id}"), InlineKeyboardButton("🏃 DECLINE", callback_data=f"pvp_decline_{pvp_id}")]
    ])
    
    await update.message.reply_text(
        f"⚠️ **[ DUEL REQUEST ]** ⚠️\n\n{mention_html(challenger.id, _display_name(challenger))} challenged {mention_html(opponent.id, _display_name(opponent))}!\n💰 **Bet:** {bet} EXP\n\nDo you accept the duel?",
        parse_mode="HTML", reply_markup=markup
    )

async def pvp_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split("_")
    action, pvp_id = data[1], "_".join(data[2:])
    
    if pvp_id not in active_pvps: return await query.answer("Duel expired or already finished!", show_alert=True)
    pvp = active_pvps[pvp_id]
    
    if user_id != pvp["o_id"] and user_id != pvp["c_id"]: return await query.answer("This duel is not for you!", show_alert=True)
    if action == "decline" and user_id == pvp["o_id"]:
        del active_pvps[pvp_id]
        return await query.edit_message_text(f"🏃 {pvp['o_name']} declined the duel. Coward!")
    
    if action == "accept" and user_id == pvp["o_id"]:
        if hunter_db[pvp["o_id"]]["exp"] < pvp["bet"] and pvp["o_id"] != OWNER_ID:
            return await query.answer("You don't have enough EXP to accept!", show_alert=True)
            
        await query.edit_message_text(f"⚔️ **DUEL STARTED!**\n{pvp['c_name']} VS {pvp['o_name']}\n\n*Clashing weapons...*")
        await asyncio.sleep(1.5)
        
        c_lvl, _ = get_hunter_stats(hunter_db[pvp["c_id"]]["exp"], pvp["c_id"])
        o_lvl, _ = get_hunter_stats(hunter_db[pvp["o_id"]]["exp"], pvp["o_id"])
        
        c_weight = c_lvl if c_lvl != "MAX" else 999
        o_weight = o_lvl if o_lvl != "MAX" else 999
        
        winner_id, loser_id = (pvp["c_id"], pvp["o_id"]) if random.choices([True, False], weights=[c_weight+10, o_weight+10])[0] else (pvp["o_id"], pvp["c_id"])
        
        if winner_id != OWNER_ID: hunter_db[winner_id]["exp"] += pvp["bet"]
        if loser_id != OWNER_ID: hunter_db[loser_id]["exp"] = max(0, hunter_db[loser_id]["exp"] - pvp["bet"])
        
        save_hunter(winner_id); save_hunter(loser_id)
        w_name = hunter_db[winner_id]["name"]
        l_name = hunter_db[loser_id]["name"]
        
        await query.edit_message_text(f"🏆 **DUEL FINISHED!** 🏆\n\n💥 {w_name} dominated the fight and defeated {l_name}!\n\n🏅 **{w_name}** won {pvp['bet']} EXP!")
        del active_pvps[pvp_id]

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    cryst = hunter_db[user.id].get("crystals", 0)
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧪 Healing Potion (50 🔮) - Remove 1 Warn", callback_data="shop_heal")],
        [InlineKeyboardButton("🗝️ Dungeon Key (100 🔮) - Reset /hunt cooldown", callback_data="shop_key")],
        [InlineKeyboardButton("👑 Custom Title (500 🔮) - Add profile title", callback_data="shop_title")]
    ])
    await update.message.reply_text(f"🛒 **SYSTEM SHOP** 🛒\n\n🔮 **Your Magic Crystals:** {cryst if user.id != OWNER_ID else '∞'}\n\nBuy items to aid your journey:", reply_markup=markup)

async def shop_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    action = query.data.split("_")[1]
    chat_id = query.message.chat.id
    
    data = hunter_db[user_id]
    cryst = data.get("crystals", 0)
    
    if action == "heal":
        if cryst < 50 and user_id != OWNER_ID: return await query.answer("Not enough crystals!", show_alert=True)
        if warnings_db[chat_id][user_id] <= 0: return await query.answer("You have 0 warnings, no need to heal!", show_alert=True)
        if user_id != OWNER_ID: data["crystals"] -= 50
        warnings_db[chat_id][user_id] -= 1
        save_hunter(user_id)
        await query.answer("Purchased Healing Potion! 1 Warning removed.", show_alert=True)
        
    elif action == "key":
        if cryst < 100 and user_id != OWNER_ID: return await query.answer("Not enough crystals!", show_alert=True)
        if user_id != OWNER_ID: data["crystals"] -= 100
        data["last_hunt"] = 0
        save_hunter(user_id)
        await query.answer("Purchased Dungeon Key! You can /hunt again right now.", show_alert=True)
        
    elif action == "title":
        if cryst < 500 and user_id != OWNER_ID: return await query.answer("Not enough crystals!", show_alert=True)
        if user_id != OWNER_ID: data["crystals"] -= 500
        titles = ["Shadow Monarch", "S-Rank Elite", "Guild Master's Right Hand", "Demon King", "Dragon Slayer"]
        new_title = random.choice(titles)
        data["title"] = new_title
        save_hunter(user_id)
        await query.answer(f"Purchased Title! You are now known as: {new_title}", show_alert=True)

# ------------- DUNGEON SYSTEM -------------
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
                
        break_caption = f"""💀 <b>[ SYSTEM WARNING ]</b> 💀
<i>Hunters failed to clear the dungeon in time...</i>

💠 <b>STATUS:</b> ⚫ <b>GATE BREAK (FAILED)</b>
⛩️ <b>GATE RANK:</b> <code> {dungeon['rank']}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {DUNGEON_RANKS[dungeon['rank']]['name']} (ESCAPED) </code>"""
        
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=dungeon["msg_id"], caption=break_caption, parse_mode="HTML")
            await context.bot.send_message(chat_id, f"🚨 <b>GATE BREAK!</b> The Boss escaped and attacked the Guild!\n📉 Penalty: {affected} active Hunters lost {penalty} EXP.", parse_mode="HTML")
        except: pass

async def clear_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, participants: list, last_hitter_id: int):
    dungeon = active_dungeons.pop(chat_id, None)
    if not dungeon: return
    
    if "job" in dungeon: dungeon["job"].schedule_removal()
    
    reward = dungeon["reward"]
    cryst = dungeon["crystals"]
    winners_text = ""
    
    for uid in participants:
        if uid in hunter_db and uid != OWNER_ID:
            hunter_db[uid]["exp"] += reward
            hunter_db[uid]["crystals"] += cryst
            save_hunter(uid)
            uname = hunter_db[uid].get('username', '')
            display_uname = uname if uname else hunter_db[uid]['name']
            winners_text += f"🗡️ {display_uname} <code> (+{reward} EXP, +{cryst} 🔮) </code>\n"
            
    clear_caption = f"""✅ <b>[ SYSTEM NOTIFICATION ]</b> ✅
<i>The Gate has been successfully secured!</i>

💠 <b>STATUS:</b> 🔴 <b>CLOSED (CLEARED)</b>
⛩️ <b>GATE RANK:</b> <code> {dungeon['rank']}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {DUNGEON_RANKS[dungeon['rank']]['name']} (DEFEATED) </code>"""
            
    try:
        await context.bot.edit_message_caption(chat_id=chat_id, message_id=dungeon["msg_id"], caption=clear_caption, parse_mode="HTML")
        
        boss_name = DUNGEON_RANKS[dungeon['rank']]['name']
        new_msg = f"""🎊 <b>DUNGEON CONQUERED!</b> 🎊

🏆 <b>HEROES OF THE RAID:</b>
{winners_text}

🌑 {mention_html(last_hitter_id, hunter_db[last_hitter_id]['name'])}, you delivered the final blow! The Boss's soul lingers.
⏳ You have 30 seconds to type <code>/arise</code> and attempt Shadow Extraction!"""
        
        await context.bot.send_message(chat_id, new_msg, parse_mode="HTML")
        arise_targets[chat_id] = {"uid": last_hitter_id, "boss": boss_name, "time": time.time()}
    except: pass

async def arise_shadow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in arise_targets or arise_targets[chat_id]["uid"] != user_id:
        return await update.message.reply_text("❌ There is no shadow for you to extract here, or you lack the authority.")
        
    target = arise_targets.pop(chat_id)
    if time.time() - target["time"] > 30:
        return await update.message.reply_text("❌ You took too long. The shadow faded into the abyss.")
        
    if random.choice([True, False]):
        hunter_db[user_id]["shadows"].append(target["boss"])
        save_hunter(user_id)
        await update.message.reply_text(f"🌑 <b>SHADOW EXTRACTION SUCCESSFUL!</b> 🌑\n\n<i>\"Arise.\"</i>\n{target['boss']} is now your loyal Shadow Soldier!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"🌑 <b>SHADOW EXTRACTION FAILED.</b> 🌑\n\n<i>The soul of {target['boss']} resisted your command and vanished.</i>", parse_mode="HTML")

async def spawn_dungeon(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    ranks = ["E", "E", "D", "D", "C", "C", "B", "A", "S", "RED"]
    rank = random.choice(ranks)
    data = DUNGEON_RANKS[rank]
    
    dtype = random.choice([1, 2, 3])
    
    dungeon_info = {
        "rank": rank, "penalty": data["penalty"], "reward": data["reward"], "crystals": data["crystals"],
        "hp": data["hp"], "max_hp": data["hp"], "type": dtype, "participants": []
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

    caption = f"""⚠️ <b>[ SYSTEM NOTIFICATION ]</b> ⚠️
<i>A dimensional rift has opened in the Guild!</i>

💠 <b>STATUS:</b> 🟢 <b>OPEN</b>
⛩️ <b>GATE RANK:</b> <code> {rank}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {data['name']} </code>
🩸 <b>BOSS HP:</b> <code> {data['hp']} </code>

📜 <b>MISSION LOG:</b>
<i>{instructions}</i>

⏳ <b>TIME REMAINING:</b> <code> 05:00 Minutes </code>
🎁 <b>CLEAR REWARD:</b> <code> +{data['reward']} EXP, +{data['crystals']} 🔮 </code>"""

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
        if user_id not in dungeon["participants"]: dungeon["participants"].append(user_id)
        dmg = random.randint(10, max(15, dungeon["max_hp"] // 10))
        dungeon["hp"] -= dmg
        
        if dungeon["hp"] <= 0:
            await query.answer("Boss Defeated! 🩸", show_alert=True)
            await clear_dungeon(update, context, chat_id, dungeon["participants"], user_id)
        else:
            try:
                await query.answer(f"Dealt {dmg} DMG! ⚔️")
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"⚔️ ATTACK (HP: {dungeon['hp']})", callback_data="dungeon_attack")]])
                await query.edit_message_reply_markup(reply_markup=markup)
            except: pass
            
    elif query.data == "dungeon_join" and dungeon["type"] == 3:
        if user_id in dungeon["participants"]: return await query.answer("You already joined the raid!", show_alert=True)
        dungeon["participants"].append(user_id)
        count = len(dungeon["participants"])
        
        if count >= 3:
            await query.answer("Raid Full! Boss Defeated! 🛡️", show_alert=True)
            await clear_dungeon(update, context, chat_id, dungeon["participants"], user_id)
        else:
            try:
                await query.answer("You joined the raid! 🛡️")
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"🛡️ JOIN RAID ({count}/3)", callback_data="dungeon_join")]])
                await query.edit_message_reply_markup(reply_markup=markup)
            except: pass

# ------------- MODERATION COMMANDS -------------
async def mod_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    action = update.message.text.split()[0][1:].split('@')[0].lower()
    if not await check_rights(update, action): return await update.message.reply_text("❌ You don't have Admin rights/permissions to do this.")
    
    target_id = await get_user_id(update, context)
    if not target_id and action not in ["unpin"]: 
        return await update.message.reply_text("❌ User not found! Reply to their message, or provide a valid ID/Username.")
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
        elif action == "demote":
            await context.bot.promote_chat_member(
                chat_id, target_id, can_manage_chat=False, can_delete_messages=False, 
                can_manage_video_chats=False, can_restrict_members=False, 
                can_promote_members=False, can_change_info=False, 
                can_invite_users=False, can_pin_messages=False, is_anonymous=False
            )
            await update.message.reply_text(f"📉 Demoted {target_id}. Unko ab wapas normal member bana diya gaya hai.")
    except BadRequest as e: await update.message.reply_text(f"❌ Error: {e.message}")
    except Exception as e: await update.message.reply_text(f"❌ System Error: {e}")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purge"): return await update.message.reply_text("❌ Admin rights required.")
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to the oldest message to start purge.")
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
        msg_ids = list(range(max(1, curr - 100), curr + 1))
        for i in range(0, len(msg_ids), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids[i:i+100])
            except: pass
        ack = await context.bot.send_message(chat_id, "✅ Group cleanup (Last 100 messages) complete."); await asyncio.sleep(5); await ack.delete()
    except: await update.message.reply_text("❌ Messages too old/already deleted.")

async def purge_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgeall"): return await update.message.reply_text("❌ Admin rights required.")
    if not update.message.reply_to_message: return await update.message.reply_text("❌ Reply to the user whose messages you want to purge.")
    
    chat_id = update.effective_chat.id
    target_id = update.message.reply_to_message.from_user.id
    
    try:
        msg_ids_to_delete = [mid for mid, uid in recent_messages_db[chat_id] if uid == target_id]
        msg_ids_to_delete.append(update.message.message_id) 
        
        if not msg_ids_to_delete or len(msg_ids_to_delete) <= 1:
            return await update.message.reply_text("❌ Is user ke koi recent messages history mein nahi mile.")
            
        for i in range(0, len(msg_ids_to_delete), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids_to_delete[i:i+100])
            except: pass
            
        recent_messages_db[chat_id] = deque([(m, u) for m, u in recent_messages_db[chat_id] if u != target_id], maxlen=1000)
        
        ack = await context.bot.send_message(chat_id, f"✅ User ke sabhi recent messages delete ho gaye."); await asyncio.sleep(5); await ack.delete()
    except Exception as e: await update.message.reply_text(f"❌ Failed to purge all: {e}")

async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🌹 **CINDRELLA COMMANDS** 🌹

**⚔️ Solo Leveling (RPG):**
`/stats [reply]` - Check Hunter License & Items
`/hunt` - Enter Dungeon & Kill Monsters
`/daily` - Daily Quest, Streak & Loot Box
`/give <reply>` - Donate EXP, Crystals, Loot Box, Shadows
`/pvp <reply> <amount>` - Duel a Hunter for EXP
`/shop` - Buy Potions, Keys & Titles
`/arise` - Extract Shadow (After Boss Kill)
`/open_box` - Open S-Rank Loot Box
`/top_hunter` - Top 10 Hunters in Group
`/world_top` - Global Top 10 S-Rank Hunters

**🛠 Moderation:**
`/ban`, `/unban`, `/kick`, `/mute`, `/unmute`
`/pin`, `/unpin`, `/promote`, `/demote`
`/warn`, `/unwarn`
`/purge`, `/purgegroup`, `/purgeall`

**🛡 Group Management:**
`/id` - Get info about user/chat
`/addblacklist`, `/rmblacklist`, `/blocklist`
`/addfilter`, `/rmfilter`, `/setrules`, `/rules`

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
    if not target_id: return await update.message.reply_text("❌ User not found! Reply to their message, or provide a valid ID/Username.")
    chat_id = update.effective_chat.id
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_id in admins_db or target_member.status in ['administrator', 'creator']: return await update.message.reply_text("❌ Cannot warn an Admin.")
    except: pass

    warnings_db[chat_id][target_id] += 1
    count = warnings_db[chat_id][target_id]
    
    reason_args = context.args
    if reason_args and not update.message.reply_to_message:
        reason_args = reason_args[1:] 
    reason = " ".join(reason_args) if reason_args else "No reason given."
    
    if count >= 3:
        await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=False))
        warnings_db[chat_id][target_id] = 0
        await update.message.reply_text(f"🛑 User {target_id} reached 3 warnings and is now MUTED!")
    else: await update.message.reply_text(f"⚠️ Warned {target_id}! ({count}/3)\nReason: {reason}")

async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "unwarn"): return await update.message.reply_text("❌ Admin rights required.")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text("❌ User not found! Reply to their message, or provide a valid ID/Username.")
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

# ------------- ADMIN PANEL -------------
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text("Hey, I'm CINDRELLA 🌹—your AI Assistant!\nType /commands to see what I can do!", reply_markup=InlineKeyboardMarkup(keyboard))

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, chat = update.effective_chat.id, update.effective_chat
    try: member_count = await chat.get_member_count()
    except: member_count = "New"

    for member in update.message.new_chat_members:
        if not member.is_bot:
            username = f"@{member.username}" if member.username else "No Username"
            
            if member.id not in hunter_db:
                hunter_db[member.id] = {
                    "name": _display_name(member), "username": username if member.username else "",
                    "exp": 0, "last_hunt": 0, "last_daily": "", "crystals": 0, "streak": 0, 
                    "loot_boxes": 0, "shadows": [], "title": ""
                }
            chat_members_db[chat_id].add(member.id)
            save_hunter(member.id)

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
    user_id = update.effective_user.id
    
    if usage_count["date"] != str(date.today()): usage_count.update({"date": str(date.today()), "count": 0})
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    
    system_prompt = "You are CINDRELLA, an exceptionally smart, empathetic, friendly, and highly intelligent AI assistant. Your personality is witty, natural, and helpful, much like a close friend who knows a lot. CRITICAL RULES: 1. You must strictly reply in the exact same language and script the user uses (e.g., English, Hindi script, or Hinglish). 2. Keep your responses concise (1-4 lines), natural, and highly engaging. 3. Do not sound like a robotic AI. Use emojis naturally. 4. Remember the context of the conversation and be a great conversationalist."
    
    models = [
        "google/gemma-3-27b-it:free", 
        "meta-llama/llama-3.3-70b-instruct:free", 
        "nvidia/nemotron-3-nano-30b-a3b:free", 
        "stepfun/step-3.5-flash:free"
    ]
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history_db[user_id])
    messages.append({"role": "user", "content": message_text})
    
    for model in models:
        try:
            payload = {"model": model, "messages": messages}
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                
                if res.status_code == 429:
                    await asyncio.sleep(2) 
                    continue
                    
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                    usage_count["count"] += 1
                    
                    chat_history_db[user_id].append({"role": "user", "content": message_text})
                    chat_history_db[user_id].append({"role": "assistant", "content": reply})
                    if len(chat_history_db[user_id]) > 40:
                        chat_history_db[user_id] = chat_history_db[user_id][-40:]
                        
                    try: return await update.message.reply_text(reply[:4096])
                    except BadRequest: return await context.bot.send_message(chat_id=update.effective_chat.id, text=reply[:4096])
        except: 
            continue
            
    try: await update.message.reply_text("Server par thoda load hai, main ek minute mein wapas aati hoon! 🌸")
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

# ------------- CORE TEXT HANDLER -------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id, user, msg_lower = update.effective_chat.id, update.effective_user, update.message.text.lower()
    
    recent_messages_db[chat_id].append((update.message.message_id, user.id))
    
    ensure_user_registered(update)
    
    if context.user_data.get("awaiting_give_shadow"):
        shadow_name = update.message.text.strip()
        target_id = context.user_data["give_target_id"]
        target_name = context.user_data["give_target_name"]
        
        sender_data = hunter_db[user.id]
        if target_id not in hunter_db:
            hunter_db[target_id] = {"name": target_name, "username": "", "exp": 0, "last_hunt": 0, "last_daily": "", "crystals": 0, "streak": 0, "loot_boxes": 0, "shadows": [], "title": ""}
        target_data = hunter_db[target_id]
        
        s_shadows = sender_data.get("shadows", [])
        if user.id == OWNER_ID: s_shadows = ALL_SHADOWS
            
        matched_shadow = next((s for s in s_shadows if s.lower() == shadow_name.lower()), None)
        
        if not matched_shadow:
            context.user_data.pop("awaiting_give_shadow", None)
            context.user_data.pop("give_target_id", None)
            return await update.message.reply_text(f"❌ Tumhare paas '{shadow_name}' naam ka koi Shadow nahi hai. Transaction cancelled.")
            
        if user.id != OWNER_ID:
            sender_data["shadows"].remove(matched_shadow)
            
        target_data["shadows"].append(matched_shadow)
        save_hunter(user.id)
        save_hunter(target_id)
        
        context.user_data.pop("awaiting_give_shadow", None)
        context.user_data.pop("give_target_id", None)
        
        return await update.message.reply_text(f"✅ **SHADOW TRANSFERRED!**\n\n🌑 You gave **{matched_shadow}** to {target_name}!", parse_mode="Markdown")

    if context.user_data.get("awaiting_give_amount"):
        amount_str = update.message.text.strip()
        if amount_str.isdigit() and int(amount_str) > 0:
            amount = int(amount_str)
            item_type = context.user_data["give_item"]
            target_id = context.user_data["give_target_id"]
            target_name = context.user_data["give_target_name"]
            
            sender_data = hunter_db[user.id]
            if target_id not in hunter_db:
                hunter_db[target_id] = {"name": target_name, "username": "", "exp": 0, "last_hunt": 0, "last_daily": "", "crystals": 0, "streak": 0, "loot_boxes": 0, "shadows": [], "title": ""}
            target_data = hunter_db[target_id]
            
            db_keys = {"exp": "exp", "crystals": "crystals", "lootbox": "loot_boxes"}
            db_key = db_keys[item_type]
            item_names = {"exp": "EXP ⚡", "crystals": "Magic Crystals 🔮", "lootbox": "S-Rank Loot Boxes 🧰"}
            
            if user.id != OWNER_ID:
                if sender_data.get(db_key, 0) < amount:
                    context.user_data.pop("awaiting_give_amount", None)
                    return await update.message.reply_text(f"❌ Tumhare paas itne {item_names[item_type]} nahi hain!")
                sender_data[db_key] -= amount
                
            target_data[db_key] += amount
            save_hunter(user.id)
            save_hunter(target_id)
            
            context.user_data.pop("awaiting_give_amount", None)
            context.user_data.pop("give_target_id", None)
            context.user_data.pop("give_item", None)
            
            return await update.message.reply_text(f"✅ **SUCCESS!**\n\nYou gave **{amount} {item_names[item_type]}** to {target_name}!", parse_mode="Markdown")
        else:
            context.user_data.pop("awaiting_give_amount", None)
            context.user_data.pop("give_target_id", None)
            context.user_data.pop("give_item", None)
            return await update.message.reply_text("❌ Invalid amount. Transaction cancelled.")
    
    if chat_id in active_dungeons and active_dungeons[chat_id]["type"] == 2:
        if update.message.reply_to_message and update.message.reply_to_message.message_id == active_dungeons[chat_id]["msg_id"]:
            if msg_lower == active_dungeons[chat_id]["word"].lower():
                if user.id not in active_dungeons[chat_id]["participants"]: active_dungeons[chat_id]["participants"].append(user.id)
                await clear_dungeon(update, context, chat_id, active_dungeons[chat_id]["participants"], user.id)
                return 

    if update.effective_chat.type in ["group", "supergroup"]:
        group_msg_counts[chat_id] += 1
        if group_msg_counts[chat_id] >= 30:
            group_msg_counts[chat_id] = 0
            if chat_id not in active_dungeons:
                asyncio.create_task(spawn_dungeon(update, context, chat_id))

    if user.id != OWNER_ID:
        hunter_db[user.id]["exp"] += 5 
        if (hunter_db[user.id]["exp"] // 5) % 5 == 0: 
            save_hunter(user.id)

    if user.id in admins_db:
        if context.user_data.pop("awaiting_broadcast", None):
            success_groups = 0
            for cid in list(known_groups.keys()):
                try: 
                    await context.bot.send_message(cid, f"📢 **Broadcast Message:**\n\n{update.message.text}", parse_mode="Markdown")
                    success_groups += 1
                    await asyncio.sleep(0.05)
                except: pass
            
            success_users = 0
            for uid in list(hunter_db.keys()):
                try:
                    await context.bot.send_message(uid, f"📢 **System Broadcast:**\n\n{update.message.text}", parse_mode="Markdown")
                    success_users += 1
                    await asyncio.sleep(0.05)
                except: pass
                
            return await update.message.reply_text(f"✅ Broadcast successfully sent to **{success_groups} Groups** and **{success_users} Users DMs**!")
            
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

    if user.id not in admins_db:
        now = time.time()
        spam_tracker[chat_id][user.id] = [t for t in spam_tracker[chat_id][user.id] + [now] if now - t < 5]
        
        if len(spam_tracker[chat_id][user.id]) > 5:
            spam_tracker[chat_id][user.id] = []
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=ChatPermissions(can_send_messages=False))
                await context.bot.send_message(chat_id, f"🚫 {_display_name(user)} muted for spamming.")
            except: 
                pass 
            return 
            
        if any(word in msg_lower for word in blacklist_db[chat_id]):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id, f"🚫 Watch your language, {_display_name(user)}!")
            except: 
                pass
            return 

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
        await update.message.reply_text(random.choice(["System Online! 🌸","Guild Manager reporting! 💕","Hey Master! ⚔️","Dungeon ready when you are! ☀️"]))
    elif mentioned or replied:
        await ai_reply(update, context)

# ------------- MAIN -------------
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("id", get_id)) 
    
    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(broadcast|list_groups|add_admin|remove_admin|list_admins)$"))
    application.add_handler(CallbackQueryHandler(dungeon_button_handler, pattern="^dungeon_"))
    application.add_handler(CallbackQueryHandler(pvp_button_handler, pattern="^pvp_"))
    application.add_handler(CallbackQueryHandler(shop_button_handler, pattern="^shop_"))
    application.add_handler(CallbackQueryHandler(give_button_handler, pattern="^give_"))
    
    application.add_handler(CommandHandler("commands", commands_list))
    application.add_handler(CommandHandler("stats", hunter_profile))
    application.add_handler(CommandHandler("hunt", hunt))
    application.add_handler(CommandHandler("daily", daily_quest))
    application.add_handler(CommandHandler("give", give_menu))
    
    application.add_handler(CommandHandler("top_hunter", top_hunter_local))
    application.add_handler(CommandHandler("world_top", world_top_global))
    
    application.add_handler(CommandHandler("pvp", pvp_request))
    application.add_handler(CommandHandler("shop", shop_menu))
    application.add_handler(CommandHandler("arise", arise_shadow))
    application.add_handler(CommandHandler("open_box", open_loot_box))

    mod_cmds = ["ban", "unban", "kick", "mute", "unmute", "pin", "unpin", "promote", "demote"]
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
    application.add_handler(CommandHandler("purgeall", purge_all))
    
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    if application.job_queue:
        ist = ZoneInfo("Asia/Kolkata")
        application.job_queue.run_daily(couple_daily_reset, time=dt_time(hour=1, minute=0, tzinfo=ist))

    threading.Thread(target=run_dummy_server, daemon=True).start()

    logging.info("🤖 Bot starting in POLLING mode without server conflicts...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
