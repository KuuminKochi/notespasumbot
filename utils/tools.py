import requests
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import io
import pypdf
import logging
import concurrent.futures
from typing import List
from utils import memory_sync, validator

logger = logging.getLogger(__name__)


def web_search(query: str) -> str:
    try:
        logger.info(f"Searching for: {query}")
        # Try DDGS Text Search with Region Pinning
        # 'wt-wt' is global, 'my-en' is Malaysia English. Using 'wt-wt' for broader coverage unless specific.
        # But user query specific to Malaysia needs region.
        # Let's try 'wt-wt' first, but if query contains "Malaysia", switch?
        # Actually, let's keep it simple: generic search first.

        # Heuristic: If query asks for "news", prioritize 'news' backend
        if any(
            k in query.lower() for k in ["news", "latest", "update", "today", "202"]
        ):
            backends = ["news", "text"]
        else:
            backends = ["text", "news"]

        blacklist = [
            "Sign in",
            "Log in",
            "Microsoft Support",
            "Zillow",
            "Facebook - log in",
            "Google",
            "哔哩哔哩",
            "知乎",
        ]

        for backend in backends:
            try:
                if backend == "text":
                    raw_results = list(
                        DDGS().text(query, max_results=5, region="wt-wt")
                    )
                else:
                    raw_results = list(
                        DDGS().news(query, max_results=5, region="wt-wt")
                    )

                # Filter Garbage
                valid_results = []
                for r in raw_results:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    # Skip if title matches blacklist
                    if any(bad in title for bad in blacklist):
                        continue
                    # Skip if body is too short or empty
                    if len(body) < 20:
                        continue
                    valid_results.append(r)

                if valid_results:
                    results = valid_results
                    break  # Found good results

            except Exception as inner_e:
                logger.warning(f"Backend {backend} failed: {inner_e}")
                continue

        if not results:
            logger.warning(f"No valid results found for: {query}")
            return "No relevant results found."

        output = []
        for r in results:
            title = r.get("title", "No Title")
            href = r.get("href", "#")
            body = r.get("body", "No Content")
            source = r.get("source", "Web")
            logger.info(f"Found: {title} ({href})")
            output.append(f"[{title}]({href}) - {source}\n{body}")

        return "\n\n".join(output)
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}")
        return f"Search error: {e}"


def web_batch_search(queries: List[str]) -> str:
    """Executes multiple search queries in parallel."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_query = {executor.submit(web_search, q): q for q in queries}
        for future in concurrent.futures.as_completed(future_to_query):
            q = future_to_query[future]
            try:
                data = future.result()
                results.append(f"--- Results for: {q} ---\n{data}")
            except Exception as e:
                results.append(f"--- Results for: {q} ---\nError: {e}")
    return "\n\n".join(results)


def web_fetch(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()

        content_type = res.headers.get("Content-Type", "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(io.BytesIO(res.content))
                text = []
                for page in reader.pages:
                    text.append(page.extract_text())
                return f"--- PDF Content ({url}) ---\n" + "\n".join(text)[:20000]
            except Exception as e:
                return f"Error parsing PDF: {e}"

        soup = BeautifulSoup(res.text, "html.parser")

        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        text = soup.get_text(separator="\n")

        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text[:15000]
    except Exception as e:
        return f"Fetch error: {e}"


def web_batch_fetch(urls: List[str]) -> str:
    """Fetches multiple URLs in parallel."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(web_fetch, u): u for u in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            u = future_to_url[future]
            try:
                data = future.result()
                results.append(f"--- Content of: {u} ---\n{data[:5000]}...")
            except Exception as e:
                results.append(f"--- Content of: {u} ---\nError: {e}")
    return "\n\n".join(results)


def perform_memory_search(query: str, user_id: int) -> str:
    """Explicit semantic search."""
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
