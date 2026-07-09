# AI Smart Allocation Engine

A Flask app that matches students to internships using a transparent,
rule-based scoring engine — students and companies each build a profile,
and every pairing gets a 0–100 match score with a plain-language reason
for each point.

## What's new in this pass

**Security**
- Passwords are hashed with `werkzeug.security` (never stored in plaintext).
  Any old plaintext passwords in an existing `allocation.db` are
  automatically re-hashed the first time the app starts.
- Real session-based login for students, companies, and admin — no more
  "log in as whichever student is first in the database."
- Admin has its own login route (`/admin-login`) gated by
  `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables (defaults to
  `admin` / `admin123` — **change this before deploying anywhere real**).
- Resume uploads are validated by extension, capped at 5 MB, and saved
  under a randomized filename so two students can't overwrite each other's file.
- Internship deletion is restricted to the company that posted it, or an admin.

**Bug fixes**
- Removed dead code that ran after early `return` statements in the
  original routes (e.g. in `/students`, `/companies`, `/internships`).
- Numeric fields (CGPA, vacancies) are now validated with clear error
  messages instead of crashing the app on bad input.
- Fixed the `static/resumes` path (it was nested under `static/css` before).

**UI**
- Full visual redesign: a proper design system (see `static/css/style.css`)
  instead of default form styling, with role-aware navigation, flash
  messages, responsive layout, and a signature "match ring" that
  visualizes each score.
- Every page now extends a shared `base.html` layout.

## Running it

```bash
pip install -r requirements.txt
cd Backend
python app.py
```

The app creates `allocation.db` and the `static/resumes` upload folder
automatically on first run. Visit `http://127.0.0.1:5000`.

### Environment variables (optional)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | a dev-only placeholder | Flask session signing key — set a real random value in production |
| `ADMIN_USERNAME` | `admin` | Admin portal username |
| `ADMIN_PASSWORD` | `admin123` | Admin portal password |

## How matching works

See `ai_engine.py`. Each pair is scored out of 100:

- **40 points** — student's CGPA meets the internship's minimum
- **20 points per skill** — for each required skill the student also lists
- **20 points** — student's preferred location matches the internship's location
- **20 points** — student's department appears in the internship's role

The score is clamped to 0–100 and returned along with a list of
human-readable reasons, which is what powers the "why this score"
explanations on the matches page.

## Troubleshooting: "my registration disappears"

The app always writes to one fixed database file (its path is printed to
the console on startup, e.g. `[db] using database at: /path/to/allocation.db`),
and starting the app never deletes or resets it — so if data seems to
vanish, it's almost always one of these:

1. **You extracted a new zip into a different folder.** Each folder gets
   its own fresh `allocation.db` the first time it runs. If you got an
   updated zip from me, copy the changed *files* into your existing
   project folder instead of extracting into a brand-new one — don't
   replace the whole folder.
2. **You're running it on free hosting with no persistent disk** (see
   below) — the filesystem resets on every redeploy or restart, taking
   the database with it.

If neither applies, check the startup log line for the exact path being
used and confirm it's the same path every time you start the app.

## Deploying to Render

This repo includes a `render.yaml` blueprint and a `Procfile`, so you can
either click **New → Blueprint** in the Render dashboard and point it at
this repo, or set it up manually as a **Web Service** with:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn --chdir Backend --bind 0.0.0.0:$PORT app:app`

Set these environment variables in the Render dashboard:

| Variable | Value |
|---|---|
| `SECRET_KEY` | a long random string (Render can generate one) |
| `ADMIN_USERNAME` | your choice |
| `ADMIN_PASSWORD` | your choice — don't leave it as `admin123` |
| `DATABASE_PATH` | `/var/data/allocation.db` (only if you add a disk, see below) |

### Important: SQLite needs a Persistent Disk on Render

Render's **free** web service plan has no persistent disk — every
redeploy (and sometimes every restart) gives you a brand-new, empty
filesystem, so `allocation.db` gets wiped exactly like the local issue
above, just outside of your control.

To keep data across deploys, either:
- **Add a Render Disk** (requires a paid instance plan): in the service
  settings, add a disk mounted at `/var/data`, and set the
  `DATABASE_PATH` env var to `/var/data/allocation.db` (already wired up
  in `render.yaml`). Data then survives redeploys and restarts.
- **Or switch to Render's managed PostgreSQL** (has a free tier) instead
  of SQLite, if you want real persistence without paying for a disk.
  That's a bigger change to `db.py` — let me know if you want that done
  instead.

## Project structure

```
Backend/
  app.py            routes
  db.py             connection helper + schema + migrations
  auth.py           login_required decorators, password hashing
  ai_engine.py       matching logic
  static/
    css/style.css   design system
    js/app.js       mobile nav + flash auto-dismiss
    resumes/        uploaded resumes (created automatically)
  templates/        Jinja templates, all extending base.html
```
