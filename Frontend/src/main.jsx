import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import SetupError from "./SetupError.jsx";
import { supabaseConfigError } from "./lib/supabase";

import "./index.css";

createRoot(document.getElementById("root")).render(
    <StrictMode>
        {supabaseConfigError ? (
            <SetupError message={supabaseConfigError} />
        ) : (
            <App />
        )}
    </StrictMode>
);
