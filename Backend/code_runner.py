"""
Code execution engine for AI Coding Mentor.

How it works
------------
* Every problem is described once in ``PROBLEMS`` (parameter types, function
  names, return type). Harness code for Python / Java / C++ / C is generated
  from that description, so adding a new problem is one dictionary entry.
* Compiled languages are compiled ONCE per run/submission. Each test case is
  then executed against the same binary, with its input sent over stdin.
* The harness prints a marker line right before the function's result, so
  anything the student prints for debugging is shown separately as "stdout"
  and does not break the output comparison.
* User code runs in a throw-away temp directory with a minimal environment
  (no API keys / database credentials), a wall-clock timeout, and - on
  Linux - CPU, memory and output-size limits.

NOTE: this is process-level hardening, not a full sandbox. For a public
deployment run the worker inside a container (Docker / gVisor / nsjail)
with no network access.
"""

from __future__ import annotations

import ast
import functools
import json
import logging
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import config

try:  # POSIX only
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

RESULT_MARKER = "<<<CM_RESULT>>>"

# Bytes of stdout/stderr we are willing to read back from a program.
MAX_OUTPUT_BYTES = 1_000_000
# Characters of debug stdout / error text returned to the client.
MAX_DISPLAY_CHARS = 20_000

SUPPORTED_LANGUAGES = ("python", "java", "cpp", "c")

LANGUAGE_ALIASES = {
    "python3": "python",
    "python 3": "python",
    "py": "python",
    "c++": "cpp",
    "c plus plus": "cpp",
    "cplusplus": "cpp",
}

# Result kinds -----------------------------------------------------------------
OK = "ok"
COMPILE_ERROR = "compile_error"
RUNTIME_ERROR = "runtime_error"
TIMEOUT = "timeout"
INTERNAL_ERROR = "internal_error"


def normalize_language(language: Optional[str]) -> str:
    value = (language or "python").strip().lower()
    return LANGUAGE_ALIASES.get(value, value)


def make_result(
    output: str = "",
    error: str = "",
    exit_code: int = 0,
    kind: str = OK,
    stdout: str = "",
    time_ms: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "output": (output or "").strip(),
        "stdout": _truncate((stdout or "").rstrip()),
        "error": _truncate((error or "").strip()),
        "exit_code": exit_code,
        "kind": kind,
        "time_ms": time_ms,
    }


def _truncate(text: str, limit: int = MAX_DISPLAY_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated, {len(text) - limit} more characters)"


# =============================================================================
# PROBLEM SPECIFICATIONS
# =============================================================================

@dataclass(frozen=True)
class ProblemSpec:
    title: str
    # (name, type) where type is "int[]", "int" or "str"
    params: Tuple[Tuple[str, str], ...]
    # Accepted Python names, snake_case first (also looked up on class Solution)
    python_names: Tuple[str, ...]
    # Java / C++ method name and C function name
    method: str
    # "int[]", "int" or "bool"
    returns: str
    # How the C version hands back its answer:
    #   "return"  -> function returns the value
    #   "print"   -> function prints the answer itself
    #   "inplace" -> function modifies the first array argument
    c_style: str = "return"
    # Two Sum: [1, 0] is as correct as [0, 1]
    unordered_output: bool = False


PROBLEMS: Dict[int, ProblemSpec] = {
    1: ProblemSpec(
        title="Two Sum",
        params=(("nums", "int[]"), ("target", "int")),
        python_names=("two_sum", "twoSum"),
        method="twoSum",
        returns="int[]",
        c_style="print",
        unordered_output=True,
    ),
    2: ProblemSpec(
        title="Binary Search",
        params=(("nums", "int[]"), ("target", "int")),
        python_names=("binary_search", "search"),
        method="search",
        returns="int",
    ),
    3: ProblemSpec(
        title="Valid Parentheses",
        params=(("s", "str"),),
        python_names=("is_valid", "isValid"),
        method="isValid",
        returns="bool",
    ),
    4: ProblemSpec(
        title="Contains Duplicate",
        params=(("nums", "int[]"),),
        python_names=("contains_duplicate", "containsDuplicate"),
        method="containsDuplicate",
        returns="bool",
    ),
    5: ProblemSpec(
        title="Best Time to Buy and Sell Stock",
        params=(("prices", "int[]"),),
        python_names=("max_profit", "maxProfit"),
        method="maxProfit",
        returns="int",
    ),
    6: ProblemSpec(
        title="Valid Anagram",
        params=(("s", "str"), ("t", "str")),
        python_names=("is_anagram", "isAnagram"),
        method="isAnagram",
        returns="bool",
    ),
    7: ProblemSpec(
        title="Maximum Subarray",
        params=(("nums", "int[]"),),
        python_names=("max_sub_array", "maxSubArray"),
        method="maxSubArray",
        returns="int",
    ),
    8: ProblemSpec(
        title="Reverse Linked List",
        params=(("head", "int[]"),),
        python_names=("reverse_list", "reverseList"),
        method="reverseList",
        returns="int[]",
        c_style="inplace",
    ),
}


