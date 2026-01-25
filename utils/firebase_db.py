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


def log_conversation(telegram_id, role, content, chat_id=None, user_name=None):
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
        "user_name": user_name,
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
        messages.append(
            {
                "role": data.get("role"),
                "content": data.get("content"),
                "user_name": data.get("user_name"),
                "user_id": data.get("user_id"),
            }
        )

    result = messages[::-1]
    total_chars = sum(len(m.get("content", "")) for m in result)
    print(
        f"DEBUG: Firestore: Retrieved {len(result)} messages ({total_chars} chars) for chat {target_id}"
    )
    return result


# Memory functions are DISABLED for refactoring
# These will be reimplemented later


def save_memory(telegram_id, content, category="User"):
    """
    Saves a verified memory using the validator pipeline.
    This writes to the JSON archive and syncs to Firestore.
    """
    from utils import validator

    return validator.process_add_memory(content, telegram_id, category)


def get_user_memories(telegram_id, category=None, limit=8):
    """
    Retrieves proactive reminiscence (semantic search) for the user.
    """
    from utils import memory_sync

    # We use a generic 'retrieve' call; 'limit' handled inside reminiscence logic mostly
    # But get_proactive_reminiscence takes a query string.
    # Here we might need a direct dump if no query provided?
    # For now, let's assume this is used for explicit recall or context injection.
    # If no query, we return recent items?
    # Actually, let's bridge it to `get_proactive_reminiscence` assuming the 'category' implies a context.
    # But wait, `get_proactive_reminiscence` requires a query.
    return []  # Placeholder as this is usually called with a query in the agent.


def search_user_memories(telegram_id, query):
    from utils import memory_sync

    return memory_sync.get_proactive_reminiscence(telegram_id, query)


def clear_user_memories(telegram_id, category=None):
    # This requires a more complex delete implementation in memory_sync
    # For now, we leave as pass or implement a basic clear
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
    # 1. Clear Legacy Conversations (users/{id}/conversations)
    user_ref = db.collection("users").document(str(telegram_id))
    for doc in user_ref.collection("conversations").stream():
        doc.reference.delete()

    # 2. Clear New Chat History (chats/{id}/messages) - Private DMs
    # Note: We assume reset is mostly for private context.
    # For groups, we'd need chat_id, but usually reset is user-centric.
    chat_ref = db.collection("chats").document(str(telegram_id))
    for doc in chat_ref.collection("messages").stream():
        doc.reference.delete()


def hard_reset_user_data(telegram_id):
    if not db:
        return
    # 1. Clear Conversations
    clear_user_conversations(telegram_id)

    # 2. Reset Personality State
    user_ref = db.collection("users").document(str(telegram_id))
    user_ref.update(
        {
            "debate_state": firestore.DELETE_FIELD,
            "favourability": 50,  # Reset to neutral
        }
    )


def get_debate_state(telegram_id):
    """Retrieves the current debate/personality state for a user."""
    if not db:
        return {}
    doc = db.collection("users").document(str(telegram_id)).get()
    if doc.exists:
        return doc.to_dict().get("debate_state", {})
    return {}


def update_debate_state(telegram_id, state):
    """Updates the debate/personality state."""
    if not db:
        return
    db.collection("users").document(str(telegram_id)).set(
        {"debate_state": state}, merge=True
    )


def get_user_favourability(telegram_id):
    """Retrieves the current favourability score (0-100)."""
    if not db:
        return 50  # Default neutral
    doc = db.collection("users").document(str(telegram_id)).get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("favourability", 50)
    return 50


def update_user_favourability(telegram_id, delta):
    """Updates favourability score. Clamped between 0 and 100."""
    if not db:
        return

    current = get_user_favourability(telegram_id)
    new_val = max(0, min(100, current + delta))

    if new_val != current:
        db.collection("users").document(str(telegram_id)).set(
            {"favourability": new_val}, merge=True
        )
        print(f"DEBUG: Updated Favourability for {telegram_id}: {current} -> {new_val}")


def get_latest_news(limit=5, last_timestamp=None):
    """Retrieves paginated news from aggregated_posts."""
    if not db:
        return []

    query = (
        db.collection("aggregated_posts")
        .where("status", "in", ["trusted", "confession", "complaint"])
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    if last_timestamp:
        query = query.start_after({"timestamp": last_timestamp})

    return list(query.stream())


def save_aggregated_post(data):
    """Saves or updates a post in the aggregated_posts collection."""
    if not db:
        return None
    doc_id = data.get("doc_id")
    if doc_id:
        doc_ref = db.collection("aggregated_posts").document(doc_id)
    else:
        doc_ref = db.collection("aggregated_posts").document()
        if "timestamp" not in data:
            data["timestamp"] = datetime.datetime.now().isoformat()

    doc_ref.set(data, merge=True)
    return doc_ref.id


def get_post_by_id(post_id):
    """Finds a post by its sequential short ID (e.g. 101)."""
    if not db:
        return None
    # Ensure post_id is treated correctly as int or str based on storage
    docs = (
        db.collection("aggregated_posts").where("post_id", "==", post_id).limit(1).get()
    )
    return docs[0] if docs else None


def get_next_post_id():
    """Generates the next sequential ID for posts."""
    if not db:
        return 0
    counter_ref = db.collection("settings").document("counters")

    @firestore.transactional
    def update_counter(transaction, ref):
        snapshot = ref.get(transaction=transaction)
        current = snapshot.get("post_id") if snapshot.exists else 100
        new_val = current + 1
        transaction.set(ref, {"post_id": new_val}, merge=True)
        return new_val

    return update_counter(db.transaction(), counter_ref)
