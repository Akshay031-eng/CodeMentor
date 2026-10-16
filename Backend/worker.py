"""
RQ worker that judges queued submissions.

Run from the Backend folder:
    python worker.py

Works on Linux/macOS (forking worker) and on Windows (RQ's default worker
uses os.fork(), which Windows does not have, so a SimpleWorker with a
timer-based timeout is used there instead).
"""

import logging
import os

from rq import SimpleWorker, Worker

import config  # noqa: F401  (loads .env + logging)
import judge
from queue_service import redis_connection, submission_queue

logger = logging.getLogger("worker")


def process_submission(submission_id: int, problem_id: int, code: str, language: str):
    """RQ entry point (referenced as 'worker.process_submission')."""
    return judge.process_submission(submission_id, problem_id, code, language)


def build_worker():
    if os.name == "nt":
        from rq.timeouts import TimerDeathPenalty

        class WindowsWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        return WindowsWorker([submission_queue], connection=redis_connection)

    return Worker([submission_queue], connection=redis_connection)


if __name__ == "__main__":
    logger.info("AI Coding Mentor worker starting (queue: %s, redis: %s)",
                config.QUEUE_NAME, config.REDIS_URL)
    build_worker().work(with_scheduler=False)
