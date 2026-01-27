import httpx
import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()


class AIModerator:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def transcribe_image(self, image_path):
        """Uses Nemotron-Nano to transcribe image content in detail."""
        if not image_path or not os.path.exists(image_path):
            return ""

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        prompt = """Transcribe EVERYTHING in this image in complete detail. Do not summarize.
For TEXT: Copy every word exactly.
For DOCUMENTS: Include all headers, bullet points, and page numbers.
For PHOTOS: Describe colors, labels, and visible text.
Output JSON: {"transcription": "..."}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/KuuminKochi/notespasumbot",
            "X-Title": "Mimi Submission Center",
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
                                "url": f"data:image/jpeg;base64,{encoded_string}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }

        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_string}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url, headers=headers, json=payload, timeout=60.0
                )
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                data = json.loads(content)
                return data.get("transcription", "")
        except Exception as e:
            print(f"❌ Vision Error: {e}")
            return ""

    async def analyze_submission(self, text, image_path=None, strict_mode=True):
        """Analyzes student submission for spam, category, and summary.
        
        Args:
            text: The submission text
            image_path: Optional path to image file
            strict_mode: If True, enforces strict quality criteria (spam checks, length limits)
        """

        transcription = ""
        if image_path:
            transcription = await self.transcribe_image(image_path)

        full_context = f"Transcription: {transcription}\n\nSubmission: {text}"

        prompt = f"""
        You are Mimi, Expert Editor for PASUM 25/26. Your goal is to moderate student submissions.
        Analyze this student submission and respond ONLY in JSON format.

        MIMI'S EDITORIAL PERSONALITY:
        - Professional yet cute student assistant.
        - ZERO TOLERANCE for low-quality content
        - Maintain community standards as a high-quality information hub

        QUALITY CRITERIA:
        {"strict": {"summary_max_words": 6, "summary_min_words": 3, "spam_patterns": ["hi", "hello", "thanks", "test", "ok"], "greeting_keywords": ["hi there", "hey everyone"], "excessive_emoji": "😂😂😂😂😂😂😂😂😂"}}

        MODERATION MODES:
        {{"standard": {"summary_max_words": 8, "content_min_words": 2}, "strict": {"summary_max_words": 6, "summary_min_words": 3, "spam_detection": "aggressive", "relevance_required": true, "professionalism_required": true}}}

        APPLY MODE: {{"mode": "strict"}}
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": full_context},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url, headers=headers, json=payload, timeout=40.0
                )
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"❌ AI Moderation Error: {e}")
            return {
                "summary": "Mimi: Someone sent a new post!",
                "tags": ["#PASUM"],
                "type": "news",
                "is_spam": False,
                "cleaned_text": text,
            }
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": full_context},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url, headers=headers, json=payload, timeout=40.0
                )
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"❌ AI Moderation Error: {e}")
            return {
                "summary": "Mimi: Someone sent a new post!",
                "tags": ["#PASUM"],
                "type": "news",
                "is_spam": False,
                "cleaned_text": text,
            }
