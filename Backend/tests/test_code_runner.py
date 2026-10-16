import os
import shutil

import pytest

import code_runner
from code_runner import (
    COMPILE_ERROR,
    OK,
    RUNTIME_ERROR,
    TIMEOUT,
    compare_for_problem,
    compare_output,
    judge,
    parse_test_input,
)
from reference_solutions import SOLUTIONS, TEST_CASES

TOOLS = {
    "python": True,
    "java": bool(shutil.which("javac") and shutil.which("java")),
    "cpp": bool(shutil.which("g++") or shutil.which("clang++")),
    "c": bool(shutil.which("gcc") or shutil.which("clang")),
}


def needs(language):
    return pytest.mark.skipif(not TOOLS[language], reason=f"{language} toolchain not installed")


# ---------------------------------------------------------------------------
# Reference solutions must pass every test case in every language.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["python", "java", "cpp", "c"])
@pytest.mark.parametrize("problem_id", sorted(TEST_CASES))
def test_reference_solutions_pass(problem_id, language):
    if not TOOLS[language]:
        pytest.skip(f"{language} toolchain not installed")

    cases = TEST_CASES[problem_id]
    results = judge(problem_id, SOLUTIONS[language][problem_id], language, [i for i, _ in cases])

    for (test_input, expected), result in zip(cases, results):
        assert result["kind"] == OK, (test_input, result)
        assert compare_for_problem(problem_id, language, result["output"], expected), (
            test_input, expected, result,
        )


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------

def test_python_syntax_error_is_compilation_error():
    [result] = judge(1, "def two_sum(nums, target)\n    return []", "python", ["nums=[1], target=1"])
    assert result["kind"] == COMPILE_ERROR
    assert "solution.py" in result["error"]
    assert "line 1" in result["error"]


def test_python_runtime_error_hides_harness_frames():
    code = "def two_sum(nums, target):\n    return nums[100]\n"
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    assert result["kind"] == RUNTIME_ERROR
    assert "IndexError" in result["error"]
    assert "line 2" in result["error"]
    assert "_cm_" not in result["error"]
    assert "coding_mentor_" not in result["error"]  # temp paths are hidden


def test_python_infinite_loop_times_out(monkeypatch):
    monkeypatch.setattr(code_runner.config, "RUN_TIMEOUT_SECONDS", 1)
    code = "def two_sum(nums, target):\n    while True:\n        pass\n"
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    assert result["kind"] == TIMEOUT


def test_debug_prints_are_separated_from_result():
    code = (
        "def two_sum(nums, target):\n"
        "    print('debugging', nums)\n"
        "    print('no newline', end='')\n"
        "    return [0, 1]\n"
    )
    [result] = judge(1, code, "python", ["nums=[2,7], target=9"])
    assert result["kind"] == OK
    assert result["output"] == "[0,1]"
    assert "debugging [2, 7]" in result["stdout"]
    assert compare_for_problem(1, "python", result["output"], "[0,1]")


def test_leetcode_style_python_class_is_supported():
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        return [0, 1]\n"
    )
    [result] = judge(1, code, "python", ["nums=[2,7], target=9"])
    assert result["kind"] == OK and result["output"] == "[0,1]"


def test_missing_function_gives_helpful_message():
    [result] = judge(1, "def something_else():\n    pass\n", "python", ["nums=[1], target=1"])
    assert result["kind"] == RUNTIME_ERROR
    assert "two_sum" in result["error"]


def test_user_code_cannot_read_backend_secrets(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "super-secret-value")
    code = (
        "import os\n"
        "def two_sum(nums, target):\n"
        "    return [len(os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')), 0]\n"
    )
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    assert result["output"] == "[0,0]"


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0 or not os.path.exists("/proc/self/environ"),
    reason="needs Linux and a non-root user (root can read every /proc file)",
)
def test_user_code_cannot_read_server_environment_via_proc(monkeypatch):
    # The API process must not expose its secrets through /proc/<pid>/environ.
    monkeypatch.setenv("CM_LEAK_CANARY", "canary-value-123")
    code = (
        "import os\n"
        "def two_sum(nums, target):\n"
        "    try:\n"
        "        data = open(f'/proc/{os.getppid()}/environ', 'rb').read()\n"
        "        return [int(b'canary-value-123' in data), 1]\n"
        "    except OSError:\n"
        "        return [0, 0]\n"
    )
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    assert result["output"] == "[0,0]"


