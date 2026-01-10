# Streaming Behavior Documentation

## Overview

Mimi uses a streaming API response with a **smooth character-by-character display** for better user experience. The API streams tokens in chunks, but the user sees content revealed 1-2 characters at a time.

## Key Concepts

### API Streaming vs Display Streaming

| Layer | Behavior |
|-------|----------|
| **API Layer** | OpenRouter streams JSON chunks (5-20+ chars per chunk) |
| **Buffer Layer** | Full response accumulated in `buffer` variable |
| **Display Layer** | Reveals 1-2 chars per Telegram `editMessageText` call |

### Why This Approach?

1. **Seamless UX**: Character-by-character reveal feels like real-time typing
2. **Readable**: User can read as content appears (no jumping text)
3. **Smooth**: Small updates (1-2 chars) don't interrupt reading flow
4. **Complete Final State**: Final message shown once, clean and readable

## Implementation Details

### Configuration Variables

Located in `utils/ai_tutor.py`, function `stream_ai_response()`:

```python
CHARS_PER_EDIT = 2     # Characters to reveal per Telegram edit
EDIT_DELAY = 0.05      # Seconds to wait between edits (50ms)
```

**Adjusting Smoothness:**

| Value | Effect |
|-------|--------|
| `CHARS_PER_EDIT = 1` | Slower, more dramatic reveal |
| `CHARS_PER_EDIT = 2` | Balanced (current default) |
| `CHARS_PER_EDIT = 3-4` | Faster, less "typing" feel |
| `EDIT_DELAY < 0.05` | Smoother but more API calls |
| `EDIT_DELAY > 0.05` | Choppier but less resource usage |

### Flow Diagram

```
API Stream (chunks)
        ↓
    buffer += content
        ↓
revealed_count += len(content)
        ↓
visible_text = clean_output(buffer[:revealed_count])
        ↓
await status_msg.edit_text(visible_text + "▌")
        ↓
await asyncio.sleep(EDIT_DELAY)
        ↓
   Repeat until [DONE]
        ↓
Show final clean message (no cursor)
```

### Cursor Handling

- **During streaming**: `"▌"` cursor appended to visible text
- **Final message**: Cursor removed, clean text displayed
- **Empty response**: Error message shown, no cursor artifacts

## Code Reference

### Main Function
`utils/ai_tutor.py::stream_ai_response()`

### Key Variables

| Variable | Purpose |
|----------|---------|
| `buffer` | Accumulates complete API response |
| `revealed_count` | Tracks how many chars user has seen |
| `status_msg` | Telegram message object to edit |

### Related Functions

- `clean_output()` - Removes links, strips whitespace
- `prune_conversation()` - Manages conversation history
- `firebase_db.log_conversation()` - Saves to Firestore

## Common Issues

### Cursor Stuck on Screen
**Cause**: Exception before final `edit_text` call  
**Fix**: Ensure final message is always shown in `try/except`

### Response Cuts Off
**Cause**: `revealed_count` exceeds buffer length  
**Fix**: The current implementation handles this via slicing `buffer[:revealed_count]`

### Too Slow
**Cause**: `EDIT_DELAY` too high or `CHARS_PER_EDIT` too low  
**Fix**: Increase `CHARS_PER_EDIT` to 3-4, decrease `EDIT_DELAY` to 0.02

## Testing Checklist

When modifying streaming behavior:

- [ ] Cursor appears immediately
- [ ] Text reveals smoothly (1-2 chars at a time)
- [ ] Final message is clean (no cursor)
- [ ] Memory logging works (check Firestore)
- [ ] Empty responses show error message
- [ ] No exceptions in logs

## Performance Notes

- Each character edit = 1 Telegram API call
- Typical response (200 chars) = ~100 API calls
- `EDIT_DELAY` of 0.05s = ~10 seconds for 200 chars
- Monitor rate limits on Telegram Bot API
