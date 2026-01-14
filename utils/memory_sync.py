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
    """
    Bi-directional sync between local JSON (Archive) and Firestore.
    Rules:
    1. Read all Firestore memories.
    2. Read local Archive.
    3. Merge lists (deduplicating by content + timestamp).
    4. Write back differences to both.
    """
    if not firebase_db.db:
        return

    try:
        # 1. Load Local Archive
        local_memories = []
        if os.path.exists(ARCHIVE_FILE):
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                local_memories = json.load(f)

        # Helper to hash memories for dedup
        def get_mem_hash(m):
            return f"{m.get('timestamp')}_{m.get('content')}"

        local_map = {get_mem_hash(m): m for m in local_memories}

        # 2. Load Firestore Memories
        user_mem_ref = (
            firebase_db.db.collection("users")
            .document(KUUMIN_ID)
            .collection("memories")
        )
        cloud_memories = []
        for doc in user_mem_ref.stream():
            data = doc.to_dict()
            # Normalize keys to match CLI format
            data["id"] = data.get("id") or int(datetime.now().timestamp() * 1000)
            cloud_memories.append(data)

        # 3. Merge Logic
        updates_to_local = []
        updates_to_cloud = []

        # Check what's missing in local
        for cm in cloud_memories:
            h = get_mem_hash(cm)
            if h not in local_map:
                updates_to_local.append(cm)
                local_map[h] = cm  # Update map to avoid dupes later

        # Check what's missing in cloud
        cloud_hashes = {get_mem_hash(cm) for cm in cloud_memories}
        for lm in local_memories:
            h = get_mem_hash(lm)
            if h not in cloud_hashes:
                updates_to_cloud.append(lm)

        # 4. Apply Updates

        # Write to Local
        if updates_to_local:
            final_list = list(local_map.values())
            # Sort by timestamp descending
            final_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
                json.dump(final_list, f, indent=2, ensure_ascii=False)

            # Re-index embeddings for new items
            for item in updates_to_local:
                vector = mimi_embeddings.get_embedding(item.get("content"))
                if vector:
                    vectors = mimi_embeddings.load_vectors()
                    vectors[str(item.get("id"))] = vector
                    mimi_embeddings.save_vectors(vectors)

            logger.info(
                f" synced {len(updates_to_local)} memories from Cloud -> Local."
            )

        # Write to Cloud
        if updates_to_cloud:
            batch = firebase_db.db.batch()
            count = 0
            for item in updates_to_cloud:
                doc_ref = user_mem_ref.document(str(item.get("id")))
                batch.set(doc_ref, item)
                count += 1
                if count >= 400:  # Firestore batch limit safety
                    batch.commit()
                    batch = firebase_db.db.batch()
                    count = 0
            if count > 0:
                batch.commit()

            logger.info(
                f" synced {len(updates_to_cloud)} memories from Local -> Cloud."
            )

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
