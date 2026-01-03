from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv
from utils import (
    lecturenotes,
    pipequestions,
    pipeanswers,
    start,
    getid,
    pasummatch,
    help,
    tutorialanswers,
    mid_sem,
    pasumpals,
    jottednotes,
    commands,
)
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))

app = Application.builder().token(API_KEY).build()

# --- AI Tutoring Handlers ---
app.add_handler(
    MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND, pipequestions.pipe_question
    )
)

# --- Command Handlers ---
app.add_handler(CommandHandler("start", start.start))
app.add_handler(CommandHandler("help", help.help_message))
app.add_handler(CommandHandler("getId", getid.get_id))
app.add_handler(CommandHandler("tutorials", tutorialanswers.tutorial_answers))
app.add_handler(CommandHandler("lecturenotes", lecturenotes.lecture_notes))
app.add_handler(CommandHandler("jottednotes", jottednotes.jotted_notes))

# New AI Management Commands
app.add_handler(CommandHandler("reset", commands.reset_context))
app.add_handler(CommandHandler("memories", commands.show_memories))
app.add_handler(CommandHandler("reprofile", commands.reprofile))

# --- Matching & Admin Handlers ---
app.add_handler(
    MessageHandler(
        filters.Chat(ADMIN_NOTES) & filters.REPLY & ~filters.COMMAND,
        pipeanswers.pipe_answer,
    )
)

app.add_handler(CommandHandler("pasummatch", pasummatch.pasum_match))
app.add_handler(
    MessageHandler(filters.ALL & filters.Chat(NOTES_PASUM), pasummatch.track_active)
)

# Profile Management
app.add_handler(pasumpals.conv)
app.add_handler(CommandHandler("profile", pasumpals.profile))
app.add_handler(CommandHandler("random", pasumpals.random_profile))

if __name__ == "__main__":
    print("Mimi Notes Bot is running...")
    app.run_polling()
