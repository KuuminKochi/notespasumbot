from telegram import Update
from telegram.ext import ContextTypes
from utils import globals as bot_globals
import os

NOTES_PASUM = int(os.getenv("NOTES_PASUM", "0"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", "0"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(bot_globals.WARNING)
        return
    await update.message.reply_text(bot_globals.INTRODUCTION)