def get_problem_spec(problem_id: int) -> Optional[ProblemSpec]:
    return PROBLEMS.get(int(problem_id))


# =============================================================================
# TEST INPUT PARSING
# =============================================================================

def _literal(node: ast.AST) -> Any:
    # Accept JSON-style true/false/null as well as Python literals.
    if isinstance(node, ast.Name) and node.id in {"true", "false", "null"}:
        return {"true": True, "false": False, "null": None}[node.id]
    return ast.literal_eval(node)


def _parse_call_arguments(text: str) -> Tuple[List[Any], Dict[str, Any]]:
    candidates = [text]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        # Support "nums = [1,2]\ntarget = 3" style inputs.
        candidates.append(", ".join(lines))

    last_error: Optional[Exception] = None
    for candidate in candidates:
        try:
            call = ast.parse(f"_cm({candidate})", mode="eval").body
            assert isinstance(call, ast.Call)
            positional = [_literal(arg) for arg in call.args]
            keywords = {
                keyword.arg: _literal(keyword.value)
                for keyword in call.keywords
                if keyword.arg
            }
            return positional, keywords
        except Exception as error:  # noqa: BLE001
            last_error = error

    raise ValueError(f"could not parse test input ({last_error})")


def _coerce(value: Any, kind: str, name: str) -> Any:
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"'{name}' must be an integer")
        return value
    if kind == "int[]":
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"'{name}' must be a list of integers")
        items = list(value)
        if any(isinstance(item, bool) or not isinstance(item, int) for item in items):
            raise ValueError(f"'{name}' must only contain integers")
        return items
    if kind == "str":
        return value if isinstance(value, str) else str(value)
    raise ValueError(f"unknown parameter type '{kind}'")


def parse_test_input(spec: ProblemSpec, input_data: str) -> List[Any]:
    """
    Parse inputs such as ``nums=[2,7,11,15], target=9`` or ``s="()"``.
    Values may be given by name or by position, separated by commas or newlines.
    """
    text = (input_data or "").strip()
    if not text:
        raise ValueError("test input is empty")

    positional, keywords = _parse_call_arguments(text)
    values = []
    for name, kind in spec.params:
        if name in keywords:
            raw = keywords[name]
        elif positional:
            raw = positional.pop(0)
        else:
            raise ValueError(f"missing value for '{name}'")
        values.append(_coerce(raw, kind, name))
    return values


def encode_stdin(spec: ProblemSpec, values: Sequence[Any]) -> str:
    """Serialize arguments into a whitespace-separated format every harness can read."""
    parts: List[str] = []
    for (_, kind), value in zip(spec.params, values):
        if kind == "int[]":
            parts.append(str(len(value)))
            parts.append(" ".join(str(item) for item in value))
        elif kind == "int":
            parts.append(str(value))
        elif kind == "str":
            encoded = value.encode("utf-8")
            parts.append(str(len(encoded)))
            parts.append(encoded.hex())
    return "\n".join(parts) + "\n"


# =============================================================================
# HARNESS GENERATION
# =============================================================================

PYTHON_HARNESS = '''


# ---- Coding Mentor harness (added automatically) ----
def _cm_format(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_cm_format(item) for item in value) + "]"
    return str(value)


def _cm_resolve(names):
    scope = globals()
    for name in names:
        if callable(scope.get(name)):
            return scope[name]
    solution_class = scope.get("Solution")
    if isinstance(solution_class, type):
        instance = solution_class()
        for name in names:
            if callable(getattr(instance, name, None)):
                return getattr(instance, name)
    raise NameError(
        "Function '" + names[0] + "' was not found. "
        "Keep the function name from the starter code."
    )


import sys as _cm_sys
_cm_result = _cm_resolve({names!r})({args})
_cm_sys.stdout.write("\\n{marker}\\n" + _cm_format(_cm_result) + "\\n")
'''


def build_python_program(spec: ProblemSpec, code: str, values: Sequence[Any]) -> str:
    # User code stays at line 1 so traceback line numbers match the editor.
    return code.rstrip() + PYTHON_HARNESS.format(
        names=tuple(spec.python_names),
        args=", ".join(repr(value) for value in values),
        marker=RESULT_MARKER,
    )


CPP_PRELUDE = """\
#include <algorithm>
#include <climits>
#include <cmath>
#include <iostream>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <stack>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using namespace std;
"""

CPP_HELPERS = """\
static long long cm_read_ll() { long long value = 0; cin >> value; return value; }
static int cm_read_int() { return (int) cm_read_ll(); }
static vector<int> cm_read_ints() {
    long long count = cm_read_ll();
    vector<int> values(count > 0 ? (size_t) count : 0);
    for (auto &value : values) value = cm_read_int();
    return values;
}
static string cm_read_str() {
    long long length = cm_read_ll();
    string value;
    if (length > 0) {
        string hex_text;
        cin >> hex_text;
        value.reserve((size_t) length);
        for (size_t i = 0; i + 1 < hex_text.size(); i += 2)
            value.push_back((char) stoi(hex_text.substr(i, 2), nullptr, 16));
    }
    return value;
}
static void cm_print_ints(const vector<int> &values) {
    cout << "[";
    for (size_t i = 0; i < values.size(); ++i) { if (i) cout << ","; cout << values[i]; }
    cout << "]";
}
"""


