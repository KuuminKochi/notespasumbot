from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from utils import globals
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

async def tutorial_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    await update.message.reply_text(globals.TUTORIAL_ANSWERS)
