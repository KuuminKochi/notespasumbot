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


def get_all_user_profiles(limit=50):
    """
    Retrieves all user profiles for matching.
    """
    if not db:
        return []

    docs = db.collection("users").limit(limit).stream()
    profiles = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        profiles.append(data)
    return profiles
