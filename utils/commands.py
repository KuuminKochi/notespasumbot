from telegram import Update
from telegram.ext import ContextTypes
from . import firebase_db
import asyncio


async def soft_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clears conversation context.
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    firebase_db.clear_user_conversations(user_id)
    await update.message.reply_text(
        "🔄 <b>Context Cleared.</b>\n\nConversation history cleared! ✨",
        parse_mode="HTML",
    )


async def hard_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clears all user data (conversations only - memories disabled for refactoring).
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    firebase_db.hard_reset_user_data(user_id)
    await update.message.reply_text(
        "🗑️ <b>Reset Complete.</b>\n\nAll data cleared! ✨",
        parse_mode="HTML",
    )
