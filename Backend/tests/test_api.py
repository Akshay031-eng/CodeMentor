from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import config
import judge
import main
import queue_service
from rag import rag_service
from reference_solutions import SOLUTIONS
from fake_supabase import FakeSupabase

TOKEN = "token-alice"
OTHER_TOKEN = "token-bob"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
OTHER_AUTH = {"Authorization": f"Bearer {OTHER_TOKEN}"}


@pytest.fixture()
def db(monkeypatch):
    fake = FakeSupabase(
        tables={
            "problems": [
                {"id": 2, "title": "Binary Search", "description": "Find target.", "topic": "Binary Search", "difficulty": "Easy"},
                {"id": 1, "title": "Two Sum", "description": "Find two numbers.", "topic": "Hashing", "difficulty": "Easy"},
            ],
            "test_cases": [
                {"id": 11, "problem_id": 1, "input": "nums=[2,7,11,15], target=9", "expected_output": "[0,1]"},
                {"id": 12, "problem_id": 1, "input": "nums=[3,2,4], target=6", "expected_output": "[1,2]"},
                {"id": 13, "problem_id": 1, "input": "nums=[3,3], target=6", "expected_output": "[0,1]"},
            ],
            "knowledge_documents": [
                {"title": "Two Sum Pattern", "category": "DSA", "content": "Use a hash map.", "similarity": 0.82},
            ],
        },
        tokens={TOKEN: "user-alice", OTHER_TOKEN: "user-bob"},
    )
    for module in (main, judge, rag_service):
        monkeypatch.setattr(module, "supabase", fake)
    monkeypatch.setattr(config, "SUBMISSION_MODE", "inline")
    return fake


@pytest.fixture()
def client(db):
    main.rate_limiter._hits.clear()
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

def test_problems_are_listed_in_order(client):
    response = client.get("/problems")
    assert response.status_code == 200
    assert [problem["id"] for problem in response.json()] == [1, 2]


