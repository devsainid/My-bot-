import os, logging, random, httpx
from flask import Flask, request
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions, ChatMemberAdministrator, ChatMemberOwner)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackQueryHandler, ConversationHandler)

# ───── ENV & INIT ─────
BOT_TOKEN = os.environ['BOT_TOKEN']
OWNER_ID = int(os.environ['OWNER_ID'])
OPENROUTER_API_KEY = os.environ['OPENROUTER_API_KEY']
WEBHOOK_URL = os.environ['WEBHOOK_URL']
PORT = int(os.environ.get('PORT','8080'))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ───── STATE & STORAGE ─────
ADMINS = {OWNER_ID}
USAGE_COUNT = 0
GREETING = {"hi","hello","hey","sup","yo","heya"}
ADMIN_PANEL, ADD_ADMIN, REMOVE_ADMIN = range(3)
WELCOME = "Welcome!"

# ───── UTILITIES ─────
async def isPrivileged(update:Update)->bool:
    uid = update.effective_user.id
    member = await update.effective_chat.get_member(uid)
    return uid in ADMINS or isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))

async def ai_reply(text):
    global USAGE_COUNT; USAGE_COUNT+=1
    payload = {"model": random.choice([
        "openchat/openchat-3.5-0106","mistralai/mixtral-8x7b",
        "gryphe/mythomax-l2-13b","openrouter/cinematika-7b",
        "nousresearch/nous-capybara-7b","google/gemma-7b-it",
        "gryphe/mythomist-7b","openrouter/chronos-hermes-13b",
        "openrouter/nous-hermes-2-mixtral","mistralai/mistral-7b-instruct"
    ]),
        "messages":[{"role":"system","content":"You are CINDRELLA, sweet 16‑year‑old best friend."},
                    {"role":"user","content":text}],
        "temperature":0.7}
    try:
        r = await httpx.AsyncClient().post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}"})
        return r.json()['choices'][0]['message']['content'].strip()[:300]
    except:
        return "Oops, AI error."

# ───── COMMANDS ─────
async def start(update:Update, ctx):
    btn = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("➕ Add me to group",
                             url=f"https://t.me/{ctx.bot.username}?startgroup=true"))
    await update.message.reply_text("Hey I'm CINDRELLA 🌹.", reply_markup=btn)

async def admin_panel(update:Update, ctx):
    if update.effective_user.id not in ADMINS:
        return await update.message.reply_text("🚫 You can't use this.")
    buttons = [
        [InlineKeyboardButton("📢 Broadcast", "broadcast")],
    ]
    if update.effective_user.id == OWNER_ID:
        buttons += [
            [InlineKeyboardButton("➕ Add Admin","add_admin")],
            [InlineKeyboardButton("➖ Remove Admin","remove_admin")],
            [InlineKeyboardButton("📋 List Admins","list_admins")],
            [InlineKeyboardButton("📊 Today Usage","usage")]
        ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(buttons))
    return ADMIN_PANEL

async def button_cb(update:Update, ctx):
    q=update.callback_query; await q.answer()
    u=q.from_user.id
    d=q.data
    if d=="broadcast":
        ctx.user_data['act']="broadcast"; await q.message.reply_text("Send broadcast text:"); return ADMIN_PANEL
    if d=="add_admin" and u==OWNER_ID:
        await q.message.reply_text("Send user ID to add:"); return ADD_ADMIN
    if d=="remove_admin" and u==OWNER_ID:
        await q.message.reply_text("Send user ID to remove:"); return REMOVE_ADMIN
    if d=="list_admins" and u==OWNER_ID:
        text = "\n".join(f"{uid}" for uid in ADMINS)
        await q.message.reply_text(f"Admins:\n{text}")
    if d=="usage" and u==OWNER_ID:
        await q.message.reply_text(f"Usage today: {USAGE_COUNT}")
    return ADMIN_PANEL

