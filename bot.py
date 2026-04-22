# bot.py - CINDRELLA final (Super Memory Fix + 100+ Users Load Balancer)
import os
import logging
import json
import random
import re
import httpx
import asyncio
import time
import html
import urllib.parse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, ChatMemberAdministrator, ChatMemberOwner, ChatMember
)
from telegram.constants import ChatAction
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

# --- ULTIMATE PREMIUM EMOJI ENGINE ---
EMOJI_MAP = {
    "🙂": '<tg-emoji emoji-id="5361811943688512595">🙂</tg-emoji>',
    "🥺": '<tg-emoji emoji-id="5359556488857659527">🥺</tg-emoji>',
    "❤️": '<tg-emoji emoji-id="5362081079224180363">❤️</tg-emoji>',
    "👍": '<tg-emoji emoji-id="5361840191688417691">👍</tg-emoji>',
    "😈": '<tg-emoji emoji-id="5361977209735094094">😈</tg-emoji>',
    "😢": '<tg-emoji emoji-id="5361967838116453579">😢</tg-emoji>',
    "🤩": '<tg-emoji emoji-id="5359823764672489041">🤩</tg-emoji>',
    "😊": '<tg-emoji emoji-id="5359619088005997893">😊</tg-emoji>',
    "😘": '<tg-emoji emoji-id="5361870050301057412">😘</tg-emoji>',
    "🫣": '<tg-emoji emoji-id="5362088337718909649">🫣</tg-emoji>',
    "🐰": '<tg-emoji emoji-id="5361584138623132120">🐰</tg-emoji>',
    "💃": '<tg-emoji emoji-id="5361979846845014099">💃</tg-emoji>',
    "😠": '<tg-emoji emoji-id="5361727491746570163">😠</tg-emoji>',
    "😭": '<tg-emoji emoji-id="5361688841335872649">😭</tg-emoji>',
    "👻": '<tg-emoji emoji-id="5359348960332882020">👻</tg-emoji>',
    "🕊️": '<tg-emoji emoji-id="5361953187983006321">🕊️</tg-emoji>',
    "☺️": '<tg-emoji emoji-id="5359295840177366796">☺️</tg-emoji>',
    "💓": '<tg-emoji emoji-id="5361744791874837044">💓</tg-emoji>',
    "🦄": '<tg-emoji emoji-id="5361682407474863210">🦄</tg-emoji>',
    "🤪": '<tg-emoji emoji-id="5361979593441942591">🤪</tg-emoji>',
    "💗": '<tg-emoji emoji-id="5362027963363632114">💗</tg-emoji>',
    "💖": '<tg-emoji emoji-id="5361698629566341740">💖</tg-emoji>',
    "🥰": '<tg-emoji emoji-id="5359703393919050005">🥰</tg-emoji>',
    "💕": '<tg-emoji emoji-id="5359477766402090098">💕</tg-emoji>',
    "🧸": '<tg-emoji emoji-id="5361897482257177939">🧸</tg-emoji>',
    "✨": '<tg-emoji emoji-id="5362085090723633936">✨</tg-emoji>',
    "😴": '<tg-emoji emoji-id="5359720835781240886">😴</tg-emoji>',
    "❤️‍🩹": '<tg-emoji emoji-id="5362080112856538764">❤️‍🩹</tg-emoji>',
    "🤔": '<tg-emoji emoji-id="5359369473096688455">🤔</tg-emoji>',
    "🤗": '<tg-emoji emoji-id="5363789578559823865">🤗</tg-emoji>',
    "😌": '<tg-emoji emoji-id="5359306977027564797">😌</tg-emoji>',
    "⭐️": '<tg-emoji emoji-id="5359686514697576863">⭐️</tg-emoji>',
    "👑": '<tg-emoji emoji-id="5359686514697576863">⭐️</tg-emoji>', 
    "😏": '<tg-emoji emoji-id="5361728020027547890">😏</tg-emoji>',
    "💎": '<tg-emoji emoji-id="5361662345682623608">💎</tg-emoji>',
    "🔮": '<tg-emoji emoji-id="5361662345682623608">💎</tg-emoji>', 
    "🔪": '<tg-emoji emoji-id="5361627281569620072">🔪</tg-emoji>',
    "🔨": '<tg-emoji emoji-id="5361627281569620072">🔪</tg-emoji>', 
    "🗡️": '<tg-emoji emoji-id="5361627281569620072">🔪</tg-emoji>', 
    "💉": '<tg-emoji emoji-id="5361717162350223774">💉</tg-emoji>',
    "🌺": '<tg-emoji emoji-id="5359370357859951786">🌺</tg-emoji>',
    "🎂": '<tg-emoji emoji-id="5362086280429577357">🎂</tg-emoji>',
    "🦋": '<tg-emoji emoji-id="5361866446823497727">🦋</tg-emoji>',
    "💦": '<tg-emoji emoji-id="5361909619834755990">💦</tg-emoji>',
    "🕹️": '<tg-emoji emoji-id="5361902593268259979">🕹️</tg-emoji>',
    "🛡️": '<tg-emoji emoji-id="5361902593268259979">🕹️</tg-emoji>', 
    "🌈": '<tg-emoji emoji-id="5362079172258702306">🌈</tg-emoji>',
    "🤷‍♀️": '<tg-emoji emoji-id="5361754519975763173">🤷‍♀️</tg-emoji>',
    "🎀": '<tg-emoji emoji-id="5359335109063353153">🎀</tg-emoji>',
    "👀": '<tg-emoji emoji-id="5364188447877635731">👀</tg-emoji>',
    "🌸": '<tg-emoji emoji-id="5361957543079844962">🌸</tg-emoji>',
    "🐾": '<tg-emoji emoji-id="5361929222065494120">🐾</tg-emoji>',
    "👼": '<tg-emoji emoji-id="5359446911357035515">👼</tg-emoji>',
    "😜": '<tg-emoji emoji-id="5361537400789016060">😜</tg-emoji>',
    "☕️": '<tg-emoji emoji-id="5361703414159908977">☕️</tg-emoji>',
    "🌍": '<tg-emoji emoji-id="5359642014541423992">🌍</tg-emoji>',
    "💍": '<tg-emoji emoji-id="5362082384894237683">💍</tg-emoji>',
    "💋": '<tg-emoji emoji-id="5361621298680175398">💋</tg-emoji>',
    "🐱": '<tg-emoji emoji-id="5361566000976240609">🐱</tg-emoji>',
    "💔": '<tg-emoji emoji-id="5361978408030968361">💔</tg-emoji>',
    "🔇": '<tg-emoji emoji-id="5361874933678876634">🔇</tg-emoji>',
    "⏳": '<tg-emoji emoji-id="5361812489149360115">⏳</tg-emoji>',
    "🚀": '<tg-emoji emoji-id="5362036733686848529">🚀</tg-emoji>',
    "👎": '<tg-emoji emoji-id="5362061288014880649">👎</tg-emoji>',
    "💸": '<tg-emoji emoji-id="5359523546458496837">💸</tg-emoji>',
    "💰": '<tg-emoji emoji-id="5361866171945592038">💰</tg-emoji>',
    "💌": '<tg-emoji emoji-id="5359778766300128093">💌</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5361977776670779271">❌</tg-emoji>',
    "✅": '<tg-emoji emoji-id="5361693153483037923">✅</tg-emoji>',
    "📌": '<tg-emoji emoji-id="5361918188294512147">📌</tg-emoji>',
    "🤡": '<tg-emoji emoji-id="5361775402106756924">🤡</tg-emoji>',
    "🤣": '<tg-emoji emoji-id="5362088045661135278">🤣</tg-emoji>',
    "😂": '<tg-emoji emoji-id="5362088045661135278">🤣</tg-emoji>',
    "☠️": '<tg-emoji emoji-id="5361981590601735641">☠️</tg-emoji>',
    "🙏": '<tg-emoji emoji-id="5361727818164083480">🙏</tg-emoji>',
    "🎉": '<tg-emoji emoji-id="5361775092869112132">🎉</tg-emoji>',
    "❓": '<tg-emoji emoji-id="5359808302790222953">❓</tg-emoji>',
    "🤍": '<tg-emoji emoji-id="5362081079224180363">❤️</tg-emoji>',
    "🩷": '<tg-emoji emoji-id="5362027963363632114">💗</tg-emoji>',
    "😅": '<tg-emoji emoji-id="5361761572312064436">😊</tg-emoji>',
    "💯": '<tg-emoji emoji-id="5362085090723633936">✨</tg-emoji>'
}

