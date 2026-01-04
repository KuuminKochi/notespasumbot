import os
import requests
import json
import pytz
import re
from datetime import datetime
from dotenv import load_dotenv
from . import firebase_db

load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")

# Model Selection (OpenRouter)
CHAT_MODEL = "deepseek/deepseek-chat"
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
        except Exception as e:
            print(f"Error reading {path}: {e}")
    return ""


def get_ai_response(telegram_id, user_message, user_name="Student"):
    """
    Generates a response using OpenRouter (DeepSeek).
    """
    if not OPENROUTER_API_KEY:
        return "⚠️ Error: OpenRouter API Key not configured."

    # 1. Load Prompts
    global_rules = load_file(GLOBAL_PROMPT_FILE)
    persona = load_file(PERSONA_PROMPT_FILE)

    # 2. Dynamic Template Replacement
    now = datetime.now(KL_TZ)
    persona = persona.replace("{{user}}", user_name)
    persona = persona.replace("{{current_date}}", now.strftime("%Y-%m-%d"))
    persona = persona.replace("{{current_time}}", now.strftime("%H:%M"))

    # 3. Get Memories (USER ONLY - Mimi reflections are deprecated)
    user_memories = firebase_db.get_user_memories(
        telegram_id, category="User", limit=15
    )

    memory_block = ""
    if user_memories:
        memory_block += f"\n\n**What I know about {user_name}:**\n" + "\n".join(
            [f"- {m.get('content')}" for m in user_memories]
        )

    # 4. Construct System Prompt
    system_content = f"{global_rules}\n\n---\n\n{persona}{memory_block}\n\nNote: Always prioritize well-being."

    # 5. Get History & Pre-log
    try:
        firebase_db.log_conversation(telegram_id, "user", user_message)
    except:
        pass

    history = firebase_db.get_recent_context(telegram_id, limit=10)

    # 6. Build Messages with Deduplication
    messages = [{"role": "system", "content": system_content}]
    for msg in history:
        content = msg["content"]
        if "timestamp" in msg and hasattr(msg["timestamp"], "astimezone"):
            time_str = msg["timestamp"].astimezone(KL_TZ).strftime("%H:%M")
            content = f"[{time_str}] {content}"
        messages.append({"role": msg["role"], "content": content})

    # Ensure current message is at the end if not in history
    if not history or history[-1]["content"] != user_message:
        messages.append(
            {"role": "user", "content": f"[{now.strftime('%H:%M')}] {user_message}"}
        )

    # 7. API Call
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
        "max_tokens": 1200,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=45
        )
        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json:
                ai_text = res_json["choices"][0]["message"]["content"]
                ai_text = re.sub(r"^(\[\d{2}:\d{2}\]\s*)+", "", ai_text).strip()
                firebase_db.log_conversation(telegram_id, "assistant", ai_text)
                return ai_text
            else:
                return f"AI Error: Received invalid response from provider: {res_json}"
        return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"


def generate_announcement_comment(announcement_text, user_memories):
    if not OPENROUTER_API_KEY:
        return ""
    memories_text = "\n".join([f"- {m.get('content')}" for m in user_memories])
    prompt = f"Announcement: {announcement_text}\nMemories: {memories_text}\nWrite a 1-sentence witty personal comment."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 60,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=15
        )
        if resp.status_code == 200:
            res_json = resp.json()
            if "choices" in res_json:
                return res_json["choices"][0]["message"]["content"].strip()
    except:
        pass
    return ""
