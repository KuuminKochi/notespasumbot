from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
from utils import globals
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Chat ID: {chat_id}")
