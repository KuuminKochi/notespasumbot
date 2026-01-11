# Memory Context Fixes

## Overview
Documenting the fixes for Mimi's conversation memory and streaming behavior.

## Issue 1: Context Not Being Used by AI

### Root Cause
The system prompt only vaguely mentioned "Use conversation context" (line 19 of global_grounding.md).
The model `xiaomi/mimo-v2-flash:free` is a small model with weak context following.

### Fix
Added a dedicated "Conversation Memory (Critical)" section in `prompts/system_prompt.md`:

```markdown
## Conversation Memory (Critical)

You are being provided with the full conversation history above.
READ IT CAREFULLY and use it to:

- **Remember what the user asked before** - Reference previous questions
- **Recall specific details the user mentioned** - Numbers, names, concepts, preferences
- **Maintain continuity** - Don't ask for information the user already gave
- **Build on previous answers** - Reference what you explained earlier

If the user asks "what did I say earlier" or "do you remember X", use the conversation history to answer accurately.

The timestamps [HH:MM] in messages show when each message was sent - use this for temporal context.

Examples of good memory usage:
- User: "Remember 2532" → You: "Got it! I'll remember 2532"
- User: "what was the first number?" → You: "You mentioned 2532 earlier"
- User: "explain that concept again" → You: refer back to your earlier explanation

**NEVER pretend to forget something the user told you in this conversation.**
```

### History Format
Messages are passed to the API in this format:
```json
[
  {"role": "system", "content": "You are Mimi..."},
  {"role": "user", "content": "[HH:MM] User message here"},
  {"role": "assistant", "content": "[HH:MM] Your response here"},
  ...
]
```

The `[HH:MM]` timestamp helps with temporal context. The model should understand this.

## Issue 2: Streaming Too Slow

### Configuration
In `utils/ai_tutor.py`, function `stream_ai_response()`:

```python
CHARS_PER_EDIT = 2     # Characters to reveal per Telegram edit
EDIT_DELAY = 0.008     # Seconds between edits (~250 chars/second)
```

### Adjustment Guide
| Value | Effect |
|-------|--------|
| 0.002 | Very fast (~1000 chars/sec) |
| 0.005 | Fast (~400 chars/sec) |
| 0.008 | Balanced - RECOMMENDED |
| 0.02 | Slower, more dramatic |
| 0.05 | Painfully slow (old default) |

## Issue 3: HTML Parsing Errors (400 Bad Request)

### Problem
Telegram's HTML parser fails on special characters:
- `&` → Must be `&amp;`
- `<` → Must be `&lt;`
- `>` → Must be `&gt;`
- `"` → Must be `&quot;`

### Fix
Added `escape_html()` function in `utils/ai_tutor.py`:

```python
def escape_html(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
```

Applied in `clean_output()` before returning.

## Issue 4: Image Duplicate Processing

### Problem
When user sends image as reply to Mimi's message, both `PHOTO` and `TEXT` handlers may trigger.

### Fix
In `utils/pipequestions.py`, added a flag to context:

```python
# Before processing
context.user_data['processing_image'] = True
await vision.process_image_question(update, context)
return

# At start of pipe_question (check flag to prevent duplicate)
if context.user_data.get('processing_image'):
    context.user_data['processing_image'] = False
    return  # Skip text processing, image handler will run
```

## Issue 5: Nemotron Output Truncation

### Problem
Some image transcriptions were truncated when saved to Firestore.

### Fix
Added debug logging in `utils/vision.py` to track transcription:
```python
print(f"DEBUG: Vision: Nemotron transcription ({len(extracted_text)} chars): {extracted_text[:100]}...")
```

This allows verification that the full transcription is being captured before sending to the AI.

## Debug Logging Reference

### Firebase Logs
| Location | Log Message |
|----------|-------------|
| `get_recent_context()` | "Firestore: Retrieved X messages (Y chars total) for user {id}" |
| `log_conversation()` | "Firestore: Saving {role} message ({len} chars) for user {id}" |
| `stream_ai_response()` | "History: X messages, Y chars total" + full history content |
| `vision.process_image_question()` | "DEBUG: Vision: Nemotron transcription (X chars): {content}..." |

### Log Interpretation
- If history shows 0 messages: Check Firestore permissions
- If history shows messages but AI doesn't use them: Model context following issue
- If messages have wrong format: Check `get_sliding_window_context()` formatting

## Firestore Schema

### Collection: `users/{telegram_id}`
```json
{
  "name": "User Full Name",
  "username": "telegram_username",
  "last_active": "ISO timestamp"
}
```

### Subcollection: `users/{telegram_id}/conversations`
```json
{
  "role": "user" | "assistant",
  "content": "Message content",
  "timestamp": "ISO timestamp"
}
```

### Pruning
- Max messages: 50
- Delete count: 25 (oldest messages)
- Called after each response

## Files Modified

| File | Changes |
|------|---------|
| `utils/ai_tutor.py` | EDIT_DELAY=0.008, add escape_html(), add debug logs |
| `prompts/system_prompt.md` | Add "Conversation Memory (Critical)" section |
| `prompts/global_grounding.md` | Strengthen "Continuity" rule |
| `utils/pipequestions.py` | Add image processing flag |
| `utils/firebase_db.py` | Add debug logs for get_recent_context() and log_conversation() |
| `utils/vision.py` | Add debug logging for transcription |
| `docs/memory_context_fixes.md` | This documentation |

## Testing Checklist

After deployment, test the following:

1. **Memory Test**
   - [ ] User: "Remember 12345"
   - [ ] User: "what number did I tell you?"
   - [ ] Expected: "You mentioned 12345"

2. **Streaming Speed Test**
   - [ ] Response appears within 2-3 seconds for short messages
   - [ ] Text updates smoothly, not choppy

3. **HTML Escaping Test**
   - [ ] Send message with `&`, `<`, `>` characters
   - [ ] No 400 Bad Request errors in logs

4. **Image Processing Test**
   - [ ] Send image as reply to bot
   - [ ] Process only once (check logs for duplicate processing)

5. **Debug Logs Test**
   - [ ] Check server logs for Firestore retrieval messages
   - [ ] Check for Vision transcription debug output
