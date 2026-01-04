import requests
import json
import os
import datetime
from . import firebase_db

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"


def extract_memories(user_id, user_text, assistant_text):
    """
    Extracts new facts and Mimi's self-reflections.
    Triggers compression if limit is exceeded.
    """
    if not OPENROUTER_API_KEY:
        return

    prompt = f"""
    Analyze this conversation turn.
    User: "{user_text}"
    Mimi: "{assistant_text}"

    Extract NEW, UNIQUE facts/traits into:
    1. "user_facts": Facts about the student.
    2. "mimi_reflections": Mimi's own growth/feelings about the relationship.

    Only extract if truly new and significant.
    Output JSON: {{"user_facts": [], "mimi_reflections": []}}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }

    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=25
        )
        if response.status_code == 200:
            data = json.loads(response.json()["choices"][0]["message"]["content"])

            # 1. Save User Facts
            for m in data.get("user_facts", []):
                firebase_db.save_memory(user_id, m, category="User")

            # 2. Save Mimi Reflections
            for m in data.get("mimi_reflections", []):
                firebase_db.save_memory(user_id, m, category="Mimi")

            # 3. Trigger Compression Check
            check_and_compress(user_id, "User")
            check_and_compress(user_id, "Mimi")

            # 4. Trigger profiling
            check_and_update_profile(user_id)

    except Exception as e:
        print(f"Memory extraction failed: {e}")


def check_and_compress(user_id, category):
    """
    If memories exceed 16, compress them into high-density insights.
    """
    # We fetch ALL memories for this category
    memories = firebase_db.get_user_memories(user_id, category=category, limit=50)

    if len(memories) <= 16:
        return

    print(f"📦 Compressing {len(memories)} {category} memories for {user_id}...")

    memory_list = [m.get("content") for m in memories]

    prompt = f"""
    The following are memories for the category: {category}.
    They are becoming redundant/bloated. 
    Compress these into exactly 8-10 high-density, unique, and significant insights.
    Wipe out trivial or repeating info. Keep only the core essence.

    Memories:
    {json.dumps(memory_list)}

    Output JSON: {{"compressed": ["Insight 1", "Insight 2"]}}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=40
        )
        if resp.status_code == 200:
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            new_memories = data.get("compressed", [])

            if new_memories:
                # WIPE OLD
                firebase_db.clear_user_memories(user_id, category=category)
                # SAVE NEW
                for m in new_memories:
                    firebase_db.save_memory(user_id, m, category=category)
                print(f"✅ Compression successful for {category}")
    except Exception as e:
        print(f"Compression error: {e}")


def check_and_update_profile(user_id):
    memories = firebase_db.get_user_memories(user_id, category="User", limit=20)
    if len(memories) < 3:
        return

    # Check if we should update (limit frequency)
    user_data = firebase_db.get_user_profile(user_id)
    last_update = user_data.get("last_profile_update") if user_data else None

    # Update only if 24 hours passed or no profile exists
    if last_update:
        if isinstance(last_update, str):  # Handle string if iso
            last_update = datetime.datetime.fromisoformat(last_update)

        diff = datetime.datetime.now() - last_update
        if diff.total_seconds() < 86400:  # 24 hours
            return

    generate_psych_profile(user_id, memories)


def generate_psych_profile(user_id, memories):
    if not OPENROUTER_API_KEY:
        return
    user_data = firebase_db.get_user_profile(user_id)
    user_name = user_data.get("name", "Student") if user_data else "Student"
    memory_text = "\n".join([f"- {m.get('content')}" for m in memories])

    prompt = f"""
    Analyze student {user_name} based on these memories:
    {memory_text}

    Provide:
    1. Psychological profile summary.
    2. Tags.
    Output JSON: {{"profile": "...", "tags": []}}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=35
        )
        if resp.status_code == 200:
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            firebase_db.create_or_update_user(
                user_id,
                {
                    "psych_profile": data.get("profile"),
                    "profile_tags": data.get("tags", []),
                    "last_profile_update": datetime.datetime.now(),
                },
            )
    except Exception as e:
        print(f"Profiling error: {e}")
