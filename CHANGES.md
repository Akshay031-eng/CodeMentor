# Changes — v2.1 (deploy-ready)

**What changed since v2.0** — apply by extracting the new zip over your project folder (your `.env` files, `venv` and `node_modules` are kept).

### Security
- **Sandbox user (Docker):** every compile/run happens as a separate unprivileged `sandbox` user. Student code can no longer kill the API (`os.kill(os.getppid(), 9)` → `PermissionError`), read its secrets or write to the app. Verified with real attack attempts.
- **Limits before start:** CPU, memory, output and a new **process cap** (fork bombs) are applied by `prlimit` *before* the student program runs.
- API process marked non-dumpable on Linux, so `/proc/<pid>/environ` can't leak keys.
- **Rate limiting** per user: 20 runs, 10 submits, 8 mentor questions per minute (`RATE_LIMIT_*` env vars) — protects the server and your Gemini quota.
- `/health` now reports `"sandboxed": true|false`.

### Deployment
- `Backend/Dockerfile` (Python + JDK 17 + gcc/g++, tuned for Render's free 512 MB instance) and `.dockerignore`.
- **`DEPLOY.md`** — step-by-step: GitHub → Render (API) → Vercel (frontend) → Supabase settings, plus troubleshooting.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): backend tests (all 4 languages + Redis queue), frontend lint/build, Docker image build + sandboxed judge smoke test.
- `CORS_ORIGIN_REGEX` for Vercel preview URLs; lazy-loaded LangChain for faster cold starts.
- `Backend/supabase_seed.sql` — the 8 problems + test cases for a fresh Supabase project.

### Frontend
- **Setup error screen** instead of a blank page / "Failed to fetch" when `VITE_SUPABASE_*` is missing, still a placeholder, malformed, or a *secret* key.
- Friendly login error when Supabase is unreachable / paused.
- "Waking up the server…" message while the free backend starts.
- Optional **"Try the demo account"** button (`VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD`).
- Monaco editor: more reliable change tracking with React 19.
- README with screenshots, architecture and judge internals.

### Verified
- 72/72 backend tests pass with the sandbox user active (73 incl. a root-only skip), 64 + skips in normal mode; frontend lint clean, build OK.
- Through the HTTP API with the sandbox active: Python, Java, C++ and C all *Accepted*; kill attempt blocked; fork bomb → *Time Limit Exceeded* with all processes cleaned up and the server still healthy.
- The Docker image itself couldn't be built in this environment (registry access blocked); the CI `docker` job builds and smoke-tests it on your first push.

---

# Changes — v2.0

Everything below was verified: 63 backend tests (all 8 problems × 4 languages, API, real Redis + worker) and a 22-step headless-browser run of the full app. Frontend lint went from 5 warnings to 0.

## ⚠️ Action needed after updating

1. **Backend `.env`** – use the **service-role key**. You can rename `SUPABASE_KEY` to `SUPABASE_SERVICE_ROLE_KEY` (the old name still works). See `Backend/.env.example`.
2. **Reinstall backend packages** – `pip install -r requirements.txt` (the old file was UTF-16 and was missing `redis`, `rq` and `langchain-google-genai`).
3. **Optional** – `python -m rag.ingest_knowledge --force` to re-embed the knowledge base with document embeddings and load the 5 new documents.
4. **Optional** – set `VITE_API_URL` in `Frontend/.env` (defaults to `http://127.0.0.1:8002`).

---

## Critical bugs fixed

