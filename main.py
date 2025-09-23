from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from utils import lecturenotes, pipequestions, pipeanswers, start, getid, pasummatch, help, tutorialanswers
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

app = Application.builder().token(API_KEY).build()

app.add_handler(MessageHandler(
    filters.ChatType.PRIVATE & ~filters.COMMAND,
    pipequestions.pipe_question
))
app.add_handler(MessageHandler(
    filters.Chat(ADMIN_NOTES) & filters.REPLY & ~filters.COMMAND,
    pipeanswers.pipe_answer
))
app.add_handler(CommandHandler(
    "getId",
    getid.get_id
))

app.add_handler(CommandHandler(
    "start",
    start.start
))

app.add_handler(CommandHandler(
    "help",
    help.help_message
))

app.add_handler(CommandHandler(
    "tutorials",
    tutorialanswers.tutorial_answers
))

app.add_handler(CommandHandler(
    "lecturenotes",
    lecturenotes.lecture_notes
))

app.add_handler(MessageHandler(
    filters.ALL & filters.Chat(NOTES_PASUM),
    pasummatch.track_active
))

# Run pasum_match
app.add_handler(CommandHandler(
    "pasummatch", pasummatch.pasum_match
))

app.run_polling()
