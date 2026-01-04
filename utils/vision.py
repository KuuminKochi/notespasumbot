import os
import requests
import base64
import json
import re
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from . import ai_tutor

# Config
XAI_API_KEY = os.getenv("XAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


async def process_image_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Analyzes images with Nemotron and solves with Reasoner or Chat (Streaming).
    """
    if not update.message:
        return

    status_msg = await update.message.reply_text("👀 Mimi is analyzing your image...")

    try:
        # 1. Determine Photo Source
        photo_obj = None
        if update.message.photo:
            photo_obj = update.message.photo[-1]
        elif update.message.reply_to_message and update.message.reply_to_message.photo:
            photo_obj = update.message.reply_to_message.photo[-1]

        if not photo_obj:
            await status_msg.edit_text("❌ No image found to process.")
            return

        # Download
        photo_file = await photo_obj.get_file()
        img_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        # 2. Vision Analysis
        await status_msg.edit_text("🧠 Processing visual data...")

        vision_prompt = """
        Describe this image exactly. If it is a math/science problem, transcribe all symbols and text.
        Output JSON: {"transcription": "...", "is_complex": true/false}
        Set is_complex to true if it requires deep reasoning or calculation.
        """

        vision_raw = await asyncio.to_thread(
            call_vision_ai, base64_image, vision_prompt
        )
        if not vision_raw:
            await status_msg.edit_text("❌ Failed to read image.")
            return

        # Parse Complexity
        try:
            clean_json = re.sub(r"```json\n|\n```", "", vision_raw).strip()
            v_data = json.loads(clean_json)
            extracted_text = v_data.get("transcription", vision_raw)
            is_complex = v_data.get("is_complex", False)
        except:
            extracted_text = vision_raw
            is_complex = any(
                word in vision_raw.lower()
                for word in ["solve", "calculate", "derive", "math"]
            )

        # 3. Decision
        action = "thinking" if is_complex else "analyzing"
        await status_msg.edit_text(f"🤔 Mimi is {action}...")

        model_id = "deepseek/deepseek-r1" if is_complex else "deepseek/deepseek-chat"
        reasoning_prompt = (
            f"Image Transcription: {extracted_text}\n\nPlease solve/answer this."
        )

        # 4. Stream Final Answer
        await ai_tutor.stream_ai_response(
            update, context, status_msg, reasoning_prompt, model_id
        )

    except Exception as e:
        try:
            await status_msg.edit_text(f"⚠️ Error: {str(e)}")
        except:
            pass


def call_vision_ai(base64_img, prompt):
    if not OPENROUTER_API_KEY:
        return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Try Nemotron Free
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
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
        "temperature": 0.1,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None
