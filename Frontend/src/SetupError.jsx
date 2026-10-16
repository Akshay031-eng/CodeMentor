import "./SetupError.css";

function SetupError({ message }) {
    return (
        <main className="setup-error">
            <section className="setup-error-card" role="alert">
                <span className="setup-error-badge">SETUP NEEDED</span>
                <h1>CodeMentor can't connect to Supabase</h1>
                <p className="setup-error-message">{message}</p>

                <ol>
                    <li>
                        Local: open <code>Frontend/.env</code> (not
                        <code>.env.example</code>). On Vercel: Project
                        Settings &rarr; Environment Variables.
                    </li>
                    <li>
                        Set <code>VITE_SUPABASE_URL</code> to your Project URL
                        and <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> to the
                        publishable / anon key (Supabase &rarr; Project
                        Settings &rarr; API Keys).
                    </li>
                    <li>
                        Restart <code>npm run dev</code> (or redeploy) - Vite
                        only reads these values at start-up.
                    </li>
                </ol>
            </section>
        </main>
    );
}

export default SetupError;
