"""
AI Coding Mentor API.

Run from the Backend folder:
    uvicorn main:app --reload --port 8002
"""

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import judge
from code_runner import SUPPORTED_LANGUAGES, normalize_language, sandbox_identity
from database import supabase
from queue_service import enqueue_submission, is_queue_available
from rag.rag_service import MentorUnavailableError, ask_mentor

try:
    from supabase_auth.errors import AuthError
except ImportError:  # older supabase-py
    from gotrue.errors import AuthError  # type: ignore

logger = logging.getLogger("api")

app = FastAPI(
    title="AI Coding Mentor API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=config.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CodeRequest(BaseModel):
    problem_id: int = Field(gt=0)
    code: str = Field(max_length=config.MAX_CODE_CHARS)
    language: str = "python"


class SubmitRequest(CodeRequest):
    pass


class MentorRequest(BaseModel):
    problem_id: int = Field(gt=0)
    code: str = Field(default="", max_length=config.MAX_CODE_CHARS)
    question: str = Field(default="", max_length=2000)
    language: str = "python"
    conversation: List[Any] = Field(default_factory=list, max_length=60)
    # Short summary of the latest Run result, so the mentor can debug failures.
    run_summary: str = Field(default="", max_length=4000)


# =============================================================================
# HELPERS
# =============================================================================

class RateLimiter:
    """
    Small in-memory sliding-window limiter (per user, per action).
    Protects the server and the Gemini quota on a public demo. For several
    server instances, move this to Redis.
    """

    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(self.window - (now - hits[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Please wait {retry_after} seconds and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


rate_limiter = RateLimiter()


def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """FastAPI dependency: validate the Supabase access token and return the user id."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    access_token = authorization.split(" ", 1)[1].strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")

    try:
        user_response = supabase.auth.get_user(access_token)
    except AuthError:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Please sign in again.",
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Auth service error")
        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable. Please try again.",
        ) from error

    user = getattr(user_response, "user", None)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Please sign in again.",
        )
    return user.id


def validate_language(language: str) -> str:
    value = normalize_language(language)
    if value not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported language. Choose Python, Java, C++, or C.",
        )
    return value


def fetch_problem(problem_id: int, columns: str = "*") -> Dict[str, Any]:
    try:
        response = (
            supabase
            .table("problems")
            .select(columns)
            .eq("id", problem_id)
            .limit(1)
            .execute()
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not load problem %s", problem_id)
        raise HTTPException(status_code=502, detail="Could not load the problem.") from error

    if not response.data:
        raise HTTPException(status_code=404, detail="Problem not found.")
    return response.data[0]


def format_conversation_history(conversation: List[Any], limit: int = 10) -> str:
    lines = []
    for message in (conversation or [])[-limit:]:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue

        content = message.get("content", "")
        if isinstance(content, dict):
            content = "\n".join(
                f"{key}: {content[key]}"
                for key in ("answer", "approach", "how_it_works", "time_complexity",
                            "space_complexity", "good_points", "improvements")
                if content.get(key)
            )

        content = str(content).strip()
        if not content:
            continue
        if len(content) > 1500:
            content = content[:1500] + " ..."

        lines.append(f"{'Student' if role == 'user' else 'Mentor'}: {content}")

    return "\n\n".join(lines)


def _judge_in_background(submission_id: int, problem_id: int, code: str, language: str) -> None:
    try:
        judge.process_submission(submission_id, problem_id, code, language)
    except Exception:  # noqa: BLE001 - already logged and saved as "Error"
        pass


# =============================================================================
# ROUTES
# =============================================================================

@app.get("/")
def home():
    return {"message": "Welcome to AI Coding Mentor"}


@app.get("/health")
def health():
    queue_ok = None
    if config.SUBMISSION_MODE != "inline":
        queue_ok = is_queue_available()
    return {
        "status": "ok",
        "submission_mode": config.SUBMISSION_MODE,
        "queue_available": queue_ok,
        # True when user code runs as a separate, unprivileged OS user.
        "sandboxed": sandbox_identity() is not None,
    }


@app.get("/problems")
def get_problems():
    try:
        response = supabase.table("problems").select("*").order("id").execute()
        return response.data or []
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not load problems")
        raise HTTPException(status_code=502, detail="Could not load problems.") from error


@app.get("/problems/{problem_id}")
def get_problem(problem_id: int):
    return fetch_problem(problem_id)


@app.get("/problems/{problem_id}/test-cases")
def get_test_cases_endpoint(problem_id: int):
    try:
        return judge.get_test_cases(problem_id)
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not load test cases for %s", problem_id)
        raise HTTPException(status_code=502, detail="Could not load test cases.") from error


@app.post("/run")
def run_code(
    request: CodeRequest,
    user_id: str = Depends(get_current_user_id),
):
    rate_limiter.check(f"run:{user_id}", config.RATE_LIMIT_RUN_PER_MIN)
    language = validate_language(request.language)

    try:
        evaluation = judge.evaluate(request.problem_id, request.code, language)
    except Exception as error:  # noqa: BLE001
        logger.exception("Run failed")
        raise HTTPException(status_code=500, detail="Code execution failed. Please try again.") from error

    results = evaluation["results"]
    if evaluation["total"] == 0:
        raise HTTPException(status_code=404, detail=evaluation["message"])

    first = results[0]
    return {
        "status": evaluation["status"],
        "message": evaluation["message"],
        "passed": evaluation["passed"],
        "total": evaluation["total"],
        "results": results,
        # Fields kept for backward compatibility with older frontends:
        "output": first["actual"],
        "error": first["error"],
        "exit_code": first["exit_code"],
        "input": first["input"],
        "expected": first["expected"],
        "testCaseId": 0,
    }


@app.post("/submit", status_code=202)
def submit_code(
    request: SubmitRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    rate_limiter.check(f"submit:{user_id}", config.RATE_LIMIT_SUBMIT_PER_MIN)
    language = validate_language(request.language)
    fetch_problem(request.problem_id, "id")

    try:
        insert_response = (
            supabase
            .table("submissions")
            .insert(
                {
                    "user_id": user_id,
                    "problem_id": request.problem_id,
                    "code": request.code,
                    "language": language,
                    "status": "Queued",
                    "passed": 0,
                    "total": 0,
                }
            )
            .execute()
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not create submission")
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not save the submission. If Row Level Security is enabled, "
                "make sure the backend uses the service-role key."
            ),
        ) from error

    if not insert_response.data:
        raise HTTPException(status_code=502, detail="Submission record could not be created.")

    submission_id = int(insert_response.data[0]["id"])
    mode = config.SUBMISSION_MODE
    job_id = None
    use_queue = mode == "queue" or (mode == "auto" and is_queue_available())

    if use_queue:
        try:
            job_id = enqueue_submission(submission_id, request.problem_id, request.code, language).id
        except Exception as error:  # noqa: BLE001
            logger.exception("Could not enqueue submission %s", submission_id)
            if mode == "queue":
                judge.update_submission(submission_id, {"status": judge.STATUS_ERROR})
                raise HTTPException(
                    status_code=503,
                    detail="Could not queue the submission. Make sure Redis and the worker are running.",
                ) from error
            use_queue = False

    if not use_queue:
        # Redis is not available: judge inside the API process after responding.
        background_tasks.add_task(
            _judge_in_background, submission_id, request.problem_id, request.code, language
        )

    return {
        "status": "Queued",
        "submission_id": submission_id,
        "job_id": job_id,
        "mode": "queue" if use_queue else "inline",
        "passed": 0,
        "total": 0,
        "message": "Submission received. Judging...",
    }


@app.get("/submission/{submission_id}")
def get_submission(
    submission_id: int,
    user_id: str = Depends(get_current_user_id),
):
    try:
        response = (
            supabase
            .table("submissions")
            .select("id, problem_id, language, status, passed, total, created_at")
            .eq("id", submission_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not load submission %s", submission_id)
        raise HTTPException(status_code=502, detail="Could not load the submission.") from error

    if not response.data:
        raise HTTPException(status_code=404, detail="Submission not found.")

    submission = response.data[0]
    submission["is_final"] = submission.get("status") in judge.FINAL_STATUSES
    return submission


@app.get("/submissions/{problem_id}")
def get_submissions(
    problem_id: int,
    user_id: str = Depends(get_current_user_id),
):
    try:
        response = (
            supabase
            .table("submissions")
            .select("id, problem_id, code, language, status, passed, total, created_at")
            .eq("problem_id", problem_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data or []
    except Exception as error:  # noqa: BLE001
        logger.exception("Could not load submission history")
        raise HTTPException(status_code=502, detail="Could not load submission history.") from error


@app.post("/mentor")
def mentor(
    request: MentorRequest,
    user_id: str = Depends(get_current_user_id),
):
    rate_limiter.check(f"mentor:{user_id}", config.RATE_LIMIT_MENTOR_PER_MIN)
    problem = fetch_problem(request.problem_id, "title, description, topic, difficulty")
    language = normalize_language(request.language)

    question = request.question.strip() or (
        "Analyze my solution: explain the approach, time and space complexity, "
        "what is good, and what I can improve."
    )

    try:
        result = ask_mentor(
            question=question,
            problem_title=problem.get("title", ""),
            code=request.code,
            language=language,
            problem_description=problem.get("description", "") or "",
            difficulty=problem.get("difficulty", "") or "",
            topic=problem.get("topic", "") or "",
            history=format_conversation_history(request.conversation),
            run_summary=request.run_summary,
        )
    except MentorUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        logger.exception("Mentor failed")
        raise HTTPException(status_code=500, detail="AI Mentor failed. Please try again.") from error

    return {
        "problem_id": request.problem_id,
        "question": question,
        **result,
    }
