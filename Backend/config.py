"""
Central configuration for the AI Coding Mentor backend.

Every module reads settings from here instead of calling os.getenv()
directly, so defaults live in one place and .env is loaded exactly once.
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Load Backend/.env no matter which directory the process is started from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _protect_process_secrets() -> None:
    """
    On Linux, any process running as the same user can read
    /proc/<pid>/environ of this server - including the user code we execute,
    which would expose the Supabase service key and the Gemini key.
    Marking the process non-dumpable makes those /proc files root-owned, so
    child programs can no longer read them (and blocks ptrace as well).
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        PR_SET_DUMPABLE = 4
        libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    except Exception:  # noqa: BLE001 - best effort hardening
        pass


_protect_process_secrets()


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()

# The backend writes submissions on behalf of users, so it should use the
# service-role key (never expose it to the frontend). SUPABASE_KEY is kept
# for backward compatibility with the existing .env.
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
).strip()

# ---------------------------------------------------------------------------
# Gemini / RAG
# ---------------------------------------------------------------------------

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or ""
).strip()

# Primary model first, then fallbacks (comma separated in .env).
GEMINI_MODELS = _get_list(
    "GEMINI_MODELS",
    ["gemini-3.6-flash", "gemini-3.5-flash-lite"],
)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = _get_int("EMBEDDING_DIMENSIONS", 768)

RAG_MATCH_COUNT = _get_int("RAG_MATCH_COUNT", 5)
try:
    RAG_MATCH_THRESHOLD = float(os.getenv("RAG_MATCH_THRESHOLD", "0.35"))
except ValueError:
    RAG_MATCH_THRESHOLD = 0.35

# ---------------------------------------------------------------------------
# Redis / RQ
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_NAME = os.getenv("QUEUE_NAME", "coding-mentor")

# auto   -> use Redis if reachable, otherwise judge in a FastAPI background task
# queue  -> always use Redis (fail if Redis is down)
# inline -> never use Redis (handy for local development)
SUBMISSION_MODE = os.getenv("SUBMISSION_MODE", "auto").strip().lower()

# ---------------------------------------------------------------------------
# Code execution limits
# ---------------------------------------------------------------------------

RUN_TIMEOUT_SECONDS = _get_int("RUN_TIMEOUT_SECONDS", 5)
COMPILE_TIMEOUT_SECONDS = _get_int("COMPILE_TIMEOUT_SECONDS", 20)
MEMORY_LIMIT_MB = _get_int("MEMORY_LIMIT_MB", 256)
MAX_CODE_CHARS = _get_int("MAX_CODE_CHARS", 50_000)
MAX_PARALLEL_TESTS = _get_int("MAX_PARALLEL_TESTS", 4)

# Run untrusted code as this OS user (Linux, server running as root - the
# Docker image sets SANDBOX_USER=sandbox). Empty = run as the server user.
SANDBOX_USER = (os.getenv("SANDBOX_USER") or "").strip()
# Max processes + threads the sandbox user may have at once (stops fork bombs).
SANDBOX_MAX_PROCESSES = _get_int("SANDBOX_MAX_PROCESSES", 256)

# ---------------------------------------------------------------------------
# Rate limits (requests per user per minute, 0 = unlimited)
# ---------------------------------------------------------------------------

RATE_LIMIT_RUN_PER_MIN = _get_int("RATE_LIMIT_RUN_PER_MIN", 20)
RATE_LIMIT_SUBMIT_PER_MIN = _get_int("RATE_LIMIT_SUBMIT_PER_MIN", 10)
RATE_LIMIT_MENTOR_PER_MIN = _get_int("RATE_LIMIT_MENTOR_PER_MIN", 8)

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# Optional regex for extra allowed origins, e.g. Vercel preview deployments:
#   CORS_ORIGIN_REGEX=https://codementor-.*\.vercel\.app
CORS_ORIGIN_REGEX = (os.getenv("CORS_ORIGIN_REGEX") or "").strip() or None

CORS_ORIGINS = _get_list(
    "CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5175",
    ],
)
