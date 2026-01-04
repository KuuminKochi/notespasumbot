from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils import globals, ai_tutor, firebase_db, memory_consolidator, vision
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

    # --- Supergroup Logic ---
    if chat_type in ["group", "supergroup"]:
        # Only reply if mentioned or replying to bot
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{context.bot.username}" in (update.message.text or "")

        if not (is_reply_to_bot or is_mention):
            return

    # --- Private Chat Logic ---
    elif chat_type == "private":
        pass  # Process everything
    else:
        return

    text = (update.message.text or update.message.caption or "").strip()
    asker_name = user.first_name or "Student"
    telegram_id = user.id

    if not text and not (update.message.photo or update.message.document):
        return

    # 1. Firebase Profile Check & Update
    try:
        user_data = {
            "name": user.full_name,
            "username": user.username,
            "last_active": datetime.datetime.now(),
        }
        # Run DB update in background to prevent blocking main loop
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            None, firebase_db.create_or_update_user, telegram_id, user_data
        )
    except Exception as e:
        print(f"DB Error: {e}")

    # 2. Check for Media/Vision FIRST (Prioritize Vision over Text)
    # Check current message photo OR replied-to message photo
    target_photo = update.message.photo
    if not target_photo and update.message.reply_to_message:
        target_photo = update.message.reply_to_message.photo

    if target_photo:
        await vision.process_image_question(update, context)
        return

    # 3. Handle Text (AI Tutor) - Only if NO photo found
    if text:
        if len(text) < 2:
            return  # Ignore very short messages

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Run AI in executor
        # Loop already acquired above or get new one
        if "loop" not in locals():
            loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None, ai_tutor.get_ai_response, telegram_id, text, asker_name
        )

        # Send AI response (Reply to message to handle threads in supergroups)
        await update.message.reply_text(response)

        # 4. Memory Extraction
        async def run_extraction_task():
            await loop.run_in_executor(
                None, memory_consolidator.extract_memories, telegram_id, text, response
            )

        asyncio.create_task(run_extraction_task())

        return
