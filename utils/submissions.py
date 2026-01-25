import os
import datetime
import httpx
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from utils import firebase_db, ai_moderator

logger = logging.getLogger(__name__)

GET_CONTENT, GET_ANONYMITY = range(2)


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /post command."""
    if not update.message:
        return ConversationHandler.END

    # Check for direct reply command: /post reply ID text
    args = context.args
    if args:
        if args[0] == "reply":
            # Incomplete reply command
            if len(args) < 2:
                await update.message.reply_text(
                    "❌ <b>Incomplete command!</b>\n\n"
                    "To reply to a post, use:\n"
                    "<code>/post reply [Post ID] [Your message]</code>\n\n"
                    "<i>Example: /post reply 123 Thanks for sharing!</i>",
                    parse_mode="HTML",
                )
                return ConversationHandler.END

            if len(args) < 3:
                await update.message.reply_text(
                    "❌ <b>Missing your reply message!</b>\n\n"
                    "To reply to a post, use:\n"
                    "<code>/post reply [Post ID] [Your message]</code>\n\n"
                    "<i>Example: /post reply 123 Thanks for sharing!</i>",
                    parse_mode="HTML",
                )
                return ConversationHandler.END

            try:
                post_id = int(args[1])
                reply_content = " ".join(args[2:])
                return await handle_direct_reply(
                    update, context, post_id, reply_content
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ <b>Invalid Post ID format!</b>\n\n"
                    "The Post ID must be a number. Use:\n"
                    "<code>/post reply [Post ID] [Your message]</code>\n\n"
                    "<i>Example: /post reply 123 Thanks for sharing!</i>",
                    parse_mode="HTML",
                )
                return ConversationHandler.END
        else:
            # User provided unknown argument to /post
            await update.message.reply_text(
                "❌ <b>Unknown command!</b>\n\n"
                "Valid usage:\n"
                "• <code>/post</code> - Create a new post\n"
                "• <code>/post reply [ID] [text]</code> - Reply to a post\n\n"
                "Which would you like to do?",
                parse_mode="HTML",
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "👋 <b>Mimi Submission Center</b>\n\n"
        "Send the content you want to post. You can include a photo/PDF and a caption, or just text.\n"
        "<i>Mimi will moderate and categorize it automatically.</i>",
        parse_mode="HTML",
    )
    return GET_CONTENT


async def get_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the content and asks for anonymity."""
    if not update.message:
        return ConversationHandler.END

    context.user_data["sub_text"] = update.message.text or update.message.caption or ""
    context.user_data["sub_photo_path"] = None

    # Handle Photo
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = f"downloads/sub_{update.effective_user.id}.jpg"
        os.makedirs("downloads", exist_ok=True)
        await file.download_to_drive(path)
        context.user_data["sub_photo_path"] = path

    # Handle Document (PDF)
    elif update.message.document:
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        path = f"downloads/sub_{update.effective_user.id}_{doc.file_name}"
        os.makedirs("downloads", exist_ok=True)
        await file.download_to_drive(path)
        context.user_data["sub_photo_path"] = path

    keyboard = [
        [
            InlineKeyboardButton("👤 Show my Name", callback_data="sub_public"),
            InlineKeyboardButton("🕵️ Post Anonymously", callback_data="sub_anon"),
        ]
    ]
    await update.message.reply_text(
        "Identity Settings:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GET_ANONYMITY


async def process_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Review and Posting logic."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()

    is_anon = query.data == "sub_anon"
    user = update.effective_user
    author_name = (
        "Anonymous Student"
        if is_anon
        else f"{user.first_name} {user.last_name or ''}".strip()
    )

    await query.edit_message_text(
        "🧠 <b>Mimi is reviewing your post...</b>", parse_mode="HTML"
    )

    text = context.user_data.get("sub_text", "")
    photo_path = context.user_data.get("sub_photo_path")

    # 1. AI Moderation (DeepSeek + Nemotron)
    moderator = ai_moderator.AIModerator()
    analysis = await moderator.analyze_submission(text, image_path=photo_path)

    if analysis.get("is_spam"):
        await query.message.reply_text(
            "❌ Sorry, Mimi flagged your post as spam or irrelevant."
        )
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return ConversationHandler.END

    # 2. Assign IDs
    post_id = firebase_db.get_next_post_id()
    dest_id = os.getenv("DESTINATION_GROUP_ID")
    bot_token = os.getenv("API_KEY")

    # 3. Format Message
    emoji_map = {"news": "✨", "complaint": "⚠️", "confession": "🤫"}
    type_emoji = emoji_map.get(analysis["type"], "📝")

    mimi_caption = (
        f"{type_emoji} <b>{analysis['summary']}</b>\n\n"
        f"📍 <i>Source: User Submission | {author_name}</i>\n"
        f"🏷️ {' '.join(analysis['tags'])}\n"
        f"🆔 ID: #{post_id}\n"
        f"────────────────────\n"
        f"{analysis['cleaned_text']}"
    )

    # 4. Forward to Group
    dest_msg_id = None
    try:
        async with httpx.AsyncClient() as client:
            if photo_path and photo_path.lower().endswith((".jpg", ".png", ".jpeg")):
                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                files = {"photo": open(photo_path, "rb")}
                data = {
                    "chat_id": dest_id,
                    "caption": mimi_caption,
                    "parse_mode": "HTML",
                }
                response = await client.post(url, files=files, data=data)
            else:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {"chat_id": dest_id, "text": mimi_caption, "parse_mode": "HTML"}
                response = await client.post(url, data=data)

            if response.status_code == 200:
                dest_msg_id = response.json()["result"]["message_id"]
    except Exception as e:
        logger.error(f"Error forwarding user post: {e}")

    # 5. Save to Firestore
    post_data = {
        "post_id": post_id,
        "content_text": analysis["cleaned_text"],
        "original_content": text,
        "summary": analysis["summary"],
        "tags": analysis["tags"],
        "status": analysis["type"],
        "source_group": "User Submission",
        "source_id": user.id,
        "author_name": author_name,
        "dest_msg_id": dest_msg_id,
        "source_type": "user_submission",
        "timestamp": datetime.datetime.now().isoformat(),
    }
    firebase_db.save_aggregated_post(post_data)

    await query.message.reply_text(
        f"✅ <b>Post Successful!</b>\nYour post is live as <b>#{post_id}</b>.",
        parse_mode="HTML",
    )
    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)
    return ConversationHandler.END


