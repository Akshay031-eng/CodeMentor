import { useCallback, useEffect, useRef, useState } from "react";
import "./ProblemDetails.css";

import AIMentor from "./AIMentor";
import CodeEditor from "./CodeEditor";
import TestConsole from "./TestConsole";
import { api } from "../services/api";
import {
    clearDraft,
    loadDraft,
    loadLanguage,
    saveDraft,
    saveLanguage,
} from "../lib/drafts";
import { getLanguageLabel, getStarterCode } from "../lib/starterCodes";

const PENDING_STATUSES = new Set(["Queued", "Running"]);
const POLL_INTERVAL_MS = 1200;
const POLL_TIMEOUT_MS = 90_000;

const MENTOR_SUGGESTIONS = [
    "Give me a hint without the full solution.",
    "Explain my code step by step.",
    "Find the bug in my code.",
    "Dry run my code.",
    "How can I optimize it?",
    "Explain the time and space complexity.",
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const clip = (text, limit = 600) => {
    const value = String(text ?? "");
    return value.length > limit ? `${value.slice(0, limit)}...` : value;
};

// A short text version of the latest Run, sent to the AI mentor so it can
// explain *why* a test failed.
function buildRunSummary(runResult) {
    if (!runResult?.status) {
        return "";
    }

    const results = Array.isArray(runResult.results) ? runResult.results : [];
    const lines = [
        `Status: ${runResult.status} (${runResult.passed ?? 0}/${runResult.total ?? 0} tests passed).`,
    ];

    const failed = results.find((item) => item?.passed === false);

    if (failed) {
        lines.push(`Failing input: ${clip(failed.input, 300)}`);
        lines.push(`Expected: ${clip(failed.expected, 300)}`);
        lines.push(`Got: ${clip(failed.actual || "(no output)", 300)}`);
        if (failed.error) {
            lines.push(`Error: ${clip(failed.error, 1200)}`);
        }
    } else if (runResult.message) {
        lines.push(`Message: ${clip(runResult.message, 1200)}`);
    }

    return lines.join("\n");
}

const statusClass = (status) => {
    if (status === "Accepted") return "accepted";
    if (PENDING_STATUSES.has(status)) return "pending";
    return "failed";
};

const statusIcon = (status) => {
    if (status === "Accepted") return "✓";
    if (PENDING_STATUSES.has(status)) return "…";
    return "×";
};

function ProblemDetails({
    problemId,
    mode = "question",
    onBack,
    onStartCoding,
    onOpenProblem,
}) {
    const [problem, setProblem] = useState(null);
    const [testCases, setTestCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [testCasesLoading, setTestCasesLoading] = useState(true);
    const [error, setError] = useState("");

    const [code, setCode] = useState("");
    const [language, setLanguage] = useState("python");
    const [running, setRunning] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [judging, setJudging] = useState(false);
    const [runResult, setRunResult] = useState(null);
    const [notice, setNotice] = useState("");
    const [submissionResult, setSubmissionResult] = useState(null);
    const [submissions, setSubmissions] = useState([]);
    const [historyLoaded, setHistoryLoaded] = useState(false);
    const [historyError, setHistoryError] = useState("");

    const [mentorLoading, setMentorLoading] = useState(false);
    const [mentorQuestion, setMentorQuestion] = useState("");
    const [mentorResponse, setMentorResponse] = useState(null);
    const [mentorError, setMentorError] = useState("");
    const [mentorMessages, setMentorMessages] = useState([]);

    const aliveRef = useRef(true);

    useEffect(() => {
        aliveRef.current = true;
        return () => {
            aliveRef.current = false;
        };
    }, []);

    // =====================================================
    // LOAD PROBLEM + TEST CASES
    // =====================================================

    useEffect(() => {
        const controller = new AbortController();

        const loadProblem = async () => {
            setLoading(true);
            setError("");

            try {
                const data = await api.getProblem(problemId, {
                    signal: controller.signal,
                });

                const savedLanguage = loadLanguage(problemId) || "python";
                const savedCode = loadDraft(problemId, savedLanguage);

                setProblem(data);
                setLanguage(savedLanguage);
                setCode(
                    savedCode ??
                        (getStarterCode(problemId, savedLanguage, data?.title) ||
                            data?.starter_code ||
                            "")
                );
            } catch (err) {
                if (err?.name === "AbortError") return;
                console.error("Problem load error:", err);
                setError(err?.message || "Failed to load the problem.");
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        };

        const loadTestCases = async () => {
            setTestCasesLoading(true);

            try {
                const data = await api.getTestCases(problemId, {
                    signal: controller.signal,
                });
                setTestCases(Array.isArray(data) ? data : []);
            } catch (err) {
                if (err?.name === "AbortError") return;
                console.error("Test cases load error:", err);
                setTestCases([]);
            } finally {
                if (!controller.signal.aborted) {
                    setTestCasesLoading(false);
                }
            }
        };

        if (problemId) {
            loadProblem();
            loadTestCases();
        }

        return () => controller.abort();
    }, [problemId]);

    // =====================================================
    // SUBMISSION HISTORY
    // =====================================================

    const applyHistory = useCallback((data, err) => {
        if (!aliveRef.current) return;

        if (err) {
            console.error("Submission history error:", err);
            setHistoryError(err?.message || "Could not load history.");
        } else {
            setSubmissions(Array.isArray(data) ? data : []);
            setHistoryError("");
        }
        setHistoryLoaded(true);
    }, []);

    // Refresh after a submission (not tied to an effect).
    const loadSubmissions = useCallback(async () => {
        try {
            applyHistory(await api.getSubmissions(problemId));
        } catch (err) {
            applyHistory(null, err);
        }
    }, [problemId, applyHistory]);

    const isEditor = mode === "editor";

    useEffect(() => {
        if (!isEditor || !problemId) {
            return undefined;
        }

        const controller = new AbortController();

        const loadInitialHistory = async () => {
            try {
                const data = await api.getSubmissions(problemId, {
                    signal: controller.signal,
                });
                applyHistory(data);
            } catch (err) {
                if (err?.name !== "AbortError") {
                    applyHistory(null, err);
                }
            }
        };

        loadInitialHistory();
        return () => controller.abort();
    }, [isEditor, problemId, applyHistory]);

    // =====================================================
    // EDITOR ACTIONS
    // =====================================================

    const updateCode = (value) => {
        setCode(value);
        saveDraft(problemId, language, value);
    };

    const changeLanguage = (nextLanguage) => {
        if (nextLanguage === language) return;

        saveDraft(problemId, language, code);
        saveLanguage(problemId, nextLanguage);

        setLanguage(nextLanguage);
        setCode(
            loadDraft(problemId, nextLanguage) ??
                getStarterCode(problemId, nextLanguage, problem?.title) ??
                ""
        );
        setRunResult(null);
        setNotice("");
        setSubmissionResult(null);
    };

    const resetCode = () => {
        const confirmed = window.confirm(
            `Reset your ${getLanguageLabel(language)} code to the starter template?`
        );
        if (!confirmed) return;

        clearDraft(problemId, language);
        setCode(getStarterCode(problemId, language, problem?.title) || "");
        setRunResult(null);
        setNotice("");
    };

    const loadSubmissionCode = (submission) => {
        if (!submission?.code) return;

        const confirmed = window.confirm(
            "Replace the code in the editor with this submission?"
        );
        if (!confirmed) return;

        const submissionLanguage = submission.language || language;

        saveDraft(problemId, submissionLanguage, submission.code);
        saveLanguage(problemId, submissionLanguage);
        setLanguage(submissionLanguage);
        setCode(submission.code);
        setRunResult(null);
        setNotice("");

        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    const runCode = async () => {
        if (!String(code || "").trim()) {
            setNotice("Please write some code first.");
            return;
        }

        setRunning(true);
        setNotice("");
        setRunResult(null);

        try {
            const data = await api.runCode({
                problem_id: Number(problemId),
                code,
                language,
            });
            setRunResult(data);
        } catch (err) {
            console.error("Run code error:", err);
            setRunResult({
                status: "Error",
                message: err?.message || "Code execution failed.",
                results: [],
            });
        } finally {
            setRunning(false);
        }
    };

    const pollSubmission = async (submissionId) => {
        const startedAt = Date.now();

        while (aliveRef.current && Date.now() - startedAt < POLL_TIMEOUT_MS) {
            await sleep(POLL_INTERVAL_MS);

            try {
                const latest = await api.getSubmission(submissionId);

                if (!aliveRef.current) return;
                setSubmissionResult(latest);

                if (!PENDING_STATUSES.has(latest?.status)) {
                    return latest;
                }
            } catch (err) {
                console.error("Submission status error:", err);
            }
        }

        if (aliveRef.current) {
            setSubmissionResult((current) => ({
                ...current,
                message:
                    "Still judging. Check Submission History in a moment " +
                    "(is the worker running?).",
            }));
        }
        return null;
    };

    const submitCode = async () => {
        if (!String(code || "").trim()) {
            setNotice("Please write some code first.");
            return;
        }

        setSubmitting(true);
        setNotice("");
        setSubmissionResult(null);

        let submissionId = null;

        try {
            const data = await api.submitCode({
                problem_id: Number(problemId),
                code,
                language,
            });

            submissionId = data?.submission_id;
            setSubmissionResult({ ...data, status: data?.status || "Queued" });
            loadSubmissions();
        } catch (err) {
            console.error("Submit code error:", err);
            setSubmissionResult({
                status: "Error",
                message: err?.message || "Submission failed.",
            });
        } finally {
            setSubmitting(false);
        }

        if (!submissionId) return;

        setJudging(true);
        try {
            await pollSubmission(submissionId);
        } finally {
            if (aliveRef.current) {
                setJudging(false);
                loadSubmissions();
            }
        }
    };

    const askMentor = async (presetQuestion) => {
        if (!String(code || "").trim()) {
            setMentorError("Please write some code first.");
            return;
        }

        const question = (
            typeof presetQuestion === "string" ? presetQuestion : mentorQuestion
        ).trim();

        setMentorLoading(true);
        setMentorError("");

        try {
            const data = await api.askMentor({
                problem_id: Number(problemId),
                code,
                question,
                language,
                // Only recent turns: keeps requests small and within the API limit.
                conversation: mentorMessages.slice(-20),
                run_summary: buildRunSummary(runResult),
            });

            setMentorResponse(data);
            setMentorMessages((previous) => [
                ...previous,
                {
                    role: "user",
                    content: question || "Analyze my solution.",
                },
                {
                    role: "assistant",
                    content:
                        data?.answer ||
                        data?.approach ||
                        data?.how_it_works ||
                        "Here is my analysis of your solution.",
                },
            ]);
            setMentorQuestion("");
        } catch (err) {
            console.error("AI Mentor error:", err);
            setMentorError(err?.message || "AI Mentor request failed.");
        } finally {
            setMentorLoading(false);
        }
    };

    const clearMentorChat = () => {
        setMentorMessages([]);
        setMentorResponse(null);
        setMentorError("");
    };

    // =====================================================
    // RENDER: LOADING / ERROR
    // =====================================================

    if (loading) {
        return (
            <div className="problem-state-page">
                <div className="state-spinner" />
                <h2>Loading problem...</h2>
            </div>
        );
    }

    if (error || !problem) {
        return (
            <div className="problem-state-page error">
                <div className="state-icon">!</div>
                <h2>{error || "Problem not found."}</h2>
                <button
                    type="button"
                    className="state-back-button"
                    onClick={onBack}
                >
                    ← Back to Problems
                </button>
            </div>
        );
    }

    const difficulty = String(problem.difficulty || "").toLowerCase();

    const constraints = Array.isArray(problem.constraints)
        ? problem.constraints
        : typeof problem.constraints === "string"
            ? problem.constraints.split("\n").filter(Boolean)
            : [];

    // =====================================================
    // RENDER: QUESTION
    // =====================================================

    if (mode === "question") {
        return (
            <div className="question-page">
                <div className="question-topbar">
                    <button
                        type="button"
                        className="back-link"
                        onClick={onBack}
                    >
                        ← Problems
                    </button>

                    <div className="question-tabs">
                        <button
                            type="button"
                            className="question-tab active"
                        >
                            Problem
                        </button>
                        <button
                            type="button"
                            className="question-tab"
                            onClick={onStartCoding}
                        >
                            Code
                        </button>
                    </div>
                </div>

                <main className="question-shell">
                    <article className="question-card">
                        <div className="question-header">
                            <div>
                                <span className="question-number">
                                    PROBLEM #{problem.id}
                                </span>
                                <h1>{problem.title}</h1>

                                <div className="question-meta">
                                    <span
                                        className={`question-difficulty ${difficulty}`}
                                    >
                                        {problem.difficulty || "—"}
                                    </span>
                                    {problem.topic && (
                                        <span className="question-topic">
                                            #{problem.topic}
                                        </span>
                                    )}
                                </div>
                            </div>

                            <button
                                type="button"
                                className="start-coding-button"
                                onClick={onStartCoding}
                            >
                                Solve Problem
                                <span>→</span>
                            </button>
                        </div>

                        <div className="question-divider" />

                        <section className="statement-section">
                            <h2>Problem</h2>
                            <div className="statement-text">
                                {problem.description}
                            </div>
                        </section>

                        <section className="statement-section">
                            <div className="section-title-row">
                                <h2>Examples</h2>
                                <span>{testCases.length}</span>
                            </div>

                            {testCasesLoading ? (
                                <div className="inline-loading">
                                    Loading examples...
                                </div>
                            ) : testCases.length === 0 ? (
                                <div className="inline-empty">
                                    No examples available.
                                </div>
                            ) : (
                                <div className="question-examples">
                                    {testCases.map((testCase, index) => (
                                        <div
                                            className="question-example"
                                            key={testCase.id ?? index}
                                        >
                                            <strong>
                                                Example {index + 1}
                                            </strong>

                                            <div className="example-code-row">
                                                <span>Input</span>
                                                <pre>{testCase.input}</pre>
                                            </div>

                                            <div className="example-code-row">
                                                <span>Output</span>
                                                <pre>{testCase.expected_output}</pre>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        {constraints.length > 0 && (
                            <section className="statement-section">
                                <h2>Constraints</h2>
                                <ul className="constraints-list">
                                    {constraints.map((constraint, index) => (
                                        <li key={`${constraint}-${index}`}>
                                            {constraint}
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}

                        <div className="question-footer">
                            <button
                                type="button"
                                className="start-coding-button footer-button"
                                onClick={onStartCoding}
                            >
                                Start Coding
                                <span>→</span>
                            </button>
                        </div>
                    </article>
                </main>
            </div>
        );
    }

    // =====================================================
    // RENDER: EDITOR
    // =====================================================

    const submissionStatus = submissionResult?.status;
    const submissionPending = PENDING_STATUSES.has(submissionStatus);

    return (
        <div className="editor-page">
            <header className="editor-page-topbar">
                <button
                    type="button"
                    className="editor-back-link"
                    onClick={onBack}
                >
                    ← Problem
                </button>

                <div className="editor-problem-heading">
                    <span>#{problem.id}</span>
                    <strong>{problem.title}</strong>
                </div>

                <div className="editor-page-tabs">
                    <button
                        type="button"
                        className="editor-page-tab"
                        onClick={onOpenProblem}
                    >
                        Problem
                    </button>
                    <button
                        type="button"
                        className="editor-page-tab active"
                    >
                        Code
                    </button>
                </div>
            </header>

            <main className="coding-layout">
                <aside className="coding-problem-panel">
                    <div className="coding-problem-header">
                        <span className="question-number">
                            PROBLEM #{problem.id}
                        </span>
                        <h1>{problem.title}</h1>
                        <div className="question-meta">
                            <span className={`question-difficulty ${difficulty}`}>
                                {problem.difficulty || "—"}
                            </span>
                            {problem.topic && (
                                <span className="question-topic">
                                    #{problem.topic}
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="coding-problem-scroll">
                        <section className="coding-description">
                            <h2>Description</h2>
                            <p>{problem.description}</p>
                        </section>

                        <section className="coding-examples">
                            <div className="section-title-row">
                                <h2>Examples</h2>
                                <span>{testCases.length}</span>
                            </div>

                            {testCasesLoading ? (
                                <div className="inline-loading">
                                    Loading...
                                </div>
                            ) : (
                                testCases.map((testCase, index) => (
                                    <div
                                        className="coding-example"
                                        key={testCase.id ?? index}
                                    >
                                        <strong>Example {index + 1}</strong>
                                        <span>Input</span>
                                        <pre>{testCase.input}</pre>
                                        <span>Output</span>
                                        <pre>{testCase.expected_output}</pre>
                                    </div>
                                ))
                            )}
                        </section>
                    </div>
                </aside>

                <section className="coding-main-panel">
                    <CodeEditor
                        code={code}
                        setCode={updateCode}
                        language={language}
                        setLanguage={changeLanguage}
                        onRun={runCode}
                        onSubmit={submitCode}
                        onMentor={askMentor}
                        onReset={resetCode}
                        running={running}
                        submitting={submitting}
                        judging={judging}
                        mentoring={mentorLoading}
                    />

                    <section className="editor-results-panel">
                        <div className="results-title-row">
                            <div>
                                <span className="question-number">TEST & RESULT</span>
                                <h2>Results</h2>
                            </div>
                            <button
                                type="button"
                                className="result-reset-button"
                                onClick={() => {
                                    setNotice("");
                                    setRunResult(null);
                                    setSubmissionResult(null);
                                }}
                                disabled={running}
                            >
                                Clear
                            </button>
                        </div>

                        {notice && (
                            <pre className="execution-output">{notice}</pre>
                        )}

                        {submissionResult && (
                            <section className="submission-panel">
                                <div
                                    className={`submission-banner ${statusClass(submissionStatus)}`}
                                    role="status"
                                >
                                    <strong>
                                        {submissionPending
                                            ? submissionStatus === "Running"
                                                ? "Judging your submission..."
                                                : "Submission queued..."
                                            : submissionStatus || "Submission Result"}
                                    </strong>

                                    {!submissionPending &&
                                        Number(submissionResult.total) > 0 && (
                                            <span>
                                                {submissionResult.passed} / {submissionResult.total} test cases passed
                                            </span>
                                        )}
                                </div>

                                {submissionResult.message &&
                                    (submissionStatus === "Error" ||
                                        submissionResult.message.startsWith("Still")) && (
                                        <p className="submission-message">
                                            {submissionResult.message}
                                        </p>
                                    )}

                                {!submissionPending &&
                                    submissionStatus &&
                                    submissionStatus !== "Accepted" &&
                                    submissionStatus !== "Error" && (
                                        <p className="submission-message">
                                            Click Run to see which test case fails and why.
                                        </p>
                                    )}
                            </section>
                        )}

                        <TestConsole
                            testCases={testCases}
                            result={runResult}
                            running={running}
                        />
                    </section>

                    <section className="mentor-panel-wrapper">
                        <div className="mentor-panel-heading">
                            <div>
                                <span className="question-number">AI MENTOR</span>
                                <h2>Ask about your solution</h2>
                                <p>
                                    Get hints, explanations, debugging help, and complexity analysis.
                                    The mentor also sees your latest Run result.
                                </p>
                            </div>
                        </div>

                        <div className="mentor-input-row">
                            <textarea
                                value={mentorQuestion}
                                onChange={(event) =>
                                    setMentorQuestion(event.target.value)
                                }
                                onKeyDown={(event) => {
                                    if (
                                        (event.ctrlKey || event.metaKey) &&
                                        event.key === "Enter" &&
                                        !mentorLoading
                                    ) {
                                        event.preventDefault();
                                        askMentor();
                                    }
                                }}
                                placeholder="Ask your AI mentor a question... (leave empty for a full analysis)"
                                rows={3}
                                maxLength={2000}
                            />
                            <button
                                type="button"
                                className="mentor-ask-button"
                                onClick={() => askMentor()}
                                disabled={mentorLoading}
                            >
                                {mentorLoading ? "Thinking..." : "Ask Mentor"}
                            </button>
                        </div>

                        <div className="mentor-suggestions-row">
                            {MENTOR_SUGGESTIONS.map((text) => (
                                <button
                                    type="button"
                                    key={text}
                                    onClick={() => askMentor(text)}
                                    disabled={mentorLoading}
                                    title="Ask this question"
                                >
                                    {text.replace(/\.$/, "")}
                                </button>
                            ))}
                        </div>

                        <AIMentor
                            response={mentorResponse}
                            loading={mentorLoading}
                            messages={mentorMessages}
                            onClear={clearMentorChat}
                            error={mentorError}
                        />
                    </section>

                    <section className="history-panel">
                        <div className="results-title-row">
                            <div>
                                <span className="question-number">ACTIVITY</span>
                                <h2>Submission History</h2>
                            </div>
                            <span className="history-count">
                                {submissions.length}
                            </span>
                        </div>

                        {!historyLoaded ? (
                            <div className="inline-loading">
                                Loading history...
                            </div>
                        ) : historyError ? (
                            <div className="inline-empty">{historyError}</div>
                        ) : submissions.length === 0 ? (
                            <div className="inline-empty">
                                No submissions yet.
                            </div>
                        ) : (
                            <div className="history-list">
                                {submissions.map((submission) => (
                                    <div
                                        className="history-row"
                                        key={submission.id}
                                    >
                                        <span
                                            className={`history-status ${statusClass(submission.status)}`}
                                        >
                                            {statusIcon(submission.status)}
                                        </span>
                                        <strong>{submission.status}</strong>
                                        <span>{getLanguageLabel(submission.language)}</span>
                                        <span>
                                            {submission.passed}/{submission.total}
                                        </span>
                                        <small>
                                            {submission.created_at
                                                ? new Date(
                                                      submission.created_at
                                                  ).toLocaleString()
                                                : "Unknown"}
                                        </small>
                                        {submission.code ? (
                                            <button
                                                type="button"
                                                className="history-load-button"
                                                onClick={() => loadSubmissionCode(submission)}
                                                title="Load this code into the editor"
                                            >
                                                Load
                                            </button>
                                        ) : (
                                            <span />
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>
                </section>
            </main>
        </div>
    );
}

export default ProblemDetails;
