import requests
import os
import base64
import json
import re
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("AIManager")


class AIManager:
    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.deepseek_url = "https://api.deepseek.com/chat/completions"

    def _call_vision_ai(self, base64_img, prompt):
        """Synchronous function to call Vision AI in a thread."""
        if not self.openrouter_key:
            return None
        url = self.openrouter_url
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
            "X-Title": "Mimi Aggregator",
        }
        payload = {
            "model": "nvidia/nemotron-nano-12b-v2-vl:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_img}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=35)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"ERROR: Vision API {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"ERROR: Vision API exception: {e}")
            return None

    async def transcribe_image(self, image_path):
        """Uses Nemotron-Nano to transcribe image content in detail."""
        if not image_path or not os.path.exists(image_path):
            logger.warning("⚠️  Vision: No image path provided or file doesn't exist")
            return ""

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        vision_prompt = """Transcribe EVERYTHING in this image in complete detail. Do not summarize.

For TEXT: Copy every word, number, and symbol exactly as written.
For DOCUMENTS: Include all text, formatting, headers, bullet points, page numbers.
For SCREENSHOTS: Transcribe all visible text, UI elements, buttons, menus.
For PHOTOS OF THINGS: Describe what you see with rich detail (colors, text, labels, brands, numbers).
For HANDWRITTEN NOTES: Read and transcribe every word and equation.

Output JSON format:
{"transcription": "...", "is_complex": true/false}

Be as thorough as possible - missing details could cause AI to misunderstand user's request."""

        logger.info(
            f"🔍 Vision: Starting transcription for {os.path.basename(image_path)}"
        )
        import asyncio

        vision_raw = await asyncio.to_thread(
            self._call_vision_ai, encoded_string, vision_prompt
        )

        if not vision_raw:
            logger.warning("⚠️  Vision: Could not analyze image")
            return ""

        try:
            clean_json = re.sub(r"```json\n|\n```", "", vision_raw).strip()
            v_data = json.loads(clean_json)
            extracted_text = v_data.get("transcription", vision_raw)
        except Exception as e:
            logger.warning(f"⚠️  Vision JSON parse error: {e}")
            extracted_text = vision_raw

        if not extracted_text or len(extracted_text) < 5:
            logger.warning("⚠️  Vision: Transcription too short or empty")
            return ""

        logger.info(
            f"✅ Vision: Successfully transcribed ({len(extracted_text)} chars): {extracted_text[:100]}..."
        )
        return extracted_text

    async def analyze_content(self, text, image_path=None, source_name="Unknown", is_confession=False, needs_vision=False):
        """Acts as an Editor to reformat content for high readability on Telegram."""

        transcription = ""
        # Only do transcription if explicitly requested (no caption) and image exists
        if needs_vision and image_path:
            transcription = await self.transcribe_image(image_path)

        if transcription:
            logger.info(f"✅ Using valid transcription ({len(transcription)} chars)")
            full_context = f"Transcription: {transcription}\n\nOriginal Message Text: {text}"
        else:
            full_context = text

        prompt = f"""
        You are the Editorial Optimizer for Mimi Aggregator (PASUM 25/26). 
        Your goal is to rewrite or author news updates into a clean, professional, and highly readable Telegram format.

        SOURCE: {source_name}
        IS_CONFESSION: {is_confession}

        EDITORIAL RULES:
        1. STRUCTURE: Use a clear headline with a relevant emoji (e.g., 📢 <b>Academic Update</b>).
        2. DYNAMIC FORMATTING:
           - IF IT'S AN EVENT (e.g., classes, tournaments): Use bullet points for structured data (📍 <b>Venue</b>, 📅 <b>Date</b>, 🕒 <b>Time</b>).
           - IF IT'S GENERAL NEWS: Provide a single high-impact sentence with 1-2 emojis. Do NOT use bullet points.
        3. TONE: Concise, "News Flash" style. Avoid robotic phrases like "This image contains".
        4. READABILITY & TRANSLATION: 
           - CRITICAL: If the content is in Malay (Bahasa Melayu) or Manglish, translate it into clear, professional English.
           - POLISH: Even if it's already English, polish it to be formal and high-readability.
        5. BREVITY: Keep the main body under 2 sentences unless the schedule is complex.
        6. NO LABELS: Do NOT use headers like "Image Analysis". The output is the final ready-to-post bulletin.

        MODERATION (LENIENT):
        - If IS_CONFESSION is false: ALLOW ALL meaningful text updates. ONLY block commercial scams, bot links, or adult content.
        - Important: If someone says "Kelas cancel esok kat DK3", Mimi should rewrite as "📢 <b>Class Cancellation</b>\n\nTomorrow's class at 📍 <b>DK3</b> has been cancelled. ✅"

        Response JSON structure:
        {{
            "is_spam": false,
            "is_complaint": false,
            "editorial_version": "...",
            "tags": ["#PASUM", "#Category"]
        }}
        """

        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": full_context},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            import asyncio

            response = await asyncio.to_thread(
                requests.post, self.deepseek_url, headers=headers, json=payload, timeout=30.0
            )
            result = response.json()

            # Check if response is valid before parsing
            if response.status_code != 200:
                logger.error(
                    f"❌ DeepSeek API Error: {response.status_code} - {result}"
                )
                return {
                    "is_spam": False,
                    "is_complaint": False,
                }

            content_raw = result["choices"][0]["message"]["content"]
            logger.info(f"🤖 AI raw output: {content_raw}")
            return json.loads(content_raw)
        except Exception as e:
            logger.error(f"❌ DeepSeek Error: {e}")
            return {
                "is_spam": False,
                "is_complaint": False,
            }
