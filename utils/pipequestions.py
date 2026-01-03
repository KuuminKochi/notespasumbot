from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils import globals, ai_tutor, firebase_db, memory_consolidator
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
    if not update.effective_chat or update.effective_chat.type != "private":
        return

    if not update.message:
        return

    text = (update.message.text or update.message.caption or "").strip()
    user = update.effective_user
    if not user:
        return

    asker_name = user.first_name or "Student"
    telegram_id = user.id

    if not text and not (
        update.message.photo
        or update.message.document
        or update.message.video
        or update.message.voice
        or update.message.audio
    ):
        return

    # 1. Firebase Profile Check & Update
    try:
        user_data = {
            "name": user.full_name,
            "username": user.username,
            "last_active": datetime.datetime.now(),
        }
        firebase_db.create_or_update_user(telegram_id, user_data)
    except Exception as e:
        print(f"DB Error: {e}")

    # 2. Handle Text (AI Tutor)
    if text and not (
        update.message.photo
        or update.message.document
        or update.message.video
        or update.message.voice
        or update.message.audio
    ):
        if len(text) < 2:
            return  # Ignore very short messages

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Run AI in executor
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, ai_tutor.get_ai_response, telegram_id, text, asker_name
        )

        # Send AI response
        await update.message.reply_text(response)

        # 3. BACKGROUND TASK: Memory Extraction (Non-blocking)
        async def run_extraction_task():
            await loop.run_in_executor(
                None, memory_consolidator.extract_memories, telegram_id, text, response
            )

        asyncio.create_task(run_extraction_task())

        # Log to Admin (Silent Monitor)
        if ADMIN_NOTES:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_NOTES,
                    text=f"🤖 AI Replied to @{user.username or user.first_name}:\nQ: {text}\nA: {response[:100]}...",
                )
            except:
                pass
        return

    # 4. Handle Media / Fallback (Forward to Admin)
    sent = None
    caption_text = f"Q from @{user.username or user.first_name} (Media):\n{text}"

    if update.message.photo:
        sent = await context.bot.send_photo(
            chat_id=ADMIN_NOTES,
            photo=update.message.photo[-1].file_id,
            caption=caption_text,
        )
    elif update.message.document:
        sent = await context.bot.send_document(
            chat_id=ADMIN_NOTES,
            document=update.message.document.file_id,
            caption=caption_text,
        )
    elif update.message.video:
        sent = await context.bot.send_video(
            chat_id=ADMIN_NOTES,
            video=update.message.video.file_id,
            caption=caption_text,
        )
    elif update.message.audio:
        sent = await context.bot.send_audio(
            chat_id=ADMIN_NOTES,
            audio=update.message.audio.file_id,
            caption=caption_text,
        )
    elif update.message.voice:
        sent = await context.bot.send_voice(
            chat_id=ADMIN_NOTES,
            voice=update.message.voice.file_id,
            caption=caption_text,
        )

    if sent:
        globals.question_map[sent.message_id] = (
            text,
            user.username or user.first_name,
            update.effective_chat.id,
            ("media", None),
        )
        await update.message.reply_text(
            "I've received your file! I'll pass it to a human admin."
        )