def test_user_code_runs_outside_backend_folder():
    code = (
        "import os\n"
        "def two_sum(nums, target):\n"
        "    return [int(os.path.exists('main.py')), int(os.path.exists('.env'))]\n"
    )
    [result] = judge(1, code, "python", ["nums=[1,2], target=3"])
    assert result["output"] == "[0,0]"


@needs("cpp")
def test_cpp_compile_error_uses_user_line_numbers():
    code = "class Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        return undefined_name;\n    }\n};\n"
    [result] = judge(1, code, "cpp", ["nums=[1], target=1"])
    assert result["kind"] == COMPILE_ERROR
    assert "solution.cpp:4" in result["error"]


@needs("cpp")
def test_cpp_wrong_signature_shows_hint():
    code = "class Solution {\npublic:\n    int twoSum(int x) { return 0; }\n};\n"
    [result] = judge(1, code, "cpp", ["nums=[1], target=1"])
    assert result["kind"] == COMPILE_ERROR
    assert "Hint" in result["error"] and "twoSum" in result["error"]


@needs("cpp")
def test_cpp_compiles_once_for_many_tests():
    cases = [i for i, _ in TEST_CASES[7]] * 3
    results = judge(7, SOLUTIONS["cpp"][7], "cpp", cases)
    assert len(results) == 9 and all(r["kind"] == OK for r in results)


@needs("c")
def test_c_segfault_is_runtime_error():
    code = "int search(int nums[], int n, int target) { int *p = 0; return *p; }\n"
    [result] = judge(2, code, "c", ["nums=[1,2], target=2"])
    assert result["kind"] == RUNTIME_ERROR
    assert result["error"]


@needs("java")
def test_java_compile_error_points_to_solution_file():
    code = "class Solution {\n    public int search(int[] nums, int target) {\n        return missing;\n    }\n}\n"
    [result] = judge(2, code, "java", ["nums=[1], target=1"])
    assert result["kind"] == COMPILE_ERROR
    assert "Solution.java:3" in result["error"]


@needs("java")
def test_java_unicode_strings_round_trip():
    code = "class Solution { public boolean isAnagram(String s, String t) { return s.equals(\"héllo ✓\") && t.isEmpty(); } }"
    [result] = judge(6, code, "java", ['s="héllo ✓", t=""'])
    assert result["kind"] == OK and result["output"] == "true"


# ---------------------------------------------------------------------------
# Parsing and comparison
# ---------------------------------------------------------------------------

def test_input_parser_accepts_spaces_newlines_and_positional_values():
    spec = code_runner.PROBLEMS[1]
    assert parse_test_input(spec, "nums = [2, 7], target = 9") == [[2, 7], 9]
    assert parse_test_input(spec, "nums=[2,7]\ntarget=9") == [[2, 7], 9]
    assert parse_test_input(spec, "[2,7], 9") == [[2, 7], 9]
    with pytest.raises(ValueError):
        parse_test_input(spec, "nums=[2,7]")


def test_invalid_test_input_is_reported_per_test():
    results = judge(1, SOLUTIONS["python"][1], "python", ["nums=[2,7], target=9", "garbage((("])
    assert results[0]["kind"] == OK
    assert results[1]["kind"] == code_runner.INTERNAL_ERROR


def test_compare_output_rules():
    assert compare_output("[0, 1]", "[0,1]")
    assert compare_output("True", "true")
    assert compare_output("None", "null")
    assert not compare_output("1", "true")       # bool and int are different answers
    assert not compare_output("", "[0,1]")
    assert compare_output("[1,0]", "[0,1]", unordered=True)
    assert not compare_output("[1,0]", "[0,1]")
    assert compare_output("0 1", "[0,1]", lenient_ints=True)
    assert compare_for_problem(1, "python", "[1,0]", "[0,1]")   # Two Sum: any order
