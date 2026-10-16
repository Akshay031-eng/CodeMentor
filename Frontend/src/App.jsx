import { useEffect, useState } from "react";
import { supabase } from "./lib/supabase";
import Auth from "./Auth";
import ProblemList from "./components/ProblemList";
import ProblemDetails from "./components/ProblemDetails";
import "./App.css";

// Simple hash routing so refresh / back button keep you on the same page:
//   #/problems            -> problem list
//   #/problems/3          -> problem statement
//   #/problems/3/code     -> editor
function parseRoute() {
    const match = window.location.hash.match(/^#\/problems\/(\d+)(\/code)?\/?$/);

    if (match) {
        return {
            problemId: Number(match[1]),
            view: match[2] ? "editor" : "question",
        };
    }

    return { problemId: null, view: "problems" };
}

function navigate(hash) {
    if (window.location.hash !== hash) {
        window.location.hash = hash;
    }
}

function App() {
    const [route, setRoute] = useState(parseRoute);
    const { problemId: selectedProblemId, view } = route;

    const [session, setSession] = useState(null);
    const [authLoading, setAuthLoading] = useState(true);

    // =====================================================
    // AUTHENTICATION
    // =====================================================

    useEffect(() => {
        let mounted = true;

        const loadSession = async () => {
            try {
                const { data, error } =
                    await supabase.auth.getSession();

                if (!mounted) {
                    return;
                }

                if (error) {
                    console.error(
                        "Session error:",
                        error
                    );
                }

                setSession(data?.session || null);
            } catch (error) {
                console.error(
                    "Failed to load session:",
                    error
                );
                setSession(null);
            } finally {
                if (mounted) {
                    setAuthLoading(false);
                }
            }
        };

        loadSession();

        const {
            data: authListener,
        } = supabase.auth.onAuthStateChange(
            (_event, newSession) => {
                if (mounted) {
                    setSession(newSession || null);
                }
            }
        );

        return () => {
            mounted = false;
            authListener?.subscription?.unsubscribe();
        };
    }, []);

    useEffect(() => {
        const onHashChange = () => {
            setRoute(parseRoute());
            window.scrollTo({ top: 0, behavior: "smooth" });
        };

        window.addEventListener("hashchange", onHashChange);
        return () => window.removeEventListener("hashchange", onHashChange);
    }, []);

    // =====================================================
    // NAVIGATION
    // =====================================================

    const openProblem = (problemId) => {
        navigate(`#/problems/${problemId}`);
    };

    const backToProblems = () => {
        navigate("#/problems");
    };

    const openEditor = () => {
        if (selectedProblemId) {
            navigate(`#/problems/${selectedProblemId}/code`);
        }
    };

    const logout = async () => {
        try {
            const { error } =
                await supabase.auth.signOut();

            if (error) {
                console.error(
                    "Logout error:",
                    error
                );
                return;
            }

            navigate("#/problems");
        } catch (error) {
            console.error(
                "Logout failed:",
                error
            );
        }
    };

    // =====================================================
    // AUTH LOADING
    // =====================================================

    if (authLoading) {
        return (
            <div className="coding-mentor-app">
                <main className="app-main">
                    <div className="loading-state">
                        <div className="loading-spinner">
                            ◌
                        </div>

                        <h2>
                            Loading CodeMentor...
                        </h2>

                        <p>
                            Checking your account session.
                        </p>
                    </div>
                </main>
            </div>
        );
    }

    // =====================================================
    // LOGIN / REGISTER
    // =====================================================

    if (!session) {
        return (
            <div className="coding-mentor-app">
                <main className="app-main">
                    <Auth />
                </main>
            </div>
        );
    }

    // =====================================================
    // MAIN APPLICATION
    // =====================================================

    return (
        <div className="coding-mentor-app">
            <header className="topbar">
                <div className="topbar-inner">
                    <button
                        type="button"
                        className="brand"
                        onClick={backToProblems}
                        aria-label="Go to problems"
                    >
                        <span className="brand-mark">
                            &lt;/&gt;
                        </span>

                        <span className="brand-copy">
                            <strong>
                                CodeMentor
                            </strong>

                            <small>
                                AI Coding Platform
                            </small>
                        </span>
                    </button>

                    <nav
                        className="main-navigation"
                        aria-label="Main navigation"
                    >
                        <button
                            type="button"
                            className={
                                view === "problems"
                                    ? "nav-link active"
                                    : "nav-link"
                            }
                            onClick={backToProblems}
                        >
                            Problems
                        </button>
                    </nav>

                    <div className="topbar-meta">
                        {selectedProblemId && (
                            <span className="problem-context">
                                Problem #
                                {selectedProblemId}
                            </span>
                        )}

                        <span
                            className="user-email"
                            title={session.user?.email || "Account"}
                        >
                            {session.user?.email || "User"}
                        </span>

                        <div
                            className="avatar"
                            title={
                                session.user?.email ||
                                "Profile"
                            }
                        >
                            {(session.user?.email || "A")
                                .charAt(0)
                                .toUpperCase()}
                        </div>

                        <button
                            type="button"
                            className="logout-button"
                            onClick={logout}
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            <main className="app-main">
                {view === "problems" && (
                    <ProblemList
                        onSelectProblem={openProblem}
                    />
                )}

                {view !== "problems" && selectedProblemId && (
                    <ProblemDetails
                        key={selectedProblemId}
                        problemId={selectedProblemId}
                        mode={view}
                        onBack={
                            view === "editor"
                                ? () => openProblem(selectedProblemId)
                                : backToProblems
                        }
                        onStartCoding={openEditor}
                        onOpenProblem={() => openProblem(selectedProblemId)}
                    />
                )}
            </main>
        </div>
    );
}

export default App;
