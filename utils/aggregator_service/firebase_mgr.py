import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import datetime
import logging

logger = logging.getLogger("FirebaseMgr")


class FirebaseManager:
    def __init__(self):
        cred_path = os.getenv("FIREBASE_CREDENTIALS", "service-account.json")
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            # Try to use the provided bucket name, or fall back to default
            if not bucket_name:
                bucket_name = f"{cred.project_id}.appspot.com"

            logger.info(f"Initializing Firebase with bucket: {bucket_name}")
            try:
                firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
            except Exception as e:
                logger.error(f"Firebase initialization error: {e}")
                firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        try:
            self.bucket = storage.bucket()
            # If bucket name was wrong, this might fail or return a bucket that doesn't exist
            if not self.bucket.exists():
                logger.warning(f"⚠️  Storage Bucket '{self.bucket.name}' not found. Trying project default...")
                self.bucket = storage.bucket(f"{cred.project_id}.appspot.com")
                if not self.bucket.exists():
                    logger.warning("⚠️  Project default bucket also not found. Image upload disabled.")
                    self.bucket = None
        except Exception as e:
            logger.error(f"⚠️  Storage initialization failed: {e}")
            self.bucket = None

    def is_album_processed(self, grouped_id: int) -> bool:
        """Checks if a grouped_id has already been processed."""
        if not grouped_id:
            return False
        docs = (
            self.db.collection("aggregated_posts")
            .where("grouped_id", "==", str(grouped_id))
            .limit(1)
            .stream()
        )
        return any(docs)

    def save_post(self, data):
        """Saves post metadata to Firestore with auto post_id generation."""
        doc_id = data.get("doc_id") or None

        # Auto-generate post_id for source posts if not provided
        if "post_id" not in data:
            data["post_id"] = self.get_next_post_id()

        if doc_id:
            doc_ref = self.db.collection("aggregated_posts").document(doc_id)
        else:
            doc_ref = self.db.collection("aggregated_posts").document()
            data["created_at"] = datetime.datetime.now()

        doc_ref.set(data, merge=True)
        return doc_ref.id

    def get_post_by_source(self, source_id, source_msg_id):
        """Finds a post by its source group and message ID."""
        docs = (
            self.db.collection("aggregated_posts")
            .where("source_id", "==", source_id)
            .where("source_msg_id", "==", source_msg_id)
            .limit(1)
            .get()
        )
        if docs:
            return docs[0]
        return None

    def get_post_by_id(self, post_id):
        """Find a post by post_id (user submissions) or source_msg_id (source posts)."""
        # Try post_id first (user submissions)
        docs = (
            self.db.collection("aggregated_posts")
            .where("post_id", "==", post_id)
            .limit(1)
            .get()
        )
        if docs:
            return docs[0]

        # Try source_msg_id (source posts) - convert to int
        try:
            post_id_int = int(post_id)
            docs = (
                self.db.collection("aggregated_posts")
                .where("source_msg_id", "==", post_id_int)
                .limit(1)
                .get()
            )
            if docs:
                return docs[0]
        except (ValueError, TypeError):
            pass

        return None

    def get_next_post_id(self) -> int:
        """Get next sequential post ID."""
        docs = (
            self.db.collection("aggregated_posts")
            .where("post_id", "!=", None)
            .order_by("post_id", direction=firestore.Query.DESCENDING)
            .limit(1)
            .get()
        )
        if docs:
            return docs[0].to_dict().get("post_id", 0) + 1
        return 1

    def update_dest_msg(self, doc_id, dest_msg_id):
        """Updates the destination message ID for a post."""
        self.db.collection("aggregated_posts").document(doc_id).update(
            {"dest_msg_id": dest_msg_id}
        )

    def upload_image(self, local_path, remote_path):
        """Uploads image to Firebase Storage and returns public URL."""
        if not self.bucket:
            return None
        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            print(f"❌ Storage Upload Error: {e}")
            return None

    def get_old_posts(self, days=3):
        """Retrieves posts older than N days with local paths."""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        docs = (
            self.db.collection("aggregated_posts")
            .where("created_at", "<", cutoff)
            .where("local_path", "!=", None)
            .stream()
        )
        return docs

    def mark_cleaned(self, doc_id):
        """Updates doc to reflect local file was deleted."""
        self.db.collection("aggregated_posts").document(doc_id).update(
            {"local_path": None}
        )

    def check_duplicate(self, content_hash):
        """Checks if a content hash already exists recently."""
        if not content_hash:
            return False
        docs = (
            self.db.collection("aggregated_posts")
            .where("content_hash", "==", content_hash)
            .limit(1)
            .get()
        )
        if not docs:
            return False

        # Check if it was in the last 24 hours in Python to avoid index requirement
        doc = docs[0]
        if not doc:
            return False

        post_data = doc.to_dict()
        if not post_data:
            return False

        created_at = post_data.get("created_at")
        if created_at:
            # Handle both datetime objects and ISO strings
            if isinstance(created_at, str):
                try:
                    created_at = datetime.datetime.fromisoformat(created_at)
                except:
                    return True  # Assume duplicate if parse fails but hash matches

            # Make sure it's offset-naive for comparison if needed, or just compare deltas
            # Firestore usually returns localized datetimes.
            now = (
                datetime.datetime.now(created_at.tzinfo)
                if created_at.tzinfo
                else datetime.datetime.now()
            )
            if (now - created_at).total_seconds() < 86400:  # 24 hours
                return True
        return False
