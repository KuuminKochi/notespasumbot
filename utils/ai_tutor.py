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
CHAT_ENDPOINT = f"{BASE_URL}/chat/completions"
CHAT_MODEL = "xiaomi/mimo-v2-flash:free"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")

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
    return escape_html(text).strip()


def escape_html(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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

    history_chars = sum(len(m.get("content", "")) for m in history)
    print(f"DEBUG: History: {len(history)} messages, {history_chars} chars total")
    print(
        f"DEBUG: History content:\n"
        + "\n".join(
            [
                f"  [{m.get('role', '?')}] {m.get('content', '')[:50]}..."
                for m in history
            ]
        )
    )

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

    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": 0.5,
        "stream": True,
    }

    buffer = ""
    revealed_count = 0
    CHARS_PER_EDIT = 2
    EDIT_DELAY = 0.008

    try:
        print(f"DEBUG: Calling OpenRouter API (streaming) with model: {CHAT_MODEL}")
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                CHAT_ENDPOINT, headers=headers, json=payload, timeout=90, stream=True
            ),
        )

        print(f"DEBUG: API Response status: {response.status_code}")

        if response.status_code != 200:
            await status_msg.edit_text(f"API Error: {response.status_code}")
            return

        await status_msg.edit_text("▌")

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data = line_str[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                buffer += content
                                revealed_count += len(content)
                                visible_text = clean_output(buffer[:revealed_count])
                                await status_msg.edit_text(
                                    visible_text + "▌", parse_mode="HTML"
                                )
                                await asyncio.sleep(EDIT_DELAY)
                    except json.JSONDecodeError:
                        pass

        final = clean_output(buffer)

        if final:
            await status_msg.edit_text(final, parse_mode="HTML")
            print(f"DEBUG: Final response: {final[:100]}...")
        else:
            await status_msg.edit_text(
                "I couldn't generate a response. Please try again."
            )
            return

        print(f"DEBUG: Logging conversation for user {telegram_id}")
        prune_conversation(telegram_id)
        firebase_db.log_conversation(telegram_id, "user", user_message)
        firebase_db.log_conversation(telegram_id, "assistant", final)

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)}")


def generate_announcement_comment(announcement_text, user_memories):
    return ""