def build_cpp_program(spec: ProblemSpec, code: str) -> str:
    reads, args = [], []
    for name, kind in spec.params:
        if kind == "int[]":
            reads.append(f"    vector<int> {name} = cm_read_ints();")
        elif kind == "int":
            reads.append(f"    int {name} = cm_read_int();")
        else:
            reads.append(f"    string {name} = cm_read_str();")
        args.append(name)

    call = f"cm_solution.{spec.method}({', '.join(args)})"
    if spec.returns == "int[]":
        result = f"    vector<int> cm_result = {call};"
        printer = "    cm_print_ints(cm_result);"
    elif spec.returns == "bool":
        result = f"    bool cm_result = {call};"
        printer = '    cout << (cm_result ? "true" : "false");'
    else:
        result = f"    int cm_result = {call};"
        printer = "    cout << cm_result;"

    marker = f'    cout << "\\n{RESULT_MARKER}\\n";'
    main = "\n".join(
        ["int main() {", *reads, "    Solution cm_solution;", result, marker, printer,
         "    cout << endl;", "    return 0;", "}"]
    )
    return "\n".join(
        [CPP_PRELUDE, '#line 1 "solution.cpp"', code.rstrip(), "",
         '#line 1 "harness.cpp"', CPP_HELPERS, main, ""]
    )


C_PRELUDE = """\
#include <limits.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
"""

C_HELPERS = """\
static long long cm_read_ll(void) { long long value = 0; if (scanf("%lld", &value) != 1) value = 0; return value; }
static int cm_read_int(void) { return (int) cm_read_ll(); }
static int *cm_read_ints(int *count_out) {
    long long count = cm_read_ll();
    if (count < 0) count = 0;
    int *values = (int *) malloc(sizeof(int) * (size_t) (count > 0 ? count : 1));
    for (long long i = 0; i < count; ++i) values[i] = cm_read_int();
    *count_out = (int) count;
    return values;
}
static char *cm_read_str(void) {
    long long length = cm_read_ll();
    if (length < 0) length = 0;
    char *value = (char *) calloc((size_t) length + 1, 1);
    for (long long i = 0; i < length; ++i) {
        unsigned int byte = 0;
        if (scanf("%2x", &byte) != 1) break;
        value[i] = (char) byte;
    }
    return value;
}
static void cm_print_ints(const int *values, int count) {
    printf("[");
    for (int i = 0; i < count; ++i) { if (i) printf(","); printf("%d", values[i]); }
    printf("]");
}
"""


def build_c_program(spec: ProblemSpec, code: str) -> str:
    reads, args = [], []
    first_array: Optional[str] = None
    for name, kind in spec.params:
        if kind == "int[]":
            reads.append(f"    int {name}_n = 0;")
            reads.append(f"    int *{name} = cm_read_ints(&{name}_n);")
            args.extend([name, f"{name}_n"])
            first_array = first_array or name
        elif kind == "int":
            reads.append(f"    int {name} = cm_read_int();")
            args.append(name)
        else:
            reads.append(f"    char *{name} = cm_read_str();")
            args.append(name)

    call = f"{spec.method}({', '.join(args)})"
    marker = f'    printf("\\n{RESULT_MARKER}\\n");'

    if spec.c_style == "print":
        # The student's function prints the answer, so the marker goes first.
        body = [marker, "    fflush(stdout);", f"    {call};", '    printf("\\n");']
    elif spec.c_style == "inplace":
        body = [f"    {call};", marker,
                f"    cm_print_ints({first_array}, {first_array}_n);", '    printf("\\n");']
    elif spec.returns == "bool":
        body = [f"    bool cm_result = {call};", marker,
                '    printf("%s\\n", cm_result ? "true" : "false");']
    else:
        body = [f"    int cm_result = {call};", marker, '    printf("%d\\n", cm_result);']

    main = "\n".join(["int main(void) {", *reads, *body, "    return 0;", "}"])
    return "\n".join(
        [C_PRELUDE, '#line 1 "solution.c"', code.rstrip(), "",
         '#line 1 "harness.c"', C_HELPERS, main, ""]
    )


JAVA_MAIN_CLASS = "CodingMentorMain"


