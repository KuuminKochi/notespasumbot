from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import firebase_db


async def display_news_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, docs):
    """Utility to send news cards to the user."""
    chat_id = update.effective_chat.id

    for doc in docs:
        data = doc.to_dict()
        summary = data.get("summary", "🎀 Mimi: New update!")
        source = data.get("source_group", "Unknown")
        topic = data.get("topic_name", "General")
        tags = " ".join(data.get("tags", ["#PASUM"]))
        content = data.get("content_text", "")
        img_url = data.get("image_url")
        post_id = data.get("post_id", "N/A")

        caption = (
            f"🎀 <b>{summary}</b>\n\n"
            f"{content[:500]}{'...' if len(content) > 500 else ''}\n\n"
            f"<i>{source} | {topic}</i>\n"
            f"🏷️ {tags} | 🆔 #{post_id}"
        )

        keyboard = [
            [InlineKeyboardButton("💬 Reply", callback_data=f"reply_{post_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if img_url:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=img_url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
        except Exception as e:
            print(f"⚠️ Error sending news card: {e}")

    # Pagination
    if len(docs) >= 5:
        last_ts = docs[-1].to_dict().get("timestamp")
        keyboard = [
            [
                InlineKeyboardButton(
                    "Next 5 Posts ➡️", callback_data=f"news_more_{last_ts}"
                )
            ]
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text="Explore older news:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /news command."""
    # Check if user provided arguments (for future filtering)
    if context.args:
        await update.message.reply_text(
            "❌ <b>Invalid arguments!</b>\n\n"
            "The <code>/news</code> command doesn't take any arguments yet.\n"
            "Simply use <code>/news</code> to view the latest posts.\n\n"
            "<i>💡 Tip: Browse the news feed and use the 💬 Reply button to respond to posts!</i>",
            parse_mode="HTML",
        )
        return

    docs = firebase_db.get_latest_news(limit=5)
    if not docs:
        await update.message.reply_text("📭 No news aggregated yet.")
        return

    await update.message.reply_text("📡 <b>Latest PASUM News</b>", parse_mode="HTML")
    await display_news_cards(update, context, docs)


async def news_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for news pagination and other interactions."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("news_more_"):
        last_ts = query.data.replace("news_more_", "")
        docs = firebase_db.get_latest_news(limit=5, last_timestamp=last_ts)
        if not docs:
            await query.edit_message_text("🔚 You've reached the end of the news feed.")
            return

        await display_news_cards(update, context, docs)

    elif query.data.startswith("reply_"):
        post_id = query.data.replace("reply_", "")
        await query.message.reply_text(
            f"💬 <b>Reply to Post #{post_id}</b>\n\n"
            f"Send your reply using this command:\n"
            f"<code>/post reply {post_id} [Your message]</code>\n\n"
            "<i>Example: /post reply {post_id} Thanks for sharing this update!</i>",
            parse_mode="HTML",
        )
