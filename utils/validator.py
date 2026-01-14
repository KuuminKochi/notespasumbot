import os
import requests
import json
import logging
from utils import memory_sync

logger = logging.getLogger(__name__)


def validate_memory(content: str) -> str:
    """
    Validates a proposed memory using Mimo-v2-flash.
    Returns the final memory content if approved, or starts with 'REJECTED: ' if not.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "REJECTED: No API Key available."

    system_prompt = """You are the Memory Validator for Mimi (an AI agent). 
    Your goal is to ensure her Long-Term Memory remains healthy, factual, and growth-oriented.
    
    Rules for Acceptance:
    1. FACTUAL: User preferences, biographical details, or specific events.
    2. EMOTIONAL GROWTH: Significant shared moments or insights.
    
    Rules for Rejection/Refinement:
    1. NO TOXICITY: Reject hate speech or harmful content.
    2. NO DEFENSIVENESS: Reject memories like "User was mean, I must be careful." or "I need to protect myself." Mimi is resilient, not paranoid.
    3. NO TRIVIA: Reject "User said hi" or meaningless chatter.

    Output Format:
    - If valid: Return the clean memory text.
    - If valid but needs tone fix: Return the REFINED memory text.
    - If invalid: Return "REJECTED: [Reason]"
    """

    payload = {
        "model": "xiaomi/mimo-v2-flash:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Proposed Memory: {content}"},
        ],
        "temperature": 0.1,
        "max_tokens": 100,
    }

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=10,
        )
        if res.ok:
            result = res.json()["choices"][0]["message"]["content"].strip()
            return result
        else:
            logger.error(f"Validator API error: {res.text}")
            # Fallback: Allow if API fails but log it? No, fail safe.
            return "REJECTED: Validator API Error."
    except Exception as e:
        logger.error(f"Validator connection failed: {e}")
        return f"REJECTED: {e}"


def process_add_memory(content: str, user_id: int, category: str = "Mimi") -> str:
    """
    Pipeline: Validate -> Save
    """
    validation_result = validate_memory(content)

    if validation_result.startswith("REJECTED"):
        return f"❌ Memory rejected by validator: {validation_result.split(':', 1)[1]}"

    # Save the refined memory
    success = memory_sync.add_memory_to_archive(user_id, validation_result, category)
    if success:
        return f"✅ Memory saved: {validation_result}"
    else:
        return "❌ Failed to write memory to archive."
