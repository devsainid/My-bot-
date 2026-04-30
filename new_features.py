# new_features.py - Tumhara safe playground! 🛠️
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

# --- 1. YAHAN APNA NAYA FUNCTION LIKHO ---
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>Yay! Main nayi file se bol rahi hoon! ✨</b>", parse_mode="HTML")

# --- 2. YAHAN APNI COMMAND KO REGISTER KARO ---
def setup(application):
    # Bas aise hi nayi commands banate jao aur yahan add karte jao
    application.add_handler(CommandHandler("testnew", test_command))
    
    logging.info("✅ New Features Module successfully active!")
