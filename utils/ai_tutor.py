import os
import requests
import json
from . import firebase_db
from datetime import datetime
from dotenv import load_dotenv
import pytz
import re

load_dotenv()

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")

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
    now = datetime.now(KL_TZ)
    persona = persona.replace("{{user}}", user_name)
    persona = persona.replace("{{current_date}}", now.strftime("%Y-%m-%d"))
    persona = persona.replace("{{current_time}}", now.strftime("%H:%M"))

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

    # 5. Get History (Conversational Context)
    history = firebase_db.get_recent_context(telegram_id, limit=8)

    # 6. Build Messages & DEDUPLICATE (Fix for "Amnesia"/Race Condition)
    messages = [{"role": "system", "content": system_content}]

    for msg in history:
        content = msg["content"]
        # Add timestamp context if available
        if "timestamp" in msg:
            try:
                ts = msg["timestamp"]
                # Handle Firestore datetime object or string
                if hasattr(ts, "strftime"):
                    time_str = ts.strftime("%H:%M")
                else:
                    # If it's a string, try to parse or just use as is if simple
                    time_str = str(ts)[11:16]  # Crude slice if ISO string, fallback
                content = f"[{time_str}] {content}"
            except:
                pass

        messages.append({"role": msg["role"], "content": content})

    # Check if the last message in history is the same as current user_message
    # If it is, we don't append it again. If it's missing (DB lag), we append it.
    # We compare original content, not timestamped content for deduplication safety
    if not history or history[-1]["content"] != user_message:
        now_kl = datetime.now(KL_TZ)
        time_tag = now_kl.strftime("%H:%M")
        print(f"DEBUG: Appending user message with time [{time_tag}]")
        messages.append(
            {
                "role": "user",
                "content": f"[{time_tag}] {user_message}",
            }
        )

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

            # Clean up timestamps from AI response if it hallucinates them
            # Matches [12:30] or [12:30] [12:30] at start
            ai_text = re.sub(r"^(\[\d{2}:\d{2}\]\s*)+", "", ai_text).strip()

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


def generate_announcement_comment(announcement_text, user_memories):
    """
    Generates a short, personalized PS for an announcement.
    """
    if not DEEPSEEK_API_KEY:
        return ""

    memories_text = "\n".join([f"- {m.get('content')}" for m in user_memories])

    prompt = f"""
    Context: I am sending a broadcast announcement to a student.
    Announcement: "{announcement_text}"
    
    Student Memories:
    {memories_text}
    
    Task: Write a very short (1 sentence), friendly, witty comment that connects the announcement to the student's specific memories/goals. 
    If no relevant memories exist, return nothing (empty string).
    Do not repeat the announcement. Just the personal comment.
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 60,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=10
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except:
        pass
    return ""