def test_unknown_problem_returns_404(client):
    response = client.get("/problems/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Problem not found."


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def test_run_requires_login(client):
    response = client.post("/run", json={"problem_id": 1, "code": "x", "language": "python"})
    assert response.status_code == 401


def test_run_accepted(client):
    response = client.post(
        "/run", headers=AUTH,
        json={"problem_id": 1, "code": SOLUTIONS["python"][1], "language": "python"},
    )
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "Accepted"
    assert (body["passed"], body["total"]) == (3, 3)
    assert body["results"][0]["input"] == "nums=[2,7,11,15], target=9"


def test_run_wrong_answer_and_compile_error(client):
    wrong = "def two_sum(nums, target):\n    print('checking')\n    return [9, 9]\n"
    body = client.post("/run", headers=AUTH, json={"problem_id": 1, "code": wrong}).json()
    assert body["status"] == "Wrong Answer"
    assert body["results"][0]["stdout"] == "checking"

    broken = "def two_sum(nums, target)\n    return []\n"
    body = client.post("/run", headers=AUTH, json={"problem_id": 1, "code": broken}).json()
    assert body["status"] == "Compilation Error"
    assert "SyntaxError" in body["message"]


def test_run_rejects_unknown_language(client):
    response = client.post("/run", headers=AUTH, json={"problem_id": 1, "code": "x", "language": "ruby"})
    assert response.status_code == 400


def test_run_rejects_oversized_code(client):
    response = client.post(
        "/run", headers=AUTH,
        json={"problem_id": 1, "code": "#" * (config.MAX_CODE_CHARS + 1)},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

def test_submit_inline_mode_judges_and_saves(client, db):
    response = client.post(
        "/submit", headers=AUTH,
        json={"problem_id": 1, "code": SOLUTIONS["python"][1], "language": "python"},
    )
    body = response.json()
    assert response.status_code == 202, body
    assert body["mode"] == "inline"

    # TestClient runs background tasks before returning, so the verdict is final.
    status = client.get(f"/submission/{body['submission_id']}", headers=AUTH).json()
    assert status["status"] == "Accepted"
    assert (status["passed"], status["total"]) == (3, 3)
    assert status["is_final"] is True

    history = client.get("/submissions/1", headers=AUTH).json()
    assert len(history) == 1 and history[0]["status"] == "Accepted"


def test_users_cannot_see_each_others_submissions(client):
    body = client.post(
        "/submit", headers=AUTH,
        json={"problem_id": 1, "code": SOLUTIONS["python"][1]},
    ).json()
    assert client.get(f"/submission/{body['submission_id']}", headers=OTHER_AUTH).status_code == 404
    assert client.get("/submissions/1", headers=OTHER_AUTH).json() == []


def test_submit_through_redis_queue_and_worker(client, db, monkeypatch):
    if not queue_service.is_queue_available():
        pytest.skip("Redis is not running")

    from rq import SimpleWorker

    queue_service.submission_queue.empty()
    monkeypatch.setattr(config, "SUBMISSION_MODE", "queue")

    body = client.post(
        "/submit", headers=AUTH,
        json={"problem_id": 1, "code": SOLUTIONS["cpp"][1], "language": "c++"},
    ).json()
    assert body["mode"] == "queue" and body["job_id"]
    assert client.get(f"/submission/{body['submission_id']}", headers=AUTH).json()["status"] == "Queued"

    worker = SimpleWorker([queue_service.submission_queue], connection=queue_service.redis_connection)
    worker.work(burst=True)

    status = client.get(f"/submission/{body['submission_id']}", headers=AUTH).json()
    assert status["status"] == "Accepted", status
    assert status["language"] == "cpp"


def test_submit_auto_mode_falls_back_when_redis_is_down(client, monkeypatch):
    monkeypatch.setattr(config, "SUBMISSION_MODE", "auto")
    monkeypatch.setattr(main, "is_queue_available", lambda: False)
    body = client.post(
        "/submit", headers=AUTH,
        json={"problem_id": 1, "code": SOLUTIONS["python"][1]},
    ).json()
    assert body["mode"] == "inline"
    assert client.get(f"/submission/{body['submission_id']}", headers=AUTH).json()["status"] == "Accepted"


# ---------------------------------------------------------------------------
# Mentor
# ---------------------------------------------------------------------------

class FakeLLM:
    def __init__(self, content=None, error=None):
        self.content, self.error, self.prompts = content, error, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


@pytest.fixture()
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(rag_service, "get_embeddings",
                        lambda: SimpleNamespace(embed_query=lambda text: [0.1] * 768))


def test_mentor_parses_fenced_json_and_lists(client, monkeypatch, fake_embeddings):
    llm = FakeLLM(content=[{"type": "text", "text": (
        "Here you go:\n```json\n"
        '{"answer": "Use a hash map.", "time_complexity": "O(n)", '
        '"good_points": ["Clear names", "Handles duplicates"]}\n```'
    )}])
    monkeypatch.setattr(rag_service, "_get_llm", lambda model: llm)

    response = client.post(
        "/mentor", headers=AUTH,
        json={
            "problem_id": 1, "code": "def two_sum(n, t): pass", "question": "Give me a hint",
            "conversation": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "run_summary": "Wrong Answer on nums=[3,3]",
        },
    )
    body = response.json()
    assert response.status_code == 200, body
    assert body["answer"] == "Use a hash map."
    assert body["time_complexity"] == "O(n)"
    assert body["good_points"] == "• Clear names\n• Handles duplicates"
    assert body["sources"][0]["title"] == "Two Sum Pattern"
    prompt = llm.prompts[0]
    assert "Find two numbers." in prompt          # problem description reaches the model
    assert "Wrong Answer on nums=[3,3]" in prompt  # run result reaches the model
    assert "Student: hi" in prompt                 # history reaches the model


def test_mentor_returns_503_when_all_models_fail(client, monkeypatch, fake_embeddings):
    monkeypatch.setattr(rag_service, "_get_llm", lambda model: FakeLLM(error=RuntimeError("quota")))
    response = client.post("/mentor", headers=AUTH, json={"problem_id": 1, "code": "x"})
    assert response.status_code == 503


def test_mentor_still_answers_when_retrieval_fails(client, monkeypatch):
    def broken_embeddings():
        raise RuntimeError("embedding service down")

    monkeypatch.setattr(rag_service, "get_embeddings", broken_embeddings)
    monkeypatch.setattr(rag_service, "_get_llm", lambda model: FakeLLM(content='{"answer": "ok"}'))
    body = client.post("/mentor", headers=AUTH, json={"problem_id": 1, "code": "x"}).json()
    assert body["answer"] == "ok" and body["sources"] == []


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_run_is_rate_limited_per_user(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_RUN_PER_MIN", 2)
    payload = {"problem_id": 1, "code": SOLUTIONS["python"][1]}

    assert client.post("/run", headers=AUTH, json=payload).status_code == 200
    assert client.post("/run", headers=AUTH, json=payload).status_code == 200

    blocked = client.post("/run", headers=AUTH, json=payload)
    assert blocked.status_code == 429
    assert "Too many requests" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) > 0

    # Another user has their own budget.
    assert client.post("/run", headers=OTHER_AUTH, json=payload).status_code == 200
