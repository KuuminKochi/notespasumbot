import json
import os
import shutil
import pytest
from utils import memory_sync, mimi_embeddings

# Test Data
TEST_ARCHIVE_PATH = "tests/test_archive.json"
TEST_VECTORS_PATH = "tests/test_vectors.json"


@pytest.fixture
def setup_test_memory():
    # 1. Backup original paths (mocking strictly for test isolation)
    original_archive = memory_sync.ARCHIVE_FILE
    original_vectors = mimi_embeddings.VECTORS_FILE

    # 2. Redirect to test files
    memory_sync.ARCHIVE_FILE = TEST_ARCHIVE_PATH
    mimi_embeddings.VECTORS_FILE = TEST_VECTORS_PATH
    mimi_embeddings.ARCHIVE_FILE = (
        TEST_ARCHIVE_PATH  # Ensure embeddings uses test path too
    )

    # 3. Create fresh test files
    with open(TEST_ARCHIVE_PATH, "w") as f:
        json.dump([], f)
    with open(TEST_VECTORS_PATH, "w") as f:
        json.dump({}, f)

    yield

    # 4. Cleanup
    if os.path.exists(TEST_ARCHIVE_PATH):
        os.remove(TEST_ARCHIVE_PATH)
    if os.path.exists(TEST_VECTORS_PATH):
        os.remove(TEST_VECTORS_PATH)

    # Restore paths
    memory_sync.ARCHIVE_FILE = original_archive
    mimi_embeddings.VECTORS_FILE = original_vectors
    mimi_embeddings.ARCHIVE_FILE = original_archive  # Restore


def test_memory_insertion_and_retrieval(setup_test_memory):
    """
    Verifies that a new fact can be added to the archive, embedded,
    and then successfully retrieved via semantic search.
    """
    # A. Insert a unique fact
    secret_fact = "Mimi secretly keeps a collection of vintage mechanical pencils in a velvet box."
    print(f"\n[Test] Injecting memory: {secret_fact}")

    success = memory_sync.add_memory_to_archive(secret_fact, "Secret")
    assert success, "Failed to add memory to archive"

    # B. Verify it exists in JSON
    with open(TEST_ARCHIVE_PATH, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["content"] == secret_fact
        print("[Test] Memory successfully written to disk.")

    # C. Verify embedding was generated
    with open(TEST_VECTORS_PATH, "r") as f:
        vectors = json.load(f)
        assert len(vectors) == 1
        print("[Test] Vector embedding generated.")

    # D. Test Retrieval (The "Intuition" Check)
    query = "Does Mimi collect anything special?"
    print(f"[Test] querying: '{query}'")

    reminiscence = memory_sync.get_proactive_reminiscence(query)
    print(f"[Test] Retrieved Intuition:\n{reminiscence}")

    assert "mechanical pencils" in reminiscence
    assert "velvet box" in reminiscence
