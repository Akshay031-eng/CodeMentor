import logging

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

import config

logger = logging.getLogger(__name__)

# IMPORTANT: no decode_responses=True here. RQ stores pickled (binary) job
# data in Redis; decoding it as UTF-8 makes every job crash in the worker.
redis_connection = Redis.from_url(
    config.REDIS_URL,
    socket_connect_timeout=2,
    socket_timeout=10,
    health_check_interval=30,
)

submission_queue = Queue(
    config.QUEUE_NAME,
    connection=redis_connection,
    default_timeout=120,
)


def is_queue_available() -> bool:
    try:
        return bool(redis_connection.ping())
    except (RedisError, OSError):
        return False


def enqueue_submission(
    submission_id: int,
    problem_id: int,
    code: str,
    language: str,
):
    return submission_queue.enqueue(
        "worker.process_submission",
        submission_id,
        problem_id,
        code,
        language,
        job_timeout=120,
        result_ttl=3600,
        failure_ttl=86400,
    )
