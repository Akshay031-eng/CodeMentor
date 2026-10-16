import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";

import { LANGUAGES, getLanguageLabel } from "../lib/starterCodes";

// If Monaco (loaded from a CDN) is blocked or offline, fall back to a textarea.
const MONACO_LOAD_TIMEOUT_MS = 12000;

const MONACO_OPTIONS = {
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: '"JetBrains Mono", "Cascadia Code", Consolas, monospace',
    lineHeight: 22,
    tabSize: 4,
    insertSpaces: true,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    padding: { top: 16, bottom: 16 },
    renderLineHighlight: "line",
    smoothScrolling: true,
    bracketPairColorization: { enabled: true },
};

const defineTheme = (monaco) => {
    monaco.editor.defineTheme("codementor-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [],
        colors: {
            "editor.background": "#08080c",
            "editorGutter.background": "#08080c",
            "editor.lineHighlightBackground": "#121217",
            "editorLineNumber.foreground": "#3d3d46",
            "editorLineNumber.activeForeground": "#9a9aa3",
        },
    });
};

const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");

const MOD_KEY = isMac ? "⌘" : "Ctrl";

function CodeEditor({
    code,
    setCode,
    language,
    setLanguage,
    onRun,
    onSubmit,
    onMentor,
    onReset,
    running = false,
    submitting = false,
    judging = false,
    mentoring = false,
}) {
    const busy = running || submitting || mentoring;
    const submitDisabled = busy || judging;

    const [editorReady, setEditorReady] = useState(false);
    const [useFallback, setUseFallback] = useState(false);

    // Monaco listeners are registered once, so they read the latest props
    // through refs. A layout effect updates them before @monaco-editor/react
    // syncs the `value` prop (a passive effect), so a language switch or reset
    // is never mistaken for a user edit.
    const actionsRef = useRef({});
    const codeRef = useRef(code);
    const setCodeRef = useRef(setCode);
    useLayoutEffect(() => {
        actionsRef.current = { onRun, onSubmit, busy, submitDisabled };
        codeRef.current = code;
        setCodeRef.current = setCode;
    });

    useEffect(() => {
        if (editorReady || useFallback) {
            return undefined;
        }

        const timer = setTimeout(
            () => setUseFallback(true),
            MONACO_LOAD_TIMEOUT_MS
        );

        return () => clearTimeout(timer);
    }, [editorReady, useFallback]);

    const handleMount = (editor, monaco) => {
        setEditorReady(true);

        // Subscribe directly instead of using <Editor onChange>: with React 19
        // the wrapper can miss the very first change made right after mount.
        const syncFromEditor = () => {
            const value = editor.getValue();
            if (value !== codeRef.current) {
                codeRef.current = value;
                setCodeRef.current?.(value);
            }
        };
        editor.onDidChangeModelContent(syncFromEditor);
        // Catch anything that changed between editor creation and this callback.
        syncFromEditor();

        editor.addCommand(
            monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
            () => {
                const actions = actionsRef.current;
                if (!actions.busy) actions.onRun?.();
            }
        );

        editor.addCommand(
            monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter,
            () => {
                const actions = actionsRef.current;
                if (!actions.submitDisabled) actions.onSubmit?.();
            }
        );
    };

    const handleTextareaKeyDown = (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            if (event.shiftKey) {
                if (!submitDisabled) onSubmit?.();
            } else if (!busy) {
                onRun?.();
            }
            return;
        }

        if (event.key !== "Tab") return;

        event.preventDefault();
        const textarea = event.currentTarget;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const value = String(code || "");

        setCode(value.slice(0, start) + "    " + value.slice(end));

        requestAnimationFrame(() => {
            textarea.selectionStart = start + 4;
            textarea.selectionEnd = start + 4;
        });
    };

    const formatCode = () => {
        const lines = String(code || "")
            .split("\n")
            .map((line) => line.replace(/[ \t]+$/g, ""));
        const formatted = lines.join("\n").trimEnd();
        setCode(formatted ? `${formatted}\n` : "");
    };

    const monacoLanguage =
        LANGUAGES.find((item) => item.value === language)?.monaco || "plaintext";

    return (
        <section className="leetcode-editor">
            <div className="leetcode-editor-topbar">
                <div className="editor-topbar-left">
                    <span className="editor-live-dot" />
                    <strong>Code</strong>
                    <span className="editor-language-label">
                        {getLanguageLabel(language)}
                    </span>
                </div>

                <div className="editor-topbar-actions">
                    {onReset && (
                        <button
                            type="button"
                            className="small-editor-button"
                            onClick={onReset}
                            disabled={busy}
                            title="Restore the starter code"
                        >
                            Reset
                        </button>
                    )}

                    <button
                        type="button"
                        className="small-editor-button"
                        onClick={formatCode}
                        disabled={busy || !String(code || "").trim()}
                        title="Trim trailing whitespace"
                    >
                        Format
                    </button>

                    <label className="language-picker">
                        <span className="sr-only">Language</span>
                        <select
                            value={language}
                            onChange={(event) => setLanguage(event.target.value)}
                            disabled={busy}
                        >
                            {LANGUAGES.map((item) => (
                                <option key={item.value} value={item.value}>
                                    {item.label}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
            </div>

            <div className="leetcode-code-body">
                {useFallback ? (
                    <textarea
                        className="leetcode-code-area"
                        value={code || ""}
                        onChange={(event) => setCode(event.target.value)}
                        onKeyDown={handleTextareaKeyDown}
                        spellCheck={false}
                        autoCapitalize="off"
                        autoCorrect="off"
                        placeholder="Write your solution here..."
                        aria-label="Code editor"
                    />
                ) : (
                    <Editor
                        height="460px"
                        language={monacoLanguage}
                        value={code || ""}
                        beforeMount={defineTheme}
                        onMount={handleMount}
                        theme="codementor-dark"
                        options={MONACO_OPTIONS}
                        loading={
                            <div className="editor-loading">
                                Loading editor...
                            </div>
                        }
                    />
                )}
            </div>

            <div className="leetcode-editor-footer">
                <div className="editor-status-line">
                    <span className="status-dot" />
                    <span>
                        {running
                            ? "Running"
                            : submitting
                                ? "Submitting"
                                : judging
                                    ? "Judging your submission"
                                    : mentoring
                                        ? "AI Mentor is thinking"
                                        : "Ready"}
                    </span>
                    <span className="editor-shortcut-hint">
                        {MOD_KEY}+Enter run · {MOD_KEY}+Shift+Enter submit
                    </span>
                </div>

                <div className="editor-action-group">
                    <button
                        type="button"
                        className="editor-run-button"
                        onClick={onRun}
                        disabled={busy}
                    >
                        {running ? "Running..." : "Run"}
                    </button>

                    <button
                        type="button"
                        className="editor-submit-button"
                        onClick={onSubmit}
                        disabled={submitDisabled}
                    >
                        {submitting
                            ? "Submitting..."
                            : judging
                                ? "Judging..."
                                : "Submit"}
                    </button>

                    <button
                        type="button"
                        className="editor-mentor-button"
                        onClick={() => onMentor?.()}
                        disabled={busy}
                    >
                        {mentoring ? "Thinking..." : "AI Mentor"}
                    </button>
                </div>
            </div>
        </section>
    );
}

export default CodeEditor;
