from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv
from utils import globals
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

async def pipe_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reply = update.message.reply_to_message

    if chat_id != int(ADMIN_NOTES) or not reply:
        return

    replied_id = reply.message_id
    if replied_id not in globals.question_map:
        return

    q_text, asker, asker_id, q_media = globals.question_map[replied_id]
    answerer = update.effective_user.username or update.effective_user.first_name
    a_text = (update.message.text or update.message.caption or "").strip()

    # --- Send to both NOTES_PASUM and asker ---
    targets = [int(NOTES_PASUM), int(asker_id)]

    for target in targets:
        # 1. Send Q first
        if q_media:
            mtype, fid = q_media
            if mtype == "photo":
                await context.bot.send_photo(target, fid, caption=f"Q:\n{q_text}")
            elif mtype == "document":
                await context.bot.send_document(target, fid, caption=f"Q:\n{q_text}")
            elif mtype == "video":
                await context.bot.send_video(target, fid, caption=f"Q:\n{q_text}")
            elif mtype == "audio":
                await context.bot.send_audio(target, fid, caption=f"Q:\n{q_text}")
            elif mtype == "voice":
                await context.bot.send_voice(target, fid, caption=f"Q:\n{q_text}")
        else:
            await context.bot.send_message(target, text=f"Q:\n{q_text}")

        # 2. Send A after
        if update.message.photo:
            fid = update.message.photo[-1].file_id
            await context.bot.send_photo(target, fid, caption=f"Answer from @{answerer}:\n{a_text}")
        elif update.message.document:
            fid = update.message.document.file_id
            await context.bot.send_document(target, fid, caption=f"Answer from @{answerer}:\n{a_text}")
        elif update.message.video:
            fid = update.message.video.file_id
            await context.bot.send_video(target, fid, caption=f"Answer from @{answerer}:\n{a_text}")
        elif update.message.audio:
            fid = update.message.audio.file_id
            await context.bot.send_audio(target, fid, caption=f"Answer from @{answerer}:\n{a_text}")
        elif update.message.voice:
            fid = update.message.voice.file_id
            await context.bot.send_voice(target, fid, caption=f"Answer from @{answerer}:\n{a_text}")
        else:
            await context.bot.send_message(target, text=f"Answer from @{answerer}:\n{a_text}")
