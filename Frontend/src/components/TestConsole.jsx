import { useMemo, useState } from "react";
import "./TestConsole.css";

const FAILURE_LABELS = {
    compile_error: "Compilation Error",
    runtime_error: "Runtime Error",
    timeout: "Time Limit Exceeded",
    internal_error: "Error",
};

const findResult = (results, testCase, index) =>
    results.find(
        (item) =>
            item?.test_case_id !== undefined &&
            String(item.test_case_id) === String(testCase?.id)
    ) ||
    results[index] ||
    null;

function TestConsole({ testCases = [], result = null, running = false }) {
    const safeTestCases = useMemo(
        () => (Array.isArray(testCases) ? testCases : []),
        [testCases]
    );

    const results = useMemo(
        () => (Array.isArray(result?.results) ? result.results : []),
        [result]
    );

    // After every new run, jump to the first failing test. The student can
    // still click any tab; that choice is remembered until the next run.
    const firstFailedIndex = useMemo(() => {
        const index = safeTestCases.findIndex(
            (testCase, i) => findResult(results, testCase, i)?.passed === false
        );
        return index >= 0 ? index : 0;
    }, [results, safeTestCases]);

    const [selection, setSelection] = useState({ result: null, index: 0 });
    const selectedTest =
        selection.result === result ? selection.index : firstFailedIndex;

    const passedCount = results.filter((item) => item?.passed === true).length;
    const failedCount = results.filter((item) => item?.passed === false).length;
    const totalCount = safeTestCases.length;
    const testedCount = results.length;

    const status = result?.status || "";
    const isCompileError = status === "Compilation Error";
    const allPassed = status === "Accepted";

    const statusText = running
        ? "Running"
        : status || (testedCount > 0 ? "Completed" : "Ready");

    const statusClass = running
        ? "running"
        : allPassed
            ? "success"
            : status
                ? "failed"
                : "neutral";

    const currentTest = safeTestCases[selectedTest] || safeTestCases[0] || null;
    const currentResult = result
        ? findResult(results, currentTest, selectedTest)
        : null;

    const currentPassed = currentResult?.passed === true;
    const currentFailed = currentResult?.passed === false;
    const currentActual = currentResult?.actual || currentResult?.output || "";
    const currentError = currentResult?.error || "";
    const currentStdout = currentResult?.stdout || "";

    const failureLabel =
        FAILURE_LABELS[currentResult?.kind] ||
        (currentFailed ? "Wrong Answer" : "");

    return (
        <section className="test-console" aria-label="Test console">
            <div className="test-console-header">
                <div className="test-console-title">
                    <span className="console-icon" aria-hidden="true">
                        ◉
                    </span>

                    <div>
                        <h2>Test Console</h2>
                        <p>Run your code against the test cases</p>
                    </div>
                </div>

                <div className={`console-status ${statusClass}`}>
                    <span className="console-status-dot" />
                    <span>{statusText}</span>
                </div>
            </div>

            {!running && result && !results.length && result.message && (
                <pre className="console-global-error">{result.message}</pre>
            )}

            {!running && isCompileError && currentError && (
                <div className="console-compile-error">
                    <strong>Compilation Error</strong>
                    <pre>{currentError}</pre>
                </div>
            )}

            {safeTestCases.length === 0 ? (
                <div className="console-empty">
                    <div className="console-empty-icon">◇</div>
                    <h3>No test cases</h3>
                    <p>Test cases will appear here.</p>
                </div>
            ) : (
                <>
                    <div className="test-tabs" role="tablist" aria-label="Test cases">
                        {safeTestCases.map((testCase, index) => {
                            const testResult = result
                                ? findResult(results, testCase, index)
                                : null;
                            const passed = testResult?.passed === true;
                            const failed = testResult?.passed === false;

                            return (
                                <button
                                    key={testCase.id ?? index}
                                    type="button"
                                    role="tab"
                                    aria-selected={index === selectedTest}
                                    className={[
                                        "test-tab",
                                        index === selectedTest ? "active" : "",
                                        passed ? "passed" : "",
                                        failed ? "failed" : "",
                                    ].filter(Boolean).join(" ")}
                                    onClick={() => setSelection({ result, index })}
                                >
                                    <span>Testcase {index + 1}</span>

                                    <span
                                        className={
                                            passed
                                                ? "tab-status pass"
                                                : failed
                                                    ? "tab-status fail"
                                                    : "tab-status pending"
                                        }
                                        aria-hidden="true"
                                    >
                                        {passed ? "✓" : failed ? "✕" : ""}
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    <div className="console-content">
                        <div className="console-grid">
                            <div className="console-card">
                                <div className="console-card-header">
                                    <span>INPUT</span>
                                    <span className="card-number">01</span>
                                </div>
                                <pre>{currentTest?.input || "N/A"}</pre>
                            </div>

                            <div className="console-card">
                                <div className="console-card-header">
                                    <span>OUTPUT</span>
                                    <span className="card-number">
                                        {currentResult?.time_ms != null
                                            ? `${currentResult.time_ms} ms`
                                            : "02"}
                                    </span>
                                </div>
                                <pre className={currentFailed ? "output-error" : "output-preview"}>
                                    {running
                                        ? "Running..."
                                        : currentActual ||
                                          (currentError && !isCompileError
                                              ? currentError
                                              : currentResult
                                                  ? "(no output)"
                                                  : "Run your code to see the output...")}
                                </pre>
                            </div>

                            <div className="console-card">
                                <div className="console-card-header">
                                    <span>EXPECTED OUTPUT</span>
                                    <span className="card-number">03</span>
                                </div>
                                <pre>
                                    {currentResult?.expected ??
                                        currentTest?.expected_output ??
                                        "N/A"}
                                </pre>
                            </div>
                        </div>

                        {!running && currentStdout && (
                            <div className="console-stdout">
                                <div className="console-card-header">
                                    <span>STDOUT (your print statements)</span>
                                </div>
                                <pre>{currentStdout}</pre>
                            </div>
                        )}

                        {!running && currentFailed && currentActual && currentError && (
                            <pre className="console-error-detail">{currentError}</pre>
                        )}

                        <div
                            className={[
                                "console-result",
                                currentPassed ? "visible success" : "",
                                currentFailed ? "visible failed" : "",
                            ].filter(Boolean).join(" ")}
                        >
                            <div className="result-left">
                                <span
                                    className={[
                                        "result-icon",
                                        currentPassed ? "success" : "",
                                        currentFailed ? "failed" : "",
                                    ].filter(Boolean).join(" ")}
                                >
                                    {running
                                        ? "…"
                                        : currentPassed
                                            ? "✓"
                                            : currentFailed
                                                ? "✕"
                                                : "○"}
                                </span>

                                <div>
                                    <strong>
                                        {running
                                            ? "Running your code..."
                                            : currentPassed
                                                ? `Testcase ${selectedTest + 1} Passed`
                                                : currentFailed
                                                    ? `Testcase ${selectedTest + 1}: ${failureLabel}`
                                                    : "Ready"}
                                    </strong>

                                    <span>
                                        {running
                                            ? "Executing your solution against every test case..."
                                            : currentPassed
                                                ? "Your output matches the expected output."
                                                : currentFailed
                                                    ? currentResult?.kind === "ok"
                                                        ? "Your output does not match the expected output."
                                                        : "See the error details above."
                                                    : "Run your code to see the result."}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {testedCount > 0 && !running && (
                            <div className="test-summary">
                                <div className="summary-main">
                                    <strong>
                                        {passedCount} / {totalCount} Passed
                                    </strong>
                                    <span>
                                        {failedCount > 0
                                            ? `${failedCount} failed`
                                            : "All tests passed"}
                                    </span>
                                </div>

                                <div className="summary-progress" aria-hidden="true">
                                    <span
                                        style={{
                                            width: `${totalCount > 0
                                                ? Math.round((passedCount / totalCount) * 100)
                                                : 0}%`,
                                        }}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </>
            )}
        </section>
    );
}

export default TestConsole;