def build_java_main(spec: ProblemSpec) -> str:
    reads, args = [], []
    for name, kind in spec.params:
        if kind == "int[]":
            reads.append(f"        int[] {name} = readInts();")
        elif kind == "int":
            reads.append(f"        int {name} = readInt();")
        else:
            reads.append(f"        String {name} = readStr();")
        args.append(name)

    call = f"cmSolution.{spec.method}({', '.join(args)})"
    if spec.returns == "int[]":
        result = f"        int[] cmResult = {call};"
        printer = "        System.out.println(fmt(cmResult));"
    elif spec.returns == "bool":
        result = f"        boolean cmResult = {call};"
        printer = "        System.out.println(cmResult);"
    else:
        result = f"        int cmResult = {call};"
        printer = "        System.out.println(cmResult);"

    reads_text = "\n".join(reads)
    return f"""\
import java.nio.charset.StandardCharsets;

public class {JAVA_MAIN_CLASS} {{
    private static String[] tokens = new String[0];
    private static int position = 0;

    private static String next() {{ return position < tokens.length ? tokens[position++] : "0"; }}
    private static int readInt() {{ return (int) Long.parseLong(next()); }}

    private static int[] readInts() {{
        int count = Math.max(readInt(), 0);
        int[] values = new int[count];
        for (int i = 0; i < count; i++) values[i] = readInt();
        return values;
    }}

    private static String readStr() {{
        int length = readInt();
        if (length <= 0) return "";
        String hex = next();
        byte[] bytes = new byte[hex.length() / 2];
        for (int i = 0; i < bytes.length; i++)
            bytes[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        return new String(bytes, StandardCharsets.UTF_8);
    }}

    private static String fmt(int[] values) {{
        if (values == null) return "null";
        StringBuilder builder = new StringBuilder("[");
        for (int i = 0; i < values.length; i++) {{
            if (i > 0) builder.append(',');
            builder.append(values[i]);
        }}
        return builder.append(']').toString();
    }}

    public static void main(String[] args) throws Exception {{
        String input = new String(System.in.readAllBytes(), StandardCharsets.UTF_8).trim();
        tokens = input.isEmpty() ? new String[0] : input.split("\\\\s+");
{reads_text}
        Solution cmSolution = new Solution();
{result}
        System.out.print("\\n{RESULT_MARKER}\\n");
{printer}
    }}
}}
"""


def signature_hint(spec: ProblemSpec, language: str) -> str:
    """The function signature the harness expects, shown on compile errors."""
    java_types = {"int[]": "int[]", "int": "int", "str": "String", "bool": "boolean"}
    cpp_params = {"int[]": "vector<int>& {n}", "int": "int {n}", "str": "string {n}"}
    cpp_returns = {"int[]": "vector<int>", "int": "int", "bool": "bool"}
    c_params = {"int[]": "int {n}[], int n", "int": "int {n}", "str": "const char *{n}"}

    names = [name for name, _ in spec.params]
    if language == "python":
        return f"def {spec.python_names[0]}({', '.join(names)}):"
    if language == "java":
        params = ", ".join(f"{java_types[k]} {n}" for n, k in spec.params)
        return f"class Solution {{ public {java_types[spec.returns]} {spec.method}({params}) }}"
    if language == "cpp":
        params = ", ".join(cpp_params[k].format(n=n) for n, k in spec.params)
        return f"class Solution {{ public: {cpp_returns[spec.returns]} {spec.method}({params}) }}"
    params = ", ".join(c_params[k].format(n=n) for n, k in spec.params)
    ret = "void" if spec.c_style in {"print", "inplace"} else spec.returns
    return f"{ret} {spec.method}({params})"


# =============================================================================
# PROCESS EXECUTION
# =============================================================================

_ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE", "JAVA_HOME",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
}


def build_safe_env(work_dir: str) -> Dict[str, str]:
    """A minimal environment: user code must never see API keys or DB credentials."""
    env = {key: value for key, value in os.environ.items() if key.upper() in _ENV_ALLOWLIST}
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        }
    )
    if os.name != "nt":
        env["HOME"] = work_dir
        env["TMPDIR"] = work_dir
    return env


@dataclass
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limit_exceeded: bool = False
    time_ms: int = 0


# ---------------------------------------------------------------------------
# Sandbox user
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def sandbox_identity() -> Optional[Tuple[int, int]]:
    """
    (uid, gid) that untrusted code runs as, or None.

    Active when SANDBOX_USER is set and the server runs as root (the Docker
    image does this). A different OS user cannot signal/kill the server,
    read its /proc files or write the app folder, and RLIMIT_NPROC can cap
    its process count (fork bombs) without touching the server itself.
    """
    name = config.SANDBOX_USER
    if not name or os.name == "nt" or not hasattr(os, "geteuid"):
        return None
    if os.geteuid() != 0:
        logger.warning("SANDBOX_USER=%s ignored: the server must run as root to switch users.", name)
        return None
    try:
        import pwd

        entry = pwd.getpwnam(name)
    except (ImportError, KeyError):
        logger.error("SANDBOX_USER=%s does not exist - user code runs as the server user!", name)
        return None
    if entry.pw_uid == 0:
        logger.error("SANDBOX_USER must not be root - ignoring it.")
        return None
    logger.info("User code runs as '%s' (uid %s).", name, entry.pw_uid)
    return entry.pw_uid, entry.pw_gid


def _hand_over(path: str) -> None:
    """Let the sandbox user write inside a folder created by the server."""
    identity = sandbox_identity()
    if identity:
        os.chown(path, identity[0], identity[1])


@functools.lru_cache(maxsize=1)
def _prlimit_binary() -> Optional[str]:
    return shutil.which("prlimit")


