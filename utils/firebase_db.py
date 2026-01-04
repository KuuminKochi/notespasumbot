import firebase_admin
from firebase_admin import credentials, firestore
import os
import datetime

# Initialize Firebase
# Expecting FIREBASE_CREDENTIALS in environment variables pointing to json file
# or default to 'service-account.json'
cred_path = os.getenv("FIREBASE_CREDENTIALS", "service-account.json")

if not firebase_admin._apps:
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        # Just a warning, main code checks for db
        pass

db = firestore.client() if firebase_admin._apps else None


def get_user_profile(telegram_id):
    if not db:
        return None
    doc_ref = db.collection("users").document(str(telegram_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None


def create_or_update_user(telegram_id, user_data):
    if not db:
        return
    doc_ref = db.collection("users").document(str(telegram_id))
    doc_ref.set(user_data, merge=True)


def log_conversation(telegram_id, role, content):
    """
    Logs a message to the user's conversation history subcollection.
    """
    if not db:
        return

    user_ref = db.collection("users").document(str(telegram_id))
    # Create conversation document
    msg_data = {"role": role, "content": content, "timestamp": datetime.datetime.now()}
    user_ref.collection("conversations").add(msg_data)


def get_recent_context(telegram_id, limit=10):
    """
    Retrieves the last N messages for context window.
    """
    if not db:
        return []

    user_ref = db.collection("users").document(str(telegram_id))
    # Use string 'DESCENDING' which is supported by google-cloud-firestore
    docs = (
        user_ref.collection("conversations")
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
        .stream()
    )

    messages = []
    for doc in docs:
        messages.append(doc.to_dict())

    # Reverse to chronological order
    return messages[::-1]


def save_memory(telegram_id, content, category="User"):
    """
    Saves a memory with a category to distinguish between User facts and Mimi's state.
    Category should be 'User' or 'Mimi'.
    """
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    user_ref.collection("memories").add(
        {
            "content": content,
            "category": category,
            "timestamp": datetime.datetime.now(),
            "type": "auto_summary",
        }
    )


def get_user_memories(telegram_id, category=None, limit=20):
    """
    Retrieves memories for the user, optionally filtered by category.
    """
    if not db:
        return []

    user_ref = db.collection("users").document(str(telegram_id))
    query = user_ref.collection("memories").order_by(
        "timestamp", direction="DESCENDING"
    )

    if category:
        query = query.where("category", "==", category)

    docs = query.limit(limit).stream()

    memories = []
    for doc in docs:
        memories.append(doc.to_dict())

    return memories


def save_announcement(text, admin_id):
    """
    Logs an announcement made by the admin.
    """
    if not db:
        return
    db.collection("announcements").add(
        {"text": text, "admin_id": str(admin_id), "timestamp": datetime.datetime.now()}
    )


def get_all_user_ids():
    """
    Efficiently retrieve just IDs for broadcasting.
    """
    if not db:
        return []
    docs = db.collection("users").stream()
    return [doc.id for doc in docs]


def clear_user_memories(telegram_id, category=None):
    """
    Deletes all memories for a user, optionally filtered by category.
    Used during memory compression.
    """
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    query = user_ref.collection("memories")
    if category:
        query = query.where("category", "==", category)

    docs = query.stream()
    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1
        if count >= 400:  # Firestore limit is 500
            batch.commit()
            batch = db.batch()
            count = 0
    batch.commit()


def add_admin(user_id):
    """Adds a user ID to the admins list."""
    if not db:
        return
    db.collection("settings").document("admins").set({str(user_id): True}, merge=True)


def remove_admin(user_id):
    """Removes a user ID from the admins list."""
    if not db:
        return
    db.collection("settings").document("admins").update(
        {str(user_id): firestore.DELETE_FIELD}
    )


def get_admins():
    """Returns a list of admin IDs (strings)."""
    if not db:
        return []
    doc = db.collection("settings").document("admins").get()
    if doc.exists:
        return list(doc.to_dict().keys())
    return []


def is_admin(user_id):
    """Checks if a user is an admin (Env Root or DB Admin)."""
    # Check Env Root
    root_admin = os.getenv("ADMIN_NOTES", "0")
    if str(user_id) == str(root_admin):
        return True

    # Check DB
    admins = get_admins()
    return str(user_id) in admins


def hard_reset_user_data(telegram_id):
    """
    Completely wipes a user's conversation history and memories.
    """
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))

    # 1. Clear Conversations
    convs = user_ref.collection("conversations").stream()
    batch = db.batch()
    for doc in convs:
        batch.delete(doc.reference)
    batch.commit()

    # 2. Clear Memories
    mems = user_ref.collection("memories").stream()
    batch = db.batch()
    for doc in mems:
        batch.delete(doc.reference)
    batch.commit()

    # 3. Clear Profile
    user_ref.update(
        {
            "psych_profile": firestore.DELETE_FIELD,
            "profile_tags": firestore.DELETE_FIELD,
            "last_profile_update": firestore.DELETE_FIELD,
        }
    )