async def add_admin(update:Update, ctx):
    try:
        ADMINS.add(int(update.message.text))
        await update.message.reply_text("✅ Admin added.")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ADMIN_PANEL

async def remove_admin(update:Update, ctx):
    try:
        ADMINS.discard(int(update.message.text))
        await update.message.reply_text("✅ Removed.")
    except:
        await update.message.reply_text("❌ Invalid.")
    return ADMIN_PANEL

async def cancel(update:Update, ctx):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ───── GROUP ADMIN COMMANDS ─────
async def ban(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.ban_chat_member(update.effective_chat.id,u.id)
        await update.message.reply_text("Banned ✅")

async def unban(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.unban_chat_member(update.effective_chat.id,u.id)
        await update.message.reply_text("Unbanned ✅")

async def kick(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.ban_chat_member(update.effective_chat.id,u.id)
        await ctx.bot.unban_chat_member(update.effective_chat.id,u.id)
        await update.message.reply_text("Kicked ✅")

async def mute(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id,u.id,ChatPermissions(can_send_messages=False))
        await update.message.reply_text("Muted ✅")

async def unmute(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id,u.id,ChatPermissions(can_send_messages=True))
        await update.message.reply_text("Unmuted ✅")

async def pin(update,ctx):
    if await isPrivileged(update):
        await update.message.reply_to_message.pin()
        await update.message.reply_text("Pinned ✅")

async def unpin(update,ctx):
    if await isPrivileged(update):
        await ctx.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("Unpinned ✅")

async def promote(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.promote_chat_member(update.effective_chat.id,u.id,
                                          can_manage_chat=True,can_delete_messages=True)
        await update.message.reply_text("Promoted ✅")

async def demote(update,ctx):
    if await isPrivileged(update):
        u=update.message.reply_to_message.from_user
        await ctx.bot.promote_chat_member(update.effective_chat.id,u.id,
                                          can_manage_chat=False,can_delete_messages=False)
        await update.message.reply_text("Demoted ✅")

async def setwelcome(update,ctx):
    if await isPrivileged(update):
        global WELCOME
        WELCOME = " ".join(update.message.text.split()[1:])
        await update.message.reply_text("Welcome msg set ✅")

# ───── HANDLERS ─────
conv = ConversationHandler(
    entry_points=[CommandHandler("admin",admin_panel)],
    states={
        ADMIN_PANEL:[CallbackQueryHandler(button_cb)],
        ADD_ADMIN:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_admin)],
        REMOVE_ADMIN:[MessageHandler(filters.TEXT & ~filters.COMMAND,remove_admin)]
    },
    fallbacks=[CommandHandler("cancel",cancel)])

telegram_app.add_handler(CommandHandler("start",start))
telegram_app.add_handler(conv)

# Admin commands
for cmd in ["ban","unban","kick","mute","unmute","pin","unpin","promote","demote","setwelcome"]:
    telegram_app.add_handler(CommandHandler(cmd, globals()[cmd]))

# Greetings & chat
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                                        lambda u,c: c.bot.send_message(u.effective_chat.id,
                                        f"{WELCOME} 👋")))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                        lambda u,c: c.message.reply_text(random.choice(["Hey","Hi!","Hello!"]))
                                          if any(w in u.message.text.lower().split() for w in GREETING) else None))
# Picture request: user says e.g. "give me cat pic"
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
    lambda u,c: c.message.reply_photo(f"https://loremflickr.com/640/360/{u.message.text.replace('give me','').replace('pic','').strip()}")
      if "give me" in u.message.text.lower() and "pic" in u.message.text.lower() else None))

telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
    lambda u,c: (await ai_reply(u.message.text) and await c.message.reply_text(await ai_reply(u.message.text)))))

# Launch
@app.route('/webhook',methods=['POST'])
def wh():
    update=Update.de_json(request.get_json(force=True),telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return 'ok'

if __name__=="__main__":
    telegram_app.run_webhook(listen='0.0.0.0',port=PORT, webhook_url=f"{WEBHOOK_URL}/webhook")
