// Saves the code a student is writing so it survives page reloads,
// tab switches and language changes. Storage may be unavailable
// (private mode, blocked cookies), so every call is wrapped in try/catch.

const PREFIX = "codementor:draft";

const draftKey = (problemId, language) =>
    `${PREFIX}:${problemId}:${language}`;

const languageKey = (problemId) => `${PREFIX}:${problemId}:language`;

export function loadDraft(problemId, language) {
    try {
        return window.localStorage.getItem(draftKey(problemId, language));
    } catch {
        return null;
    }
}

export function saveDraft(problemId, language, code) {
    try {
        window.localStorage.setItem(draftKey(problemId, language), code ?? "");
    } catch {
        // Ignore quota / privacy errors - drafts are a convenience.
    }
}

export function clearDraft(problemId, language) {
    try {
        window.localStorage.removeItem(draftKey(problemId, language));
    } catch {
        // ignore
    }
}

export function loadLanguage(problemId) {
    try {
        return window.localStorage.getItem(languageKey(problemId));
    } catch {
        return null;
    }
}

export function saveLanguage(problemId, language) {
    try {
        window.localStorage.setItem(languageKey(problemId), language);
    } catch {
        // ignore
    }
}
