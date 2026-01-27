import os
import datetime
import time
from utils import firebase_db
# from .firebase_mgr import FirebaseManager


def cleanup_task():
    print("🧹 Starting 3-day local cache cleanup...")
    fb = firebase_db
    # old_posts = fb.get_old_posts(days=3) # We need to implement this in firebase_db if missing
    # For now, let's just implement get_old_posts logic using existing db ref
    cutoff = datetime.datetime.now() - datetime.timedelta(days=3)
    try:
        old_posts = fb.db.collection("aggregated_posts") \
            .where("created_at", "<", cutoff) \
            .where("local_path", "!=", None) \
            .stream()
    except Exception as e:
        print(f"Cleanup error: {e}")
        return

    count = 0
    for doc in old_posts:
        data = doc.to_dict()
        path = data.get("local_path")

        if path and os.path.exists(path):
            try:
                os.remove(path)
                # fb.mark_cleaned(doc.id)
                doc.reference.update({"local_path": None})
                count += 1
            except Exception as e:
                print(f"❌ Failed to delete {path}: {e}")

    print(f"✨ Cleanup finished. Removed {count} files.")


if __name__ == "__main__":
    # For testing standalone
    cleanup_task()