async def handle_direct_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, reply_text: str
):
    """Handles direct /post reply ID content."""
    parent_post = firebase_db.get_post_by_id(post_id)
    if not parent_post:
        await update.message.reply_text(f"❌ Could not find post #{post_id}")
        return ConversationHandler.END

    parent_data = parent_post.to_dict()
    if not parent_data:
        return ConversationHandler.END

    dest_msg_id = parent_data.get("dest_msg_id")
    dest_chat_id = os.getenv("DESTINATION_GROUP_ID")
    bot_token = os.getenv("API_KEY")
    user = update.effective_user
    author = (
        "Anonymous" if parent_data.get("status") == "confession" else user.first_name
    )

    if not dest_msg_id:
        await update.message.reply_text("❌ This post cannot be replied to via bot.")
        return ConversationHandler.END

    # Universal Edit & Append Logic
    update_prefix = (
        "\n\n🤫 <b>Confession Reply:</b>"
        if parent_data.get("status") == "confession"
        else f"\n\n💬 <b>Update from {author}:</b>"
    )
    new_full_text = (
        parent_data.get("content_text", "") + f"{update_prefix}\n{reply_text}"
    )

    mimi_caption = (
        f"✨ <b>{parent_data.get('summary')}</b>\n\n"
        f"📍 <i>Source: {parent_data.get('source_group')}</i>\n"
        f"🏷️ {' '.join(parent_data.get('tags', []))}\n"
        f"🆔 ID: #{post_id}\n"
        f"────────────────────\n"
        f"{new_full_text}"
    )

    # We always use editMessageCaption if an image_url or local_path exists
    if not parent_data.get("image_url") and not parent_data.get("local_path"):
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        data = {
            "chat_id": dest_chat_id,
            "message_id": dest_msg_id,
            "text": mimi_caption,
            "parse_mode": "HTML",
        }
    else:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageCaption"
        data = {
            "chat_id": dest_chat_id,
            "message_id": dest_msg_id,
            "caption": mimi_caption,
            "parse_mode": "HTML",
        }

    async with httpx.AsyncClient() as client:
        await client.post(url, data=data)

    firebase_db.save_aggregated_post(
        {"doc_id": parent_post.id, "content_text": new_full_text}
    )
    await update.message.reply_text(f"✅ Reply sent to post #{post_id}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


conv_handler = ConversationHandler(
    entry_points=[CommandHandler("post", post_start)],
    states={
        GET_CONTENT: [
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.Document.ALL, get_content
            )
        ],
        GET_ANONYMITY: [CallbackQueryHandler(process_submission, pattern="^sub_")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