def premium(text):
    """Replaces standard emojis with custom Telegram Premium aesthetic tags."""
    for std, prem in EMOJI_MAP.items():
        text = text.replace(std, prem)
    return text

# --- BUILT-IN DUMMY SERVER (NO FLASK) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write("🌸 CINDRELLA BOT IS AWAKE AND RUNNING! 🌸".encode('utf-8'))
    
    def log_message(self, format, *args):
        pass 

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL") or f"http://localhost:{os.environ.get('PORT', 10000)}"
    while True:
        time.sleep(300)
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
    "<b>Welcome to the aesthetic side, {name}! ✨\nWe are so happy to have you here, make yourself at home! 🎀</b>",
    "<b>Hey {name}! 🌸 Step into our world!\nDrop a 'hi' and let's get this party started! 🦋</b>",
    "<b>A lovely hello to {name}! 💕\nGrab a seat, relax, and enjoy the premium vibes! ☕️</b>",
    "<b>Look who just joined us! {name} is here! 🤩\nGet ready for some fun and good times! 🎉💖</b>"
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
            return await update.message.reply_text(premium("<b>❌ System Error:</b> User not found! Reply to a message or check the username. ✨"), parse_mode="HTML")
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

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("👤 Profile", url=f"tg://user?id={target_id}")]])
    await update.message.reply_text(premium(text), parse_mode="HTML", reply_markup=markup)

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

    await update.message.reply_text(premium(text), parse_mode="HTML")

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user, now = update.effective_user, time.time()
    data = hunter_db[user.id]
    
    if now - data["last_hunt"] < 3600: 
        m, s = divmod(int(3600 - (now - data["last_hunt"])), 60)
        return await update.message.reply_text(premium(f"<b>⏳ Dungeon portal closed!</b>\nWait {m}m {s}s to hunt again. ✨"), parse_mode="HTML")
    
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
    text = f"<b>⛩️ Dungeon Raid Results:</b>\n\n{event} ✨\n⚡ <b>EXP:</b> {exp_gain}{shadow_text} | 🔮 <b>Crystals:</b> {cryst_gain}\n📊 <b>Total EXP:</b> {data['exp'] if level != 'MAX' else '∞'} | <b>Level:</b> {level}"
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def daily_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    now_ist = dt.now(ZoneInfo("Asia/Kolkata"))
    today = str(now_ist.date() if now_ist.hour >= 1 else (now_ist - timedelta(days=1)).date())
    yesterday = str((now_ist - timedelta(days=1)).date() if now_ist.hour >= 1 else (now_ist - timedelta(days=2)).date())
    
    data = hunter_db[user.id]
    if data["last_daily"] == today:
        return await update.message.reply_text(premium("<b>⏳ Daily Quest already completed!</b> Next quest unlocks at 1:00 AM IST. 🌸"), parse_mode="HTML")
        
    if data["last_daily"] == yesterday: data["streak"] = data.get("streak", 0) + 1
    else: data["streak"] = 1
        
    data["last_daily"] = today
    if user.id != OWNER_ID: 
        data["exp"] += 150
        data["crystals"] += 20
        
    streak_msg = f"🔥 <b>Streak:</b> Day {data['streak']}!"
    if data["streak"] % 7 == 0:
        data["loot_boxes"] += 1
        streak_msg += "\n🎁 <b>7-DAY REWARD: You received an S-Rank Loot Box! (/open_box)</b>"
    
    save_hunter(user.id)
    level, rank = get_hunter_stats(data["exp"], user.id)
    text = f"<b>🏋️‍♂️ Daily Quest Completed!</b>\n100 Pushups, 100 Situps, 10km Run! 💦\n\n🌟 +150 EXP | 🔮 +20 Crystals\n{streak_msg}\n📊 <b>Current Level:</b> {level}"
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def open_loot_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    user = update.effective_user
    data = hunter_db[user.id]
    
    if data.get("loot_boxes", 0) <= 0 and user.id != OWNER_ID: 
        return await update.message.reply_text(premium("<b>❌ You don't have any S-Rank Loot Boxes.</b> Complete a 7-day /daily streak to get one! ✨"), parse_mode="HTML")
        
    if user.id != OWNER_ID:
        data["loot_boxes"] -= 1
        
    exp_win = random.randint(500, 2000)
    cryst_win = random.randint(50, 200)
    
    if user.id != OWNER_ID:
        data["exp"] += exp_win
        data["crystals"] += cryst_win
    save_hunter(user.id)
    
    text = f"<b>🧰 Opening S-Rank Loot Box...</b>\n\n✨ <b>JACKPOT!</b> ✨\nYou found <b>{exp_win} EXP</b> and <b>{cryst_win} Magic Crystals</b> 🔮!"
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def give_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sender = update.effective_user
    
    if not update.message.reply_to_message: 
        return await update.message.reply_text(premium("<b>❌ Reply to a Hunter's message</b> and type `/give` to send items. 🌸"), parse_mode="HTML")
    target = update.message.reply_to_message.from_user
    if sender.id == target.id: 
        return await update.message.reply_text(premium("<b>❌ You cannot give items to yourself!</b> 🤡"), parse_mode="HTML")
        
    context.user_data["give_target_id"] = target.id
    context.user_data["give_target_name"] = _display_name(target)
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Give EXP", callback_data="give_exp"), InlineKeyboardButton("🔮 Give Crystals", callback_data="give_crystals")],
        [InlineKeyboardButton("🧰 Give Loot Box", callback_data="give_lootbox"), InlineKeyboardButton("👥 Give Shadow", callback_data="give_shadow")],
        [InlineKeyboardButton("❌ Cancel", callback_data="give_cancel")]
    ])
    await update.message.reply_text(premium(f"<b>🎁 What would you like to give to {_display_name(target)}?</b> ✨"), parse_mode="HTML", reply_markup=markup)

