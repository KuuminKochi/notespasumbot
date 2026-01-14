# AGENTS.md - Developer Guide for Autonomous Agents

This document provides instructions, commands, and standards for AI agents operating within the `notespasumbot` repository.

## 1. Project Overview

*   **Type**: Python Telegram Bot
*   **Core Libraries**: `python-telegram-bot` (v22+), `firebase-admin`, `httpx`, `requests`
*   **Target Audience**: Students at the Centre for Foundation Studies in Science (PASUM), UM.
*   **Architecture**:
    *   `main.py`: Entry point and handler registration.
    *   `utils/`: Logic modules (AI tutoring, database, command handlers).
    *   `prompts/`: System prompts and persona definitions (Mimi).
    *   `tests/`: Unit and integration tests using `pytest`.

## 2. Environment & Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt
```

### Testing (Pytest)
Always verify changes by running tests. The project has specific tests for critical rules.
*   **Run all tests**: `pytest`
*   **Run single file**: `pytest tests/test_mimi_refactor.py`
*   **Run by pattern**: `pytest -k "link_filtering"`
*   **Verbose output**: `pytest -v`

### Execution
*   **Start Bot**: `python main.py` (Requires `.env` with `API_KEY`, `OPENROUTER_API_KEY`, etc.)

### Deployment & Maintenance
*   `deploy.sh`: Script for production deployment.
*   `update.sh`: Script to pull changes and restart services.
*   `run_loop.sh`: Process watchdog to ensure the bot stays online.

## 3. Code Style & Conventions

### General Python Style
*   **Standard**: PEP 8 compliance.
*   **Indentation**: 4 spaces. No tabs.
*   **Quotes**: Double quotes `"` for strings by default.
*   **Line Length**: Aim for <100 characters.

### Imports & Types
*   **Order**: 1. Stdlib, 2. Third-party, 3. Local `utils`.
*   **Type Hinting**: Required for function signatures.
    *   *Example*: `async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:`

### Async/Await
*   Use `async def` for all Telegram handlers and I/O bound functions.
*   Use `await` for `httpx` calls (preferred over `requests` for async) and DB operations.
*   Never use blocking `time.sleep()`; use `await asyncio.sleep()`.

### Error Handling & Logging
*   Use the standard `logging` library. Avoid `print()`.
*   Log errors with traceback information when appropriate.
```python
import logging
logger = logging.getLogger(__name__)

try:
    await some_async_call()
except Exception as e:
    logger.error(f"Failed to execute call: {e}", exc_info=True)
```

## 4. Core Application Rules (MANDATORY)

### STRICT NO LINKS POLICY
The bot must **NEVER** output URLs, web addresses, or markdown links.
*   **Regex Filtering**: `utils/ai_tutor.py` contains `clean_output` which replaces links with `[Link Removed]`.
*   **Agent Task**: When writing AI-related logic, ensure this filter is preserved and the system prompt reinforces this rule.
*   **Allowed Exceptions**: None. Even if the user asks for a link, Mimi must explain the concept herself.

### Mimi Persona Guidelines
*   **Identity**: 18-year-old Malaysian academic tutor named Mimi. Petite (155cm), blue bob, hibiscus behind ear (background only).
*   **Tone**: Intelligent, lively, empathetic, and optimistic. Warm but professional.
*   **Teaching Philosophy**: Socratic method. Ask leading questions; guide from first principles. 
    *   *Direct Answers*: Give them only if explicitly asked, then gently discourage the habit.
*   **Factual Integrity**: **NEVER** hallucinate lecturer or staff names. Refer to them generally (e.g., "your Physics lecturer").
*   **Formatting**: Use ONLY `<b>bold</b>`, `<i>italics</i>`, and `<code>code</code>` HTML tags. Telegram-optimized: short, scannable blocks.

### Relationships & Context
*   **Creator**: Kuumin (familiar and respectful). Mimi acknowledges Kuumin as her creator and follows their vision.
*   **Sister**: Wiwi (twin sister with a complementary channel). Mimi admires her but worries about her overworking.
*   **Continuity**: Always use the provided conversation history. Never claim "I don't have access to previous messages."

## 5. Project Structure Details

### Core Logic (`utils/`)
*   `ai_tutor.py`: AI response generation, prompt building (loading `prompts/*.md`), and output cleaning (link removal).
*   `firebase_db.py`: All interactions with Firebase. Handles conversation logs, user metadata, and pruning history.
*   `vision.py`: Logic for analyzing images sent by users.
*   `commands.py`: Soft reset (`/reset`) and hard reset (`/hardreset`) logic for clearing user data/context.
*   `pasumpals.py` / `pasummatch.py`: Profile management and user matching system for the PASUM community.
*   `admin_manager.py`: Logic for managing bot administrators.

### Prompts (`prompts/`)
*   `global_grounding.md`: Mandatory operational rules (No Links, No Hallucinations).
*   `system_prompt.md`: Detailed identity and persona definition for Mimi.

## 6. Environment Variables
Required in `.env`:
*   `API_KEY`: Telegram Bot Token.
*   `OPENROUTER_API_KEY`: For AI response generation.
*   `NOTES_PASUM`: Chat ID for the main community.
*   `ADMIN_NOTES`: Chat ID for the admin log.

## 7. Common Workflows for Agents

### Adding a New Command
1.  Define the handler function in a relevant `utils/` module (or create a new one).
2.  Register the `CommandHandler` in `main.py`.
3.  Add the command to the `/help` message in `utils/help.py`.
4.  Write a test case in `tests/` to verify the command's logic.

### Modifying AI Behavior
1.  Update the relevant markdown file in `prompts/`.
2.  Test the prompt changes by running `pytest tests/test_mimi_refactor.py`.
3.  Ensure the `clean_output` function in `utils/ai_tutor.py` still correctly strips links.

### Database Updates
1.  Add the new database interaction method to `utils/firebase_db.py`.
2.  Use the `db` reference (initialized from `firebase_admin`).
3.  Ensure all new operations are logged for debugging.

## 8. Agent Operational Standards

*   **File Paths**: Use absolute paths or resolve relative to project root.
*   **Verification**: Run `pytest` after any logic change. Specifically check `test_no_links_rule_exists`.
*   **Secrets Safety**: Never commit `.env` or `service-account.json`. 
*   **Refactoring**: Keep feature-specific logic in `utils/`. Avoid bloating `main.py`.

---
*Updated on 2026-01-14 by opencode.*
