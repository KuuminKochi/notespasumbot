from telegram import Update
from telegram.ext import ContextTypes
from utils import firebase_db
import os

ADMIN_NOTES = os.getenv("ADMIN_NOTES", "0")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Only existing admins can add other admins
    if not firebase_db.is_admin(user.id):
        await update.message.reply_text("🔒 Only admins can add new admins.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return

    new_admin_id = context.args[0]
    firebase_db.add_admin(new_admin_id)
    await update.message.reply_text(f"✅ User {new_admin_id} is now an Admin.")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Only existing admins can remove admins
    if not firebase_db.is_admin(user.id):
        await update.message.reply_text("🔒 Only admins can remove other admins.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /removeadmin <user_id>")
        return

    target_id = context.args[0]
    firebase_db.remove_admin(target_id)
    await update.message.reply_text(f"🗑️ User {target_id} removed from Admins.")