async def give_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    action = query.data.split("_")[1]
    
    if action == "cancel":
        context.user_data.pop("give_target_id", None)
        context.user_data.pop("give_item", None)
        context.user_data.pop("awaiting_give_amount", None)
        context.user_data.pop("awaiting_give_shadow", None)
        return await query.edit_message_text(premium("<b>❌ Transaction Cancelled.</b> ✨"), parse_mode="HTML")
        
    target_id = context.user_data.get("give_target_id")
    if not target_id:
        return await query.answer("Session expired. Try /give again.", show_alert=True)
        
    target_name = context.user_data.get("give_target_name", "Hunter")
    
    if action == "shadow":
        s_shadows = hunter_db[user_id].get("shadows", [])
        if user_id == OWNER_ID: s_shadows = ALL_SHADOWS
        
        if not s_shadows:
            return await query.answer("You don't have any Shadow Soldiers to give!", show_alert=True)
            
        shadow_list = "\n".join([f"🌑 <code>{s}</code>" for s in set(s_shadows)])
        context.user_data["awaiting_give_shadow"] = True
        return await query.edit_message_text(premium(f"<b>👥 Your Shadow Soldiers:</b>\n{shadow_list}\n\n<i>Type the EXACT name of the Shadow you want to give to {target_name}:</i> ✨"), parse_mode="HTML")

    item_names = {"exp": "EXP ⚡", "crystals": "Magic Crystals 🔮", "lootbox": "S-Rank Loot Boxes 🧰"}
    context.user_data["give_item"] = action
    context.user_data["awaiting_give_amount"] = True
    
    await query.edit_message_text(premium(f"<b>🔢 How much {item_names[action]} do you want to give to {target_name}?</b>\n\n<i>Type the number in the chat now:</i> 🌸"), parse_mode="HTML")

