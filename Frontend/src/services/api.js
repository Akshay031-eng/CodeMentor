import { supabase } from "../lib/supabase";

// One place for the backend URL. Override with VITE_API_URL in Frontend/.env
export const API_URL = (
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8002"
).replace(/\/+$/, "");

export class ApiError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.data = data;
    }
}

export function getErrorMessage(data, fallback = "Something went wrong.") {
    if (typeof data === "string" && data.trim()) {
        return data;
    }

    const detail = data?.detail;

    // FastAPI validation errors: [{ loc, msg, type }, ...]
    if (Array.isArray(detail)) {
        const messages = detail
            .map((item) => item?.msg)
            .filter(Boolean);
        if (messages.length) {
            return messages.join(" ");
        }
    }

    return (
        (typeof detail === "string" && detail) ||
        data?.message ||
        data?.error ||
        fallback
    );
}

async function getAccessToken() {
    const { data, error } = await supabase.auth.getSession();

    if (error) {
        console.error("Auth session error:", error);
    }

    return data?.session?.access_token || null;
}

async function readBody(response) {
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        return response.json().catch(() => null);
    }

    return response.text().catch(() => "");
}

/**
 * Call the FastAPI backend.
 * Adds the Supabase access token, parses JSON and throws ApiError on failure.
 */
export async function apiRequest(
    path,
    { method = "GET", body, auth = false, signal } = {}
) {
    const headers = {};

    if (body !== undefined) {
        headers["Content-Type"] = "application/json";
    }

    if (auth) {
        const token = await getAccessToken();

        if (!token) {
            throw new ApiError(
                "Your session has expired. Please sign in again.",
                401
            );
        }

        headers.Authorization = `Bearer ${token}`;
    }

    let response;

    try {
        response = await fetch(`${API_URL}${path}`, {
            method,
            headers,
            body: body === undefined ? undefined : JSON.stringify(body),
            signal,
        });
    } catch (error) {
        if (error?.name === "AbortError") {
            throw error;
        }

        throw new ApiError(
            `Cannot reach the backend at ${API_URL}. Make sure FastAPI is running.`,
            0
        );
    }

    const data = await readBody(response);

    if (!response.ok) {
        throw new ApiError(
            getErrorMessage(data, `Request failed (${response.status}).`),
            response.status,
            data
        );
    }

    return data;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
    getProblems: (options) => apiRequest("/problems", options),

    getProblem: (problemId, options) =>
        apiRequest(`/problems/${problemId}`, options),

    getTestCases: (problemId, options) =>
        apiRequest(`/problems/${problemId}/test-cases`, options),

    runCode: (payload) =>
        apiRequest("/run", { method: "POST", body: payload, auth: true }),

    submitCode: (payload) =>
        apiRequest("/submit", { method: "POST", body: payload, auth: true }),

    getSubmission: (submissionId) =>
        apiRequest(`/submission/${submissionId}`, { auth: true }),

    getSubmissions: (problemId, options) =>
        apiRequest(`/submissions/${problemId}`, { ...options, auth: true }),

    askMentor: (payload) =>
        apiRequest("/mentor", { method: "POST", body: payload, auth: true }),
};
