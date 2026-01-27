from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PicklePersistence,
    CallbackQueryHandler,
)
from dotenv import load_dotenv
from utils import (
    pipequestions,
    pipeanswers,
    resource_handler,
    getid,
    pasummatch,
    help,
    commands,
    pasumpals,
    announcer,
    admin_manager,
    sync_cmd,
    news_browser,
    submissions,
    status,
)
from utils.aggregator_service.aggregator import Aggregator
from utils.aggregator_service.cleaner import cleanup_task
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import asyncio

load_dotenv()

API_KEY = os.getenv("API_KEY")
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES", 0))

if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")


async def start_aggregator_task(application: Application):
    """Starts the Mimi Aggregator service in the background."""
    if TELEGRAM_API_ID and TELEGRAM_API_HASH:
        print("🚀 Starting Mimi Aggregator Service...")

        # 1. Start Cleaner Scheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(cleanup_task, "interval", days=1)
        scheduler.start()
        print("🧹 Cleaner Scheduler Started.")

        # 2. Initialize Aggregator
        aggregator = Aggregator(
            "mimi_aggregator", int(TELEGRAM_API_ID), TELEGRAM_API_HASH
        )
        # Start as background task
        asyncio.create_task(aggregator.start())
    else:
        print("⚠️ Aggregator skipped: Missing TELEGRAM_API_ID/HASH")


persistence = PicklePersistence(filepath="bot_persistence.pickle")
app = (
    Application.builder()
    .token(API_KEY)
    .persistence(persistence)
    .post_init(start_aggregator_task)
    .read_timeout(100)
    .write_timeout(100)
    .connect_timeout(60)
    .build()
)


async def debug_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log every message the bot sees for debugging."""
    if update.effective_message:
        logger.info(
            f"🔍 DEBUG BOT SAW MSG: '{update.effective_message.text}' from {update.effective_user.id if update.effective_user else 'None'} in {update.effective_chat.id if update.effective_chat else 'None'}"
        )
    elif update.callback_query:
        logger.info(f"🔍 DEBUG BOT SAW CALLBACK: {update.callback_query.data}")
    else:
        logger.info(
            f"🔍 DEBUG BOT SAW UPDATE: {update.to_dict() if hasattr(update, 'to_dict') else update}"
        )


# --- Command Handlers ---
app.add_handler(
    MessageHandler(filters.ALL, debug_message_handler), group=-1
)  # Run before others
app.add_handler(
    CommandHandler(
        "start", lambda u, c: resource_handler.send_resource(u, c, "INTRODUCTION")
    )
)
app.add_handler(CommandHandler("help", help.help_message))
app.add_handler(CommandHandler("getId", getid.get_id))
app.add_handler(
    CommandHandler(
        "tutorials",
        lambda u, c: resource_handler.send_resource(u, c, "TUTORIAL_ANSWERS"),
    )
)
app.add_handler(
    CommandHandler(
        "lecturenotes",
        lambda u, c: resource_handler.send_resource(u, c, "LECTURE_NOTES"),
    )
)
app.add_handler(
    CommandHandler(
        "jottednotes", lambda u, c: resource_handler.send_resource(u, c, "JOTTED_NOTES")
    )
)

# New AI Management Commands
app.add_handler(CommandHandler("hardreset", commands.hard_reset))
app.add_handler(CommandHandler("reset", commands.soft_reset))
app.add_handler(
    CommandHandler(
        "midsem", lambda u, c: resource_handler.send_resource(u, c, "MID_SEM")
    )
)
app.add_handler(CommandHandler("announce", announcer.announce))
app.add_handler(CommandHandler("addadmin", admin_manager.add_admin))
app.add_handler(CommandHandler("removeadmin", admin_manager.remove_admin))
app.add_handler(CommandHandler("sync", sync_cmd.sync))
app.add_handler(CommandHandler("news", news_browser.news_command))
app.add_handler(CommandHandler("reply", submissions.reply_command_handler))
app.add_handler(CommandHandler("status", status.status_command))
app.add_handler(CallbackQueryHandler(news_browser.news_callback, pattern="^news_"))
app.add_handler(CallbackQueryHandler(news_browser.news_callback, pattern="^reply_"))

# --- Conversation Handlers (must be before general MessageHandlers) ---
app.add_handler(submissions.conv_handler)
app.add_handler(pasumpals.conv)

# --- AI Tutoring Handlers (must be last to allow conversations to work) ---
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, pipequestions.pipe_question)
)
app.add_handler(MessageHandler(filters.PHOTO, pipequestions.pipe_question))
app.add_handler(MessageHandler(filters.Document.PDF, pipequestions.pipe_question))

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
app.add_handler(CommandHandler("profile", pasumpals.profile))
app.add_handler(CommandHandler("random", pasumpals.random_profile))

import logging
import time
import sys
import traceback
import html

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("bot_errors.log")],
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(f"Exception while handling an update: {context.error}")

    if not context.error:
        return

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    message = (
        f"🚨 <b>An exception occurred while handling an update</b>\n"
        f"<pre>{html.escape(tb_string[-4000:])}</pre>"
    )

    if ADMIN_NOTES:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_NOTES, text=message, parse_mode="HTML"
            )
        except:
            print("Failed to send error alert to admin.")


if __name__ == "__main__":
    print("Mimi Notes Bot is starting...")

    # Add error handler
    app.add_error_handler(error_handler)

    try:
        print("🚀 Starting polling loop...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        logger.critical(f"Bot exited with error: {e}", exc_info=True)
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user.")