async def top_hunter_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat_id = update.effective_chat.id
    members = chat_members_db.get(chat_id, set())
    sorted_hunters = sorted([uid for uid in members if uid in hunter_db], key=lambda x: hunter_db[x]["exp"], reverse=True)[:10]
    if not sorted_hunters: return await update.message.reply_text(premium("<b>No active hunters in this guild.</b> 🌸"), parse_mode="HTML")
        
    text = "<b>🏆 TOP 10 GUILD HUNTERS 🏆</b>\n\n"
    for i, uid in enumerate(sorted_hunters, 1):
        h = hunter_db[uid]
        level, rank = get_hunter_stats(h["exp"], uid)
        text += f"<b>{i}.</b> {str(h['name']).replace('<','&lt;')}{' '+h.get('username') if h.get('username') else ''} - Lvl {level} ({rank})\n"
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def world_top_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    sorted_hunters = sorted(hunter_db.items(), key=lambda x: x[1]["exp"], reverse=True)[:10]
    if not sorted_hunters: return await update.message.reply_text(premium("<b>The world is empty. No hunters found.</b> 🌸"), parse_mode="HTML")
        
    text = "<b>🌍 WORLD TOP 10 S-RANK HUNTERS 🌍</b>\n\n"
    for i, (uid, h) in enumerate(sorted_hunters, 1):
        level, rank = get_hunter_stats(h["exp"], uid)
        text += f"<b>{i}.</b> {str(h['name']).replace('<','&lt;')}{' '+h.get('username') if h.get('username') else ''} - Lvl {level} ({rank})\n"
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def pvp_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    challenger = update.effective_user
    chat_id = update.effective_chat.id
    
    if not update.message.reply_to_message: return await update.message.reply_text(premium("<b>❌ Reply to the Hunter you want to duel with:</b> `/pvp <amount>` ⚔️"), parse_mode="HTML")
    opponent = update.message.reply_to_message.from_user
    
    if challenger.id == opponent.id or opponent.is_bot: return await update.message.reply_text(premium("<b>❌ System error: Invalid target for duel.</b> 🤡"), parse_mode="HTML")
    if not context.args or not context.args[0].isdigit(): return await update.message.reply_text(premium("<b>❌ Correct format:</b> `/pvp <amount>` 🌸"), parse_mode="HTML")
        
    bet = int(context.args[0])
    if bet < 10: return await update.message.reply_text(premium("<b>❌ Minimum bet is 10 EXP.</b> ✨"), parse_mode="HTML")
    
    c_data = hunter_db[challenger.id]
    if c_data["exp"] < bet and challenger.id != OWNER_ID: return await update.message.reply_text(premium(f"<b>❌ You don't have enough EXP!</b> (You have {c_data['exp']}) 🥺"), parse_mode="HTML")
        
    pvp_id = f"{chat_id}_{challenger.id}_{opponent.id}_{int(time.time())}"
    active_pvps[pvp_id] = {"c_id": challenger.id, "o_id": opponent.id, "bet": bet, "c_name": _display_name(challenger), "o_name": _display_name(opponent)}
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ ACCEPT", callback_data=f"pvp_accept_{pvp_id}"), InlineKeyboardButton("🏃 DECLINE", callback_data=f"pvp_decline_{pvp_id}")]
    ])
    
    text = f"<b>⚠️ [ DUEL REQUEST ] ⚠️</b>\n\n{mention_html(challenger.id, _display_name(challenger))} challenged {mention_html(opponent.id, _display_name(opponent))}!\n💰 <b>Bet:</b> {bet} EXP\n\nDo you accept the duel? ✨"
    await update.message.reply_text(premium(text), parse_mode="HTML", reply_markup=markup)

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
        return await query.edit_message_text(premium(f"<b>🏃 {pvp['o_name']} declined the duel. Coward!</b> 😂"), parse_mode="HTML")
    
    if action == "accept" and user_id == pvp["o_id"]:
        if hunter_db[pvp["o_id"]]["exp"] < pvp["bet"] and pvp["o_id"] != OWNER_ID:
            return await query.answer("You don't have enough EXP to accept!", show_alert=True)
            
        await query.edit_message_text(premium(f"<b>⚔️ DUEL STARTED!</b>\n{pvp['c_name']} VS {pvp['o_name']}\n\n<i>Clashing weapons...</i> 🔥"), parse_mode="HTML")
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
        
        text = f"<b>🏆 DUEL FINISHED! 🏆</b>\n\n💥 {w_name} dominated the fight and defeated {l_name}!\n\n🏅 <b>{w_name}</b> won {pvp['bet']} EXP! 🎉"
        await query.edit_message_text(premium(text), parse_mode="HTML")
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
    await update.message.reply_text(premium(f"<b>🛒 SYSTEM SHOP 🛒</b>\n\n🔮 <b>Your Magic Crystals:</b> {cryst if user.id != OWNER_ID else '∞'}\n\n<i>Buy items to aid your journey:</i> ✨"), reply_markup=markup, parse_mode="HTML")

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
                
        break_caption = premium(f"""<b>💀 [ SYSTEM WARNING ] 💀</b>
<i>Hunters failed to clear the dungeon in time...</i>

💠 <b>STATUS:</b> ⚫ <b>GATE BREAK (FAILED)</b>
⛩️ <b>GATE RANK:</b> <code> {dungeon['rank']}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {DUNGEON_RANKS[dungeon['rank']]['name']} (ESCAPED) </code> ⚠️""")
        
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=dungeon["msg_id"], caption=break_caption, parse_mode="HTML")
            await context.bot.send_message(chat_id, premium(f"<b>🚨 GATE BREAK!</b> The Boss escaped and attacked the Guild!\n📉 Penalty: {affected} active Hunters lost {penalty} EXP. 😭"), parse_mode="HTML")
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
            
    clear_caption = premium(f"""<b>✅ [ SYSTEM NOTIFICATION ] ✅</b>
<i>The Gate has been successfully secured!</i>

💠 <b>STATUS:</b> 🔴 <b>CLOSED (CLEARED)</b>
⛩️ <b>GATE RANK:</b> <code> {dungeon['rank']}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {DUNGEON_RANKS[dungeon['rank']]['name']} (DEFEATED) </code> ✨""")
            
    try:
        await context.bot.edit_message_caption(chat_id=chat_id, message_id=dungeon["msg_id"], caption=clear_caption, parse_mode="HTML")
        
        boss_name = DUNGEON_RANKS[dungeon['rank']]['name']
        new_msg = premium(f"""<b>🎊 DUNGEON CONQUERED! 🎊</b>

<b>🏆 HEROES OF THE RAID:</b>
{winners_text}

🌑 {mention_html(last_hitter_id, hunter_db[last_hitter_id]['name'])}, you delivered the final blow! The Boss's soul lingers.
⏳ You have 30 seconds to type <code>/arise</code> and attempt Shadow Extraction! ✨""")
        
        await context.bot.send_message(chat_id, new_msg, parse_mode="HTML")
        arise_targets[chat_id] = {"uid": last_hitter_id, "boss": boss_name, "time": time.time()}
    except: pass

async def arise_shadow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_registered(update)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in arise_targets or arise_targets[chat_id]["uid"] != user_id:
        return await update.message.reply_text(premium("<b>❌ There is no shadow for you to extract here, or you lack the authority.</b> 🤡"), parse_mode="HTML")
        
    target = arise_targets.pop(chat_id)
    if time.time() - target["time"] > 30:
        return await update.message.reply_text(premium("<b>❌ You took too long. The shadow faded into the abyss.</b> 😢"), parse_mode="HTML")
        
    if random.choice([True, False]):
        hunter_db[user_id]["shadows"].append(target["boss"])
        save_hunter(user_id)
        await update.message.reply_text(premium(f"<b>🌑 SHADOW EXTRACTION SUCCESSFUL! 🌑</b>\n\n<i>\"Arise.\"</i>\n{target['boss']} is now your loyal Shadow Soldier! 👑"), parse_mode="HTML")
    else:
        await update.message.reply_text(premium(f"<b>🌑 SHADOW EXTRACTION FAILED. 🌑</b>\n\n<i>The soul of {target['boss']} resisted your command and vanished.</i> 💔"), parse_mode="HTML")

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

    caption = premium(f"""<b>⚠️ [ SYSTEM NOTIFICATION ] ⚠️</b>
<i>A dimensional rift has opened in the Guild!</i>

💠 <b>STATUS:</b> 🟢 <b>OPEN</b>
⛩️ <b>GATE RANK:</b> <code> {rank}-Rank </code>
👹 <b>BOSS NAME:</b> <code> {data['name']} </code>
🩸 <b>BOSS HP:</b> <code> {data['hp']} </code>

📜 <b>MISSION LOG:</b>
<i>{instructions}</i>

⏳ <b>TIME REMAINING:</b> <code> 05:00 Minutes </code>
🎁 <b>CLEAR REWARD:</b> <code> +{data['reward']} EXP, +{data['crystals']} 🔮 </code> ✨""")

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

