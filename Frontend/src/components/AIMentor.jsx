import { useMemo } from "react";
import "./AIMentor.css";

function AIMentor({ response, loading, messages = [], onClear = null, error = "" }) {
    const isObject = response && typeof response === "object";

    const answer = useMemo(() => {
        if (!isObject) return String(response || "");
        return (
            response.answer ||
            response.approach ||
            response.how_it_works ||
            ""
        );
    }, [response, isObject]);

    const approach = isObject ? response.approach || "" : answer;
    const howItWorks = isObject ? response.how_it_works || "" : "";
    const timeComplexity = isObject ? response.time_complexity || "" : "";
    const spaceComplexity = isObject ? response.space_complexity || "" : "";
    const goodPoints = isObject ? response.good_points || "" : "";
    const improvements = isObject ? response.improvements || "" : "";

    const sources =
        isObject && Array.isArray(response.sources)
            ? response.sources
            : [];

    const getSimilarity = (similarity) => {
        const value = Number(similarity);
        if (Number.isNaN(value)) return 0;
        return Math.max(0, Math.min(100, value * 100));
    };

    const normalizedMessages = Array.isArray(messages)
        ? messages.filter(
              (message) =>
                  message &&
                  (message.role === "user" || message.role === "assistant") &&
                  String(message.content ?? "").trim()
          )
        : [];

    return (
        <section className="ai-mentor">
            <div className="ai-mentor-header">
                <div className="ai-mentor-title">
                    <div className="ai-mentor-icon">✦</div>
                    <div>
                        <h2>AI Coding Mentor</h2>
                        <p>Guidance from your code + RAG knowledge</p>
                    </div>
                </div>

                <div className="ai-mentor-header-actions">
                    <span className="ai-mentor-badge">RAG + GEMINI</span>
                    {typeof onClear === "function" && normalizedMessages.length > 0 && (
                        <button
                            type="button"
                            className="ai-clear-button"
                            onClick={onClear}
                            disabled={loading}
                        >
                            Clear chat
                        </button>
                    )}
                </div>
            </div>

            {error && !loading && (
                <div className="ai-mentor-error" role="alert">
                    <span>!</span>
                    <p>{error}</p>
                </div>
            )}

            {normalizedMessages.length > 0 ? (
                <>
                    <div className="ai-chat-list">
                        {normalizedMessages.map((message, index) => {
                            const isUser = message.role === "user";

                            return (
                                <div
                                    className={`ai-chat-row ${isUser ? "user" : "assistant"}`}
                                    key={`${message.role}-${index}`}
                                >
                                    <div className="ai-chat-avatar">
                                        {isUser ? "A" : "✦"}
                                    </div>
                                    <div className="ai-chat-bubble">
                                        <div className="ai-chat-label">
                                            {isUser ? "You" : "AI Mentor"}
                                        </div>
                                        <div className="ai-chat-content">
                                            {String(message.content)}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {loading && (
                        <div className="ai-mentor-loading-panel">
                            <div className="ai-loading-dots" aria-hidden="true">
                                <span />
                                <span />
                                <span />
                            </div>
                            <div>
                                <strong>Mentor is thinking...</strong>
                                <p>Analyzing your code and retrieving useful knowledge.</p>
                            </div>
                        </div>
                    )}
                </>
            ) : loading ? (
                <div className="ai-mentor-loading-panel">
                    <div className="ai-loading-dots" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                    </div>
                    <div>
                        <strong>Mentor is thinking...</strong>
                        <p>Analyzing your code and retrieving useful knowledge.</p>
                    </div>
                </div>
            ) : response ? (
                <div className="ai-response-preview">
                    <div className="ai-chat-row assistant">
                        <div className="ai-chat-avatar">✦</div>
                        <div className="ai-chat-bubble">
                            <div className="ai-chat-label">AI Mentor</div>
                            <div className="ai-chat-content">
                                {answer || "Your mentor response is ready."}
                            </div>
                        </div>
                    </div>
                </div>
            ) : error ? null : (
                <div className="ai-empty-panel">
                    <div className="ai-empty-icon">✦</div>
                    <h3>Ask your mentor</h3>
                    <p>
                        Get hints, debugging help, dry runs, optimization tips,
                        and complexity explanations without leaving the coding page.
                    </p>
                </div>
            )}

            {isObject && !loading && (
                <div className="ai-analysis">
                    <div className="ai-analysis-heading">
                        <span className="ai-section-kicker">LATEST ANALYSIS</span>
                        <h3>Solution feedback</h3>
                    </div>

                    {approach && (
                        <section className="ai-section">
                            <div className="ai-section-header">
                                <span className="ai-section-icon">⌁</span>
                                <span className="ai-section-title">Approach</span>
                            </div>
                            <div className="ai-section-content">{approach}</div>
                        </section>
                    )}

                    {howItWorks && (
                        <section className="ai-section">
                            <div className="ai-section-header">
                                <span className="ai-section-icon">◎</span>
                                <span className="ai-section-title">How it works</span>
                            </div>
                            <div className="ai-section-content">{howItWorks}</div>
                        </section>
                    )}

                    <div className="ai-complexity">
                        <div className="complexity-card">
                            <span className="complexity-label">Time complexity</span>
                            <strong className="complexity-value">
                                {timeComplexity || "N/A"}
                            </strong>
                        </div>
                        <div className="complexity-card">
                            <span className="complexity-label">Space complexity</span>
                            <strong className="complexity-value">
                                {spaceComplexity || "N/A"}
                            </strong>
                        </div>
                    </div>

                    {goodPoints && (
                        <section className="ai-section ai-good">
                            <div className="ai-section-header">
                                <span className="ai-section-icon">✓</span>
                                <span className="ai-section-title">What's good</span>
                            </div>
                            <div className="ai-section-content">{goodPoints}</div>
                        </section>
                    )}

                    {improvements && (
                        <section className="ai-section ai-improvement">
                            <div className="ai-section-header">
                                <span className="ai-section-icon">↗</span>
                                <span className="ai-section-title">Improvements</span>
                            </div>
                            <div className="ai-section-content">{improvements}</div>
                        </section>
                    )}

                    {sources.length > 0 && (
                        <section className="mentor-sources">
                            <div className="sources-header">
                                <div className="sources-icon">⌘</div>
                                <div>
                                    <h3>Knowledge used</h3>
                                    <p>Retrieved from your RAG knowledge base</p>
                                </div>
                            </div>

                            <div className="source-list">
                                {sources.map((source, index) => {
                                    const similarity = getSimilarity(source?.similarity);

                                    return (
                                        <div
                                            className="source-item"
                                            key={`${source?.title || "source"}-${index}`}
                                        >
                                            <div className="source-main">
                                                <div className="source-title-row">
                                                    <strong>
                                                        {source?.title || "Knowledge Document"}
                                                    </strong>
                                                    {source?.category && (
                                                        <span className="source-category">
                                                            {source.category}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="source-progress">
                                                    <span
                                                        style={{ width: `${similarity}%` }}
                                                    />
                                                </div>
                                            </div>
                                            <div className="source-score-wrapper">
                                                <strong>{similarity.toFixed(1)}%</strong>
                                                <span>match</span>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            <p className="rag-info">
                                Semantic retrieval selected these documents as context for the mentor response.
                            </p>
                        </section>
                    )}
                </div>
            )}
        </section>
    );
}

export default AIMentor;
