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
                    "<i>Example: /post reply 123 Thanks!</i>",
                    parse_mode="HTML",
                )
                return ConversationHandler.END
            if len(args) < 3:
                await update.message.reply_text(
                    "❌ <b>Missing your reply message!</b>\n\n"
                    "To reply to a post, use:\n"
                    "<code>/post reply [Post ID] [Your message]</code>\n\n"
                    "<i>Example: /post reply 123 Thanks!</i>",
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
                await update.message.reply_text("❌ Post ID must be a number.")
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
        "Send content you want to post. You can include a photo/PDF and a caption, or just text.\n"
        "<i>Mimi will moderate and categorize it automatically.</i>",
        parse_mode="HTML",
    )
    return GET_CONTENT


async def get_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores content and asks for anonymity."""
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
    """AI Review and Posting logic with strict quality control."""
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

    await query.edit_message_text("🚀 <b>Analyzing your submission...</b>", parse_mode="HTML")

    text = context.user_data.get("sub_text", "")
    photo_path = context.user_data.get("sub_photo_path")

    # AI Quality Moderation with strict mode
    transcrion = ""
    if photo_path:
        transcrion = await ai_moderator.transcribe_image(photo_path)

    full_context = f"Transcrion: {transcrion}\n\nSubmission: {text}"

    moderation = await ai_moderator.analyze_submission(text, photo_path, strict_mode=True)

    # Check if post was rejected for quality reasons
    if moderation.get("is_spam"):
        await query.edit_message_text(
            "🚫 <b>Post Rejected</b>\n\n"
            f"<i>Reason: {moderation.get('rejection_reason') or 'Low quality content'}</i>\n\n"
            "<b>Requirements:</b>\n"
            "• Relevant to PASUM/academics\n"
            "• 3-6 word summary\n"
            "• Professional tone\n"
            "<i>Please try again with higher quality content.</i>",
            parse_mode="HTML",
        )
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return ConversationHandler.END

    # Validate summary length (6 words max in strict mode)
    summary = moderation.get("summary", "")
    if len(summary.split()) > 6:
        await query.edit_message_text(
            "🚫 <b>Post Rejected</b>\n\n"
            f"<i>Reason: Summary too long ({len(summary.split())} words, max 6)</i>\n\n"
            "<b>Requirements:</b>\n"
            "• Relevant to PASUM/academics\n"
            "• Maximum 6 words in summary\n"
            "• Professional tone\n"
            "<i>Please shorten your summary to 6 words maximum.</i>",
            parse_mode="HTML",
        )
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return ConversationHandler.END

    # Validate minimum content (3 words min for text, or image required)
    text_length = len(text.split())
    if text_length < 3 and not photo_path:
        await query.edit_message_text(
            "🚫 <b>Post Rejected</b>\n\n"
            f"<i>Reason: Content too brief ({text_length} words, min 3)</i>\n\n"
            "<b>Requirements:</b>\n"
            "• Relevant to PASUM/academics\n"
            "• At least 3 words OR include image\n"
            "• Professional tone\n"
            "<i>Please add more details or include an image.</i>",
            parse_mode="HTML",
        )
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return ConversationHandler.END

    # Assign IDs and save to database
    post_id = firebase_db.get_next_post_id()
    dest_id = os.getenv("DESTINATION_GROUP_ID")
    bot_token = os.getenv("API_KEY")

    # Validate destination group is configured
    if not dest_id:
        await query.edit_message_text(
            "❌ <b>Configuration Error:</b>\n"
            "Destination group not configured. Please contact admin.",
            parse_mode="HTML",
        )
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return ConversationHandler.END

    # Format Message - Professional Style
    ts = datetime.datetime.now().strftime("%I:%M %p")

    # Use AI-moderated content and status
    editorial_content = moderation.get("cleaned_text", text)
    post_type = moderation.get("type", "news")
    status = moderation.get("status", "trusted")

    mimi_caption = (
        f"{editorial_content}\n\n"
        f"▫️ #ID{post_id} • 📍 {author_name} • 🕒 {ts}"
    )

    # 4. Forward to Group
    dest_msg_id = None
    send_success = False
    error_message = None

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
                send_success = True
            else:
                error_message = response.text
                logger.error(
                    f"Telegram API error: {response.status_code} - {response.text}"
                )
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error forwarding user post: {e}", exc_info=True)

    # 5. Save to Firestore and respond to user
    if send_success:
        post_data = {
            "post_id": post_id,
            "editorial_content": editorial_content,
            "original_caption": text,
            "summary": moderation.get("summary", "User Update"),
            "tags": moderation.get("tags", ["#user_submission"]),
            "status": status,
            "source_group": author_name,
            "source_id": user.id,
            "dest_msg_id": dest_msg_id,
            "source_type": "user_submission",
            "timestamp": datetime.datetime.now().isoformat(),
        }
        firebase_db.save_aggregated_post(post_data)

        await query.message.reply_text(
            f"✅ <b>Post Successful!</b>\nYour post is live as <b>#{post_id}</b>.",
            parse_mode="HTML",
        )
    else:
        await query.message.reply_text(
            f"❌ <b>Failed to post</b>\n\n"
            f"<i>Error: {error_message or 'Unknown error'}</i>\n\n"
            f"Please try again or contact admin if the issue persists.",
            parse_mode="HTML",
        )

    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def reply_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /reply [ID] [Text] shortcut."""
    logger.info(f"📥 Received /reply command from {update.effective_user.id}")
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Incomplete command!</b>\n\n"
            "Usage: <code>/reply [ID] [Message]</code>\n"
            "<i>Example: /reply 123 Thanks!</i>",
            parse_mode="HTML",
        )
        return

    try:
        post_id = int(context.args[0])
        reply_content = " ".join(context.args[1:])
        # Reuse AI moderation logic
        await handle_direct_reply(update, context, post_id, reply_content)
    except ValueError:
        await update.message.reply_text("❌ Post ID must be a number.")


