import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim() || "";

const supabaseKey = (
    import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
    import.meta.env.VITE_SUPABASE_ANON_KEY ||
    ""
).trim();

const PLACEHOLDER = /your-project-ref|your-anon|APNA|YAHAN_|PASTE_/i;

// A readable explanation instead of a blank page or "Failed to fetch"
// when the environment variables are missing or wrong.
function findConfigError() {
    if (!supabaseUrl) {
        return "VITE_SUPABASE_URL is missing.";
    }
    if (!supabaseKey) {
        return "VITE_SUPABASE_PUBLISHABLE_KEY is missing.";
    }
    if (PLACEHOLDER.test(supabaseUrl) || PLACEHOLDER.test(supabaseKey)) {
        return "The Supabase settings still contain placeholder values from .env.example.";
    }
    if (!/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/i.test(supabaseUrl)) {
        return `VITE_SUPABASE_URL looks wrong: "${supabaseUrl}". It should look like https://xxxxxxxx.supabase.co`;
    }
    if (supabaseKey.startsWith("sb_secret_")) {
        return "VITE_SUPABASE_PUBLISHABLE_KEY contains a SECRET key. Use the publishable (sb_publishable_...) or anon key here - secret keys must never be in the frontend.";
    }
    return "";
}

export const supabaseConfigError = findConfigError();

export const supabase = supabaseConfigError
    ? null
    : createClient(supabaseUrl, supabaseKey);
