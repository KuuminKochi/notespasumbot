import os
import requests
import json
import pytz
import re
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from . import firebase_db

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")
CHAT_MODEL = "xiaomi/mimo-v2-flash:free"

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


def build_system_prompt(user_name="Student"):
    global_rules = load_file(GLOBAL_PROMPT_FILE)
    persona = load_file(PERSONA_PROMPT_FILE)

    now = datetime.now(KL_TZ)
    time_context = f"Current: {now.strftime('%H:%M')} | {now.strftime('%A')}"

    no_links = (
        "ABSOLUTE PRIORITY: NEVER output links/URLs/web addresses.\n"
        "Explain concepts yourself. No http://, https://, www., markdown links.\n"
    )

    persona = persona.replace("{{user}}", user_name)
    persona = persona.replace("{{current_date}}", now.strftime("%Y-%m-%d"))
    persona = persona.replace("{{current_time}}", now.strftime("%H:%M"))

    format_note = "\nUse HTML: <b>bold</b>, <i>italics</i>, <code>code</code>"

    return f"{no_links}\n{time_context}\n\n{global_rules}\n\n{persona}\n\n{format_note}"


def clean_output(text):
    patterns = [
        (r"https?://\S+", "[Link Removed]"),
        (r"\[.+?\]\(.+?\)", "[Link Removed]"),
        (r"www\.\S+", "[Link Removed]"),
        (r"\.(com|org|edu|gov|net|io)\S*", "[Link Removed]"),
        (r"(?i)khanacademy\.org", "[Link Removed]"),
        (r"(?i)wikipedia\.org", "[Link Removed]"),
        (r"(?i)youtube\.com", "[Link Removed]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text.strip()


def get_sliding_window_context(telegram_id, limit=10):
    context = firebase_db.get_recent_context(telegram_id, limit=limit)
    formatted = []
    for msg in context:
        content = msg.get("content", "")
        if "timestamp" in msg:
            try:
                ts = msg["timestamp"]
                if hasattr(ts, "astimezone"):
                    time_str = ts.astimezone(KL_TZ).strftime("%H:%M")
                    content = f"[{time_str}] {content}"
            except:
                pass
        formatted.append({"role": msg.get("role", "user"), "content": content})
    return formatted


def prune_conversation(telegram_id):
    firebase_db.prune_conversation(telegram_id, max_messages=50, delete_count=25)


async def stream_ai_response(update, context, status_msg, user_message):
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Student"

    system_content = build_system_prompt(user_name)
    history = get_sliding_window_context(telegram_id, limit=10)

    messages = [{"role": "system", "content": system_content}]
    messages.extend(history)

    now = datetime.now(KL_TZ)
    messages.append(
        {"role": "user", "content": f"[{now.strftime('%H:%M')}] {user_message}"}
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }

    payload = {"model": CHAT_MODEL, "messages": messages, "temperature": 0.5}

    full_text = ""
    last_update = 0
    update_interval = 1.0

    try:
        print(f"DEBUG: Calling OpenRouter API with model: {CHAT_MODEL}")
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(BASE_URL, headers=headers, json=payload, timeout=90),
        )

        print(f"DEBUG: API Response status: {response.status_code}")
        print(f"DEBUG: API Response body: {response.text[:500]}")

        if response.status_code != 200:
            await status_msg.edit_text(f"API Error: {response.status_code}")
            return

        try:
            data = response.json()
            print(f"DEBUG: Parsed JSON: {json.dumps(data)[:500]}")
            if "choices" in data and len(data["choices"]) > 0:
                full_text = data["choices"][0]["message"].get("content", "")
            else:
                full_text = ""
                print("DEBUG: No choices in response")
        except json.JSONDecodeError as e:
            print(f"DEBUG: JSON decode error: {e}")
            full_text = ""

        if full_text:
            final = clean_output(full_text)
            await status_msg.edit_text(final, parse_mode="HTML")
            prune_conversation(telegram_id)
            firebase_db.log_conversation(telegram_id, "user", user_message)
            firebase_db.log_conversation(telegram_id, "assistant", final)
        else:
            await status_msg.edit_text(
                "I couldn't generate a response. Please try again."
            )

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")


def generate_announcement_comment(announcement_text, user_memories):
    return ""