async def handle_direct_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, reply_text: str
):
    """Handles direct /post reply ID content."""
    try:
        parent_post = firebase_db.get_post_by_id(post_id)
        if not parent_post:
            logger.warning(f"🔍 Post #{post_id} not found in DB")
            await update.message.reply_text(f"❌ Could not find post #{post_id}")
            return ConversationHandler.END

        parent_data = parent_post.to_dict()
        if not parent_data:
            logger.error(f"❌ Post #{post_id} document is empty")
            return ConversationHandler.END

        dest_msg_id = parent_data.get("dest_msg_id")
        dest_chat_id = os.getenv("DESTINATION_GROUP_ID")
        bot_token = os.getenv("API_KEY")

        if not dest_msg_id:
            logger.warning(f"⚠️ Post #{post_id} has no dest_msg_id")
            await update.message.reply_text("❌ This post cannot be replied to via bot.")
            return ConversationHandler.END

        is_anon_reply = parent_data.get("status") == "confession"

        author = (
            "Anonymous"
            if is_anon_reply
            else f"{update.effective_user.first_name} {update.effective_user.last_name or ''}".strip()
        )

        # Universal Edit & Append Logic with AI moderation
        reply_prefix = f"\n\n💬 {reply_text}"

        # Apply AI moderation to the reply text
        moderation = await ai_moderator.analyze_submission(reply_text, strict_mode=False)

        new_editorial = parent_data.get("editorial_content", "") + reply_prefix

        # Prepare data for formatting
        format_data = {
            **parent_data,
            "editorial_content": new_editorial,
        }

        # Replicate formatting
        import html

        content = format_data.get("editorial_content", "")
        original = format_data.get("original_caption", "")
        source = format_data.get("source_group", "Unknown")
        parent_post_id = format_data.get("post_id")

        orig_section = ""
        if original and original.strip() != content.strip().replace(reply_prefix, "").strip():
            safe_original = html.escape(original)
            orig_section = f"\n\n---\n<blockquote>{safe_original}</blockquote>"

        try:
            dt_str = format_data.get("timestamp", "")
            ts = datetime.datetime.fromisoformat(dt_str).strftime("%I:%M %p")
        except:
            ts = datetime.datetime.now().strftime("%I:%M %p")

        mimi_caption = f"{content}{orig_section}\n\n▫️ #ID{parent_post_id} • 📍 {source} • 🕒 {ts}"

        logger.info(f"📤 Updating message {dest_msg_id} in {dest_chat_id}")

        # Prepare payload
        is_media = parent_data.get("image_url") or parent_data.get("local_path") or parent_data.get("media_type") != "text"

        if not is_media:
            url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
            payload = {
                "chat_id": dest_chat_id,
                "message_id": int(dest_msg_id),
                "text": mimi_caption,
                "parse_mode": "HTML",
            }
        else:
            url = f"https://api.telegram.org/bot{bot_token}/editMessageCaption"
            payload = {
                "chat_id": dest_chat_id,
                "message_id": int(dest_msg_id),
                "caption": mimi_caption,
                "parse_mode": "HTML",
            }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            logger.error(f"❌ Telegram API Error: {resp.status_code} - {resp.text}")
            await update.message.reply_text(f"❌ Failed to update Telegram message: {resp.text}")
            return ConversationHandler.END

        firebase_db.save_aggregated_post(
            {"doc_id": parent_post.id, "editorial_content": new_editorial}
        )

        await update.message.reply_text(f"✅ Reply sent to post #{post_id}")
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"🔥 Critical error in handle_direct_reply: {e}", exc_info=True)
        await update.message.reply_text(f"🔥 A critical error occurred: {e}")
        return ConversationHandler.END


conv_handler = ConversationHandler(
    entry_points=[CommandHandler("post", post_start)],
    states={
        GET_CONTENT: [
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.Document.ALL, get_content
            )
        ]
    },
    GET_ANONYMITY: [CallbackQueryHandler(process_submission, pattern="^sub_")],
    fallbacks=[CommandHandler("cancel", cancel)],
)