# name -> resource constant (names match the util-linux `prlimit` flags)
_LIMIT_NAMES = {
    "fsize": "RLIMIT_FSIZE",
    "core": "RLIMIT_CORE",
    "cpu": "RLIMIT_CPU",
    "as": "RLIMIT_AS",
    "nproc": "RLIMIT_NPROC",
}


def _resource_limits(
    memory_mb: Optional[int],
    cpu_seconds: Optional[int],
    max_processes: Optional[int] = None,
) -> List[Tuple[str, int]]:
    if resource is None:
        return []
    limits = [("fsize", MAX_OUTPUT_BYTES * 8), ("core", 0)]
    if cpu_seconds:
        limits.append(("cpu", int(cpu_seconds) + 1))
    if memory_mb:
        limits.append(("as", int(memory_mb) * 1024 * 1024))
    if max_processes:
        limits.append(("nproc", int(max_processes)))
    return limits


def _apply_limits(pid: int, limits: List[Tuple[str, int]]) -> None:
    # prlimit() after spawn is thread-safe, unlike Popen(preexec_fn=...).
    if resource is None or not hasattr(resource, "prlimit"):
        return
    for name, value in limits:
        try:
            resource.prlimit(pid, getattr(resource, _LIMIT_NAMES[name]), (value, value))
        except (OSError, ValueError, AttributeError):
            pass


def _kill_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:  # noqa: BLE001
            pass
    try:
        process.kill()
    except Exception:  # noqa: BLE001
        pass


def _read_capped(handle) -> Tuple[str, bool]:
    handle.flush()
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(0)
    data = handle.read(MAX_OUTPUT_BYTES)
    return data.decode("utf-8", errors="replace"), size > MAX_OUTPUT_BYTES


