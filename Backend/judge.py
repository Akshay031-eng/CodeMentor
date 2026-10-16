"""
Shared evaluation logic used by both the API (/run) and the RQ worker (/submit).
"""

import logging
from typing import Any, Dict, List, Optional

from code_runner import (
    COMPILE_ERROR,
    INTERNAL_ERROR,
    OK,
    RUNTIME_ERROR,
    TIMEOUT,
    compare_for_problem,
    judge,
    normalize_language,
)
from database import supabase

logger = logging.getLogger(__name__)

STATUS_ACCEPTED = "Accepted"
STATUS_WRONG_ANSWER = "Wrong Answer"
STATUS_COMPILE_ERROR = "Compilation Error"
STATUS_RUNTIME_ERROR = "Runtime Error"
STATUS_TIME_LIMIT = "Time Limit Exceeded"
STATUS_ERROR = "Error"

FINAL_STATUSES = {
    STATUS_ACCEPTED,
    STATUS_WRONG_ANSWER,
    STATUS_COMPILE_ERROR,
    STATUS_RUNTIME_ERROR,
    STATUS_TIME_LIMIT,
    STATUS_ERROR,
}

_KIND_TO_STATUS = {
    COMPILE_ERROR: STATUS_COMPILE_ERROR,
    RUNTIME_ERROR: STATUS_RUNTIME_ERROR,
    TIMEOUT: STATUS_TIME_LIMIT,
    INTERNAL_ERROR: STATUS_ERROR,
}


def get_test_cases(problem_id: int) -> List[Dict[str, Any]]:
    response = (
        supabase
        .table("test_cases")
        .select("id, input, expected_output")
        .eq("problem_id", problem_id)
        .order("id")
        .execute()
    )
    return response.data or []


def overall_status(results: List[Dict[str, Any]]) -> str:
    """LeetCode-style verdict: the first failing test decides the status."""
    for item in results:
        if not item["passed"]:
            return _KIND_TO_STATUS.get(item.get("kind"), STATUS_WRONG_ANSWER)
    return STATUS_ACCEPTED


def evaluate(
    problem_id: int,
    code: str,
    language: str,
    test_cases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    language = normalize_language(language)
    if test_cases is None:
        test_cases = get_test_cases(problem_id)

    if not test_cases:
        return {
            "status": STATUS_ERROR,
            "message": "No test cases found for this problem.",
            "passed": 0,
            "total": 0,
            "results": [],
            "test_cases": [],
        }

    executions = judge(
        problem_id,
        code,
        language,
        [test_case.get("input", "") for test_case in test_cases],
    )

    results = []
    passed_count = 0
    for test_case, execution in zip(test_cases, executions):
        expected = test_case.get("expected_output", "") or ""
        is_passed = execution["kind"] == OK and compare_for_problem(
            problem_id, language, execution["output"], expected
        )
        passed_count += int(is_passed)
        results.append(
            {
                "test_case_id": test_case.get("id"),
                "input": test_case.get("input", ""),
                "passed": is_passed,
                "expected": expected,
                "actual": execution["output"],
                "stdout": execution.get("stdout", ""),
                "error": execution["error"],
                "exit_code": execution["exit_code"],
                "kind": execution["kind"],
                "time_ms": execution.get("time_ms"),
            }
        )

    status = overall_status(results)
    first_failure = next((item for item in results if not item["passed"]), None)

    return {
        "status": status,
        "message": (first_failure or {}).get("error", "") if status != STATUS_WRONG_ANSWER else "",
        "passed": passed_count,
        "total": len(test_cases),
        "results": results,
        "test_cases": test_cases,
    }


def update_submission(submission_id: int, values: Dict[str, Any]) -> None:
    supabase.table("submissions").update(values).eq("id", submission_id).execute()


def process_submission(submission_id: int, problem_id: int, code: str, language: str) -> Dict[str, Any]:
    """
    Judge a stored submission and save the verdict.
    Lifecycle: Queued -> Running -> final status.
    Used by the RQ worker and by the in-process fallback.
    """
    try:
        update_submission(submission_id, {"status": "Running"})
        result = evaluate(problem_id, code, language)
        update_submission(
            submission_id,
            {
                "status": result["status"],
                "passed": result["passed"],
                "total": result["total"],
            },
        )
        logger.info(
            "Submission %s judged: %s (%s/%s)",
            submission_id, result["status"], result["passed"], result["total"],
        )
        return {
            "submission_id": submission_id,
            "status": result["status"],
            "passed": result["passed"],
            "total": result["total"],
        }
    except Exception:
        logger.exception("Submission %s failed", submission_id)
        try:
            update_submission(submission_id, {"status": STATUS_ERROR, "passed": 0, "total": 0})
        except Exception:  # noqa: BLE001
            logger.exception("Could not mark submission %s as failed", submission_id)
        raise
