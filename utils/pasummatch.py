from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from utils import globals, firebase_db
import os
import random
import requests
import json
import asyncio

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = os.getenv("CHAT_MODEL", "xiaomi/mimo-v2-flash:free")


async def track_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track users in group (Legacy support)."""
    chat = update.effective_chat
    user = update.effective_user
    NOTES_PASUM = int(os.getenv("NOTES_PASUM", 0))

    if chat and chat.id == NOTES_PASUM and user:
        display_name = f"@{user.username}" if user.username else user.full_name
        globals.active_users.add((user.id, display_name))


async def pasum_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends AI-Powered PASUM matches based on Psych Profiles."""
    user = update.effective_user

    await update.message.reply_text(
        "🪄 Mimi is analyzing the PASUM ecosystem to find your perfect study partners... (this takes a moment)"
    )

    # 1. Fetch current user profile
    my_profile = firebase_db.get_user_profile(user.id)
    my_profile_text = (
        my_profile.get("psych_profile", "A motivated PASUM student.")
        if my_profile
        else "A motivated PASUM student."
    )

    # 2. Fetch potential matches from Firebase
    all_profiles = firebase_db.get_all_user_profiles(limit=20)

    # Filter out self and people without names
    pool = [
        p
        for p in all_profiles
        if p["id"] != str(user.id) and (p.get("name") or p.get("username"))
    ]

    if not pool:
        await update.message.reply_text(
            "The student database is still growing! I couldn't find anyone else to match you with yet. 🥲"
        )
        return

    # Select 5 random candidates
    candidates = random.sample(pool, min(5, len(pool)))

    # 3. Use OpenRouter to calculate compatibility
    match_data = []
    for c in candidates:
        match_data.append(
            {
                "name": c.get("name") or f"@{c.get('username')}",
                "profile": c.get("psych_profile", "A fellow learner."),
            }
        )

    prompt = f"""
As Mimi, AI Tutor, calculate "Study Chemistry" between a User and 5 potential study partners.
User Profile: "{my_profile_text}"

Candidates:
{json.dumps(match_data, indent=2)}

For each candidate, provide:
1. Compatibility Score (0-100)
2. A witty, senior-student-style comment explaining WHY they match (based on their learning styles, goals, or character traits).

Output JSON Format:
{{
  "matches": [
    {{"name": "Name", "score": 85, "comment": "Comment"}},
    ...
  ]
}}
"""

    # Check if API key is set
    if not OPENROUTER_API_KEY:
        await update.message.reply_text(
            "⚠️ OpenRouter API key not configured! Check .env file."
        )
        print(f"ERROR: OPENROUTER_API_KEY not set in pasummatch.py")
        return

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }

    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
    }

    try:
        print(f"DEBUG: Calling OpenRouter API with model: {CHAT_MODEL}")
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=40,
            ),
        )

        print(f"DEBUG: API Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"ERROR: API returned status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            await update.message.reply_text(
                f"⚠️ API Error (status {response.status_code}). Try again later!"
            )
            return

        results = json.loads(response.json()["choices"][0]["message"]["content"]).get(
            "matches", []
        )

        text = f"💘 **AI-Powered PASUM Matches for {user.first_name}** 💘\n\n"
        for m in results:
            score = m.get("score", 0)
            emoji = "🔥" if score > 80 else "🤝" if score > 50 else "📚"
            text += f"{emoji} **{m.get('name')}** = {score}%\n_{m.get('comment')}_\n\n"

        text += (
            "✨ <i>Matches are calculated based on your unique student profiles.</i>"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    except json.JSONDecodeError as e:
        print(f"ERROR: JSON decode error in pasummatch: {e}")
        print(f"Response content: {response.text[:500]}")
        await update.message.reply_text("⚠️ Failed to parse AI response. Try again!")
        return

    except Exception as e:
        print(f"ERROR: Unexpected error in pasummatch: {e}")
        print(f"Traceback: {type(e).__name__}: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)}. Please try later!")