def run_process(
    command: Sequence[str],
    *,
    stdin_text: str = "",
    cwd: Optional[str] = None,
    timeout: float = config.RUN_TIMEOUT_SECONDS,
    env: Optional[Dict[str, str]] = None,
    memory_mb: Optional[int] = None,
    cpu_seconds: Optional[int] = None,
) -> ProcessResult:
    """
    Run a compiler or program with a hard timeout and process-tree cleanup.
    stdout/stderr go to temp files (not pipes) so a program that prints in an
    infinite loop cannot exhaust the backend's memory.
    """
    popen_kwargs: Dict[str, Any] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    identity = sandbox_identity()
    limits = _resource_limits(
        memory_mb,
        cpu_seconds,
        config.SANDBOX_MAX_PROCESSES if identity else None,
    )

    if identity:
        # Drop to the sandbox user before exec (done in C, thread-safe).
        popen_kwargs.update(user=identity[0], group=identity[1], extra_groups=[])
        prlimit = _prlimit_binary()
        if prlimit and limits:
            # Apply every limit *before* the program starts, so not even its
            # first instructions (e.g. a fork bomb) run unlimited.
            command = [prlimit, *(f"--{name}={value}" for name, value in limits), "--", *command]
            limits = []

    with tempfile.TemporaryFile() as out_file, tempfile.TemporaryFile() as err_file:
        started = time.perf_counter()
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.PIPE,
            stdout=out_file,
            stderr=err_file,
            cwd=cwd,
            env=env,
            **popen_kwargs,
        )
        if limits:
            _apply_limits(process.pid, limits)

        timed_out = False
        try:
            process.communicate(input=stdin_text.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        except BrokenPipeError:
            # Program exited without reading its stdin - that's fine.
            process.wait()
        finally:
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        stdout, stdout_capped = _read_capped(out_file)
        stderr, _ = _read_capped(err_file)

    return ProcessResult(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        output_limit_exceeded=stdout_capped,
        time_ms=elapsed_ms,
    )


_SIGNAL_MESSAGES = {
    getattr(signal, "SIGSEGV", 11): "Segmentation fault (invalid memory access, e.g. index out of bounds)",
    getattr(signal, "SIGABRT", 6): "Aborted (assertion failed or uncaught exception)",
    getattr(signal, "SIGFPE", 8): "Floating point exception (e.g. division by zero)",
    getattr(signal, "SIGKILL", 9): "Killed (memory limit exceeded?)",
    getattr(signal, "SIGBUS", 7): "Bus error (invalid memory access)",
}

_WINDOWS_EXIT_MESSAGES = {
    0xC0000005: "Access violation (invalid memory access, e.g. index out of bounds)",
    0xC00000FD: "Stack overflow (infinite or too deep recursion?)",
    0xC0000094: "Integer division by zero",
    0xC0000409: "Stack buffer overrun",
}


def describe_exit_code(code: int) -> str:
    if code < 0:
        number = -code
        if number == getattr(signal, "SIGXCPU", 24):
            return "CPU time limit exceeded"
        if number == getattr(signal, "SIGXFSZ", 25):
            return "Output limit exceeded"
        return _SIGNAL_MESSAGES.get(number, f"Process terminated by signal {number}")
    if code > 0xC0000000 - 1:
        return _WINDOWS_EXIT_MESSAGES.get(code, f"Process exited with code {hex(code)}")
    return f"Process exited with code {code}"


def _clean_paths(text: str, work_dir: str) -> str:
    """Hide temp-folder paths from compiler / traceback messages."""
    if not text:
        return text
    variants = {work_dir, os.path.realpath(work_dir)}
    variants |= {value.replace("\\", "/") for value in list(variants)}
    for value in sorted(variants, key=len, reverse=True):
        for sep in ("/", "\\"):
            text = text.replace(value + sep, "")
        text = text.replace(value, "")
    return text


def split_program_output(stdout: str) -> Tuple[str, str]:
    """Return (function result, debug stdout printed by the student)."""
    index = stdout.rfind(RESULT_MARKER)
    if index == -1:
        return "", stdout
    debug = stdout[:index]
    if debug.endswith("\n"):
        debug = debug[:-1]
    if debug.endswith("\r"):
        debug = debug[:-1]
    return stdout[index + len(RESULT_MARKER):].strip(), debug


def _program_result(process: ProcessResult, work_dir: str) -> Dict[str, Any]:
    output, debug = split_program_output(process.stdout)
    stderr = _clean_paths(process.stderr, work_dir)
    debug = _clean_paths(debug, work_dir)

    if process.timed_out:
        return make_result(output, "Time Limit Exceeded", -1, TIMEOUT, debug, process.time_ms)

    signal_number = -process.returncode if process.returncode < 0 else 0
    if signal_number == getattr(signal, "SIGXCPU", 24):
        return make_result(output, "Time Limit Exceeded (CPU limit)", process.returncode,
                           TIMEOUT, debug, process.time_ms)

    if process.output_limit_exceeded or signal_number == getattr(signal, "SIGXFSZ", 25):
        return make_result("", "Output Limit Exceeded - your program printed too much.",
                           process.returncode, RUNTIME_ERROR, debug, process.time_ms)

    if process.returncode != 0:
        message = stderr or describe_exit_code(process.returncode)
        if stderr and (process.returncode < 0 or process.returncode > 0xC0000000 - 1):
            message = f"{stderr}\n{describe_exit_code(process.returncode)}"
        return make_result(output, message, process.returncode, RUNTIME_ERROR, debug, process.time_ms)

    # Exit code 0 but stderr output (warnings, debug prints to stderr) is not an error.
    result = make_result(output, "", 0, OK, debug, process.time_ms)
    if stderr:
        result["stdout"] = _truncate(
            ((result["stdout"] + "\n") if result["stdout"] else "") + "[stderr]\n" + stderr
        )
    return result


# =============================================================================
# LANGUAGE BACKENDS
# =============================================================================

def _compile(command: List[str], work_dir: str, spec: ProblemSpec, language: str,
             harness_files: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Run a compiler. Returns an error result, or None if compilation succeeded."""
    try:
        process = run_process(
            command,
            cwd=work_dir,
            timeout=config.COMPILE_TIMEOUT_SECONDS,
            env=build_safe_env(work_dir),
        )
    except FileNotFoundError as error:
        return make_result("", f"Compiler not found: {error}", -1, INTERNAL_ERROR)

    if process.timed_out:
        return make_result("", "Compilation timed out.", -1, COMPILE_ERROR)

    if process.returncode != 0:
        message = _clean_paths(process.stderr or process.stdout, work_dir).strip()
        if any(name in message for name in harness_files):
            message += (
                "\n\nHint: keep the function signature from the starter code:\n  "
                + signature_hint(spec, language)
            )
        return make_result("", message or "Compilation failed.", process.returncode, COMPILE_ERROR)
    return None


class _Prepared:
    """A compiled (or syntax-checked) program that can be run per test case."""

    def __init__(self, run_one, error: Optional[Dict[str, Any]] = None):
        self.run_one = run_one
        self.error = error


_PY_FRAME = re.compile(r'^\s*File "solution\.py", line (\d+)')


def _strip_harness_frames(stderr: str, user_line_count: int) -> str:
    """Remove traceback frames that point into the auto-generated harness."""
    lines = stderr.splitlines()
    kept: List[str] = []
    index = 0
    while index < len(lines):
        match = _PY_FRAME.match(lines[index])
        if match and int(match.group(1)) > user_line_count:
            index += 1
            # Skip the source line and ^^^ markers that belong to this frame.
            while index < len(lines) and lines[index].startswith("    "):
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    return "\n".join(kept)


def _prepare_python(spec: ProblemSpec, code: str, work_dir: str) -> _Prepared:
    user_line_count = len(code.rstrip().splitlines())
    try:
        compile(code, "solution.py", "exec", dont_inherit=True)
    except SyntaxError as error:
        message = "".join(traceback.format_exception_only(type(error), error)).strip()
        return _Prepared(None, make_result("", message, 1, COMPILE_ERROR))
    except (ValueError, MemoryError, RecursionError) as error:
        return _Prepared(None, make_result("", f"Invalid code: {error}", 1, COMPILE_ERROR))

    def run_one(index: int, values: Sequence[Any]) -> Dict[str, Any]:
        test_dir = os.path.join(work_dir, f"test_{index}")
        os.makedirs(test_dir, exist_ok=True)
        _hand_over(test_dir)
        with open(os.path.join(test_dir, "solution.py"), "w", encoding="utf-8") as file:
            file.write(build_python_program(spec, code, values))
        process = run_process(
            [sys.executable, "-I", "-X", "utf8", "solution.py"],
            cwd=test_dir,
            timeout=config.RUN_TIMEOUT_SECONDS,
            env=build_safe_env(test_dir),
            memory_mb=config.MEMORY_LIMIT_MB,
            cpu_seconds=config.RUN_TIMEOUT_SECONDS,
        )
        result = _program_result(process, test_dir)
        if result["error"]:
            result["error"] = _strip_harness_frames(result["error"], user_line_count)
        return result

    return _Prepared(run_one)


def _prepare_native(spec: ProblemSpec, code: str, work_dir: str, language: str) -> _Prepared:
    if language == "cpp":
        compiler = shutil.which("g++") or shutil.which("clang++")
        source, standard, extra = "program.cpp", "-std=c++17", []
        program = build_cpp_program(spec, code)
        harness_files = ("harness.cpp",)
        missing = "C++ compiler not found. Install g++ (MinGW on Windows) or clang++ and add it to PATH."
    else:
        compiler = shutil.which("gcc") or shutil.which("clang")
        source, standard, extra = "program.c", "-std=c11", ["-lm"]
        program = build_c_program(spec, code)
        harness_files = ("harness.c",)
        missing = "C compiler not found. Install gcc (MinGW on Windows) or clang and add it to PATH."

    if not compiler:
        return _Prepared(None, make_result("", missing, -1, INTERNAL_ERROR))

    with open(os.path.join(work_dir, source), "w", encoding="utf-8") as file:
        file.write(program)

    executable = os.path.join(work_dir, "solution.exe" if os.name == "nt" else "solution")
    error = _compile(
        [compiler, standard, "-O2", "-pipe", source, "-o", executable, *extra],
        work_dir, spec, language, harness_files,
    )
    if error:
        return _Prepared(None, error)

    def run_one(index: int, values: Sequence[Any]) -> Dict[str, Any]:
        process = run_process(
            [executable],
            stdin_text=encode_stdin(spec, values),
            cwd=work_dir,
            timeout=config.RUN_TIMEOUT_SECONDS,
            env=build_safe_env(work_dir),
            memory_mb=config.MEMORY_LIMIT_MB,
            cpu_seconds=config.RUN_TIMEOUT_SECONDS,
        )
        return _program_result(process, work_dir)

    return _Prepared(run_one)


def _prepare_java(spec: ProblemSpec, code: str, work_dir: str) -> _Prepared:
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java:
        return _Prepared(None, make_result(
            "", "Java not found. Install a JDK (17+) and make sure javac and java are in PATH.",
            -1, INTERNAL_ERROR,
        ))

    with open(os.path.join(work_dir, "Solution.java"), "w", encoding="utf-8") as file:
        file.write(code)
    with open(os.path.join(work_dir, f"{JAVA_MAIN_CLASS}.java"), "w", encoding="utf-8") as file:
        file.write(build_java_main(spec))

    error = _compile(
        [javac, "-J-XX:TieredStopAtLevel=1", "-J-XX:+UseSerialGC", "-encoding", "UTF-8",
         "-d", ".", "Solution.java", f"{JAVA_MAIN_CLASS}.java"],
        work_dir, spec, "java", (f"{JAVA_MAIN_CLASS}.java",),
    )
    if error:
        return _Prepared(None, error)

    def run_one(index: int, values: Sequence[Any]) -> Dict[str, Any]:
        process = run_process(
            [java, "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData",
             "-Xshare:auto", f"-Xmx{config.MEMORY_LIMIT_MB}m", "-Dfile.encoding=UTF-8",
             "-Dstdout.encoding=UTF-8", "-cp", ".", JAVA_MAIN_CLASS],
            stdin_text=encode_stdin(spec, values),
            cwd=work_dir,
            timeout=config.RUN_TIMEOUT_SECONDS,
            env=build_safe_env(work_dir),
            # No RLIMIT_AS for the JVM (it reserves a lot of virtual memory); -Xmx caps the heap.
            cpu_seconds=config.RUN_TIMEOUT_SECONDS,
        )
        return _program_result(process, work_dir)

    return _Prepared(run_one)


# =============================================================================
# PUBLIC API
# =============================================================================

def judge(
    problem_id: int,
    code: str,
    language: str,
    inputs: Sequence[str],
) -> List[Dict[str, Any]]:
    """
    Run ``code`` against every input. Compiles at most once.
    Returns one result dict per input:
        {output, stdout, error, exit_code, kind, time_ms}
    """
    language = normalize_language(language)
    count = len(inputs)
    if count == 0:
        return []

    def same_for_all(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [dict(result) for _ in range(count)]

    spec = get_problem_spec(problem_id)
    if spec is None:
        return same_for_all(make_result(
            "", f"No runner configured for problem {problem_id}.", -1, INTERNAL_ERROR))

    if language not in SUPPORTED_LANGUAGES:
        return same_for_all(make_result(
            "", f"Unsupported language '{language}'. Choose Python, Java, C++ or C.",
            -1, INTERNAL_ERROR))

    if not (code or "").strip():
        return same_for_all(make_result("", "Code is empty.", -1, COMPILE_ERROR))

    # Parse every test input up front.
    parsed: List[Optional[List[Any]]] = []
    parse_errors: Dict[int, str] = {}
    for index, raw in enumerate(inputs):
        try:
            parsed.append(parse_test_input(spec, raw))
        except ValueError as error:
            parsed.append(None)
            parse_errors[index] = f"Invalid test case input: {error}"

    work_dir = tempfile.mkdtemp(prefix=f"coding_mentor_{language}_")
    _hand_over(work_dir)
    try:
        if language == "python":
            prepared = _prepare_python(spec, code, work_dir)
        elif language == "java":
            prepared = _prepare_java(spec, code, work_dir)
        else:
            prepared = _prepare_native(spec, code, work_dir, language)

        if prepared.error:
            return same_for_all(prepared.error)

        def run_index(index: int) -> Dict[str, Any]:
            if index in parse_errors:
                return make_result("", parse_errors[index], -1, INTERNAL_ERROR)
            try:
                return prepared.run_one(index, parsed[index])
            except Exception as error:  # noqa: BLE001
                logger.exception("Test execution failed")
                return make_result("", f"Execution failed: {error}", -1, INTERNAL_ERROR)

        workers = max(1, min(config.MAX_PARALLEL_TESTS, count))
        if workers == 1:
            return [run_index(i) for i in range(count)]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(run_index, range(count)))

    except Exception as error:  # noqa: BLE001
        logger.exception("Judge failed")
        return same_for_all(make_result("", f"Execution failed: {error}", -1, INTERNAL_ERROR))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run_problem(
    problem_id: int, code: str, input_data: str, language: str = "python"
) -> Dict[str, Any]:
    """Run a single test input (kept for backward compatibility)."""
    return judge(problem_id, code, language, [input_data])[0]


def run_two_sum(code: str, input_data: str, language: str = "python") -> Dict[str, Any]:
    return run_problem(1, code, input_data, language)


# =============================================================================
# OUTPUT COMPARISON
# =============================================================================

_MISSING = object()


def _parse_value(text: str) -> Any:
    for parser in (ast.literal_eval, json.loads):
        try:
            return parser(text)
        except Exception:  # noqa: BLE001
            continue
    return _MISSING


def _values_equal(actual: Any, expected: Any, unordered: bool) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return False
        if unordered:
            try:
                actual, expected = sorted(actual), sorted(expected)
            except TypeError:
                pass
        return all(_values_equal(a, e, False) for a, e in zip(actual, expected))

    numbers = (int, float)
    if isinstance(actual, numbers) and isinstance(expected, numbers):
        if isinstance(actual, float) or isinstance(expected, float):
            return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9)
        return actual == expected

    return actual == expected


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).lower()


def compare_output(
    actual: str,
    expected: str,
    unordered: bool = False,
    lenient_ints: bool = False,
) -> bool:
    actual_text = (actual or "").strip()
    expected_text = (expected or "").strip()

    if not actual_text and not expected_text:
        return True
    if not actual_text:
        return False

    actual_value = _parse_value(actual_text)
    expected_value = _parse_value(expected_text)

    if actual_value is not _MISSING and expected_value is not _MISSING:
        return _values_equal(actual_value, expected_value, unordered)

    if lenient_ints and isinstance(expected_value, list):
        # C functions that print their own answer may print "0 1" instead of "[0,1]".
        numbers = [int(match) for match in re.findall(r"-?\d+", actual_text)]
        return _values_equal(numbers, expected_value, unordered)

    return _normalize_text(actual_text) == _normalize_text(expected_text)


def compare_for_problem(problem_id: int, language: str, actual: str, expected: str) -> bool:
    spec = get_problem_spec(problem_id)
    unordered = bool(spec and spec.unordered_output)
    lenient = bool(spec and spec.c_style == "print" and normalize_language(language) == "c")
    return compare_output(actual, expected, unordered=unordered, lenient_ints=lenient)


# =============================================================================
# QUICK SELF-TEST:  python code_runner.py
# =============================================================================

if __name__ == "__main__":
    print("AI Coding Mentor code_runner self-test")
    for tool in ("g++", "gcc", "javac", "java"):
        print(f"  {tool:6s}: {shutil.which(tool) or 'NOT FOUND'}")

    sample = (
        "def two_sum(nums, target):\n"
        "    seen = {}\n"
        "    for i, n in enumerate(nums):\n"
        "        if target - n in seen:\n"
        "            return [seen[target - n], i]\n"
        "        seen[n] = i\n"
    )
    outcome = run_problem(1, sample, "nums=[2,7,11,15], target=9", "python")
    passed = outcome["kind"] == OK and compare_for_problem(1, "python", outcome["output"], "[0,1]")
    print("Two Sum (python):", "PASS" if passed else f"FAIL {outcome}")
    print("Run `python -m pytest tests` for the full multi-language test suite.")
