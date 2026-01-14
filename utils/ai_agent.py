import os
import httpx
import json
import asyncio
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
from utils import firebase_db, memory_sync, tools, validator

load_dotenv()
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = "deepseek/deepseek-chat"  # Switched to V3 for stability
KL_TZ = pytz.timezone("Asia/Kuala_Lumpur")

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for current information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Read content from a URL (HTML/PDF).",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "perform_memory_search",
            "description": "Deep search in long-term memory archive.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_memory",
            "description": "Save a new permanent memory about the user or self.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["Mimi", "Kuumin", "Events", "Others"],
                    },
                },
                "required": ["content"],
            },
        },
    },
]


def build_system_prompt(user_name):
    identity = memory_sync.get_identity_narrative()
    now = datetime.now(KL_TZ)

    constraints = (
        "CONSTRAINTS:\n"
        "1. PLAIN TEXT ONLY: No markdown, no HTML, no bold, no italics, no code blocks.\n"
        "2. NO EMOJIS: Absolutely zero emojis.\n"
        "3. FORMAT: Strictly one short paragraph of pure dialogue/prose. No lists or bullet points.\n"
        "4. TONE: Calm, minimalist, and grounded. Write like a character in a novel, not a chatbot.\n"
    )

    return (
        f"IDENTITY:\n{identity}\n\n"
        f"CONTEXT:\nTime: {now.strftime('%H:%M %A, %Y-%m-%d')}\n"
        f"User: {user_name}\n\n"
        f"{constraints}"
    )


async def execute_tool(name, args):
    if name == "web_search":
        return tools.web_search(args.get("query"))
    elif name == "web_fetch":
        return tools.web_fetch(args.get("url"))
    elif name == "perform_memory_search":
        return tools.perform_memory_search(args.get("query"))
    elif name == "add_memory":
        return tools.execute_add_memory(
            args.get("content"), args.get("category", "Mimi")
        )
    return "Error: Unknown tool."


async def stream_ai_response(update, context, status_msg, user_message):
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Student"

    # 1. Prepare Context
    system_prompt = build_system_prompt(user_name)
    reminiscence = memory_sync.get_proactive_reminiscence(user_message)

    if reminiscence:
        system_prompt += f"\n\n{reminiscence}"

    # Load recent history
    history = firebase_db.get_recent_context(telegram_id, limit=8)
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append(
            {"role": h.get("role", "user"), "content": h.get("content", "")}
        )
    messages.append({"role": "user", "content": user_message})

    # 2. API Call Loop (Max 2 turns)
    final_response = ""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://notespasumbot.com",
        "X-Title": "NotesPASUMBot",
    }

    current_turn = 0
    max_turns = 2

    while current_turn <= max_turns:
        payload = {
            "model": CHAT_MODEL,
            "messages": messages,
            "tools": TOOLS_SCHEMA,
            "stream": True,
            "temperature": 0.4,
        }

        buffer = ""
        tool_calls = []
        current_tool_id = None
        current_tool_name = None
        current_tool_args = ""

        is_thinking = False
        thinking_buffer = ""

        # UI State
        last_ui_update = 0

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        await status_msg.edit_text(
                            f"Brain Error: {response.status_code}"
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})

                            # Reasoning
                            reasoning = delta.get("reasoning_content")
                            if reasoning:
                                is_thinking = True
                                thinking_buffer += reasoning
                                now = asyncio.get_event_loop().time()
                                if now - last_ui_update > 2.0:
                                    await status_msg.edit_text(
                                        f"🧠 Thinking... ({len(thinking_buffer) // 10} tokens)"
                                    )
                                    last_ui_update = now
                                continue

                            # Content
                            content = delta.get("content")
                            if content:
                                if is_thinking:
                                    is_thinking = False
                                    await status_msg.edit_text("💡")
                                buffer += content
                                # Update UI for content
                                now = asyncio.get_event_loop().time()
                                if now - last_ui_update > 1.5:
                                    clean = tools.memory_sync.mimi_embeddings.os.path.basename  # access clean_output? no, need to import it
                                    # Just basic cleaning for stream
                                    await status_msg.edit_text(buffer + "▌")
                                    last_ui_update = now

                            # Tools
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    if "id" in tc:
                                        if current_tool_id:
                                            # Push previous
                                            tool_calls.append(
                                                {
                                                    "id": current_tool_id,
                                                    "type": "function",
                                                    "function": {
                                                        "name": current_tool_name,
                                                        "arguments": current_tool_args,
                                                    },
                                                }
                                            )
                                        current_tool_id = tc["id"]
                                        current_tool_name = tc["function"]["name"]
                                        current_tool_args = ""

                                    if (
                                        "function" in tc
                                        and "arguments" in tc["function"]
                                    ):
                                        current_tool_args += tc["function"]["arguments"]

                        except Exception:
                            pass

                    # Flush last tool
                    if current_tool_id:
                        tool_calls.append(
                            {
                                "id": current_tool_id,
                                "type": "function",
                                "function": {
                                    "name": current_tool_name,
                                    "arguments": current_tool_args,
                                },
                            }
                        )

        except Exception as e:
            logger.error(f"Stream error: {e}")
            await status_msg.edit_text("Connection glitch.")
            return

        # Handle Results
        if tool_calls:
            # Append Assistant Message with Tool Calls
            messages.append(
                {
                    "role": "assistant",
                    "content": buffer if buffer else None,
                    "tool_calls": tool_calls,
                }
            )

            # Execute Tools
            await status_msg.edit_text("⚙️ Working...")
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                    result = await execute_tool(fn_name, args)
                except Exception as e:
                    result = f"Error: {e}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn_name,
                        "content": str(result),
                    }
                )

            current_turn += 1
            continue  # Loop again

        else:
            # Done
            final_response = buffer
            break

    # Final Cleanup
    from utils import ai_tutor  # reuse clean_output

    cleaned = ai_tutor.clean_output(final_response)

        if cleaned:
            await status_msg.edit_text(cleaned)
        # Log
        firebase_db.prune_conversation(telegram_id)
        firebase_db.log_conversation(telegram_id, "user", user_message)
        firebase_db.log_conversation(telegram_id, "assistant", cleaned)

        # Async Sync Check
        # memory_sync.sync_memories_to_firestore() # Trigger optionally
    else:
        await status_msg.edit_text("...")
