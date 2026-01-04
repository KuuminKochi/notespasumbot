import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore
import os
import datetime

# Initialize Firebase Admin (for other features if needed)
cred_path = os.getenv("FIREBASE_CREDENTIALS", "service-account.json")
if not firebase_admin._apps:
    if os.path.exists(cred_path):
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    else:
        try:
            firebase_admin.initialize_app()
        except:
            pass

# Initialize Firestore Client explicitly with credentials to avoid ADC errors
if os.path.exists(cred_path):
    db = firestore.Client.from_service_account_json(cred_path)
else:
    db = firestore.Client()


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
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    msg_data = {"role": role, "content": content, "timestamp": datetime.datetime.now()}
    user_ref.collection("conversations").add(msg_data)


def get_recent_context(telegram_id, limit=5):
    """
    Retrieves the last N messages (Sliding Window: 5 messages).
    """
    if not db:
        return []
    user_ref = db.collection("users").document(str(telegram_id))
    docs = (
        user_ref.collection("conversations")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    messages = []
    for doc in docs:
        messages.append(doc.to_dict())
    return messages[::-1]


def save_memory(telegram_id, content, category="User"):
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


def get_user_memories(telegram_id, category=None, limit=8):
    if not db:
        return []
    user_ref = db.collection("users").document(str(telegram_id))
    query = user_ref.collection("memories").order_by(
        "timestamp", direction=firestore.Query.DESCENDING
    )
    if category:
        query = query.where("category", "==", category)
    docs = query.limit(limit).stream()
    memories = []
    for doc in docs:
        memories.append(doc.to_dict())
    return memories


def clear_user_memories(telegram_id, category=None):
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    query = user_ref.collection("memories")
    if category:
        query = query.where("category", "==", category)
    docs = query.stream()
    for doc in docs:
        doc.reference.delete()


def save_announcement(text, admin_id):
    if not db:
        return
    db.collection("announcements").add(
        {"text": text, "admin_id": str(admin_id), "timestamp": datetime.datetime.now()}
    )


def get_all_user_ids():
    if not db:
        return []
    docs = db.collection("users").stream()
    return [doc.id for doc in docs]


def get_all_user_profiles(limit=50):
    if not db:
        return []
    docs = db.collection("users").limit(limit).stream()
    profiles = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        profiles.append(data)
    return profiles


def add_admin(user_id):
    if not db:
        return
    db.collection("settings").document("admins").set({str(user_id): True}, merge=True)


def remove_admin(user_id):
    if not db:
        return
    db.collection("settings").document("admins").update(
        {str(user_id): firestore.DELETE_FIELD}
    )


def get_admins():
    if not db:
        return []
    doc = db.collection("settings").document("admins").get()
    if doc.exists:
        data = doc.to_dict()
        return list(data.keys()) if data else []
    return []


def is_admin(user_id):
    root_admin = os.getenv("ADMIN_NOTES", "0")
    if str(user_id) == str(root_admin):
        return True
    return str(user_id) in get_admins()


def hard_reset_user_data(telegram_id):
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    # Clear Conversations
    for doc in user_ref.collection("conversations").stream():
        doc.reference.delete()
    # Clear Memories
    for doc in user_ref.collection("memories").stream():
        doc.reference.delete()
    # Clear Profile
    user_ref.update(
        {
            "psych_profile": firestore.DELETE_FIELD,
            "profile_tags": firestore.DELETE_FIELD,
            "last_profile_update": firestore.DELETE_FIELD,
        }
    )
