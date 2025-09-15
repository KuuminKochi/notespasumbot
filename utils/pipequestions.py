from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from utils import globals
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

async def pipe_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    text = (update.message.text or update.message.caption or "").strip()
    asker = update.effective_user.username or update.effective_user.first_name

    if len(text) < 5:
        return

    media = None
    sent = None

    if update.message.photo:
        media = ("photo", update.message.photo[-1].file_id)
        sent = await context.bot.send_photo(
            chat_id=ADMIN_NOTES,
            photo=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.document:
        media = ("document", update.message.document.file_id)
        sent = await context.bot.send_document(
            chat_id=ADMIN_NOTES,
            document=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.video:
        media = ("video", update.message.video.file_id)
        sent = await context.bot.send_video(
            chat_id=ADMIN_NOTES,
            video=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.audio:
        media = ("audio", update.message.audio.file_id)
        sent = await context.bot.send_audio(
            chat_id=ADMIN_NOTES,
            audio=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.voice:
        media = ("voice", update.message.voice.file_id)
        sent = await context.bot.send_voice(
            chat_id=ADMIN_NOTES,
            voice=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    else:
        sent = await context.bot.send_message(
            chat_id=ADMIN_NOTES,
            text=f"Q from @{asker}:\n{text}"
        )

    if sent:
        globals.question_map[sent.message_id] = (
            text,
            asker,
            update.effective_chat.id,
            media
        )
