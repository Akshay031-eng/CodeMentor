import { useEffect, useMemo, useState } from "react";
import "./ProblemList.css";
import { api } from "../services/api";

function ProblemList({ onSelectProblem }) {
    const [problems, setProblems] = useState([]);
    const [search, setSearch] = useState("");
    const [difficulty, setDifficulty] = useState("ALL");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [reloadKey, setReloadKey] = useState(0);
    const [slow, setSlow] = useState(false);

    // Free hosting puts the backend to sleep; the first request can take
    // up to a minute while it wakes up. Tell the visitor instead of spinning.
    useEffect(() => {
        if (!loading) {
            return undefined;
        }

        const timer = setTimeout(() => setSlow(true), 4000);
        return () => clearTimeout(timer);
    }, [loading]);

    useEffect(() => {
        const controller = new AbortController();

        const loadProblems = async () => {
            setLoading(true);
            setError("");

            try {
                const data = await api.getProblems({
                    signal: controller.signal,
                });

                if (!Array.isArray(data)) {
                    throw new Error("Invalid problems response.");
                }

                setProblems(data);
            } catch (err) {
                if (err?.name === "AbortError") return;
                console.error("Problem list error:", err);
                setError(err?.message || "Could not load problems.");
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        };

        loadProblems();

        return () => controller.abort();
    }, [reloadKey]);

    const filteredProblems = useMemo(() => {
        const query = search.trim().toLowerCase();

        return problems.filter((problem) => {
            const title = String(problem?.title || "").toLowerCase();
            const topic = String(problem?.topic || "").toLowerCase();
            const level = String(problem?.difficulty || "").toUpperCase();

            const matchesSearch =
                !query ||
                title.includes(query) ||
                topic.includes(query);

            const matchesDifficulty =
                difficulty === "ALL" || level === difficulty;

            return matchesSearch && matchesDifficulty;
        });
    }, [problems, search, difficulty]);

    if (loading) {
        return (
            <section className="leetcode-problems-page">
                <div className="page-state">
                    <div className="state-spinner" />
                    <h2>{slow ? "Waking up the server..." : "Loading problems..."}</h2>
                    <p>
                        {slow
                            ? "The backend runs on a free plan and sleeps when idle. The first load can take up to a minute - thanks for waiting!"
                            : "Preparing your coding problems."}
                    </p>
                </div>
            </section>
        );
    }

    if (error) {
        return (
            <section className="leetcode-problems-page">
                <div className="page-state error">
                    <div className="state-icon">!</div>
                    <h2>Could not load problems</h2>
                    <p>{error}</p>
                    <button
                        type="button"
                        className="retry-button"
                        onClick={() => setReloadKey((key) => key + 1)}
                    >
                        Try again
                    </button>
                </div>
            </section>
        );
    }

    return (
        <section className="leetcode-problems-page">
            <div className="problems-header">
                <div>
                    <span className="eyebrow">CODING PRACTICE</span>
                    <h1>Problems</h1>
                    <p>
                        Pick a problem, read the statement, then open the editor.
                    </p>
                </div>

                <div className="problems-count">
                    <strong>{filteredProblems.length}</strong>
                    <span>problems</span>
                </div>
            </div>

            <div className="problems-toolbar">
                <div className="search-box">
                    <span aria-hidden="true">⌕</span>
                    <input
                        type="search"
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Search questions..."
                        aria-label="Search problems"
                    />
                    {search && (
                        <button
                            type="button"
                            className="clear-search"
                            onClick={() => setSearch("")}
                            aria-label="Clear search"
                        >
                            ×
                        </button>
                    )}
                </div>

                <div className="difficulty-tabs" role="tablist" aria-label="Difficulty">
                    {["ALL", "EASY", "MEDIUM", "HARD"].map((level) => (
                        <button
                            key={level}
                            type="button"
                            role="tab"
                            aria-selected={difficulty === level}
                            className={
                                difficulty === level
                                    ? "difficulty-tab active"
                                    : "difficulty-tab"
                            }
                            onClick={() => setDifficulty(level)}
                        >
                            {level === "ALL" ? "All" : level[0] + level.slice(1).toLowerCase()}
                        </button>
                    ))}
                </div>
            </div>

            <div className="problem-table" role="table" aria-label="Coding problems">
                <div className="problem-table-head" role="row">
                    <span>#</span>
                    <span>Title</span>
                    <span>Difficulty</span>
                    <span>Topic</span>
                    <span aria-hidden="true" />
                </div>

                {filteredProblems.length === 0 ? (
                    <div className="empty-problems">
                        <strong>No problems found</strong>
                        <span>Try another search or difficulty.</span>
                    </div>
                ) : (
                    filteredProblems.map((problem) => {
                        const level = String(
                            problem?.difficulty || ""
                        ).toLowerCase();

                        return (
                            <button
                                key={problem.id}
                                type="button"
                                className="problem-row"
                                onClick={() => onSelectProblem(problem.id)}
                            >
                                <span className="problem-number">
                                    {String(problem.id).padStart(2, "0")}
                                </span>

                                <span className="problem-title-cell">
                                    <strong>{problem.title}</strong>
                                    <small>
                                        Open problem statement
                                    </small>
                                </span>

                                <span
                                    className={`difficulty-text ${level}`}
                                >
                                    {problem.difficulty || "—"}
                                </span>

                                <span className="topic-text">
                                    {problem.topic ? `#${problem.topic}` : "—"}
                                </span>

                                <span className="problem-row-arrow">›</span>
                            </button>
                        );
                    })
                )}
            </div>
        </section>
    );
}

export default ProblemList;
