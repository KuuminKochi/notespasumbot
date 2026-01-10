from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from utils import globals, firebase_db
import os
import random

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = os.getenv("CHAT_MODEL", "xiaomi/mimo-v2-flash:free")


async def track_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track users in group (Legacy support)."""
    chat = update.effective_chat
    user = update.effective_user
    NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))

    if chat and chat.id == NOTES_PASUM and user:
        display_name = f"@{user.username}" if user.username else user.full_name
        globals.active_users.add((user.id, display_name))


async def pasum_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finds random study partners from PASUM community."""
    user = update.effective_user

    await update.message.reply_text(
        "🔍 Finding study partners from the PASUM community..."
    )

    all_users = firebase_db.get_all_user_ids()
    other_users = [uid for uid in all_users if uid != str(user.id)]

    if not other_users:
        await update.message.reply_text(
            "No other students found yet! Be the first to join! 🌟"
        )
        return

    matches = random.sample(other_users, min(5, len(other_users)))

    text = f"💘 **Study Partners for {user.first_name}** 💘\n\n"
    text += "Found some potential study partners from the PASUM community!\n\n"

    for i, uid in enumerate(matches, 1):
        score = random.randint(50, 95)
        emoji = "🔥" if score > 80 else "🤝" if score > 60 else "📚"
        text += f"{emoji} Study Partner #{i}\n"

    text += "\n✨ <i>Connect with them to study together!</i>"
    await update.message.reply_text(text, parse_mode="HTML")
