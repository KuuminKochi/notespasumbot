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


def log_conversation(telegram_id, role, content, chat_id=None):
    if not db:
        return
    # Use chat_id as the primary scope if provided, otherwise default to telegram_id (for legacy/DMs)
    target_id = str(chat_id) if chat_id else str(telegram_id)

    # Store in a "chats" collection to isolate environments
    chat_ref = db.collection("chats").document(target_id)
    msg_data = {
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now(),
        "user_id": str(telegram_id),
    }
    chat_ref.collection("messages").add(msg_data)
    print(
        f"DEBUG: Firestore: Saving {role} message ({len(content)} chars) for chat {target_id}"
    )


def prune_conversation(telegram_id, chat_id=None, max_messages=50, delete_count=25):
    """Prune oldest messages when conversation exceeds max_messages."""
    if not db:
        return

    target_id = str(chat_id) if chat_id else str(telegram_id)
    chat_ref = db.collection("chats").document(target_id)
    conv_ref = chat_ref.collection("messages")

    total = len(list(conv_ref.stream()))
    if total <= max_messages:
        return

    old_docs = conv_ref.order_by("timestamp").limit(delete_count).stream()
    count = 0
    for doc in old_docs:
        doc.reference.delete()
        count += 1


def get_recent_context(telegram_id, chat_id=None, limit=5):
    """
    Retrieves the last N messages (Sliding Window: 5 messages).
    """
    if not db:
        return []

    target_id = str(chat_id) if chat_id else str(telegram_id)
    chat_ref = db.collection("chats").document(target_id)

    docs = (
        chat_ref.collection("messages")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    messages = []
    for doc in docs:
        data = doc.to_dict()
        # Clean internal fields before returning to context
        messages.append({"role": data.get("role"), "content": data.get("content")})

    result = messages[::-1]
    total_chars = sum(len(m.get("content", "")) for m in result)
    print(
        f"DEBUG: Firestore: Retrieved {len(result)} messages ({total_chars} chars) for chat {target_id}"
    )
    return result


# Memory functions are DISABLED for refactoring
# These will be reimplemented later


def save_memory(telegram_id, content, category="User"):
    pass


def get_user_memories(telegram_id, category=None, limit=8):
    return []


def clear_user_memories(telegram_id, category=None):
    pass


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


def clear_user_conversations(telegram_id):
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    for doc in user_ref.collection("conversations").stream():
        doc.reference.delete()


def hard_reset_user_data(telegram_id):
    if not db:
        return
    user_ref = db.collection("users").document(str(telegram_id))
    # Clear Conversations only (memories disabled)
    for doc in user_ref.collection("conversations").stream():
        doc.reference.delete()
