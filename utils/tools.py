import requests
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import io
import pypdf
import logging
from utils import memory_sync, validator

logger = logging.getLogger(__name__)


def web_search(query: str) -> str:
    """Searches DuckDuckGo for the query."""
    try:
        results = list(DDGS().text(query, max_results=3))
        if not results:
            return "No results found."

        output = []
        for r in results:
            output.append(f"[{r['title']}]({r['href']})\n{r['body']}")
        return "\n\n".join(output)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search Error: {e}"


def web_fetch(url: str) -> str:
    """Fetches text content from a URL (supports PDF)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()

        content_type = res.headers.get("Content-Type", "").lower()

        # PDF Handling
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(io.BytesIO(res.content))
                text = []
                for page in reader.pages:
                    text.append(page.extract_text())
                return f"--- PDF Content ({url}) ---\n" + "\n".join(text)[:5000]
            except Exception as e:
                return f"PDF Error: {e}"

        # HTML Handling
        soup = BeautifulSoup(res.text, "html.parser")
        # Remove scripts and styles
        for script in soup(["script", "style", "nav", "footer", "iframe"]):
            script.decompose()

        text = soup.get_text(separator="\n")
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text[:5000]  # Limit context

    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return f"Fetch Error: {e}"


def perform_memory_search(query: str, user_id: int) -> str:
    """Explicit semantic search."""
    # We can reuse the proactive logic but maybe with more results
    try:
        results = memory_sync.get_proactive_reminiscence(user_id, query)
        if not results:
            return "No relevant long-term memories found."
        return results
    except Exception as e:
        return f"Memory Search Error: {e}"


def execute_add_memory(content: str, user_id: int, category: str = "Mimi") -> str:
    """Bridge to the validator."""
    return validator.process_add_memory(content, user_id, category)
