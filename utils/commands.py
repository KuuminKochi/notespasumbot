from telegram import Update
from telegram.ext import ContextTypes
from . import firebase_db, memory_consolidator
import asyncio


async def soft_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clears only the conversation context (not memories or profile).
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    firebase_db.clear_user_conversations(user_id)
    await update.message.reply_text(
        "🔄 <b>Context Cleared.</b>\n\nI've cleared our conversation history. I still remember your learning patterns and personality traits from our previous interactions! 💬",
        parse_mode="HTML",
    )


async def hard_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Completely wipes the user's data (conversations, memories, profile).
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    firebase_db.hard_reset_user_data(user_id)
    await update.message.reply_text(
        "🗑️ <b>Hard Reset Complete.</b>\n\nI have wiped all our previous conversations, memories, and your psychological profile. We're starting from a blank slate! ✨",
        parse_mode="HTML",
    )


async def show_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays what Mimi has stored in the user's long-term memory.
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    memories = firebase_db.get_user_memories(user_id, limit=10)

    if not memories:
        await update.message.reply_text(
            "I don't have any specific long-term memories stored yet! Let's chat more so I can learn about your study habits. 📚",
            parse_mode="HTML",
        )
        return

    text = "🧠 <b>What I remember about you:</b>\n\n"
    for m in memories:
        text += f"- {m.get('content')}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def reprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forces an AI psych profile update for the user.
    """
    if not update.message:
        return
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🧬 Mimi is re-analyzing your learning patterns to update your psych profile... please wait.",
        parse_mode="HTML",
    )

    memories = firebase_db.get_user_memories(user_id, limit=30)
    if not memories:
        await update.message.reply_text(
            "I need a bit more shared history before I can generate a profile. Let's chat more first! 💬",
            parse_mode="HTML",
        )
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, memory_consolidator.generate_psych_profile, user_id, memories
    )

    # Fetch updated profile
    profile = firebase_db.get_user_profile(user_id)
    profile_text = profile.get(
        "psych_profile", "Analysis complete, but I couldn't summarize it yet."
    )

    await update.message.reply_text(
        f"✨ <b>Profile Updated!</b>\n\n{profile_text}\n\n<i>This profile will now be used for more accurate matching in /pasummatch!</i>",
        parse_mode="HTML",
    )
