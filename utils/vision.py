import os
import requests
import base64
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import asyncio

# Config
XAI_API_KEY = os.getenv("XAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


async def process_image_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1. Download Photo
    2. Send to Vision AI -> Get Description/Problem Text
    3. Send to Reasoner AI -> Solve
    4. Reply
    """
    user = update.effective_user
    status_msg = await update.message.reply_text("👀 Mimi is analyzing your image...")

    try:
        # 1. Determine Photo Source
        photo_obj = None
        if update.message.photo:
            photo_obj = update.message.photo[-1]
        elif update.message.reply_to_message and update.message.reply_to_message.photo:
            photo_obj = update.message.reply_to_message.photo[-1]

        if not photo_obj:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="❌ No image found to process.",
            )
            return

        # Download Image
        photo_file = await photo_obj.get_file()
        img_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        # 2. Vision (Opaque)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="🧠 Processing visual data...",
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

        # 3. Reasoning (Opaque)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="🤔 Mimi is thinking...",
        )

        reasoning_prompt = f"The user uploaded an image. Here is the transcription/description:\n\n{extracted_text}\n\nSolve this problem or answer the user's implicit question step-by-step."

        final_answer = await asyncio.to_thread(call_deepseek_reasoner, reasoning_prompt)

        # 4. Final Reply
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, message_id=status_msg.message_id
        )

        await update.message.reply_text(f"{final_answer}", parse_mode="Markdown")

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

    # Try the requested fast model first, fallback to stable
    models_to_try = ["grok-4-1-fast-non-reasoning", "grok-2-vision-1212"]

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_img}"
                            },
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
        except:
            continue

    return None


def call_deepseek_reasoner(prompt):
    if not OPENROUTER_API_KEY:
        return "Error: OPENROUTER_API_KEY missing."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }
    payload = {
        "model": "deepseek/deepseek-r1",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return "Failed to get reasoning."
