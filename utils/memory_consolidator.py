import requests
import json
import os
import datetime
import pytz
from . import firebase_db

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")


def extract_memories(user_id, user_text, assistant_text):
    """
    Extracts high-value facts about the USER only.
    """
    if not OPENROUTER_API_KEY:
        return

    prompt = f"""
    Analyze this conversation turn between a student and Mimi (AI Tutor).
    User: "{user_text}"
    Mimi: "{assistant_text}"

    Task: Extract only TRULY NEW and SIGNIFICANT facts about the STUDENT.
    Focus on: Academic struggles/strengths, Specific goals, Personal preferences.
    DO NOT extract anything about Mimi.

    Output JSON: {{"user_facts": ["Fact 1"]}}
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
            res_json = response.json()
            if "choices" in res_json:
                content = res_json["choices"][0]["message"]["content"]
                data = json.loads(content)
                new_facts = data.get("user_facts", [])
                for m in new_facts:
                    firebase_db.save_memory(user_id, m, category="User")

                if new_facts:
                    check_and_compress(user_id, "User")
                    check_and_update_profile(user_id)
            else:
                print(f"OpenRouter Error in extraction: {res_json}")
    except Exception as e:
        print(f"Memory extraction failed: {e}")


def check_and_compress(user_id, category):
    memories = firebase_db.get_user_memories(user_id, category=category, limit=50)
    if len(memories) <= 16:
        return

    print(f"📦 Compressing {len(memories)} {category} memories for {user_id}...")
    memory_list = [m.get("content") for m in memories]

    prompt = f'Compress these student memories into 8-10 high-density insights: {json.dumps(memory_list)}. Output JSON: {{"compressed": []}}'

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
            res_json = resp.json()
            if "choices" in res_json:
                data = json.loads(res_json["choices"][0]["message"]["content"])
                new_memories = data.get("compressed", [])
                if new_memories:
                    firebase_db.clear_user_memories(user_id, category=category)
                    for m in new_memories:
                        firebase_db.save_memory(user_id, m, category=category)
            else:
                print(f"OpenRouter Error in compression: {res_json}")
    except Exception as e:
        print(f"Compression error: {e}")


def check_and_update_profile(user_id):
    memories = firebase_db.get_user_memories(user_id, category="User", limit=20)
    if len(memories) < 3:
        return

    user_data = firebase_db.get_user_profile(user_id)
    last_update = user_data.get("last_profile_update") if user_data else None

    if last_update:
        # Fix: ensure comparison between offset-aware datetimes
        if not last_update.tzinfo:
            last_update = last_update.replace(tzinfo=datetime.timezone.utc)

        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - last_update
        if diff.total_seconds() < 86400:
            return

    generate_psych_profile(user_id, memories)


def generate_psych_profile(user_id, memories):
    if not OPENROUTER_API_KEY:
        return
    user_data = firebase_db.get_user_profile(user_id)
    user_name = user_data.get("name", "Student") if user_data else "Student"
    memory_text = "\n".join([f"- {m.get('content')}" for m in memories])

    prompt = f'Analyze student {user_name} based on: {memory_text}. Provide personality profile and tags. Output JSON: {{"profile": "...", "tags": []}}'

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
            res_json = resp.json()
            if "choices" in res_json:
                data = json.loads(res_json["choices"][0]["message"]["content"])
                firebase_db.create_or_update_user(
                    user_id,
                    {
                        "psych_profile": data.get("profile"),
                        "profile_tags": data.get("tags", []),
                        "last_profile_update": datetime.datetime.now(
                            datetime.timezone.utc
                        ),
                    },
                )
    except Exception as e:
        print(f"Profiling error: {e}")
