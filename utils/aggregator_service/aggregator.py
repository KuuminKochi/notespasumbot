import os
import yaml
import imagehash
import httpx
import logging
import asyncio
import re
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from PIL import Image
from telethon import TelegramClient, events, types
from telethon.tl.functions.messages import GetForumTopicsRequest
from telethon.tl.types import Message
from utils import firebase_db, globals as g

# from .firebase_mgr import FirebaseManager
from utils.aggregator_service.ai_mgr import AIManager
# from .reply_handler import handle_reply_command

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("Aggregator")


class Aggregator:
    def __init__(
        self,
        session_name: str,
        api_id: int,
        api_hash: str,
        bot_token: str,
        dest_id: str,
        confessions_id: int,
    ):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.fb = firebase_db
        self.ai = AIManager()
        self.sources: Dict[int, Any] = self.load_config()
        self.topic_cache: Dict[str, str] = {}
        self.bot_token = bot_token
        self.dest_id = dest_id
        self.confessions_id = confessions_id
        self.processed_cache: set = set()

        # Album (Grouped Media) Buffer
        self.album_buffer: Dict[int, Dict[str, Any]] = {}
        self.album_lock = asyncio.Lock()
        self.processed_grouped_ids: set = set()  # Track processed album IDs

        # Initialize global status
        g.aggregator_status["is_running"] = True
        g.aggregator_status["start_time"] = datetime.now().isoformat()

    def load_config(self):
        # Adjusted path for unified bot structure
        config_path = "config/sources.yaml"
        if not os.path.exists(config_path):
            # Fallback if running from utils/
            config_path = "../../config/sources.yaml"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return {s["id"]: s for s in config.get("sources", [])}

    async def edit_mimi_message(
        self, dest_msg_id: str, caption: str, photo_path: Any = None
    ):
        """Edits an existing message sent by Mimi."""
        if not self.bot_token or not self.dest_id or not dest_msg_id:
            return

        if not photo_path:
            url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
            data = {
                "chat_id": self.dest_id,
                "message_id": dest_msg_id,
                "text": caption,
                "parse_mode": "HTML",
            }
        else:
            url = f"https://api.telegram.org/bot{self.bot_token}/editMessageCaption"
            data = {
                "chat_id": self.dest_id,
                "message_id": dest_msg_id,
                "caption": caption,
                "parse_mode": "HTML",
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data)
                if response.status_code != 200:
                    logger.error(f"❌ Edit failed: {response.text}")
        except Exception as e:
            logger.error(f"❌ Bot Editing Error: {e}")

    async def forward_text_to_mimi(self, text: str) -> Optional[int]:
        """Sends aggregated text content using Mimi bot token."""
        if not self.bot_token or not self.dest_id:
            return None

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "chat_id": self.dest_id,
                    "text": text,
                    "parse_mode": "HTML",
                }
                response = await client.post(url, data=data)
                if response.status_code == 200:
                    return response.json()["result"]["message_id"]
                return None
        except Exception as e:
            logger.error(f"❌ Bot Text Forwarding Error: {e}")
            return None

    async def _send_single_media(self, path, caption, media_type):
        """Helper to send a single media file."""
        if media_type == "photo":
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            field = "photo"
        elif media_type == "video":
            url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
            field = "video"
        else:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
            field = "document"

        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    data = {
                        "chat_id": self.dest_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                    }
                    response = await client.post(url, files={field: f}, data=data)
                    return (
                        response.json()["result"]["message_id"]
                        if response.status_code == 200
                        else None
                    )
        except Exception as e:
            logger.error(f"❌ Single Media Send Error: {e}")
            return None

    async def forward_media_group_to_mimi(
        self, paths: List[str], caption: str
    ) -> Optional[int]:
        """Sends a media group (album) to the destination channel."""
        if not self.bot_token or not self.dest_id or not paths:
            return None

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"
        media = []
        files = {}

        for i, path in enumerate(paths):
            ext = os.path.splitext(path)[1].lower()
            m_type = "photo"
            if ext in [".mp4", ".mov"]:
                m_type = "video"
            elif ext in [".pdf", ".zip", ".bin"]:
                m_type = "document"

            item = {"type": m_type, "media": f"attach://file{i}"}
            if i == 0:
                item["caption"] = caption
                item["parse_mode"] = "HTML"

            media.append(item)
            files[f"file{i}"] = open(path, "rb")

        try:
            async with httpx.AsyncClient() as client:
                data = {"chat_id": self.dest_id, "media": json.dumps(media)}
                response = await client.post(url, data=data, files=files, timeout=60.0)

                for f in files.values():
                    f.close()

                if response.status_code == 200:
                    return response.json()["result"][0]["message_id"]
                return None
        except Exception as e:
            logger.error(f"❌ Bot Media Group Error: {e}")
            return None

    async def get_topic_name(self, chat_id: Any, reply_to_id: Any) -> str:
        if not reply_to_id:
            return "General"

        tid = reply_to_id
        if hasattr(reply_to_id, "reply_to_msg_id"):
            tid = reply_to_id.reply_to_msg_id

        cache_key = f"{chat_id}_{tid}"
        if cache_key in self.topic_cache:
            return self.topic_cache[cache_key]

        try:
            result: Any = await self.client(
                GetForumTopicsRequest(
                    peer=chat_id,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            if result and hasattr(result, "topics"):
                for t in result.topics:
                    self.topic_cache[f"{chat_id}_{t.id}"] = t.title

            return self.topic_cache.get(cache_key, "General")
        except Exception as e:
            logger.debug(f"Could not resolve topic name: {e}")
            return "General"

    async def process_message(self, event_data: Any, is_edit: bool = False):
        """Core logic to process a message, handling both Events and Message objects."""
        message: Any = getattr(event_data, "message", None) or event_data
        if not message or not hasattr(message, "chat_id"):
            return

        if hasattr(message, "action") and message.action:
            return

        # Album Grouping
        if not is_edit and hasattr(message, "grouped_id") and message.grouped_id:
            gid = message.grouped_id

            # 1. Check in-memory processed cache (fastest)
            if gid in self.processed_grouped_ids:
                return

            # 2. Check Database for this grouped_id (persistence)
            if self.fb.is_album_processed(gid):
                self.processed_grouped_ids.add(gid)
                return

            async with self.album_lock:
                if gid not in self.album_buffer:
                    self.album_buffer[gid] = {"messages": [], "timer": None}

                self.album_buffer[gid]["messages"].append(message)

                if self.album_buffer[gid]["timer"]:
                    self.album_buffer[gid]["timer"].cancel()
                self.album_buffer[gid]["timer"] = asyncio.create_task(
                    self._process_album_after_delay(gid)
                )
            return

        await self._do_process_single(message, is_edit)

    async def _process_album_after_delay(self, gid: int):
        await asyncio.sleep(10.0)
        async with self.album_lock:
            data = self.album_buffer.pop(gid, None)
            if not data:
                return
            messages = data["messages"]
            self.processed_grouped_ids.add(gid)

        messages.sort(key=lambda x: x.id)
        lead_msg = next((m for m in messages if m.message), messages[0])
        await self._do_process_single(lead_msg, is_edit=False, album_messages=messages)

    async def _do_process_single(
        self, message: Any, is_edit: bool, album_messages: List[Any] = None
    ):
        chat_id = message.chat_id
        is_confession = chat_id == self.confessions_id

        if not is_edit:
            existing = self.fb.get_post_by_source(chat_id, message.id)
            if existing:
                return

        parent_dest_msg_id: Optional[int] = None
        parent_doc: Any = None
        if message.is_reply:
            parent_post = self.fb.get_post_by_source(chat_id, message.reply_to_msg_id)
            if parent_post:
                parent_doc = parent_post
                parent_data = parent_doc.to_dict()
                if parent_data:
                    parent_dest_msg_id = parent_data.get("dest_msg_id")

        local_paths = []
        media_type = "text"
        content_hash = None

        msgs_to_download = album_messages if album_messages else [message]
        for m in msgs_to_download:
            l_path, m_type = self._get_media_info(m)
            if l_path:
                if not os.path.exists(l_path):
                    await self.client.download_media(m, file=l_path)
                local_paths.append(l_path)
                media_type = m_type

        if local_paths:
            if not album_messages and media_type == "photo":
                content_hash = self._generate_content_hash(local_paths[0])
                if not is_edit and self.fb.check_duplicate(content_hash):
                    os.remove(local_paths[0])
                    return
            else:
                content_hash = str(abs(hash("_".join(local_paths))))
        else:
            # text only - use md5 for persistent hash
            import hashlib

            content_hash = hashlib.md5(content.encode()).hexdigest()
            if not is_edit and self.fb.check_duplicate(content_hash):
                return

        content = message.message or ""
        source_info = self.sources.get(chat_id, {})
        source_name = source_info.get("name", "Unknown Group")
        topic_name = await self.get_topic_name(chat_id, message.reply_to_msg_id)

        logger.info(
            f"🔄 Processing message {message.id} from {source_name} (media={media_type}, len={len(content)})"
        )

        # Mimi will ONLY narrate if it's an image with NO caption
        needs_vision = (media_type in ["photo", "document"]) and not content.strip()
        main_media_path = local_paths[0] if local_paths else None

        try:
            analysis = await self.ai.analyze_content(
                content,
                main_media_path,
                source_name=source_name,
                is_confession=is_confession,
                needs_vision=needs_vision,
            )
            logger.info(
                f"🤖 AI Analysis for {message.id}: spam={analysis.get('is_spam')}, complaint={analysis.get('is_complaint')}"
            )
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
            fallback_text = content if content.strip() else "🖼️ New Media Update"
            analysis = {
                "editorial_version": fallback_text,
                "is_spam": False,
                "is_complaint": False,
                "tags": [],
            }

        if analysis.get("is_spam"):
            for p in local_paths:
                if os.path.exists(p):
                    os.remove(p)
            return

        post_data: Dict[str, Any] = {
            "source_msg_id": message.id,
            "grouped_id": str(message.grouped_id)
            if hasattr(message, "grouped_id")
            else None,
            "post_id": self.fb.get_next_post_id(),
            "editorial_content": analysis.get("editorial_version", content),
            "original_caption": content,
            "tags": analysis.get("tags", []),
            "status": "confession"
            if is_confession
            else ("complaint" if analysis.get("is_complaint") else "trusted"),
            "source_group": source_name,
            "source_id": chat_id,
            "topic_name": topic_name,
            "image_url": None,
            "local_path": os.path.abspath(main_media_path) if main_media_path else None,
            "content_hash": content_hash,
            "timestamp": message.date.isoformat(),
            "media_type": media_type,
        }

        if main_media_path:
            remote_path = f"aggregated/{os.path.basename(main_media_path)}"
            post_data["image_url"] = self.fb.upload_image(main_media_path, remote_path)

        if is_edit:
            post = self.fb.get_post_by_source(chat_id, message.id)
            if post:
                post_dict = post.to_dict()
                if post_dict:
                    post_data["post_id"] = post_dict.get("post_id")
                    d_msg_id = post_dict.get("dest_msg_id")
                    if d_msg_id:
                        mimi_caption = self.format_mimi_caption(post_data)
                        await self.edit_mimi_message(
                            d_msg_id, mimi_caption, photo_path=main_media_path
                        )
                        post_data["doc_id"] = post.id
                        self.fb.save_post(post_data)
        elif parent_dest_msg_id:
            if parent_doc:
                parent_data = parent_doc.to_dict()
                if parent_data:
                    await self._handle_reply(
                        message,
                        parent_doc,
                        parent_data,
                        local_paths[0] if local_paths else None,
                    )
                    post_data["dest_msg_id"] = parent_dest_msg_id
                    self.fb.save_post(post_data)
        else:
            doc_id = self.fb.save_post(post_data)
            mimi_caption = self.format_mimi_caption(post_data)
            d_id = None
            if len(local_paths) > 1:
                d_id = await self.forward_media_group_to_mimi(local_paths, mimi_caption)
            elif local_paths:
                d_id = await self._send_single_media(
                    local_paths[0], mimi_caption, media_type
                )
            else:
                d_id = await self.forward_text_to_mimi(mimi_caption)
            if d_id:
                self.fb.update_dest_msg(doc_id, d_id)

        logger.info(f"✅ Processed: {source_name} | {message.id}")

        # Update global status
        g.aggregator_status["last_run"] = datetime.now().isoformat()
        g.aggregator_status["total_processed"] += 1
        g.aggregator_status["last_post_id"] = post_data.get("post_id")

    async def _handle_reply(
        self,
        message: Any,
        parent_post: Any,
        parent_data: Dict[str, Any],
        local_path: Optional[str],
    ):
        """Handle reply to existing post from the Scraper (internal)."""
        reply_prefix = f"\n\n💬 {message.message}"
        new_editorial = parent_data.get("editorial_content", "") + reply_prefix

        parent_data["editorial_content"] = new_editorial
        mimi_caption = self.format_mimi_caption(parent_data)
        dest_msg_id = parent_data.get("dest_msg_id")

        await self.edit_mimi_message(dest_msg_id, mimi_caption, photo_path=local_path)

        # Save update to Firebase
        self.fb.save_aggregated_post(
            {"doc_id": parent_post.id, "editorial_content": new_editorial}
        )

        logger.info(f"🔄 Appended internal scraper update to {dest_msg_id}")

    def _get_media_info(self, message: Any) -> tuple[Optional[str], str]:
        media = message.photo or message.document or message.video
        if not media:
            return None, "text"
        m_type = "photo"
        if message.video:
            m_type = "video"
        elif message.document:
            m_type = "document"
        ext = ".jpg" if message.photo else (".mp4" if message.video else ".bin")
        if message.document:
            for attr in getattr(message.document, "attributes", []):
                if isinstance(attr, types.DocumentAttributeFilename):
                    ext = os.path.splitext(attr.file_name)[1]
                    break
        file_name = f"{message.date.strftime('%Y%m%d_%H%M%S')}_{message.id}{ext}"
        return os.path.join("downloads", file_name), m_type

    def _generate_content_hash(self, local_path: str) -> Optional[str]:
        try:
            img = Image.open(local_path)
            return str(imagehash.phash(img))
        except:
            return None

    def format_mimi_caption(self, data: Dict[str, Any]) -> str:
        post_id = data.get("post_id")
        editorial = data.get("editorial_content", "")
        original = data.get("original_caption", "")
        source = data.get("source_group", "Unknown")

        text = editorial if editorial else "New Update"

        orig_section = ""
        if original and original.strip() != editorial.strip():
            orig_section = f"\n\n---\n<blockquote>{original}</blockquote>"

        try:
            ts = datetime.fromisoformat(data.get("timestamp", "")).strftime("%I:%M %p")
        except:
            ts = datetime.now().strftime("%I:%M %p")

        return f"{text}{orig_section}\n\n▫️ #ID{post_id} • 📍 {source} • 🕒 {ts}"

    async def sync_history(self):
        logger.info("🔍 Starting deep sync of history...")
        for chat_id, source_config in self.sources.items():
            source_name = source_config.get("name", "Unknown")
            topics = source_config.get("topics", [])
            logger.info(f"📡 Checking {source_name} (General Feed)...")
            try:
                msgs = await self.client.get_messages(chat_id, limit=50)
                if msgs:
                    msgs.sort(key=lambda x: x.date)
                    for msg in msgs:
                        await self.process_message(msg)
            except Exception as e:
                logger.error(f"❌ Sync error: {e}")

            if topics:
                for topic in topics:
                    try:
                        msgs = await self.client.get_messages(
                            chat_id, limit=50, reply_to=topic["id"]
                        )
                        if msgs:
                            msgs.sort(key=lambda x: x.date)
                            for msg in msgs:
                                await self.process_message(msg)
                    except Exception as e:
                        logger.error(f"❌ Topic Sync error: {e}")
        logger.info("🎯 History sync complete.")

    async def start(self):
        # Start User Client (Scraper)
        await self.client.start()
        logger.info("📡 User Client: Populating entity cache...")
        await self.client.get_dialogs()

        # Start Bot Client (Interaction) - DISABLED
        # await self.bot.start(bot_token=self.bot_token)
        # logger.info("🤖 Bot Client: Online and listening.")

        # Disabled historical sync to only listen for new news
        # try:
        #     await self.sync_history()
        # except Exception as e: logger.error(f"❌ Sync failed: {e}")

        # --- User Client Handlers (Scraping) ---
        @self.client.on(events.MessageEdited(chats=list(self.sources.keys())))
        async def edit_handler(event: Any):
            await self.process_message(event, is_edit=True)

        @self.client.on(events.NewMessage(chats=list(self.sources.keys())))
        async def handler(event: Any):
            await self.process_message(event)

        # --- Bot Client Handlers (Interaction) - DISABLED
        # @self.bot.on(events.NewMessage(pattern=r"/reply\s+(\d+)\s+(.+)"))
        # async def reply_handler(event: Any): await handle_reply_command(self, event)

        logger.info("🚀 Mimi Aggregator Live (Scraper Only).")

        # Run only user client
        await self.client.run_until_disconnected()
