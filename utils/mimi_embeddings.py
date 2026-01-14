import requests
import json
import os
import math
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Paths (Absolute paths as per AGENTS.md)
PROJECT_ROOT = "/home/kuumin/Development/Projects/notespasumbot"
CLI_ROOT = "/home/kuumin/Projects/mimi-cli"
VECTORS_FILE = os.path.join(CLI_ROOT, "mimi_memory_vectors.json")
ARCHIVE_FILE = os.path.join(CLI_ROOT, "mimi_memory_archive.json")

# Caches
_http_session = None


def get_session():
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def get_embedding(text: str) -> Optional[List[float]]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    session = get_session()
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/text-embedding-3-small",
        "input": text.replace("\n", " "),
    }

    try:
        res = session.post(url, headers=headers, json=payload, timeout=10)
        if res.ok:
            data = res.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
        else:
            print(f"[Embeddings] API Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[Embeddings] Connection failed: {e}")
    return None


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def load_vectors() -> Dict[str, List[float]]:
    if not os.path.exists(VECTORS_FILE):
        return {}
    try:
        with open(VECTORS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_vectors(vectors: Dict[str, List[float]]):
    try:
        with open(VECTORS_FILE, "w", encoding="utf-8") as f:
            json.dump(vectors, f)
    except Exception as e:
        print(f"Failed to save vectors: {e}")


def semantic_search(query_text: str, top_k: int = 3) -> List[Dict]:
    """Returns the most relevant memories from the archive using semantic similarity."""
    if not os.path.exists(ARCHIVE_FILE):
        return []

    # Get query embedding
    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    # Load archive and vectors
    try:
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            archive = json.load(f)
        vectors = load_vectors()
    except:
        return []

    if not archive or not vectors:
        return []

    scored_memories = []
    for item in archive:
        mem_id = str(item.get("id"))
        if mem_id in vectors:
            sim = cosine_similarity(query_vector, vectors[mem_id])
            if sim > 0.25:  # Slightly lower threshold for broader recall
                scored_memories.append((sim, item))

    scored_memories.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_memories[:top_k]]
