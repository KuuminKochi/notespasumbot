import os
import requests
import base64
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import asyncio

# Config
XAI_API_KEY = os.getenv("XAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


async def process_image_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1. Download Photo
    2. Send to Grok Vision -> Get Description/Problem Text
    3. Send to DeepSeek Reasoner -> Solve
    4. Reply
    """
    user = update.effective_user
    status_msg = await update.message.reply_text("👀 Mimi is analyzing your image...")

    try:
        # 1. Download Image
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        # 2. Vision (Grok)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="🧠 Processing visual data (Grok Vision)...",
        )

        vision_prompt = "Describe this image in detail. If it's a math/science problem, transcribe it exactly. If it's general, describe what's happening."

        # xAI API Call (OpenAI-compatible)
        vision_response = await asyncio.to_thread(
            call_grok_vision, base64_image, vision_prompt
        )

        if not vision_response:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="❌ Failed to recognize image.",
            )
            return

        extracted_text = vision_response

        # 3. Reasoning (DeepSeek)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="🤔 Mimi is thinking (DeepSeek Reasoner)...",
        )

        reasoning_prompt = f"The user uploaded an image. Here is the transcription/description:\n\n{extracted_text}\n\nSolve this problem or answer the user's implicit question step-by-step."

        final_answer = await asyncio.to_thread(call_deepseek_reasoner, reasoning_prompt)

        # 4. Final Reply
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, message_id=status_msg.message_id
        )
        await update.message.reply_text(
            f"**Transcription:**\n_{extracted_text[:200]}..._\n\n**Solution:**\n{final_answer}",
            parse_mode="Markdown",
        )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"⚠️ Error: {str(e)}",
        )


def call_grok_vision(base64_img, prompt):
    if not XAI_API_KEY:
        return "Error: XAI_API_KEY missing."

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "grok-4-1-fast-non-reasoning",  # Optimized for fast vision/description
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                    },
                ],
            }
        ],
        "stream": False,
        "temperature": 0.01,
    }
    payload = {
        "model": "grok-vision-beta",  # Or grok-2-vision-1212 if available
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                    },
                ],
            }
        ],
        "stream": False,
        "temperature": 0.01,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"Grok Error: {resp.text}")
    except Exception as e:
        print(f"Grok Exception: {e}")
    return None


def call_deepseek_reasoner(prompt):
    if not DEEPSEEK_API_KEY:
        return "Error: DEEPSEEK_API_KEY missing."

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-reasoner",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"DeepSeek Error: {resp.text}")
    except Exception as e:
        print(f"DeepSeek Exception: {e}")
    return "Failed to get reasoning."
