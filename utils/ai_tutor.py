import os
import requests
import json
import pytz
import re
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from . import firebase_db, concurrency

load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")

# Model Selection
CHAT_MODEL = "xiaomi/mimo-v2-flash:free"
FALLBACK_MODEL = "deepseek/deepseek-chat"
REASONER_MODEL = "deepseek/deepseek-r1"

# Prompt Paths
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
GLOBAL_PROMPT_FILE = os.path.join(PROMPTS_DIR, "global_grounding.md")
PERSONA_PROMPT_FILE = os.path.join(PROMPTS_DIR, "system_prompt.md")


def load_file(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            pass
    return ""


async def stream_ai_response(update, context, status_msg, user_message, model_id=None):
    """
    Streams AI response to Telegram using HTML mode.
    Memory system disabled for refactoring.
    """
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Student"

    # 1. Setup Context (no memories)
    global_rules = load_file(GLOBAL_PROMPT_FILE)
    persona = load_file(PERSONA_PROMPT_FILE)
    now = datetime.now(KL_TZ)
    persona = (
        persona.replace("{{user}}", user_name)
        .replace("{{current_date}}", now.strftime("%Y-%m-%d"))
        .replace("{{current_time}}", now.strftime("%H:%M"))
    )

    # System instruction with no-links rule
    persona_instruction = (
        "\n\nCRITICAL RULES:\n"
        "1. NEVER embed any links, URLs, or web addresses - explain concepts in your own words\n"
        "2. Use HTML tags for formatting: <i>italics</i>, <b>bold</b>, <code>code</code>\n"
        "3. NEVER use Markdown (* or _)\n"
    )

    # No memory block - system content is clean
    system_content = f"{global_rules}\n\n{persona}\n\n{persona_instruction}"

    history = firebase_db.get_recent_context(telegram_id, limit=5)

    messages = [{"role": "system", "content": system_content}]
    for msg in history:
        content = msg["content"]
        if "timestamp" in msg and hasattr(msg["timestamp"], "astimezone"):
            time_str = msg["timestamp"].astimezone(KL_TZ).strftime("%H:%M")
            content = f"[{time_str}] {content}"
        messages.append({"role": msg["role"], "content": content})

    messages.append(
        {"role": "user", "content": f"[{now.strftime('%H:%M')}] {user_message}"}
    )

    # 2. Call API
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }
    target_model = model_id or CHAT_MODEL
    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.5,
        "stream": True,
    }

    full_text = ""
    last_edit_time = 0
    update_interval = 1.2

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            concurrency.get_pool(),
            lambda: requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=90,
            ),
        )

        if response.status_code != 200:
            if target_model == CHAT_MODEL:
                return await stream_ai_response(
                    update, context, status_msg, user_message, FALLBACK_MODEL
                )
            await status_msg.edit_text(
                f"API Error: {response.status_code}", parse_mode="HTML"
            )
            return

        for line in response.iter_lines():
            if line:
                line_text = line.decode("utf-8")
                if line_text.startswith("data: "):
                    data_str = line_text[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        full_text += content

                        if time.time() - last_edit_time > update_interval:
                            clean_text = re.sub(
                                r"^(\[\d{2}:\d{2}\]\s*)+", "", full_text
                            ).strip()
                            if clean_text:
                                try:
                                    await status_msg.edit_text(
                                        clean_text + " ▌", parse_mode="HTML"
                                    )
                                    last_edit_time = time.time()
                                except:
                                    pass
                    except:
                        pass

        final_text = re.sub(r"^(\[\d{2}:\d{2}\]\s*)+", "", full_text).strip()

        # Safety Net: Strip ALL URLs to prevent link spamming
        final_text = re.sub(r"http[s]?://\S+", "[Link Removed]", final_text)
        final_text = re.sub(r"\[.+\]\(.+\)", "[Link Removed]", final_text)
        final_text = re.sub(r"www\.\S+", "[Link Removed]", final_text)
        final_text = re.sub(
            r"\.com\S*|\.org\S*|\.edu\S*|\.gov\S*|\.net\S*|\.io\S*",
            "[Link Removed]",
            final_text,
        )
        final_text = re.sub(r"\s+\.\s+com\s*", " [Link Removed] ", final_text)
        final_text = re.sub(r"\s+\(dot\)\s+", " [Link Removed] ", final_text)
        final_text = re.sub(r"\s+\(\s*\.\s*\)\s+", " [Link Removed] ", final_text)
        final_text = re.sub(
            r"(?i)gmail\.com|yahoo\.com|outlook\.com|hotmail\.com",
            "[Email Removed]",
            final_text,
        )
        final_text = re.sub(
            r"(?i)wikipedia\.org|khanacademy\.org|youtube\.com",
            "[Link Removed]",
            final_text,
        )

        if not final_text:
            final_text = "I'm sorry, I couldn't generate a response."

        await status_msg.edit_text(final_text, parse_mode="HTML")

        firebase_db.log_conversation(telegram_id, "user", user_message)
        firebase_db.log_conversation(telegram_id, "assistant", final_text)

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}", parse_mode="HTML")


def get_ai_response(telegram_id, user_message, user_name="Student"):
    return "Error: Use streaming."


def generate_announcement_comment(announcement_text, user_memories):
    return ""
