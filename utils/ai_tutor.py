import os
import requests
import json
from . import firebase_db
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"

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
    Generates a response using Deepseek V3.2.
    Architecture: [Global Rules] + [Persona] + [Categorized Memories] + [History]
    """
    if not DEEPSEEK_API_KEY:
        return "⚠️ Error: Deepseek API Key not configured."

    # 1. Load Prompts
    global_rules = load_file(GLOBAL_PROMPT_FILE)
    persona = load_file(PERSONA_PROMPT_FILE)

    # 2. Dynamic Template Replacement
    persona = persona.replace("{{user}}", user_name)
    persona = persona.replace("{{current_date}}", datetime.now().strftime("%Y-%m-%d"))

    # 3. Get Categorized Memories (Rigorously separated)
    user_memories = firebase_db.get_user_memories(
        telegram_id, category="User", limit=15
    )
    mimi_memories = firebase_db.get_user_memories(
        telegram_id, category="Mimi", limit=10
    )

    memory_block = ""
    if user_memories:
        memory_block += (
            f"\n\n**What I know about {user_name} (Permanent History):**\n"
            + "\n".join([f"- {m.get('content')}" for m in user_memories])
        )

    if mimi_memories:
        memory_block += (
            f"\n\n**Mimi's Self-Reflections (My evolution with {user_name}):**\n"
            + "\n".join([f"- {m.get('content')}" for m in mimi_memories])
        )

    # 4. Construct Final System Prompt
    system_content = f"{global_rules}\n\n---\n\n{persona}{memory_block}\n\nNote: Always prioritize the User's well-being and academic growth."

    # 5. Get History (Conversational Context)
    history = firebase_db.get_recent_context(telegram_id, limit=8)

    # 6. Build Messages
    messages = [{"role": "system", "content": system_content}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    # 7. Pre-log user message to ensure history continuity (Memory Fix)
    try:
        firebase_db.log_conversation(telegram_id, "user", user_message)
    except Exception as e:
        print(f"Failed to log user message: {e}")

    # 8. API Call
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1200,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30
        )
        if response.status_code == 200:
            ai_text = response.json()["choices"][0]["message"]["content"]

            # Log assistant response
            try:
                firebase_db.log_conversation(telegram_id, "assistant", ai_text)
            except Exception as e:
                print(f"Failed to log AI message: {e}")

            return ai_text
        else:
            return f"Error from AI: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"