| # | Bug | Effect before | Fix |
|---|-----|---------------|-----|
| 1 | `/submit` used `insert().select("id").single()` – `.single()` does not exist on insert queries | **Every submission failed** with an `AttributeError` | Plain `insert().execute()` and read the id from `data[0]` |
| 2 | Redis client created with `decode_responses=True` | RQ stores binary (pickled) jobs → **worker crashed on every job**, submissions stayed "Queued" forever | Removed `decode_responses` |
| 3 | User code ran with the backend's environment and working folder | Any user could `print(os.environ)` to steal the **Supabase service key and Gemini key**, or read `.env` | Minimal environment without secrets + a throw-away temp folder per run |
| 4 | Frontend never checked the result of a submission | Users only ever saw "Queued" | New `GET /submission/{id}` + polling until a final verdict |
| 5 | Switching Problem ↔ Code tab remounted the page | **Code typed by the user was lost** | One component instance per problem + drafts saved in the browser |
| 6 | Changing language replaced the code with the starter template | Code lost on language switch | Separate saved draft per language |
| 7 | `requirements.txt` saved as UTF-16 (PowerShell `pip freeze >`) and missing packages | `pip install` breaks on Linux/CI; queue + RAG imports fail on a fresh install | Clean UTF-8 file with the real direct dependencies |
| 8 | RQ's default worker uses `os.fork()` | `python worker.py` **could not run on Windows** | Windows uses `SimpleWorker` with a timer-based timeout |

## Other bugs fixed

