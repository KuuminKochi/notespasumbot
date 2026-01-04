from telegram import Update
from telegram.ext import ContextTypes
from utils import firebase_db, ai_tutor
import asyncio
import os

ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))


async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Security Check
    if not user or update.effective_chat.id != ADMIN_NOTES:
        await update.message.reply_text(
            "🔒 Nice try! This command is for the Admin only."
        )
        return

    # Parse Message
    if not context.args:
        await update.message.reply_text("Usage: /announce [Your message here]")
        return

    announcement_text = " ".join(context.args)

    # Save to DB
    firebase_db.save_announcement(announcement_text, user.id)

    await update.message.reply_text(
        "📣 Starting broadcast... This might take a while due to AI personalization."
    )

    # Get all users
    user_ids = firebase_db.get_all_user_ids()
    count = 0

    for uid in user_ids:
        try:
            # Skip if uid is invalid or the bot itself
            if not uid or uid == str(context.bot.id):
                continue

            # 1. Fetch Memories for Personalization
            memories = firebase_db.get_user_memories(uid, limit=5)

            # 2. Generate Personal Comment (Async to avoid blocking too long? Ideally run in executor)
            # For simplicity in this loop, we call it directly but we should be careful about timeouts.
            personal_note = ""
            if memories:
                loop = asyncio.get_running_loop()
                personal_note = await loop.run_in_executor(
                    None,
                    ai_tutor.generate_announcement_comment,
                    announcement_text,
                    memories,
                )

            # 3. Format Message
            final_msg = f"📢 **ANNOUNCEMENT**\n\n{announcement_text}"
            if personal_note:
                final_msg += f"\n\n_Mimi: {personal_note}_"

            # 4. Send
            await context.bot.send_message(
                chat_id=uid, text=final_msg, parse_mode="Markdown"
            )
            count += 1

            # Rate limiting safety (Telegram allows 30/sec, but let's be safe)
            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"Failed to send to {uid}: {e}")

    await update.message.reply_text(f"✅ Broadcast complete! Sent to {count} students.")
