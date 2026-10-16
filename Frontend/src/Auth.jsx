import { useState } from "react";
import { supabase } from "./lib/supabase";
import "./Auth.css";

// Optional one-click demo account (set both in Frontend/.env or on Vercel).
// Create this user in Supabase -> Authentication -> Users -> Add user.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL?.trim() || "";
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "";

function friendlyAuthError(error) {
    const message = String(error?.message || "");

    if (/failed to fetch|networkerror|load failed/i.test(message)) {
        return (
            "Cannot reach the authentication server. Check your internet " +
            "connection - if this keeps happening, the Supabase project may " +
            "be paused (Supabase dashboard -> Resume project)."
        );
    }

    return message || "Authentication failed. Please try again.";
}

function Auth() {
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");
    const [messageType, setMessageType] = useState("");

    const submit = async (event) => {
        event.preventDefault();

        setLoading(true);
        setMessage("");
        setMessageType("");

        try {
            const cleanEmail = email.trim();

            if (!cleanEmail || !password) {
                throw new Error("Please enter your email and password.");
            }

            if (password.length < 6) {
                throw new Error(
                    "Password must contain at least 6 characters."
                );
            }

            if (isLogin) {
                const { error } =
                    await supabase.auth.signInWithPassword({
                        email: cleanEmail,
                        password,
                    });

                if (error) {
                    throw error;
                }

                setMessage("Welcome back. Opening your workspace...");
                setMessageType("success");
            } else {
                const { data, error } =
                    await supabase.auth.signUp({
                        email: cleanEmail,
                        password,
                    });

                if (error) {
                    throw error;
                }

                if (data?.session) {
                    setMessage(
                        "Account created. Your workspace is ready."
                    );
                    setMessageType("success");
                } else {
                    setMessage(
                        "Account created. Check your email to confirm your account."
                    );
                    setMessageType("success");
                }
            }
        } catch (error) {
            console.error("Authentication error:", error);

            setMessage(friendlyAuthError(error));
            setMessageType("error");
        } finally {
            setLoading(false);
        }
    };

    const signInDemo = async () => {
        setLoading(true);
        setMessage("");
        setMessageType("");

        try {
            const { error } = await supabase.auth.signInWithPassword({
                email: DEMO_EMAIL,
                password: DEMO_PASSWORD,
            });

            if (error) {
                throw error;
            }

            setMessage("Opening the demo workspace...");
            setMessageType("success");
        } catch (error) {
            console.error("Demo login error:", error);
            setMessage(friendlyAuthError(error));
            setMessageType("error");
        } finally {
            setLoading(false);
        }
    };

    const switchMode = () => {
        setIsLogin((current) => !current);
        setMessage("");
        setMessageType("");
        setPassword("");
    };

    return (
        <div className="auth-shell">
            <div className="auth-glow auth-glow-one" />
            <div className="auth-glow auth-glow-two" />
            <div className="auth-grid" />

            <div className="auth-content">
                <div className="auth-brand">
                    <div className="auth-brand-mark">
                        <span>&lt;/&gt;</span>
                    </div>

                    <div>
                        <strong>CodeMentor</strong>
                        <span>AI Coding Platform</span>
                    </div>
                </div>

                <div className="auth-layout">
                    <section className="auth-intro">
                        <div className="auth-kicker">
                            <span className="auth-live-dot" />
                            SMART CODING WORKSPACE
                        </div>

                        <h1>
                            Code smarter.
                            <br />
                            <span>Learn faster.</span>
                        </h1>

                        <p className="auth-intro-text">
                            Practice coding problems, run your solutions,
                            track submissions, and get personalized help
                            from your AI mentor.
                        </p>

                        <div className="auth-feature-list">
                            <div className="auth-feature">
                                <span>✦</span>
                                <div>
                                    <strong>AI-powered guidance</strong>
                                    <p>
                                        Hints, debugging, dry runs and
                                        complexity analysis.
                                    </p>
                                </div>
                            </div>

                            <div className="auth-feature">
                                <span>⌘</span>
                                <div>
                                    <strong>Multi-language practice</strong>
                                    <p>
                                        Solve with Python, Java, C++ and C.
                                    </p>
                                </div>
                            </div>

                            <div className="auth-feature">
                                <span>◈</span>
                                <div>
                                    <strong>Progress tracking</strong>
                                    <p>
                                        Keep your submissions and practice
                                        history in one place.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section className="auth-card">
                        <div className="auth-card-top">
                            <div className="auth-card-icon">
                                {isLogin ? "→" : "+"}
                            </div>

                            <div>
                                <span className="auth-card-label">
                                    {isLogin ? "WELCOME BACK" : "GET STARTED"}
                                </span>

                                <h2>
                                    {isLogin
                                        ? "Sign in to CodeMentor"
                                        : "Create your account"}
                                </h2>

                                <p>
                                    {isLogin
                                        ? "Continue where you left off."
                                        : "Start your coding journey today."}
                                </p>
                            </div>
                        </div>

                        <div className="auth-mode-toggle">
                            <button
                                type="button"
                                className={
                                    isLogin
                                        ? "active"
                                        : ""
                                }
                                onClick={() => {
                                    setIsLogin(true);
                                    setMessage("");
                                    setMessageType("");
                                }}
                            >
                                Sign In
                            </button>

                            <button
                                type="button"
                                className={
                                    !isLogin
                                        ? "active"
                                        : ""
                                }
                                onClick={() => {
                                    setIsLogin(false);
                                    setMessage("");
                                    setMessageType("");
                                }}
                            >
                                Create Account
                            </button>
                        </div>

                        <form
                            className="auth-form"
                            onSubmit={submit}
                        >
                            <label className="auth-field">
                                <span>Email address</span>

                                <div className="auth-input-wrap">
                                    <span className="auth-input-icon">
                                        @
                                    </span>

                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(event) =>
                                            setEmail(event.target.value)
                                        }
                                        placeholder="you@example.com"
                                        autoComplete="email"
                                    />
                                </div>
                            </label>

                            <label className="auth-field">
                                <div className="auth-field-heading">
                                    <span>Password</span>

                                    {!isLogin && (
                                        <small>
                                            Minimum 6 characters
                                        </small>
                                    )}
                                </div>

                                <div className="auth-input-wrap">
                                    <span className="auth-input-icon">
                                        •••
                                    </span>

                                    <input
                                        type={
                                            showPassword
                                                ? "text"
                                                : "password"
                                        }
                                        value={password}
                                        onChange={(event) =>
                                            setPassword(event.target.value)
                                        }
                                        placeholder="Enter your password"
                                        autoComplete={
                                            isLogin
                                                ? "current-password"
                                                : "new-password"
                                        }
                                    />

                                    <button
                                        type="button"
                                        className="auth-show-password"
                                        onClick={() =>
                                            setShowPassword(
                                                (value) => !value
                                            )
                                        }
                                        aria-label={
                                            showPassword
                                                ? "Hide password"
                                                : "Show password"
                                        }
                                    >
                                        {showPassword ? "Hide" : "Show"}
                                    </button>
                                </div>
                            </label>

                            {message && (
                                <div
                                    className={`auth-message ${messageType}`}
                                    role="alert"
                                >
                                    <span>
                                        {messageType === "success"
                                            ? "✓"
                                            : "!"}
                                    </span>

                                    <p>{message}</p>
                                </div>
                            )}

                            <button
                                type="submit"
                                className="auth-submit"
                                disabled={loading}
                            >
                                <span>
                                    {loading
                                        ? isLogin
                                            ? "Signing in..."
                                            : "Creating account..."
                                        : isLogin
                                            ? "Sign in to CodeMentor"
                                            : "Create my account"}
                                </span>

                                {!loading && (
                                    <b aria-hidden="true">→</b>
                                )}
                            </button>
                        </form>

                        {DEMO_EMAIL && DEMO_PASSWORD && (
                            <button
                                type="button"
                                className="auth-demo"
                                onClick={signInDemo}
                                disabled={loading}
                            >
                                Try the demo account - no sign-up needed
                            </button>
                        )}

                        <div className="auth-security">
                            <span>⌁</span>
                            <p>
                                Your account session is secured by Supabase
                                Authentication.
                            </p>
                        </div>

                        <div className="auth-switch">
                            <span>
                                {isLogin
                                    ? "New to CodeMentor?"
                                    : "Already have an account?"}
                            </span>

                            <button
                                type="button"
                                onClick={switchMode}
                            >
                                {isLogin
                                    ? "Create an account"
                                    : "Sign in"}
                            </button>
                        </div>
                    </section>
                </div>

                <div className="auth-footer">
                    <span>Practice</span>
                    <span>•</span>
                    <span>Run</span>
                    <span>•</span>
                    <span>Learn</span>
                    <span>•</span>
                    <span>Improve</span>
                </div>
            </div>
        </div>
    );
}

export default Auth;
