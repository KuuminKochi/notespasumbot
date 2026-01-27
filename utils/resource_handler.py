from telegram import Update
from telegram.ext import ContextTypes
from utils import globals as bot_globals
import os

NOTES_PASUM = int(os.getenv("NOTES_PASUM", "0"))


async def send_resource(
    update: Update, context: ContextTypes.DEFAULT_TYPE, content_key: str
):
    """Generic handler for sending resource messages from globals."""
    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(bot_globals.WARNING)
        return

    content = getattr(bot_globals, content_key, "")
    await update.message.reply_text(content)
