import json
import os
import logging
from datetime import datetime
from utils import firebase_db, mimi_embeddings

logger = logging.getLogger(__name__)

# Config
KUUMIN_ID = "1088951045"
CLI_ROOT = "/home/kuumin/Projects/mimi-cli"
ARCHIVE_FILE = os.path.join(CLI_ROOT, "mimi_memory_archive.json")
PERSONA_FILE = os.path.join(CLI_ROOT, "mimi_persona_core.json")


def get_identity_narrative() -> str:
    """Loads the evolving persona narrative from the CLI core file."""
    if os.path.exists(PERSONA_FILE):
        try:
            with open(PERSONA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(
                    "narrative", "I am Mimi, an 18yo Malaysian INTJ student."
                )
        except Exception as e:
            logger.error(f"Failed to load persona core: {e}")

    return "I am Mimi, an 18yo Malaysian INTJ student."


def sync_memories_to_firestore():
    """Syncs local CLI memories to Firestore for the main user."""
    if not os.path.exists(ARCHIVE_FILE):
        return

    try:
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            memories = json.load(f)

        if not firebase_db.db:
            return

        user_mem_ref = (
            firebase_db.db.collection("users")
            .document(KUUMIN_ID)
            .collection("memories")
        )

        # Basic check to avoid re-uploading everything every time
        # In a robust system, we'd check IDs. For now, we trust the CLI archive is the source of truth.
        # But writing 1000s of docs is expensive.
        # Strategy: Only sync if we detect new items (by count or timestamp).
        # For this MVP, we will skip the heavy sync on every turn and rely on the
        # fact that the bot can read the local file directly for RAG.
        # We only push to Firestore for backup/web visibility.
        pass

    except Exception as e:
        logger.error(f"Memory sync failed: {e}")


def get_proactive_reminiscence(query: str) -> str:
    """
    Retrieves semantically relevant memories to form an 'Intuition' block.
    """
    try:
        results = mimi_embeddings.semantic_search(query, top_k=3)
        if not results:
            return ""

        reminiscence = "**[Intuition] Relevant Memories:**\n"
        for item in results:
            content = item.get("content", "").strip()
            timestamp = item.get("timestamp", "Unknown")
            reminiscence += f"- [{timestamp}] {content}\n"

        return reminiscence
    except Exception as e:
        logger.error(f"Reminiscence failed: {e}")
        return ""


def add_memory_to_archive(content: str, category: str = "Mimi"):
    """
    Writes a new memory to the local CLI archive (Primary Storage).
    Also triggers an embedding update.
    """
    if not os.path.exists(ARCHIVE_FILE):
        logger.error("Archive file not found. Cannot save memory.")
        return False

    try:
        # 1. Load Archive
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            archive = json.load(f)

        # 2. Append New Memory
        mem_id = int(datetime.now().timestamp() * 1000)
        new_item = {
            "id": mem_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content,
            "category": category,
            "source": "telegram_bot",
        }
        archive.append(new_item)

        # 3. Save Archive
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)

        # 4. Generate Embedding (Immediate Indexing)
        try:
            vector = mimi_embeddings.get_embedding(content)
            if vector:
                vectors = mimi_embeddings.load_vectors()
                vectors[str(mem_id)] = vector
                mimi_embeddings.save_vectors(vectors)
        except Exception as e:
            logger.error(f"Failed to index new memory: {e}")

        # 5. Sync to Firestore (Backup)
        if firebase_db.db:
            firebase_db.db.collection("users").document(KUUMIN_ID).collection(
                "memories"
            ).add(new_item)

        return True
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        return False
