from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils import firebase_db, ai_tutor, concurrency, vision
import asyncio
import os
import base64

ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Security Check: Allow both root admin and additional admins
    if not user or not firebase_db.is_admin(user.id):
        print(f"Unauthorized /announce attempt by {user.id} ({user.first_name})")
        await update.message.reply_text(
            f"🔒 Nice try! This command is for Admin only.\nYour ID: `{user.id}`"
        )
        return

    # --- 1. Determine Content Source ---
    target_msg = update.message.reply_to_message

    announcement_text = ""
    file_id = None
    media_type = None  # 'photo', 'video', 'document', 'audio', 'voice'

    if target_msg:
        # Case A: Replying to a message
        announcement_text = target_msg.caption or target_msg.text or ""

        # Check for media (Priority order matches Telegram object structure)
        if target_msg.photo:
            media_type = "photo"
            file_id = target_msg.photo[-1].file_id  # Best quality
        elif target_msg.document:
            media_type = "document"
            file_id = target_msg.document.file_id
        elif target_msg.video:
            media_type = "video"
            file_id = target_msg.video.file_id
        elif target_msg.audio:
            media_type = "audio"
            file_id = target_msg.audio.file_id
        elif target_msg.voice:
            media_type = "voice"
            file_id = target_msg.voice.file_id

        # If admin added extra text in the command while replying, prepend it
        if context.args:
            extra_text = " ".join(context.args)
            announcement_text = f"{extra_text}\n\n{announcement_text}".strip()

    else:
        # Case B: Text-only command
        if not context.args:
            await update.message.reply_text(
                "Usage:\n"
                "1. Reply to a message with /announce\n"
                "2. Or type: /announce [Your message]"
            )
            return
        announcement_text = " ".join(context.args)

    # Fallback if empty
    if not announcement_text and not file_id:
        await update.message.reply_text(
            "❌ Error: The message seems empty (no text and no media)."
        )
        return

    # --- 2. Save to DB ---
    # We save a string representation. If it's a file, we note it.
    log_text = announcement_text
    if media_type:
        log_text = f"[{media_type.upper()}] {log_text}"

    firebase_db.save_announcement(log_text, user.id)

    await update.message.reply_text(
        f"📣 Analyzing & Broadcasting... (Media: {media_type or 'None'})"
    )

    # --- 3. Broadcast Loop ---
    user_ids = firebase_db.get_all_user_ids()
    count = 0
    loop = asyncio.get_running_loop()

    for uid in user_ids:
        try:
            # Skip invalid or self
            if not uid or uid == str(context.bot.id):
                continue

            # A. Generate Personal Note (DISABLED - memories disabled for refactoring)
            # Personal comments are skipped
            personal_note = ""

            # B. Format Final Caption/Message
            # Base content
            if announcement_text:
                final_content = f"📢 <b>ANNOUNCEMENT</b>\n\n{announcement_text}"
            else:
                final_content = "📢 <b>ANNOUNCEMENT</b>"  # File only case

            # No Mimi's note appended (memories disabled)

            # C. Send based on type
            # Use HTML parsing consistently with the rest of the bot

            if media_type == "photo":
                await context.bot.send_photo(
                    chat_id=uid,
                    photo=file_id,
                    caption=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )
            elif media_type == "document":
                await context.bot.send_document(
                    chat_id=uid,
                    document=file_id,
                    caption=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )
            elif media_type == "video":
                await context.bot.send_video(
                    chat_id=uid,
                    video=file_id,
                    caption=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )
            elif media_type == "audio":
                await context.bot.send_audio(
                    chat_id=uid,
                    audio=file_id,
                    caption=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )
            elif media_type == "voice":
                await context.bot.send_voice(
                    chat_id=uid,
                    voice=file_id,
                    caption=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )
            else:
                # Text only
                await context.bot.send_message(
                    chat_id=uid,
                    text=ai_tutor.escape_html(final_content),
                    parse_mode="HTML",
                )

            count += 1
            await asyncio.sleep(0.05)  # Rate limit safety

        except Exception as e:
            # Log but don't stop
            print(f"Broadcast fail for {uid}: {e}")

    await update.message.reply_text(f"✅ Broadcast complete! Sent to {count} students.")
