from concurrent.futures import ThreadPoolExecutor
import os

# Create a shared thread pool for I/O bound tasks (API calls, DB writes)
# We use a high number because these threads mostly just wait for network responses
# and don't consume much CPU.
MAX_WORKERS = int(os.getenv("MAX_THREADS", 50))

pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="MimiWorker")


def get_pool():
    return pool
