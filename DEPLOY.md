# Deploying CodeMentor

| Part | Where | Cost |
|---|---|---|
| Frontend (React) | **Vercel** | Free (Hobby) |
| Backend API + code judge (Docker) | **Render** web service | Free instance |
| Database + Auth + vector search | **Supabase** | Free plan |
| Code + CI | **GitHub** (Actions) | Free |

> **Why not the backend on Vercel?** The judge needs Python, Java, gcc and g++
> installed and a long-running process. Vercel functions have none of that,
> so the backend runs as a Docker container on Render.

Total time: about 30–45 minutes the first time.

---

## 0. Before you start

1. **Rotate any key that was ever shared** (screenshots, chats, commits):
   - Supabase → Project Settings → **API Keys** → create a new **secret key** and delete the old one.
   - Google AI Studio → **API Keys** → create a new Gemini key and delete the old one.
   Put the new keys in your local `Backend/.env` and check the app still works locally.
2. Make sure the app works locally (README → *Run locally*).
3. Create free accounts: [GitHub](https://github.com), [Render](https://render.com) (sign in with GitHub), [Vercel](https://vercel.com) (sign in with GitHub).

Keep these values ready (Supabase → Project Settings → API Keys / Data API):

| Value | Looks like | Goes to |
|---|---|---|
| Project URL | `https://xxxx.supabase.co` | Render **and** Vercel |
| Publishable key | `sb_publishable_...` (or legacy `anon` key `eyJ...`) | **Vercel only** |
| Secret key | `sb_secret_...` (or legacy `service_role` key `eyJ...`) | **Render only** |
| Gemini API key | from Google AI Studio | **Render only** |

> The secret key and the Gemini key must **never** go into Vercel or any `VITE_` variable —
> everything in the frontend is public.

---

## 1. Push the code to GitHub

Install Git once (Windows): `winget install -e --id Git.Git`, then open a **new** terminal.

```powershell
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

Create an **empty** repository on GitHub (New repository → name e.g. `codementor`
→ no README, no .gitignore). Then, in the folder that contains `Backend`,
`Frontend` and `.github`:

```powershell
cd "C:\path\to\Coding Mentor"
git init
git add .
git ls-files | Select-String "\.env"
```

**Stop and check:** the last command must show only `.env.example` files.
If you see `Backend/.env` or `Frontend/.env`, do not continue — the
`.gitignore` is missing or was changed.

```powershell
git commit -m "CodeMentor: initial version"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/codementor.git
git push -u origin main
```

A browser window asks you to sign in to GitHub the first time.

On GitHub open the **Actions** tab: the CI workflow runs the backend tests,
the frontend lint/build and builds the Docker image. All three should turn green.

---

## 2. Database (Supabase)

If your Supabase project already has the problems and test cases, skip to step 3.

For a **new** project: Dashboard → **SQL Editor** → run `Backend/supabase_schema.sql`,
then `Backend/supabase_seed.sql`. Then, locally, load the AI mentor's knowledge base once:

```powershell
cd Backend
.\venv\Scripts\Activate.ps1
python -m rag.ingest_knowledge
```

> Free Supabase projects **pause after about a week without activity**.
> Dashboard → *Resume project* brings it back (data is kept).

---

## 3. Backend on Render

1. Render dashboard → **New → Web Service** → connect your GitHub repo.
2. Settings:

   | Field | Value |
   |---|---|
   | Name | `codementor-api` (becomes `https://codementor-api.onrender.com`) |
   | Region | Singapore (closest to India) — or nearest to your users |
   | Branch | `main` |
   | **Root Directory** | `Backend` |
   | Runtime / Language | **Docker** (detected from `Backend/Dockerfile`) |
   | Instance type | **Free** |

3. **Environment variables** (Add from .env is fine, but only these):

   | Key | Value |
   |---|---|
   | `SUPABASE_URL` | your Project URL |
   | `SUPABASE_SERVICE_ROLE_KEY` | your **secret** key |
   | `GEMINI_API_KEY` | your Gemini key |
   | `CORS_ORIGINS` | `http://localhost:5173` for now — you update it in step 5 |

   Do **not** set `SANDBOX_USER`, `PORT` or `SUBMISSION_MODE` — the Dockerfile sets the right values.

4. **Advanced → Health Check Path:** `/health`
5. **Create Web Service.** The first build takes ~5–10 minutes (it installs Java and gcc).
6. When it says *Live*, open `https://YOUR-SERVICE.onrender.com/health`. You should see:

   ```json
   {"status":"ok","submission_mode":"inline","queue_available":null,"sandboxed":true}
   ```

   `"sandboxed": true` means student code runs as the separate unprivileged user.

> **Free instance:** 512 MB RAM, 0.1 CPU, **sleeps after 15 minutes without requests**
> (the next request takes up to a minute while it wakes up — the frontend shows a
> "Waking up the server…" message). 750 free instance hours per month.

---

## 4. Frontend on Vercel

1. Vercel → **Add New… → Project** → import the same GitHub repo.
2. **Root Directory:** click *Edit* → choose `Frontend`. Framework preset: **Vite** (auto-detected).
   Build command `npm run build`, output directory `dist` (defaults).
3. **Environment Variables:**

   | Key | Value |
   |---|---|
   | `VITE_SUPABASE_URL` | your Project URL |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | your **publishable** key |
   | `VITE_API_URL` | `https://YOUR-SERVICE.onrender.com` (no `/` at the end) |
   | `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD` | optional, see step 6 |

4. **Deploy.** You get a URL like `https://codementor-xyz.vercel.app`.

> `VITE_` variables are baked in at build time. After changing one on Vercel,
> **redeploy** (Deployments → ⋯ → Redeploy).

---

## 5. Connect everything

1. **Render → your service → Environment** → set
   `CORS_ORIGINS=https://codementor-xyz.vercel.app` (your exact Vercel URL, no `/` at the end).
   Several origins: separate them with commas. Save — Render redeploys.
   Optional, to also allow Vercel preview deployments:
   `CORS_ORIGIN_REGEX=https://codementor-.*\.vercel\.app`
2. **Supabase → Authentication → URL Configuration:**
   - Site URL: `https://codementor-xyz.vercel.app`
   - Redirect URLs: add `https://codementor-xyz.vercel.app/**`

   (Otherwise sign-up confirmation emails link to `localhost`.)

---

## 6. Optional: one-click demo account

Great for a portfolio — visitors can try it without signing up.

1. Supabase → Authentication → **Users → Add user** → email + password, tick **Auto Confirm User**.
2. Vercel → Environment Variables: `VITE_DEMO_EMAIL`, `VITE_DEMO_PASSWORD` → Redeploy.

The sign-in page now shows **"Try the demo account"**. Everyone shares this
account's submission history, so use a throwaway password.

---

## 7. Test the live site

- [ ] Open the Vercel URL → sign in (or demo button)
- [ ] Problem list loads (first load after idle can take ~1 minute)
- [ ] Run Two Sum in **Python, Java, C++ and C** → *Accepted*
- [ ] Submit → status goes *Queued → Accepted* and appears in Submission History
- [ ] AI Mentor answers a question
- [ ] Update the placeholders in `README.md` (CI badge, live demo link), commit and push

---

## Updating the live app

```powershell
git add .
git commit -m "Describe your change"
git push
```

Render and Vercel both redeploy automatically on every push to `main`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Page says **"CodeMentor can't connect to Supabase"** | Wrong/missing `VITE_SUPABASE_*` on Vercel → fix and **Redeploy**. |
| Login: *Cannot reach the authentication server* | Supabase project paused → Dashboard → Resume project. |
| Browser console: **CORS** error calling `onrender.com` | `CORS_ORIGINS` on Render doesn't exactly match the Vercel URL (https, no trailing `/`). |
| *Cannot reach the backend* | `VITE_API_URL` wrong, or Render service still waking up / failed — check Render **Logs**. |
| Submit stays **Queued** | Backend has the publishable key instead of the **secret** key (`SUPABASE_SERVICE_ROLE_KEY`). |
| AI Mentor: *temporarily unavailable* | `GEMINI_API_KEY` missing/invalid or quota used up. |
| *Too many requests* | Rate limit hit (20 runs / 10 submits / 8 mentor questions per minute per user) — adjustable with `RATE_LIMIT_*` env vars. |
| Render deploy fails / out of memory | Check the build log; on the free instance keep `MAX_PARALLEL_TESTS=2` (default in the image). |

---

## Security notes (read before sharing widely)

- Student code runs as a separate unprivileged user with time, CPU, memory,
  output and process limits. It cannot read the API keys, kill the server or
  change the app.
- It **can still make network requests** from the server. That's acceptable for
  a portfolio / class demo with rate limits, but before opening it to a large
  public audience, move code execution into a network-isolated sandbox
  (e.g. gVisor, Firecracker or a hosted judge such as Judge0).
- Keys live only in Render / Vercel / your local `.env` files — never in Git.