# ------------- MODERATION COMMANDS (Enhanced) -------------
async def mod_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    action = update.message.text.split()[0][1:].split('@')[0].lower()
    if not await check_rights(update, action): 
        return await update.message.reply_text(premium("<b>❌ You don't have Admin rights/permissions to do this.</b> 🤡"), parse_mode="HTML")
    
    target_id = await get_user_id(update, context)
    if not target_id and action not in ["unpin"]: 
        return await update.message.reply_text(premium("<b>❌ User not found!</b> Reply to their message, or provide a valid ID/Username. 🥺"), parse_mode="HTML")
    chat_id = update.effective_chat.id
    target_mention = mention_html(target_id, "User")

    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, target_id)
            await update.message.reply_text(premium(f"<b>🔨 Banished!</b>\n{target_mention} has been exiled from the realm! ✨"), parse_mode="HTML")
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(premium(f"<b>✅ Redemption!</b>\n{target_mention} has been unbanned. Welcome back! 🌸"), parse_mode="HTML")
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, target_id)
            await context.bot.unban_chat_member(chat_id, target_id)
            await update.message.reply_text(premium(f"<b>🦵 Kicked!</b>\n{target_mention} was removed from the group! 💨"), parse_mode="HTML")
        elif action == "mute":
            await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=False))
            await update.message.reply_text(premium(f"<b>🔇 Silenced!</b>\n{target_mention} can no longer speak. 🤫✨"), parse_mode="HTML")
        elif action == "unmute":
            await context.bot.restrict_chat_member(chat_id, target_id, permissions=ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True, can_add_web_page_previews=True))
            await update.message.reply_text(premium(f"<b>🔊 Unmuted!</b>\n{target_mention} is free to speak again! 🎶🎀"), parse_mode="HTML")
        elif action == "pin":
            if update.message.reply_to_message: 
                await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
                await update.message.reply_text(premium("<b>📌 Pinned successfully!</b> ✨"), parse_mode="HTML")
        elif action == "unpin":
            if update.message.reply_to_message: await context.bot.unpin_chat_message(chat_id, update.message.reply_to_message.message_id)
            else: await context.bot.unpin_chat_message(chat_id)
            await update.message.reply_text(premium("<b>✅ Unpinned successfully!</b> 🌸"), parse_mode="HTML")
        elif action == "promote":
            await context.bot.promote_chat_member(chat_id, target_id, can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False, can_change_info=True, can_invite_users=True, can_pin_messages=True)
            await update.message.reply_text(premium(f"<b>🌟 Promoted!</b>\n{target_mention} is now an Admin! 👑✨"), parse_mode="HTML")
        elif action == "demote":
            await context.bot.promote_chat_member(
                chat_id, target_id, can_manage_chat=False, can_delete_messages=False, 
                can_manage_video_chats=False, can_restrict_members=False, 
                can_promote_members=False, can_change_info=False, 
                can_invite_users=False, can_pin_messages=False, is_anonymous=False
            )
            await update.message.reply_text(premium(f"<b>📉 Demoted!</b>\n{target_mention} is back to being a normal member! 🐾"), parse_mode="HTML")
    except BadRequest as e: await update.message.reply_text(premium(f"<b>❌ Error:</b> {e.message} ⚠️"), parse_mode="HTML")
    except Exception as e: await update.message.reply_text(premium(f"<b>❌ System Error:</b> {e} ☠️"), parse_mode="HTML")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purge"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    if not update.message.reply_to_message: return await update.message.reply_text(premium("<b>❌ Reply to the oldest message to start purge.</b> ✨"), parse_mode="HTML")
    try:
        start_id, end_id, chat_id = update.message.reply_to_message.message_id, update.message.message_id, update.effective_chat.id
        msg_ids = list(range(start_id, end_id + 1))
        for i in range(0, len(msg_ids), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids[i:i+100])
            except: pass 
        ack = await context.bot.send_message(chat_id, premium("<b>✅ Purge complete! Area secured.</b> 🧹✨"), parse_mode="HTML"); await asyncio.sleep(3); await ack.delete()
    except Exception as e: await update.message.reply_text(premium(f"<b>Error:</b> {e} ⚠️"), parse_mode="HTML")

async def purge_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgegroup"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    chat_id, curr = update.effective_chat.id, update.message.message_id
    try:
        msg_ids = list(range(max(1, curr - 100), curr + 1))
        for i in range(0, len(msg_ids), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids[i:i+100])
            except: pass
        ack = await context.bot.send_message(chat_id, premium("<b>✅ Group cleanup (Last 100 messages) complete!</b> 🫧🌸"), parse_mode="HTML"); await asyncio.sleep(5); await ack.delete()
    except: await update.message.reply_text(premium("<b>❌ Messages too old/already deleted.</b> 🥺"), parse_mode="HTML")

async def purge_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "purgeall"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    if not update.message.reply_to_message: return await update.message.reply_text(premium("<b>❌ Reply to the user whose messages you want to purge.</b> ✨"), parse_mode="HTML")
    
    chat_id = update.effective_chat.id
    target_id = update.message.reply_to_message.from_user.id
    
    try:
        msg_ids_to_delete = [mid for mid, uid in recent_messages_db[chat_id] if uid == target_id]
        msg_ids_to_delete.append(update.message.message_id) 
        
        if not msg_ids_to_delete or len(msg_ids_to_delete) <= 1:
            return await update.message.reply_text(premium("<b>❌ Is user ke koi recent messages history mein nahi mile.</b> 🤔"), parse_mode="HTML")
            
        for i in range(0, len(msg_ids_to_delete), 100):
            try: await context.bot.delete_messages(chat_id, msg_ids_to_delete[i:i+100])
            except: pass
            
        recent_messages_db[chat_id] = deque([(m, u) for m, u in recent_messages_db[chat_id] if u != target_id], maxlen=1000)
        
        ack = await context.bot.send_message(chat_id, premium("<b>✅ User ke sabhi recent messages delete ho gaye!</b> 🧹✨"), parse_mode="HTML"); await asyncio.sleep(5); await ack.delete()
    except Exception as e: await update.message.reply_text(premium(f"<b>❌ Failed to purge all:</b> {e} ⚠️"), parse_mode="HTML")

async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
<b>🌹 CINDRELLA COMMANDS 🌹</b>

