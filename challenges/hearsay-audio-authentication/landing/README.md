# ECHOTRACE landing page

The public front door for ECHOTRACE: an interactive product page, login and signup (Google or email), a product guide in the bottom-right corner, and a slot for the demo video.

The Python backend (`../backend`) owns everything behind it: accounts, sessions, Google sign-in and the guide. In production it serves this page at `/`, the workspace (`../frontend`) at `/app/` and all APIs at `/api/`, from one origin.

## Run with the backend

Build the page, then start the backend with accounts turned on. From this folder:

```sh
npm run build                  # writes dist/, which the backend serves at /
cd ../backend
ECHOTRACE_AUTH=required uv run uvicorn echotrace.api:app
```

Open http://127.0.0.1:8000/. After login or signup the page sends you to the workspace at `/app/` (or to a safe `?next=` path on the same site).

## Develop the page

Keep the backend running as above, then in this folder:

```sh
npm run dev      # page on http://127.0.0.1:5190, /api proxied to http://127.0.0.1:8000
```

Email login and signup work through the proxy. Google sign-in returns to the backend's own origin (`ECHOTRACE_PUBLIC_URL`, default `http://127.0.0.1:8000`), so test it there rather than on port 5190.

## Accounts

Accounts, password hashing, session cookies, rate limits and origin checks all live in the backend (`../backend/echotrace/accounts.py`). The page only calls:

- `GET /api/auth/me` and `GET /api/auth/providers` (whether Google is configured)
- `POST /api/auth/signup`, `/api/auth/login`, `/api/auth/logout`
- `/api/auth/google/start?next=/app/` as a full page navigation

The "Continue with Google" button appears only when the backend reports Google as available (`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` set). A failed Google sign-in comes back as `/login?error=...` and is shown on the form. `next` is accepted only when it starts with `/` and not `//`; anything else falls back to `/app/`.

"Open workspace" links to `VITE_WORKSPACE_URL` (default `/app/`).

## Demo video

Put the recording at `public/demo/echotrace-demo.mp4`, then build or start the page with:

```sh
VITE_DEMO_VIDEO_URL=/demo/echotrace-demo.mp4 npm run dev
```

A YouTube or Vimeo link also works (`VITE_DEMO_VIDEO_URL=https://youtu.be/...`). Without it, the page shows a clearly labelled placeholder.

## Product guide

The guide calls `POST /api/assistant` on the backend (`../backend/echotrace/guide.py`), which answers from curated, verified product facts. When `GROQ_API_KEY` is present in the repository-root `.env`, Groq phrases the answer from those facts; otherwise, or if Groq fails, the built-in guide answers directly. Every reply says which one answered. The key is read only by the backend and never reaches the browser.

## Check

```sh
npm test         # UI tests (Vitest)
npm run build    # type-check and production build
```

The hero waveform and the three-step workflow mock use illustrative values and are labelled as such. The results section uses the project's measured benchmark counts.
