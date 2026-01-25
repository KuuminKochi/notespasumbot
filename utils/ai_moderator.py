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

    async def analyze_submission(self, text, image_path=None):
        """Analyzes student submission for spam, category, and summary."""

        transcription = ""
        if image_path:
            transcription = await self.transcribe_image(image_path)

        full_context = f"Transcription: {transcription}\n\nSubmission: {text}"

        prompt = """
        You are Mimi, the Expert Editor for PASUM 25/26. Your goal is to moderate student submissions.
        Analyze this student submission and respond ONLY in JSON format.
        
        MIMI'S EDITOR PERSONALITY:
        - Professional yet cute student assistant.
        - Summary MUST be extremely concise (strictly 5-8 words).
        
        STRICT EDITING RULES:
        1. SUMMARY: Strictly 5-8 words. Direct and punchy.
        2. TAGS: Choose at least one from [#Kuaz, #Dayasari, #PASUM, #confessions, #academic, #complaint].
        3. TYPE: Classify as "news", "complaint", or "confession".
        4. NEWS-WORTHY (CRITICAL): Set is_spam=True if the content is trivial, repetitive reminders, generic greetings, insignificant operational updates, or promotional spam.
        5. HTML-FORMATTING (FOR NEWS/COMPLAINTS): 
           - If it's a "news" or "complaint", rewrite the content to be highly legible with bullet points and spacing.
           - Apply beautiful formatting (<b>, <i>, <blockquote>, emojis).
           - If it's a "confession", DO NOT reformat it. Keep the original voice and text exactly as is (just clean harmful content).
        
        Response JSON structure:
        {
            "summary": "Brief punchy headline here",
            "tags": ["#tag1", ...],
            "type": "...",
            "is_spam": false,
            "cleaned_text": "Beautifully formatted text or original confession text..."
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
