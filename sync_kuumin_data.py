import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import sys

# Add local scripts path for credentials
sys.path.append("/home/kuumin/Development/Projects/notespasumbot")
from utils import firebase_db

# Local Store Paths
MEMORY_STORE_FILE = "/home/kuumin/Script/mimi_memory_store.json"
DIARY_STORE_FILE = "/home/kuumin/Script/mimi_diary_store.json"
KUUMIN_ID = "1088951045"


def sync_local_to_firebase():
    print(f"Starting sync for Kuumin ({KUUMIN_ID})...")

    # 1. Sync Memories
    if os.path.exists(MEMORY_STORE_FILE):
        with open(MEMORY_STORE_FILE, "r", encoding="utf-8") as f:
            memories = json.load(f)

        user_mem_ref = (
            firebase_db.db.collection("users")
            .document(KUUMIN_ID)
            .collection("memories")
        )

        # Get existing memories to avoid duplicates
        existing = [d.to_dict().get("content") for d in user_mem_ref.stream()]

        count = 0
        for m in memories:
            content = m.get("content")
            if content and content not in existing:
                # Map desktop categories to Firebase categories
                raw_cat = m.get("category", "Kuumin")
                firebase_cat = "Mimi" if raw_cat == "Mimi" else "User"

                user_mem_ref.add(
                    {
                        "content": content,
                        "timestamp": datetime.fromtimestamp(
                            m.get("id", datetime.now().timestamp() * 1000) / 1000.0
                        ),
                        "category": firebase_cat,
                        "source": "jan_sync",
                    }
                )
                count += 1
        print(f"Synced {count} new memories.")

    # 2. Sync Diary
    if os.path.exists(DIARY_STORE_FILE):
        with open(DIARY_STORE_FILE, "r", encoding="utf-8") as f:
            diaries = json.load(f)

        user_diary_ref = (
            firebase_db.db.collection("users").document(KUUMIN_ID).collection("diaries")
        )

        # Get existing dates
        existing_dates = [d.to_dict().get("date") for d in user_diary_ref.stream()]

        count = 0
        for d in diaries:
            date_str = d.get("date")
            if date_str and date_str not in existing_dates:
                user_diary_ref.add(
                    {
                        "date": date_str,
                        "content": d.get("content"),
                        "timestamp": datetime.fromtimestamp(
                            d.get("timestamp", datetime.now().timestamp())
                        ),
                    }
                )
                count += 1
        print(f"Synced {count} new diary entries.")


if __name__ == "__main__":
    if not firebase_db.db:
        print("Error: Firebase not initialized. Check FIREBASE_CREDENTIALS.")
    else:
        sync_local_to_firebase()