<b>⚔️ Solo Leveling (RPG):</b>
<code>/stats [reply]</code> - Check Hunter License & Items
<code>/hunt</code> - Enter Dungeon & Kill Monsters
<code>/daily</code> - Daily Quest, Streak & Loot Box
<code>/give &lt;reply&gt;</code> - Donate EXP, Crystals, Loot Box, Shadows
<code>/pvp &lt;reply&gt; &lt;amount&gt;</code> - Duel a Hunter for EXP
<code>/shop</code> - Buy Potions, Keys & Titles
<code>/arise</code> - Extract Shadow (After Boss Kill)
<code>/open_box</code> - Open S-Rank Loot Box
<code>/top_hunter</code> - Top 10 Hunters in Group
<code>/world_top</code> - Global Top 10 S-Rank Hunters

<b>🛠 Moderation:</b>
<code>/ban</code>, <code>/unban</code>, <code>/kick</code>, <code>/mute</code>, <code>/unmute</code>
<code>/pin</code>, <code>/unpin</code>, <code>/promote</code>, <code>/demote</code>
<code>/warn</code>, <code>/unwarn</code>
<code>/purge</code>, <code>/purgegroup</code>, <code>/purgeall</code>

<b>🛡 Group Management:</b>
<code>/id</code> - Get info about user/chat
<code>/addblacklist</code>, <code>/rmblacklist</code>, <code>/blocklist</code>
<code>/addfilter</code>, <code>/rmfilter</code>, <code>/setrules</code>, <code>/rules</code>

