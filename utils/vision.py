import os
import requests
import base64
import json
import re
import random
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from . import ai_tutor

# Config
XAI_API_KEY = os.getenv("XAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Splash text rotation to avoid repetition
last_splash_index = -1

SPLASH_TEXTS = [
    "Mimi is sharpening her pencils...",
    "Checking library archives...",
    "Mimi is adjusting her hibiscus flower...",
    "Consulting PASUM scrolls...",
    "Mimi is having a quick tea break while thinking...",
    "Optimizing brain cells...",
    "Scanning cosmic background radiation...",
    "Mimi is flipping through her notes...",
    "Analyzing molecular structure of this query...",
    "Mimi is doing some quick mental math...",
    "Let me put on my reading glasses...",
    "Mimi is zooming in on the details...",
    "Time to activate thinking cap...",
    "Channeling inner genius...",
    "Mimi is organizing her thoughts...",
    "Decoding the visual puzzle...",
    "Processing with maximum brain power...",
    "Mimi is cross-referencing her knowledge...",
    "Bringing analytical focus to bear...",
    "Mimi is doing a quick visual scan...",
    "Preparing to unleash insight...",
    "Mimi is summoning her academic expertise...",
    "Deep diving into this problem...",
]


async def process_image_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Analyzes images with Nemotron (with timeout) and solves with Reasoner or Chat (Streaming).
    """
    if not update.message:
        return

    # Rotate splash text to avoid repetition
    global last_splash_index
    last_splash_index = (last_splash_index + 1) % len(SPLASH_TEXTS)
    splash_text = SPLASH_TEXTS[last_splash_index]

    status_msg = await update.message.reply_text(f"👀 {splash_text}")

    try:
        # 1. Determine Photo Source
        photo_obj = None
        if update.message.photo:
            photo_obj = update.message.photo[-1]
        elif update.message.reply_to_message and update.message.reply_to_message.photo:
            photo_obj = update.message.reply_to_message.photo[-1]

        if not photo_obj:
            await status_msg.edit_text(
                "❌ No image found to process.", parse_mode="HTML"
            )
            return

        # Download
        photo_file = await photo_obj.get_file()
        img_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        # 2. Vision Analysis
        await status_msg.edit_text(
            f"🧠 {random.choice(SPLASH_TEXTS)}", parse_mode="HTML"
        )

        vision_prompt = """
        Describe this image exactly. If it is a math/science problem, transcribe all symbols and text.
        Output JSON: {"transcription": "...", "is_complex": true/false}
        Set is_complex to true if it requires deep reasoning or calculation.
        """

        # Call vision with 30s timeout
        vision_raw = await asyncio.to_thread(
            call_vision_ai, base64_image, vision_prompt
        )
        if not vision_raw:
            await status_msg.edit_text(
                "❌ Mimi got a bit distracted (Vision Timeout).", parse_mode="HTML"
            )
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
        await status_msg.edit_text(
            f"🤔 {random.choice(SPLASH_TEXTS)}", parse_mode="HTML"
        )

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
            await status_msg.edit_text(f"⚠️ Error: {str(e)}", parse_mode="HTML")
        except:
            pass


def call_vision_ai(base64_img, prompt):
    if not OPENROUTER_API_KEY:
        return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }

    # Nemotron Free with timeout
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
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"ERROR: Vision API returned status {resp.status_code}")
            print(f"Response body: {resp.text[:500]}")
            return None
    except requests.Timeout:
        print("ERROR: Vision API timeout after 35s")
        return None
    except Exception as e:
        print(f"ERROR: Vision API exception: {e}")
        return None
    return None
