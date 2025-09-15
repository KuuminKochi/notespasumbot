from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from utils import pipequestions, pipeanswers, globals
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

app = Application.builder().token(API_KEY).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(globals.INTRODUCTION)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Chat ID: {chat_id}")


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
    get_id
))
app.add_handler(CommandHandler(
    "start",
    start
))

app.run_polling()
