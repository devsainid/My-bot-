import os import logging import random import httpx from flask import Flask, request from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import ( ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters )

✅ ENV Variables

BOT_TOKEN = os.environ.get("BOT_TOKEN") OWNER_ID = int(os.environ.get("OWNER_ID", "6559745280")) OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") WEBHOOK_URL = os.environ.get("WEBHOOK_URL") PORT = int(os.environ.get("PORT", 10000))

✅ Logging

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

✅ Admins

ADMINS = set([OWNER_ID])

✅ Known chats

KNOWN_CHATS_FILE = "known_chats.txt"

def load_known_chats(): if os.path.exists(KNOWN_CHATS_FILE): with open(KNOWN_CHATS_FILE, "r") as f: return set(int(line.strip()) for line in f if line.strip().isdigit()) return set()

def save_known_chat(chat_id): if chat_id not in known_chats: known_chats.add(chat_id) with open(KNOWN_CHATS_FILE, "a") as f: f.write(str(chat_id) + "\n")

known_chats = load_known_chats()

✅ Prompt

SYSTEM_PROMPT = { "role": "system", "content": "You are CINDRELLA, a 16-year-old sweet, kind and emotionally intelligent girl. You respond like a real person and connect emotionally like a best friend. Reply in few natural words." }

FREE_MODELS = [ "openrouter/cypher-alpha:free", "gryphe/mythomax-l2-13b", "mistralai/mistral-7b-instruct:free", "intel/neural-chat-7b" ]

GREETINGS = [ "Hey, how can I help you?", "Hi, what's going on?", "Hello there, all good?", "Hey, what’s up?", "Hi, need anything?" ]

CONVO_START_WORDS = ["hi", "hello", "hey", "heyy", "sup", "good morning", "good night", "gm", "gn"]

def random_greeting(): return random.choice(GREETINGS)

✅ AI Generator

async def generate_reply(user_message): for model in FREE_MODELS: try: async with httpx.AsyncClient() as client: res = await client.post( "https://openrouter.ai/api/v1/chat/completions", headers={ "Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://t.me/YOUR_CINDRELLABOT", "X-Title": "CINDRELLA-Bot" }, json={ "model": model, "messages": [SYSTEM_PROMPT, {"role": "user", "content": user_message}] } ) data = res.json() if "choices" in data: return data["choices"][0]["message"]["content"] except Exception as e: logger.warning(f"Model {model} failed: {e}") return "My developer is updating me, share feedback at @animalin_tm_empire 🌹🕯️"

✅ Commands

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): save_known_chat(update.effective_chat.id) keyboard = [[InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{context.bot.username}?startgroup=true")]] await update.message.reply_text( "HEY, I'M CINDRELLA 🌹🕯️🕯️. JOIN FOR UPDATES & DROP FEEDBACK @animalin_tm_empire 🌹🕯️🕯️. WHAT'S UP DEAR?", reply_markup=InlineKeyboardMarkup(keyboard) )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_user.id not in ADMINS: return buttons = [[InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]] if update.effective_user.id == OWNER_ID: buttons += [ [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")], [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")], [InlineKeyboardButton("📋 List Admins", callback_data="list_admins")] ] await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query user_id = query.from_user.id await query.answer() if user_id not in ADMINS: return context.user_data["action"] = query.data await query.message.reply_text("Send me the input now.")

✅ Messages

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): chat = update.effective_chat user = update.effective_user text = update.message.text or "" is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id is_mention = f"@{context.bot.username.lower()}" in text.lower()

save_known_chat(chat.id)

if user.id in ADMINS and "action" in context.user_data:
    action = context.user_data.pop("action")
    if action == "broadcast":
        count = 0
        for cid in known_chats:
            try:
                await context.bot.send_message(cid, text)
                count += 1
            except:
                pass
        await update.message.reply_text(f"📢 Broadcast sent to {count} chats.")
    elif action == "add_admin":
        try:
            ADMINS.add(int(text.strip()))
            await update.message.reply_text("✅ Admin added.")
        except:
            await update.message