**Backend**
- Errors were returned as HTTP 200 with `{"error": ...}`; the problem list showed "Invalid problems response." instead of the real error → proper 401/404/400/502/503 responses with readable messages.
- Missing/expired login returned 200 → now 401.
- Compiler and runtime errors were both reported as "Runtime Error"; compile timeouts (5 s, too short for `javac` on Windows) were reported as "Time Limit Exceeded" → new verdicts **Compilation Error / Runtime Error / Time Limit Exceeded / Wrong Answer**, and a separate 20 s compile timeout.
- On Windows, program output was decoded with the system code page → crashes on non-ASCII output. Now UTF-8 everywhere (`javac -encoding UTF-8`, `PYTHONUTF8`, etc.).
- Any `print()` debugging made the answer wrong → the result is now separated from debug output, which is shown as **STDOUT**.
- Two Sum answers in a different order (`[1,0]` vs `[0,1]`) were marked wrong → order-insensitive comparison for that problem.
- `1` and `true` were treated as equal answers → booleans and numbers are now compared strictly.
- Test input parsing broke on extra spaces (`nums = [1, 2], target = 3`) or newlines → robust parser.
- AI mentor: JSON wrapped in ```` ```json ```` fences, or list values, ended up as raw text / could crash the React UI → robust JSON extraction, every field normalized to text.
- AI mentor: one failing knowledge-base lookup broke the whole mentor → retrieval failures are logged and the mentor answers without context.
- AI mentor: the problem description was fetched but never sent to Gemini; the chat history was embedded for retrieval (hurting search quality) → description is in the prompt, retrieval uses only problem + question.
- `ai_mentor.py` used `gemini-3.5-flash`, which is not a current model ID → models configurable via `GEMINI_MODELS`.
- RAG ingestion inserted duplicates every time it ran and embedded documents as *queries* → idempotent, uses document embeddings, `--force` to rebuild.

**Frontend**
- The "AI Mentor" button in the editor always showed "Please enter a question" → empty question now means "analyze my solution".
- The chat history was stored but never displayed (`messages` prop not passed) → full conversation shown, with "Clear chat".
- Error messages were rendered as an "analysis" with N/A complexity cards → separate error state.
- The mentor received the whole chat every time; after ~30 questions the request would exceed the API limit → only the last 20 messages are sent.
- Test console showed an empty Output box for crashed programs (`??` doesn't fall through on `""`) → shows the error.
- When the first test case errored, per-test results were thrown away → all results always shown.
- `api.js` pointed to port 8000 and a non-existent `/test` endpoint while components hard-coded port 8002 in 8 places → single API client using `VITE_API_URL`.
- Problem titles were near-black (invisible) on light-mode systems, and the app was capped at 1126 px wide — both leftovers from the Vite template CSS.
- The top bar overflowed on phones (horizontal scroll); the email and Logout button had no styles (white default button).
- FastAPI validation errors showed as `[object Object]` → readable messages.
- Problem numbers in the list changed when filtering (used list index) → real problem ids.
- "Reload" button reloaded the entire page → retries just the request.

## Improvements

**Code execution engine (`code_runner.py`, rewritten)**
- **Compiles once per run** instead of once per test case, and runs test cases in parallel: Java ~5× faster, C++ ~3× faster (measured with 6 test cases).
- One `ProblemSpec` entry per problem generates the Python/Java/C++/C harness — adding a problem is a few lines instead of ~100.
- Compiler errors point to the **user's own line numbers** (`solution.cpp:4`), temp paths are hidden, and a wrong function signature shows a hint with the expected signature.
- Python tracebacks hide the auto-generated harness frames.
- LeetCode-style Python (`class Solution: def twoSum(self, ...)`) is accepted too.
- C/C++ get the common headers automatically (`<unordered_map>`, `<string.h>`, ...).
- Linux: CPU, memory and output-size limits; output goes to files so an infinite `print` loop can't exhaust server memory. Readable messages for segfaults, stack overflows, etc. (Linux and Windows exit codes).
- Runtime per test case is reported (ms).

**Backend**
- New `config.py` (all settings + defaults in one place) and `judge.py` (shared by API and worker — removed duplicated code).
- `SUBMISSION_MODE=auto|queue|inline`: in `auto`, submissions still work when Redis is down.
- `/run` and `/mentor` now require login (they execute code / spend Gemini quota).
- Request size limits (code 50 000 chars, question 2 000 chars).
- Submission history returns the latest 50 and only the user's own; `/health` reports queue status.
- Mentor prompt now includes difficulty, topic, description and **the latest Run result** (failing input, expected vs actual, error), and returns a direct `answer` to the student's question.
- Gemini model fallback list; JSON response mode.
- 5 new knowledge documents: stock (min-tracking), Kadane's algorithm, linked-list reversal, frequency counting, debugging checklist — covering all 8 problems.
- Proper logging instead of `print`.
- Test suite: `python -m pytest tests`.

**Frontend**
- **Monaco editor** (VS Code's editor – it was already in `package.json` but unused) with syntax highlighting and a dark theme matching the app. Falls back to the plain textarea automatically if the CDN is blocked.
- Shortcuts: Ctrl/⌘+Enter run, Ctrl/⌘+Shift+Enter submit, Ctrl/⌘+Enter to ask the mentor.
- Code is auto-saved per problem and language; **Reset** button restores the starter code.
- URL routing (`#/problems/3/code`): refresh and the browser back button keep you where you were.
- Live submission status (Queued → Judging → verdict with passed/total).
- Submission history shows status icons and a **Load** button to restore any previous submission's code.
- Mentor suggestion chips ask immediately.
- Compilation errors shown once in a dedicated panel; debug output in a STDOUT panel; per-test runtime.
- Page title and description; `.env.example`.

## Removed
- Unused components never imported anywhere: `Navbar`, `ProblemPanel`, `ProblemSidebar`, `SubmissionHistory` (+ their CSS), `CodeEditor.css`, Vite template assets and README.

## New files
- `README.md` – setup and run instructions
- `Backend/config.py`, `Backend/judge.py`
- `Backend/.env.example`, `Frontend/.env.example`, `.gitignore`
- `Backend/supabase_schema.sql` – reference schema, vector search function and RLS policies
- `Backend/tests/` – test suite
- `Frontend/src/services/api.js` (rewritten), `src/lib/drafts.js`, `src/lib/starterCodes.js`

## Known limitations / next steps
- Code execution is hardened but not a full sandbox — run the worker in Docker/gVisor before a public launch (see README).
- `/run` still executes inside the API process; for production, route it through the worker as well.
- No rate limiting yet on `/run` and `/mentor` (consider `slowapi` or a Supabase-side quota).
- Test cases have no "hidden" flag, so Run and Submit use the same cases.
