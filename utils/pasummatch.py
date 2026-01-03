from telegram import Update
from telegram.ext import (
    Application,
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

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"


async def track_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track users in the group (Legacy support)."""
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

    # 3. Use Deepseek to calculate compatibility
    match_data = []
    for c in candidates:
        match_data.append(
            {
                "name": c.get("name") or f"@{c.get('username')}",
                "profile": c.get("psych_profile", "A fellow learner."),
            }
        )

    prompt = f"""
As Mimi, the AI Tutor, calculate the 'Study Chemistry' between a User and 5 potential study partners.
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

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }

    try:
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

        if response.status_code == 200:
            results = json.loads(
                response.json()["choices"][0]["message"]["content"]
            ).get("matches", [])

            text = f"💘 **AI-Powered PASUM Matches for {user.first_name}** 💘\n\n"
            for m in results:
                score = m.get("score", 0)
                emoji = "🔥" if score > 80 else "🤝" if score > 50 else "📚"
                text += (
                    f"{emoji} **{m.get('name')}** = {score}%\n_{m.get('comment')}_\n\n"
                )

            text += "✨ _Matches are calculated based on your unique student profiles._"
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "Mimi's analytical engine hit a snag! Let's try again in a bit."
            )

    except Exception as e:
        print(f"Match error: {e}")
        await update.message.reply_text(
            "Connection to the matching engine failed. Please try later!"
        )
