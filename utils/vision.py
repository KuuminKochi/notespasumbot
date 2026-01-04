import os
import requests
import base64
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import asyncio

# Config
XAI_API_KEY = os.getenv("XAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def call_deepseek_reasoner(prompt):
    if not OPENROUTER_API_KEY:
        return "Error: OPENROUTER_API_KEY missing."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
        "X-Title": "NotesPASUMBot",
    }
    payload = {
        "model": "deepseek/deepseek-r1",  # OpenRouter ID for Reasoner
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"OpenRouter Error: {resp.text}")
    except Exception as e:
        print(f"OpenRouter Exception: {e}")
    return "Failed to get reasoning."
