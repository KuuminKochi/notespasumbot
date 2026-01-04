from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils import (
    globals,
    ai_tutor,
    firebase_db,
    memory_consolidator,
    vision,
    concurrency,
)
import os
import asyncio
import datetime
from dotenv import load_dotenv

load_dotenv()

# Basic config from env
API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))


async def pipe_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type if update.effective_chat else ""
    user = update.effective_user
    if not user or not update.message:
        return

    # --- 1. Supergroup/Group Filtering ---
    if chat_type in ["group", "supergroup"]:
        # Only reply if mentioned or replying to bot
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{context.bot.username}" in (update.message.text or "")

        if not (is_reply_to_bot or is_mention):
            return

    # --- 2. Private Chat or Validated Group Message ---
    elif chat_type != "private":
        return

    text = (update.message.text or update.message.caption or "").strip()
    asker_name = user.first_name or "Student"
    telegram_id = user.id

    # 1. Update User Profile in Background
    try:
        user_data = {
            "name": user.full_name,
            "username": user.username,
            "last_active": datetime.datetime.now(),
        }
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            concurrency.get_pool(),
            firebase_db.create_or_update_user,
            telegram_id,
            user_data,
        )
    except Exception as e:
        print(f"Async DB Error: {e}")

    # 2. Check for Media/Vision FIRST (Prioritize Vision over Text)
    target_photo = update.message.photo
    if not target_photo and update.message.reply_to_message:
        target_photo = update.message.reply_to_message.photo

    if target_photo:
        await vision.process_image_question(update, context)
        return

    # 3. Handle Text (AI Tutor with Streaming)
    if text:
        if len(text) < 2:
            return  # Ignore very short messages

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Create placeholder for streaming
        status_msg = await update.message.reply_text("💭 Thinking...")

        # Call the streaming version
        await ai_tutor.stream_ai_response(update, context, status_msg, text)
        return
