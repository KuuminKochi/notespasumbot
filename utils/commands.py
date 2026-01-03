from telegram import Update
from telegram.ext import ContextTypes
from . import firebase_db, memory_consolidator
import asyncio


async def reset_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Resets the conversation context for the user.
    """
    await update.message.reply_text(
        "🔄 My short-term memory of our current conversation has been reset! (But I still remember our long-term bond ✨)"
    )


async def show_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays what Mimi has stored in the user's long-term memory.
    """
    user_id = update.effective_user.id
    memories = firebase_db.get_user_memories(user_id, limit=10)

    if not memories:
        await update.message.reply_text(
            "I don't have any specific long-term memories stored yet! Let's chat more so I can learn about your study habits. 📚"
        )
        return

    text = "🧠 **What I remember about you:**\n\n"
    for m in memories:
        text += f"- {m.get('content')}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def reprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forces an AI psych profile update for the user.
    """
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🧬 Mimi is re-analyzing your learning patterns to update your psych profile... please wait."
    )

    memories = firebase_db.get_user_memories(user_id, limit=30)
    if not memories:
        await update.message.reply_text(
            "I need a bit more shared history before I can generate a profile. Let's chat more first! 💬"
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
        f"✨ **Profile Updated!**\n\n{profile_text}\n\n_This profile will now be used for more accurate matching in /pasummatch!_",
        parse_mode="Markdown",
    )
