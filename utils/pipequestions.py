import os
import asyncio
import datetime
import random
import time
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from utils import firebase_db, ai_agent, vision, concurrency


async def pipe_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_type = update.effective_chat.type if update.effective_chat else ""
    user = update.effective_user
    if not user or not context.bot:
        return

    text = (update.message.text or update.message.caption or "").strip()
    telegram_id = user.id
    user_name = user.first_name or "Student"
    chat_id = update.effective_chat.id

    # 1. Background Logging (Always listen in groups)
    if chat_type in ["group", "supergroup"] and text:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            concurrency.get_pool(),
            firebase_db.log_conversation,
            telegram_id,
            "user",
            text,
            chat_id,
            user_name
        )

    # 2. Trigger Check
    is_summoned = False
    if chat_type in ["group", "supergroup"]:
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{context.bot.username}" in (update.message.text or "")
        
        if is_reply_to_bot or is_mention:
            is_summoned = True
        else:
            # 7% chance with 5 min cooldown
            last_activation = context.chat_data.get("last_mimi_activation", 0)
            now = time.time()
            if (now - last_activation) > 300: # 5 mins
                if random.random() < 0.07:
                    is_summoned = True
                    context.chat_data["last_mimi_activation"] = now
    elif chat_type == "private":
        is_summoned = True
    else:
        return

    if not is_summoned:
        return

    # 3. Update User Profile in Background
    try:
        user_data = {
            "name": user.full_name,
            "username": user.username,
            "last_active": datetime.datetime.now(),
        }
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            concurrency.get_pool(),
            firebase_db.create_or_update_user,
            telegram_id,
            user_data,
        )
    except:
        pass

    # 4. Vision Priority
    target_photo = update.message.photo
    if not target_photo and update.message.reply_to_message:
        target_photo = update.message.reply_to_message.photo

    if target_photo:
        context.user_data["processing_image"] = True
        await vision.process_image_question(update, context)
        return

    # 4b. Skip if image processing flag is set (prevents duplicate handling)
    if context.user_data.get("processing_image"):
        context.user_data["processing_image"] = False
        return

    # 5. Text Streaming
    if text:
        if len(text) < 2:
            return
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )

        # Random splash text
        splash = random.choice(vision.SPLASH_TEXTS)
        status_msg = await update.message.reply_text(f"🤔 {splash}")

        # Call the new AI Agent (Tool-enabled) with chat_id for scoping
        await ai_agent.stream_ai_response(
            update, context, status_msg, text, chat_id
        )
        return