<b>✨ Fun & Utils:</b>
<code>/couple</code> - Couple of the day!
<code>/afk [reason]</code> - Set AFK status
<code>/anime [name]</code> - Search for an anime
<code>/admin</code> - Bot Admin Panel
    """
    await update.message.reply_text(premium(text), parse_mode="HTML")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "warn"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text(premium("<b>❌ User not found!</b> Reply to their message, or provide a valid ID/Username. 🥺"), parse_mode="HTML")
    chat_id = update.effective_chat.id
    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_id in admins_db or target_member.status in ['administrator', 'creator']: return await update.message.reply_text(premium("<b>❌ Cannot warn an Admin.</b> 👑"), parse_mode="HTML")
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
        await update.message.reply_text(premium(f"<b>🛑 MUTED!</b>\nUser {target_id} reached 3 warnings and is now silenced! 🤫"), parse_mode="HTML")
    else: await update.message.reply_text(premium(f"<b>⚠️ Warned!</b>\nUser {target_id} has been warned! ({count}/3)\n<b>Reason:</b> {reason} ✨"), parse_mode="HTML")

async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "unwarn"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    target_id = await get_user_id(update, context)
    if not target_id: return await update.message.reply_text(premium("<b>❌ User not found!</b> Reply to their message, or provide a valid ID/Username. 🥺"), parse_mode="HTML")
    chat_id = update.effective_chat.id
    if warnings_db[chat_id][target_id] > 0:
        warnings_db[chat_id][target_id] -= 1
        await update.message.reply_text(premium(f"<b>✅ Removed 1 warning.</b> Current warns: {warnings_db[chat_id][target_id]}/3 🌸"), parse_mode="HTML")
    else: await update.message.reply_text(premium("<b>✅ User has 0 warnings.</b> ✨"), parse_mode="HTML")

async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "rules"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b>"), parse_mode="HTML")
    text = update.message.text.split(None, 1)
    if len(text) < 2: return await update.message.reply_text(premium("<b>❌ Please provide rules text.</b>"), parse_mode="HTML")
    rules_db[update.effective_chat.id] = text[1]
    await update.message.reply_text(premium("<b>✅ Rules updated successfully!</b> 🌸"), parse_mode="HTML")

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(premium(f"<b>📜 Group Rules:</b>\n\n{rules_db.get(update.effective_chat.id, 'No rules set yet.')} ✨"), parse_mode="HTML")

async def add_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    if not context.args: return await update.message.reply_text(premium("<b>❌ Provide a word.</b> 🥺"), parse_mode="HTML")
    blacklist_db[update.effective_chat.id].add(context.args[0].lower()); await update.message.reply_text(premium(f"<b>✅ Word '{context.args[0]}' added to blacklist.</b> 🌸"), parse_mode="HTML")

async def rm_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    if not context.args: return await update.message.reply_text(premium("<b>❌ Provide a word.</b> 🥺"), parse_mode="HTML")
    blacklist_db[update.effective_chat.id].discard(context.args[0].lower()); await update.message.reply_text(premium(f"<b>✅ Word '{context.args[0]}' removed from blacklist.</b> ✨"), parse_mode="HTML")

async def show_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "blacklist"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    words = blacklist_db[update.effective_chat.id]
    if not words: return await update.message.reply_text(premium("<b>✅ Blocklist ekdum khali hai.</b> 🌸"), parse_mode="HTML")
    await update.message.reply_text(premium("<b>🚫 Blocked Words:</b>\n" + "\n".join([f"- <code>{w}</code>" for w in words])), parse_mode="HTML")

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    text = update.message.text.split(None, 2)
    if len(text) < 3: return await update.message.reply_text(premium("<b>❌ Format: /addfilter &lt;word&gt; &lt;reply&gt;</b> 🥺"), parse_mode="HTML")
    filters_db[update.effective_chat.id][text[1].lower()] = text[2]; await update.message.reply_text(premium("<b>✅ Filter added successfully!</b> 🎀"), parse_mode="HTML")

async def rm_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rights(update, "filter"): return await update.message.reply_text(premium("<b>❌ Admin rights required.</b> 🤡"), parse_mode="HTML")
    if not context.args: return await update.message.reply_text(premium("<b>❌ Provide a word.</b> 🥺"), parse_mode="HTML")
    filters_db[update.effective_chat.id].pop(context.args[0].lower(), None); await update.message.reply_text(premium("<b>✅ Filter removed!</b> ✨"), parse_mode="HTML")

async def set_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = " ".join(context.args) if context.args else "No reason"
    afk_db[update.effective_user.id] = {"reason": reason, "time": dt.now(), "name": _display_name(update.effective_user)}
    await update.message.reply_text(premium(f"<b>💤 {_display_name(update.effective_user)} is now AFK.</b>\nReason: {reason} 😴"), parse_mode="HTML")

async def get_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text(premium("<b>❌ Search naam toh batao!</b> (e.g., /anime naruto) 🥺"), parse_mode="HTML")
    query = " ".join(context.args)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://api.jikan.moe/v4/anime?q={query}&limit=1")
            data = res.json()
            if data['data']:
                anime = data['data'][0]
                await update.message.reply_text(premium(f"<b>🎬 {anime['title']}</b>\n\n📊 <b>Score:</b> {anime.get('score', 'N/A')}\n🎞 <b>Episodes:</b> {anime.get('episodes', 'N/A')}\n🔄 <b>Status:</b> {anime.get('status', 'N/A')}\n\n🔗 <a href='{anime['url']}'>More Info</a> ✨"), parse_mode="HTML")
            else: await update.message.reply_text(premium("<b>❌ Anime not found!</b> 🥺"), parse_mode="HTML")
    except: await update.message.reply_text(premium("<b>❌ API error.</b> ☠️"), parse_mode="HTML")

# ------------- ADMIN PANEL -------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins_db: 
        return await update.message.reply_text(premium("<b>❌ Only Bot Admins & Owner can use this.</b> 🤡"), parse_mode="HTML")
    
    if user_id == OWNER_ID:
        buttons = [
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🌐 List Groups", callback_data="list_groups")],
            [InlineKeyboardButton("➕ Add Bot Admin", callback_data="add_admin"), InlineKeyboardButton("➖ Remove Bot Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
        await update.message.reply_text(premium(f"<b>👑 Owner Panel</b>\n📊 Replies Today: {usage_count['count']} ✨"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    else:
        buttons = [
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🌐 List Groups", callback_data="list_groups")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")]
        ]
        await update.message.reply_text(premium(f"<b>🛠 Bot Admin Panel</b>\n📊 Replies Today: {usage_count['count']} ✨"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in admins_db: return await query.answer("❌ You are not a Bot Admin!", show_alert=True)
    await query.answer()

    if query.data == "broadcast":
        await query.message.reply_text(premium("<b>📢 Send me the broadcast message:</b> ✨"), parse_mode="HTML")
        context.user_data["awaiting_broadcast"] = True
    elif query.data == "list_groups":
        if not known_groups: return await query.message.reply_text(premium("<b>Bot is not active in any groups yet.</b> 🌸"), parse_mode="HTML")
        await query.message.reply_text(premium("<b>Fetching group links... please wait.</b> ⏳"), parse_mode="HTML")
        text = "<b>🌐 Bot Groups & Links:</b>\n\n"
        for cid, title in list(known_groups.items()):
            safe_title = str(title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            try: link = await context.bot.export_chat_invite_link(cid); text += f"🔹 {safe_title}: <a href='{link}'>Invite Link</a>\n"
            except: text += f"🔹 {safe_title}: <i>(No Admin Rights)</i>\n"
        for i in range(0, len(text), 4000): await query.message.reply_text(premium(text[i:i+4000]), parse_mode="HTML", disable_web_page_preview=True)
    elif query.data == "add_admin":
        if user_id != OWNER_ID: return await query.message.reply_text(premium("<b>❌ Only the Owner can add admins.</b> 👑"), parse_mode="HTML")
        await query.message.reply_text(premium("<b>Send user ID to add as Bot Admin:</b> ✨"), parse_mode="HTML")
        context.user_data["awaiting_add_admin"] = True
    elif query.data == "remove_admin":
        if user_id != OWNER_ID: return await query.message.reply_text(premium("<b>❌ Only the Owner can remove admins.</b> 👑"), parse_mode="HTML")
        await query.message.reply_text(premium("<b>Send user ID to remove from Bot Admins:</b> ✨"), parse_mode="HTML")
        context.user_data["awaiting_remove_admin"] = True
    elif query.data == "list_admins":
        admin_text = "<b>📋 Current Bot Admins:</b>\n\n"
        for aid in admins_db:
            if aid == OWNER_ID:
                admin_text += f"👑 Owner (<code>{aid}</code>)\n"
            else:
                if aid in hunter_db:
                    h = hunter_db[aid]
                    uname = f" {h['username']}" if h.get("username") else ""
                    admin_text += f"🔹 {h['name']}{uname} (<code>{aid}</code>)\n"
                else:
                    admin_text += f"🔹 Unknown Hunter (<code>{aid}</code>)\n"
        await query.message.reply_text(premium(admin_text), parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.message.reply_text(premium("<b>Hey, I'm CINDRELLA! 🌸</b>\nYour AI Assistant! Type /commands to see what I can do! ✨"), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --- 🚀 UPGRADED AI REPLY (No Load Spam + Huge Memory) ---
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Typing Action
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except: pass
    
    if usage_count["date"] != str(date.today()): usage_count.update({"date": str(date.today()), "count": 0})
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    
    system_prompt = "You are CINDRELLA, an exceptionally smart, caring, and witty AI companion. Speak naturally like a close best friend. CRITICAL RULES: 1. Reply in the exact same language and script the user uses (Hindi, Hinglish, or English). 2. Keep responses concise (1-3 lines). 3. You MUST remember all details, names, and places the user mentioned earlier. 4. Do not act like a bot. 5. Use basic emojis (like 🌸, ❤️, 🥺, ✨, 🎀, 🦋, 💖, 💗, 💕, 😊, 🥰, 😭, 🔥, 😂, 🤣, 👍, ✅, ❌, ⚠️, 👑, 🤍, 🩷, 😅, ☕️, 🧸). I will handle replacing them with premium aesthetic versions."
    
    models = [
        "meta-llama/llama-3.3-70b-instruct:free", 
        "google/gemma-2-9b-it:free", 
        "microsoft/phi-3-mini-128k-instruct:free",
        "huggingface/zephyr-7b-beta:free"
    ]
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history_db[user_id][-30:]) # Now tracking 30 items
    messages.append({"role": "user", "content": message_text})
    
    # Retry Loop (Solves 100+ User Load without spam)
    for _ in range(2): 
        for model in models:
            try:
                payload = {
                    "model": model, 
                    "messages": messages,
                    "temperature": 0.6,
                    "frequency_penalty": 0.0, # ZERO Penalty for flawless memory!
                    "presence_penalty": 0.0
                }
                async with httpx.AsyncClient(timeout=25) as client:
                    res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    
                    if res.status_code == 429:
                        await asyncio.sleep(1.5) 
                        continue
                        
                    if res.status_code == 200:
                        data = res.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        
                        reply = reply.replace("**", "").replace("*", "")
                        
                        # Apply Premium Emoji Filter
                        premium_reply = premium(reply)
                        
                        # Bold Formatting
                        bold_reply = f"<b>{premium_reply}</b>"
                        
                        usage_count["count"] += 1
                        
                        chat_history_db[user_id].append({"role": "user", "content": message_text})
                        chat_history_db[user_id].append({"role": "assistant", "content": reply})
                        if len(chat_history_db[user_id]) > 60:
                            chat_history_db[user_id] = chat_history_db[user_id][-60:]
                            
                        try: return await update.message.reply_text(bold_reply, parse_mode="HTML")
                        except BadRequest: return await context.bot.send_message(chat_id=chat_id, text=bold_reply, parse_mode="HTML")
            except: 
                continue
                
    # If all models fail after 2 full sweeps, it simply skips responding to avoid spam.

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
            return await update.message.reply_text(premium(f"<b>❌ Tumhare paas '{shadow_name}' naam ka koi Shadow nahi hai. Transaction cancelled.</b> 🤡"), parse_mode="HTML")
            
        if user.id != OWNER_ID:
            sender_data["shadows"].remove(matched_shadow)
            
        target_data["shadows"].append(matched_shadow)
        save_hunter(user.id)
        save_hunter(target_id)
        
        context.user_data.pop("awaiting_give_shadow", None)
        context.user_data.pop("give_target_id", None)
        
        return await update.message.reply_text(premium(f"<b>✅ SHADOW TRANSFERRED!</b>\n\n🌑 You gave <b>{matched_shadow}</b> to {target_name}! ✨"), parse_mode="HTML")

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
                    return await update.message.reply_text(premium(f"<b>❌ Tumhare paas itne {item_names[item_type]} nahi hain!</b> 🥺"), parse_mode="HTML")
                sender_data[db_key] -= amount
                
            target_data[db_key] += amount
            save_hunter(user.id)
            save_hunter(target_id)
            
            context.user_data.pop("awaiting_give_amount", None)
            context.user_data.pop("give_target_id", None)
            context.user_data.pop("give_item", None)
            
            return await update.message.reply_text(premium(f"<b>✅ SUCCESS!</b>\n\nYou gave <b>{amount} {item_names[item_type]}</b> to {target_name}! 🌸"), parse_mode="HTML")
        else:
            context.user_data.pop("awaiting_give_amount", None)
            context.user_data.pop("give_target_id", None)
            context.user_data.pop("give_item", None)
            return await update.message.reply_text(premium("<b>❌ Invalid amount. Transaction cancelled.</b> 🤡"), parse_mode="HTML")
    
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
                    await context.bot.send_message(cid, premium(f"<b>📢 Broadcast Message:</b>\n\n{update.message.text} ✨"), parse_mode="HTML")
                    success_groups += 1
                    await asyncio.sleep(0.05)
                except: pass
            
            success_users = 0
            for uid in list(hunter_db.keys()):
                try:
                    await context.bot.send_message(uid, premium(f"<b>📢 System Broadcast:</b>\n\n{update.message.text} 🌸"), parse_mode="HTML")
                    success_users += 1
                    await asyncio.sleep(0.05)
                except: pass
                
            return await update.message.reply_text(premium(f"<b>✅ Broadcast successfully sent to {success_groups} Groups and {success_users} Users DMs!</b> 🎉"), parse_mode="HTML")
            
        if user.id == OWNER_ID:
            if context.user_data.pop("awaiting_add_admin", None):
                try: admins_db.add(int(update.message.text.strip())); save_admins(); await update.message.reply_text(premium("<b>✅ Admin added.</b> ✨"), parse_mode="HTML")
                except: await update.message.reply_text(premium("<b>❌ Invalid ID.</b> 🤡"), parse_mode="HTML")
                return
            if context.user_data.pop("awaiting_remove_admin", None):
                try: 
                    if int(update.message.text.strip()) != OWNER_ID: admins_db.discard(int(update.message.text.strip())); save_admins(); await update.message.reply_text(premium("<b>✅ Removed.</b> 🌸"), parse_mode="HTML")
                except: await update.message.reply_text(premium("<b>❌ Invalid ID.</b> 🤡"), parse_mode="HTML")
                return

    if user.id not in admins_db:
        now = time.time()
        spam_tracker[chat_id][user.id] = [t for t in spam_tracker[chat_id][user.id] + [now] if now - t < 5]
        
        if len(spam_tracker[chat_id][user.id]) > 5:
            spam_tracker[chat_id][user.id] = []
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(chat_id, user.id, permissions=ChatPermissions(can_send_messages=False))
                await context.bot.send_message(chat_id, premium(f"<b>🚫 {_display_name(user)} muted for spamming.</b> 🤫"), parse_mode="HTML")
            except: 
                pass 
            return 
            
        if any(word in msg_lower for word in blacklist_db[chat_id]):
            try:
                await update.message.delete()
                await context.bot.send_message(chat_id, premium(f"<b>🚫 Watch your language, {_display_name(user)}!</b> ⚠️"), parse_mode="HTML")
            except: 
                pass
            return 

    if user.id in afk_db:
        afk_db.pop(user.id); await update.message.reply_text(premium(f"<b>👋 Welcome back {_display_name(user)}, AFK removed!</b> ✨"), parse_mode="HTML")
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id in afk_db:
        afk_user = afk_db[update.message.reply_to_message.from_user.id]
        await update.message.reply_text(premium(f"<b>💤 {afk_user['name']} is currently AFK:</b> {afk_user['reason']} 😴"), parse_mode="HTML")

    if msg_lower in filters_db[chat_id]: return await update.message.reply_text(premium(f"<b>{filters_db[chat_id][msg_lower]}</b>"), parse_mode="HTML")

    bot_un = context.bot.username.lower() if context.bot.username else ""
    mentioned = (update.message.entities and any(e.type == "mention" and bot_un in msg_lower for e in update.message.entities)) or any(f in msg_lower for f in filters_db[chat_id].keys())
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg_lower in ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","gn"] and not mentioned and not replied:
        await update.message.reply_text(premium(random.choice(["<b>System Online! 🌸</b>","<b>Guild Manager reporting! 💕</b>","<b>Hey Master! ⚔️</b>","<b>Dungeon ready when you are! ☀️</b>"])), parse_mode="HTML")
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
