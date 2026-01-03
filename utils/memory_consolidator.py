import requests
import json
import os
import datetime
from . import firebase_db

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"


def extract_memories(user_id, user_text, assistant_text):
    """
    Uses Deepseek to extract new facts or preferences from a conversation turn.
    Rigorously separates facts about the student from facts about Mimi's own evolution.
    """
    if not DEEPSEEK_API_KEY:
        return

    prompt = f"""
Analyze this conversation turn between a student (User) and Mimi (AI Tutor).
User: "{user_text}"
Assistant: "{assistant_text}"

Extract any NEW information into two distinct categories:
1. "user_facts": Facts about the student (e.g., academic struggles, goals, learning style, personal details).
2. "mimi_reflections": Observations about Mimi's own behavior, evolution, or relationship with this user (AI self-reflection).

Output JSON: {{"user_facts": ["Fact 1"], "mimi_reflections": ["Reflection 1"]}}
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=20
        )
        if response.status_code == 200:
            data = json.loads(response.json()["choices"][0]["message"]["content"])

            # Save User Facts
            for m in data.get("user_facts", []):
                firebase_db.save_memory(user_id, m, category="User")

            # Save Mimi Reflections
            for m in data.get("mimi_reflections", []):
                firebase_db.save_memory(user_id, m, category="Mimi")

            # Trigger profiling only based on User data
            check_and_update_profile(user_id)

    except Exception as e:
        print(f"Memory extraction failed: {e}")


def check_and_update_profile(user_id):
    """
    Periodically generates a psych/character profile based on User-specific memories.
    """
    memories = firebase_db.get_user_memories(user_id, category="User", limit=40)
    if len(memories) < 3:
        return

    generate_psych_profile(user_id, memories)


def generate_psych_profile(user_id, memories):
    """
    Generates a deep character/psych profile exclusively for the student.
    """
    if not DEEPSEEK_API_KEY:
        return

    # Fetch user name for the prompt
    user_data = firebase_db.get_user_profile(user_id)
    user_name = user_data.get("name", "Student") if user_data else "Student"

    memory_text = "\n".join([f"- {m.get('content')}" for m in memories])

    prompt = f"""
As an expert psychologist, analyze the following memories of a student named {user_name}.
IMPORTANT: Do NOT confuse the student with the AI (Mimi). Focus ONLY on the student's traits.

Analyze these memories to capture:
1. Cognitive Style (how the student thinks/learns)
2. Student Motivations & Goals
3. Student's Emotional Baseline
4. "The Core Paradox" (a one-sentence summary of the STUDENT'S internal complexity)

Student Memories:
{memory_text}

Output JSON: {{"profile": "Full profile text here", "tags": ["tag1", "tag2"]}}
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30
        )
        if response.status_code == 200:
            data = json.loads(response.json()["choices"][0]["message"]["content"])
            profile_text = data.get("profile")
            tags = data.get("tags", [])

            firebase_db.create_or_update_user(
                user_id,
                {
                    "psych_profile": profile_text,
                    "profile_tags": tags,
                    "last_profile_update": datetime.datetime.now(),
                },
            )
    except Exception as e:
        print(f"Profiling error: {e}")
