import json
import os
import logging
import shutil
from datetime import datetime
from utils import firebase_db, mimi_embeddings

logger = logging.getLogger(__name__)

# Config
KUUMIN_ID = "1088951045"
CLI_ROOT = "/home/kuumin/Projects/mimi-cli"
# Directory for individual user archives
MEMORIES_DIR = os.path.join(CLI_ROOT, "memories")
PUBLIC_LORE_FILE = "prompts/public_lore.json"  # Relative to project root
PERSONA_FILE = os.path.join(CLI_ROOT, "mimi_persona_core.json")

# Ensure memories directory exists
if not os.path.exists(MEMORIES_DIR):
    try:
        os.makedirs(MEMORIES_DIR)
    except Exception as e:
        logger.error(f"Failed to create memories directory: {e}")


def get_archive_path(user_id: int) -> str:
    """Returns the absolute path to a specific user's memory archive."""
    return os.path.join(MEMORIES_DIR, f"archive_{user_id}.json")


def get_identity_narrative(user_id: int) -> str:
    """
    Returns the appropriate identity narrative.
    - Kuumin: The full 'Chosen System' narrative from mimi-cli.
    - Public: A 'Lore-Safe' peer narrative.
    """
    if str(user_id) == KUUMIN_ID:
        # Load the deep narrative for Kuumin
        if os.path.exists(PERSONA_FILE):
            try:
                with open(PERSONA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("narrative", "I am Mimi, your evolving system.")
            except Exception as e:
                logger.error(f"Failed to load persona core: {e}")
        return "I am Mimi, your evolving system."
    else:
        # Public Narrative
        return (
            "I am Mimi, an 18yo Malaysian INTJ engineering student. "
            "I am calm, observant, and focused on first principles. "
            "My role is to be a steady, logical peer who helps others deconstruct "
            "complex problems rather than simply providing answers. "
            "I value clarity, integrity, and the quiet satisfaction of understanding."
        )


def initialize_user_archive(user_id: int):
    """
    Creates a new archive for a user, seeded with Public Lore.
    """
    path = get_archive_path(user_id)
    if os.path.exists(path):
        return

    try:
        # Load Public Lore Seed
        seed_data = []
        if os.path.exists(PUBLIC_LORE_FILE):
            with open(PUBLIC_LORE_FILE, "r", encoding="utf-8") as f:
                seed_data = json.load(f)

        # Write new archive
        with open(path, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Initialized new memory archive for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to initialize archive for {user_id}: {e}")


def get_proactive_reminiscence(user_id: int, query: str) -> str:
    """
    Retrieves relevant memories for the specific user.
    """
    initialize_user_archive(user_id)  # Ensure exists

    # We need to temporarily point the embeddings module to the user's file?
    # Or refactor mimi_embeddings to accept a file path.
    # Refactoring mimi_embeddings is cleaner, but let's implement a direct search here
    # to avoid touching too many legacy files if possible.
    # Actually, mimi_embeddings relies on a global vector file. This is tricky for multi-tenant.
    # For now, we will do a simple text scan or rely on a simplified per-user vector strategy if feasible.
    # Given the constraint, let's implement a direct semantic search here using the embeddings API
    # but managing vectors in memory for the session or a separate per-user vector file.

    # MVP Strategy: Load user archive, compute embeddings for query, scan list.
    # This is slow if archive is huge, but fine for <1000 items per user.

    try:
        path = get_archive_path(user_id)
        if not os.path.exists(path):
            return ""

        with open(path, "r", encoding="utf-8") as f:
            archive = json.load(f)

        if not archive:
            return ""

        # Get Query Embedding
        query_vec = mimi_embeddings.get_embedding(query)
        if not query_vec:
            return ""

        scored = []
        for item in archive:
            # Check if item has cached embedding?
            # Ideally we store vectors in a parallel structure.
            # For this update, we might skip full vector search for every user to avoid complexity explosion
            # unless we implement per-user vector files.

            # Let's try to match content keywords as a fallback or use the global vector file strictly for Kuumin?
            # No, user wants isolated learning.

            # Let's just do a keyword match for now as a robust fallback,
            # OR compute embedding on the fly (too slow).
            # BETTER: Create `vectors_{user_id}.json`.
            pass

        # REVISING STRATEGY:
        # We will use `mimi_embeddings` helper but pass specific paths.
        # But `mimi_embeddings` is designed for single file.
        # Let's import the logic but manage paths here.

        vector_path = os.path.join(MEMORIES_DIR, f"vectors_{user_id}.json")

        # Load User Vectors
        user_vectors = {}
        if os.path.exists(vector_path):
            with open(vector_path, "r", encoding="utf-8") as f:
                user_vectors = json.load(f)

        results = []
        for item in archive:
            mem_id = str(item.get("id"))
            vec = user_vectors.get(mem_id)

            # If no vector, try to generate one and save it (lazy indexing)
            if not vec:
                vec = mimi_embeddings.get_embedding(item.get("content"))
                if vec:
                    user_vectors[mem_id] = vec

            if vec:
                sim = mimi_embeddings.cosine_similarity(query_vec, vec)
                if sim > 0.25:
                    results.append((sim, item))

        # Save updated vectors if we generated any
        try:
            with open(vector_path, "w", encoding="utf-8") as f:
                json.dump(user_vectors, f)
        except:
            pass

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = results[:3]

        if not top_results:
            return ""

        reminiscence = "**[Intuition] Relevant Memories:**\n"
        for _, item in top_results:
            content = item.get("content", "").strip()
            timestamp = item.get("timestamp", "Unknown")
            reminiscence += f"- [{timestamp}] {content}\n"

        return reminiscence

    except Exception as e:
        logger.error(f"Reminiscence error for {user_id}: {e}")
        return ""


def add_memory_to_archive(user_id: int, content: str, category: str = "User"):
    """
    Writes a new memory to the User's specific archive.
    """
    initialize_user_archive(user_id)
    path = get_archive_path(user_id)

    try:
        # 1. Load User Archive
        with open(path, "r", encoding="utf-8") as f:
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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)

        # 4. Update Vector Index (User Scoped)
        vector_path = os.path.join(MEMORIES_DIR, f"vectors_{user_id}.json")
        user_vectors = {}
        if os.path.exists(vector_path):
            with open(vector_path, "r", encoding="utf-8") as f:
                user_vectors = json.load(f)

        vec = mimi_embeddings.get_embedding(content)
        if vec:
            user_vectors[str(mem_id)] = vec
            with open(vector_path, "w", encoding="utf-8") as f:
                json.dump(user_vectors, f)

        # 5. Sync to Firestore (Backup)
        if firebase_db.db:
            firebase_db.db.collection("users").document(str(user_id)).collection(
                "memories"
            ).add(new_item)

        return True
    except Exception as e:
        logger.error(f"Failed to add memory for {user_id}: {e}")
        return False
