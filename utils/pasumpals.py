from telegram import Update, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes
)
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
NOTES_PASUM = int(os.getenv("NOTES_PASUM"))
ADMIN_NOTES = int(os.getenv("ADMIN_NOTES"))

DATA_FILE = "users.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

# States for registration flow
PHOTO, DESCRIPTION = range(2)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# Registration process
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    await update.message.reply_text("Send a picture that shows your personality!")
    return PHOTO


async def save_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    user = update.effective_user
    photo = update.message.photo[-1]
    file_id = photo.file_id
    context.user_data["photo_id"] = file_id
    await update.message.reply_text("Now send me a short description (max 200 chars).")
    return DESCRIPTION


async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    user = update.effective_user
    desc = update.message.text.strip()[:200]
    data = load_data()
    data[str(user.id)] = {
        "name": user.full_name,
        "username": user.username,
        "photo_id": context.user_data["photo_id"],
        "description": desc,
    }
    save_data(data)
    await update.message.reply_text("✅ Profile saved! Use /profile to see it.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    await update.message.reply_text("❌ Registration cancelled.")
    return ConversationHandler.END


# Show own profile
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    user = update.effective_user
    data = load_data()
    if str(user.id) not in data:
        await update.message.reply_text("You don’t have a profile yet. Use /register.")
        return
    info = data[str(user.id)]
    caption = f"{info['name']} (@{info['username']})\n\n{info['description']}"
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=info["photo_id"],
        caption=caption
    )


# Show a random PASUM student
import random
async def random_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == NOTES_PASUM:
        await update.message.reply_text(globals.WARNING)
        return
    data = load_data()
    if not data:
        await update.message.reply_text("No PASUM profiles yet.")
        return
    uid, info = random.choice(list(data.items()))
    caption = f"{info['name']} (@{info['username']})\n\n{info['description']}"
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=info["photo_id"],
        caption=caption
    )

conv = ConversationHandler(
    entry_points=[CommandHandler("register", register)],
    states={
        PHOTO: [MessageHandler(filters.PHOTO, save_photo)],
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_description)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
