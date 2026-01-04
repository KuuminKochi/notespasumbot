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

        # Vision API Call
        vision_response = await asyncio.to_thread(
            call_vision_ai, base64_image, vision_prompt
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


def call_vision_ai(base64_img, prompt):
    """
    Uses OpenRouter to analyze images.
    Default: nvidia/nemotron-nano-12b-v2-vl:free
    """
    if not OPENROUTER_API_KEY:
        return "Error: OPENROUTER_API_KEY missing."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }

    # Use Nemotron as default, with xAI as fallback
    models_to_try = ["nvidia/nemotron-nano-12b-v2-vl:free", "x-ai/grok-2-vision-1212"]

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
            "temperature": 0.1,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                res_json = resp.json()
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    return res_json["choices"][0]["message"]["content"]
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

    # Try DeepSeek Reasoner first, then Mimo as fallback
    models = ["deepseek/deepseek-r1", "xiaomi/mimo-v2-flash"]

    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                res_json = resp.json()
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    return res_json["choices"][0]["message"]["content"]
        except:
            continue

    return "Failed to get reasoning after trying fallback."
