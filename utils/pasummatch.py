from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from utils import globals
import os
import random

load_dotenv()

API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

# Track active users (people who messaged in NOTES_PASUM group)
async def track_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track every user who speaks in NOTES_PASUM."""
    chat = update.effective_chat
    user = update.effective_user

    # Only track if message is in the NOTES_PASUM group
    if chat and chat.id == NOTES_PASUM and user:
        display_name = f"@{user.username}" if user.username else user.full_name
        globals.active_users.add((user.id, display_name))

        # (optional) Debug log
        print(f"Tracked active: {display_name} ({user.id})")

async def pasum_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Due to the fact that PASUM Match is flooding Notes PASUM, it has been disabled until I care enough to reprogram it :3")
    # """Sends PASUM matches both in group and DM."""
    # user = update.effective_user
    #
    # if not globals.active_users:
    #     await update.message.reply_text("No active users yet to match with 🥲")
    #     return
    #
    # # Remove self from pool
    # pool = [u for u in globals.active_users if u[0] != user.id]
    # if not pool:
    #     await update.message.reply_text("You’re the only active one 💀")
    #     return
    #
    # # Generate random matches
    # matches = random.sample(pool, min(5, len(pool)))  # up to 5
    # text = f"💘 PASUM Matches for {user.mention_html()} 💘\n\n"
    # for uid, uname in matches:
    #     score = random.randint(0, 100)
    #     if score == 100:
    #         comment = "💍 Perfect match! Wedding at DKU next week!"
    #     elif score > 70:
    #         comment = "🔥 High chemistry detected. Go study together before you fall in love."
    #     elif score > 40:
    #         comment = "😅 Potential… but might just end up as lab partners."
    #     elif score > 10:
    #         comment = "🥲 Like H₂O and oil. Maybe in another semester?"
    #     else:
    #         comment = "💀 Please stick to group study only."
    #     text += f"{uname} = {score}%\n{comment}\n\n"
    #
    # # Always send to group
    # await context.bot.send_message(
    #     chat_id=update.effective_chat.id,
    #     text=text,
    #     parse_mode="HTML"
    # )
    #
    # # Also try to DM the user
    # try:
    #     await context.bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")
    # except Exception:
    #     pass  # ignore if they haven't started bot

