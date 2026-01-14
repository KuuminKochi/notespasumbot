import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils import memory_sync

logger = logging.getLogger(__name__)


async def sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manually triggers the memory synchronization between Local and Cloud.
    """
    user_id = update.effective_user.id
    # Only allow Kuumin (Admin) to run this
    if str(user_id) != "1088951045":
        await update.message.reply_text("⛔ Access Denied.")
        return

    msg = await update.message.reply_text("🔄 Syncing memories (Local ↔ Cloud)...")

    try:
        memory_sync.sync_memories_to_firestore()
        await msg.edit_text("✅ Sync complete! Brain is unified.")
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        await msg.edit_text(f"❌ Sync failed: {e}")
