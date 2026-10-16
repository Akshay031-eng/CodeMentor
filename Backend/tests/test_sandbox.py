"""
Checks for the sandbox user (used in the Docker image).

Run as root with an existing unprivileged user, e.g.:
    useradd --system --no-create-home cmsandbox
    TEST_SANDBOX_USER=cmsandbox python -m pytest tests/test_sandbox.py
Skipped everywhere else (Windows, non-root, CI).
"""
import os

import pytest

import code_runner
from code_runner import OK, judge
from reference_solutions import SOLUTIONS, TEST_CASES

SANDBOX_USER = os.environ.get("TEST_SANDBOX_USER", "")

pytestmark = pytest.mark.skipif(
    not SANDBOX_USER or not hasattr(os, "geteuid") or os.geteuid() != 0,
    reason="needs root and TEST_SANDBOX_USER",
)


@pytest.fixture(autouse=True)
def sandbox(monkeypatch):
    monkeypatch.setattr(code_runner.config, "SANDBOX_USER", SANDBOX_USER)
    monkeypatch.setattr(code_runner.config, "SANDBOX_MAX_PROCESSES", 123)
    code_runner.sandbox_identity.cache_clear()
    assert code_runner.sandbox_identity() is not None
    yield
    code_runner.sandbox_identity.cache_clear()


def run_python(body):
    code = "import os, resource\ndef two_sum(nums, target):\n" + body
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    return result


def test_user_code_is_not_root():
    result = run_python("    return [int(os.getuid() == 0), int(os.geteuid() == 0)]\n")
    assert result["output"] == "[0,0]", result


def test_user_code_cannot_signal_the_server():
    result = run_python(
        "    try:\n"
        "        os.kill(os.getppid(), 0)\n"
        "        return [1, 1]\n"
        "    except PermissionError:\n"
        "        return [0, 0]\n"
    )
    assert result["output"] == "[0,0]", result


def test_process_limit_is_set_before_the_program_starts():
    result = run_python("    return list(resource.getrlimit(resource.RLIMIT_NPROC))\n")
    assert result["output"] == "[123,123]", result


def test_user_code_cannot_write_the_app_folder():
    target = os.path.join(os.path.dirname(code_runner.__file__), "sandbox_probe.txt")
    result = run_python(
        "    try:\n"
        f"        open({target!r}, 'w').write('x')\n"
        "        return [1, 1]\n"
        "    except OSError:\n"
        "        return [0, 0]\n"
    )
    assert result["output"] == "[0,0]", result
    assert not os.path.exists(target)


@pytest.mark.parametrize("language", ["python", "java", "cpp", "c"])
def test_all_languages_work_in_the_sandbox(language):
    cases = TEST_CASES[1]
    results = judge(1, SOLUTIONS[language][1], language, [i for i, _ in cases])
    assert all(r["kind"] == OK for r in results), results
