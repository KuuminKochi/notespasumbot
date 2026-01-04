#!/usr/bin/env python3
"""
One-time cleanup script to remove all memories Mimi has about herself
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv(
    "FIREBASE_CREDENTIALS", "service-account.json"
)

cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()

print("🧹 Starting cleanup of Mimi's self-memories...")

# Get all users
users_ref = db.collection("users")
users = list(users_ref.stream())

total_deleted = 0

for user_doc in users:
    user_id = user_doc.id
    memories_ref = user_doc.reference.collection("memories")
    memories = list(memories_ref.stream())

    for memory_doc in memories:
        memory_content = memory_doc.to_dict().get("content", "")

        # Check if memory is about Mimi herself
        mimi_keywords = ["mimi", "my sister", "wiwi", "twin", "i'm", "i am"]
        is_about_mimi = any(
            keyword in memory_content.lower() for keyword in mimi_keywords
        )

        # Delete all self-referential memories (including Kuumin's)
        if is_about_mimi:
            print(f"Deleting memory from user {user_id}: {memory_content[:50]}...")
            memory_doc.reference.delete()
            total_deleted += 1

print(f"✅ Cleanup complete! Deleted {total_deleted} self-referential memories.")
