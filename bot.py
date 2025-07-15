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

openrouter_models = [
    "openchat/openchat-3.5", "gryphe/mythomax-l2-13b",
    "undi95/toppy-m-7b", "mistralai/mixtral-8x7b",
    "nousresearch/nous-capybara-7b", "nousresearch/nous-hermes-2-mixtral",
    "meta-llama/llama-3-8b-instruct", "intel/neural-chat-7b",
    "mistralai/mistral-7b-instruct", "cinematika/cinematika-7b"
]

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
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if res.status_code != 200:
            raise Exception(f"API error {res.status_code}: {res.text}")
        result = res.json()
        reply = result["choices"][0]["message"]["content"]

        today = str(datetime.date.today())
        if usage_count["date"] != today:
            usage_count["date"] = today
            usage_count["count"] = 0
        usage_count["count"] += 1

        await update.message.reply_text(reply[:4096])
    except Exception as e:
        logging.error("❌ OpenRouter Error:", exc_info=True)
        await update.message.reply_text("😓 I'm being upgraded or having a little nap. Try again soon!")

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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()
    bot_username = context.bot.username.lower()

    greetings = ["hi","hello","hey","yo","sup","hii","heyy","heya","cindy","cindrella","gm","good morning","gn","good night"]
    replies = ["Hey cutie 💖","hello sir 💕","Hey master 🌸","Yo! how’s your day? ☀️","Hii bestie","Hey sunshine","Hi there 👋"," what’s up buddy","Sup sweetie 🍬"]
    mentioned = update.message.entities and any(e.type=="mention" and bot_username in update.message.text.lower() for e in update.message.entities)
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if msg in greetings and not mentioned and not replied:
        await update.message.reply_text(random.choice(replies))
    elif mentioned or replied:
        await ai_reply(update, context)

# Admin Panel, Buttons, and Moderation Code stays same (you already had it perfect)

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
