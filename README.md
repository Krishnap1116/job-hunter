# JobHunter AI 🎯

An AI-powered job matching system that collects jobs daily from 6 sources, runs a two-stage filtering pipeline against your resume using Claude, and surfaces only the roles actually worth applying to — with zero repeat analysis and no wasted API calls.

**Live:** https://job-searching.streamlit.app/

---

## The Problem

Job boards return hundreds of listings. Most are the wrong seniority, wrong location, wrong tech stack, or require security clearance you don't have. Reading them manually takes hours. Sending them all through an AI is expensive and slow.

This system solves both problems: cheap regex rules eliminate ~70% of jobs before Claude ever runs, and a shared daily job pool means the scraping cost is paid once for all users.

---

## Architecture

```
GitHub Actions (9 AM UTC daily)
        │
        ▼
  daily_collect.py
  ┌─────────────────────────────────────┐
  │  IntegratedScraper                  │
  │  ├── Greenhouse ATS API  (free)     │
  │  ├── Lever ATS API       (free)     │
  │  ├── RemoteOK JSON feed  (free)     │
  │  ├── Jobicy JSON feed    (free)     │
  │  ├── JSearch RapidAPI    (paid key) │
  │  └── Adzuna API          (paid key) │
  └─────────────────────────────────────┘
        │
        ▼
  global_raw_jobs table (Neon PostgreSQL)
  One shared pool — scraped once, used by all users
        │
        ▼  (when user logs in — their Anthropic key)
  ┌──────────────────────────────────────────┐
  │  Two-stage matching pipeline             │
  │                                          │
  │  Stage 1 — Pre-filter (instant, free)   │
  │  ├── Seniority gate (title keywords)    │
  │  ├── Experience year cap (regex)        │
  │  ├── Job type filter (contract/intern)  │
  │  ├── Auto-reject phrases                │
  │  └── ~70% of jobs eliminated here      │
  │                                          │
  │  Stage 2 — Claude AI analysis           │
  │  ├── Skills match score (0–100%)        │
  │  ├── Role relevance score (0–100%)      │
  │  ├── Experience fit check               │
  │  ├── Tier 1 / Tier 2 classification     │
  │  └── Tailored resume bullets (Tier 2)   │
  └──────────────────────────────────────────┘
        │
        ▼
  analyzed_jobs + user_job_status (per user)
        │
        ▼
  Streamlit UI — Matches page
```

---

## How It Works End-to-End

### Daily collection (automated, costs nothing)

Every day at 9 AM UTC, a GitHub Actions workflow runs `daily_collect.py`. It scrapes all 6 sources in parallel using ThreadPoolExecutor, deduplicates results (fuzzy match on company + title), and saves new jobs to the `global_raw_jobs` table in Neon PostgreSQL. Old jobs (>7 days) are purged automatically. The whole run takes ~90 seconds.

This happens once per day regardless of how many users are on the platform. All users draw from the same pool.

### When a user logs in

The app checks: *are there any jobs in `global_raw_jobs` with a `scraped_at` timestamp newer than this user's `last_analyzed_at`?* If yes, analysis fires automatically — no button click needed. If no (browser refresh, same session), nothing runs. The `last_analyzed_at` timestamp is stored in PostgreSQL, not in browser session state, so it survives refreshes and tab closes.

### Two-stage filtering

**Stage 1 — Pre-filter** (runs in milliseconds, zero API cost):
- Rejects jobs where the title contains seniority keywords (`Senior`, `Staff`, `Principal`, `Lead`, `Director`, `VP`) configured per user
- Rejects jobs requiring more years of experience than the user's cap (regex extracts `X+ years required` from description)
- Rejects contract/freelance/internship/part-time roles (configurable)
- Rejects jobs containing auto-reject phrases set by the user
- Each rejected job is written to `user_job_status` as `rejected` and never seen again

**Stage 2 — Claude AI analysis** (runs only on jobs that passed Stage 1):
- Claude receives the full job description + the user's parsed resume (skills, experience years, target roles)
- Scores `skill_match_pct` (0–100): how much of the job's required stack the user has
- Scores `role_match_pct` (0–100): how closely the role aligns with the user's target roles
- Determines tier: **Tier 1** = skill ≥ 80% AND role ≥ 60% (best matches), **Tier 2** = skill ≥ 60% AND role ≥ 60% (good matches, gets tailored resume bullets)
- Provides plain-English reasoning for the match score
- For Tier 2 jobs: generates 3 tailored resume bullets reworded to match the job's language

### Analyze-once guarantee

Each job is analyzed or rejected exactly once per user. The `user_job_status` table stores `(profile_id, job_id, status)` with a UNIQUE constraint. Once a job is marked `analyzed` or `rejected`, it's excluded from all future `get_global_jobs_for_user` queries. Browser refresh, tab reopen, new session — none of these trigger re-analysis.

---

## Key Design Decisions

**Why a shared global job pool instead of per-user scraping?**

Per-user scraping means if 10 users are on the platform, the same Greenhouse/Lever APIs get hit 10 times for the same data. The shared pool scrapes once, stores to Postgres, and each user's analysis runs against that. Scraping cost (time + rate limits) is O(1), not O(n users).

**Why two stages instead of just sending everything to Claude?**

Claude is ~$0.002/job at the Haiku tier. With 150 jobs/day and 10 users, that's $3/day or ~$90/month just in API costs — before pre-filtering. Pre-filtering eliminates 70%+ of jobs using zero-cost regex, bringing the real Claude cost to ~$0.60/day for the same setup.

**Why store `last_analyzed_at` in PostgreSQL instead of session state?**

Streamlit's `session_state` resets on every browser refresh. If we gated analysis on a session flag, every refresh would re-trigger Claude calls and charge the user's API key. Storing the timestamp in the database means the app checks "has anything new arrived since I last ran?" — and the answer is durable across sessions.

**Why `st.query_params` for login persistence?**

Streamlit has no native cookie/session system. `query_params` (URL parameters) persist across refreshes because they're part of the URL, not in-memory state. On login, we set `?pid=3` in the URL. On refresh, the app reads it back, validates the profile exists in the DB, and restores the session — all transparent to the user.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (Python), deployed on Streamlit Cloud |
| AI — Resume Parsing | Claude Sonnet (Anthropic API) |
| AI — Job Matching | Claude Haiku (Anthropic API, user's own key) |
| Scraping | Greenhouse API, Lever API, RemoteOK, Jobicy, JSearch (RapidAPI), Adzuna |
| Database | PostgreSQL via psycopg2, hosted on Neon |
| Scheduling | GitHub Actions (cron workflow) |
| Language | Python 3.11 |

---

## Source Coverage

| Source | Type | Auth | Typical ML/AI yield |
|---|---|---|---|
| Greenhouse ATS | Official public API | None | 30–80 jobs |
| Lever ATS | Official public API | None | 20–60 jobs |
| RemoteOK | Public JSON feed | None | 20–50 jobs |
| Jobicy | Public JSON feed | None | 15–40 jobs |
| JSearch | RapidAPI (aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter) | RapidAPI key | 60–100 jobs |
| Adzuna | REST API | Adzuna key | 30–60 jobs |

Greenhouse and Lever use official public ATS APIs — no scraping fragility, no IP blocks, works reliably on Streamlit Cloud's shared AWS infrastructure. The free sources (RemoteOK, Jobicy) require no keys and run on every collection.

---

## Database Schema (key tables)

```sql
-- One row per user
profiles (id, name, email, experience_years, experience_level,
          core_skills, target_roles, collection_time, last_analyzed_at)

-- Shared across all users — filled by GitHub Actions daily
global_raw_jobs (id, job_id UNIQUE, company, title, url,
                 location, description, source, scraped_at)

-- Per-user tracking — prevents re-analysis
user_job_status (profile_id, job_id, status, PRIMARY KEY(profile_id, job_id))
-- status: 'analyzed' | 'rejected'

-- Per-user results
analyzed_jobs (id, profile_id, job_id, company, title, url,
               match_score, skill_match_pct, role_match_pct,
               experience_required, tier, reasoning,
               tailored_bullets, applied, applied_at, analyzed_at)

-- Per-user filter settings
pre_filter_config (profile_id, max_years_experience,
                   reject_seniority_levels, reject_job_types,
                   auto_reject_phrases)

claude_filter_config (profile_id, tier1_skill_threshold,
                      tier2_skill_threshold, min_target_role_percentage,
                      requires_visa_sponsorship, reject_clearance_jobs, ...)
```

---

## Features

**Matching**
- Resume uploaded once; Claude extracts skills, experience level, target roles, and years of experience
- Tier 1 / Tier 2 classification with configurable thresholds
- Per-job match score, skill match %, role relevance %, experience requirement
- Plain-English reasoning for every match
- Tailored resume bullets for Tier 2 jobs (reworded to match the job's language)

**Filtering (configurable per user, no redeploy)**
- Seniority level gate: toggle Senior / Staff / Principal / Lead / Manager / Director / VP individually
- Max experience cap: rejects jobs requiring more than N years
- Job type filter: contract, freelance, internship, part-time
- Auto-reject phrases: any custom strings that instantly eliminate a job
- Visa sponsorship flag: Claude factors in whether the job sponsors visas
- Security clearance filter: rejects jobs requiring clearance

**Tracking**
- ✅ Applied / ↩ Undo buttons per job card
- Applied status and timestamp stored in DB
- "New for You" counter showing unanalyzed jobs in pool

**Multi-user**
- Email-based account creation
- Each user brings their own Anthropic API key (they pay for their own analysis)
- Job pool is shared; analysis results, filter settings, and applied status are fully isolated per user
- Free sources (Greenhouse, Lever, RemoteOK, Jobicy) work with no keys; JSearch/Adzuna are optional upgrades per user

---

## Project Structure

```
├── streamlit/
│   ├── app.py                      # Streamlit UI, auth, session, auto-analyze flow
│   ├── job_scraper_integrated.py   # 6-source scraper with threading
│   ├── job_matcher_integrated.py   # Pre-filter + Claude AI matching pipeline
│   ├── resume_parser.py            # Claude-based resume parsing
│   ├── daily_collect.py            # GitHub Actions entry point
│   ├── database.py                 # SQLite (local dev)
│   ├── database_postgres.py        # PostgreSQL (production)
│   └── database_manager.py        # Auto-switches based on DATABASE_URL
├── .github/
│   └── workflows/
│       └── collect_jobs.yml        # Daily cron: 9 AM UTC
└── requirements.txt
```

---

## Setup

### 1. Clone and install
```bash
git clone https://github.com/Krishnap1116/job-hunter.git
cd job-hunter
pip install -r requirements.txt
```

### 2. Environment variables

For local dev, create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."   # optional — users provide their own
JSEARCH_API_KEY   = ""             # optional
ADZUNA_APP_ID     = ""             # optional
ADZUNA_API_KEY    = ""             # optional
# Omit DATABASE_URL to use local SQLite automatically
```

For Streamlit Cloud, add to Secrets:
```toml
DATABASE_URL      = ""
JSEARCH_API_KEY   = "..."
ADZUNA_APP_ID     = "..."
ADZUNA_API_KEY    = "..."
```

For GitHub Actions, add repository secrets:
```
DATABASE_URL, JSEARCH_API_KEY, ADZUNA_APP_ID, ADZUNA_API_KEY
```

### 3. Run locally
```bash
streamlit run streamlit/app.py

# Simulate daily collection (populates local SQLite)
python streamlit/daily_collect.py
```

### 4. Reset local DB
```bash
rm job_hunter.db
```

---

## Why I Built This

Job searching at scale is a data pipeline problem. Applying to 10–20 roles a day and reading listings that were obviously wrong fits — wrong seniority, wrong stack, required clearance — was wasting an hour a day.

The interesting engineering challenge was the two-stage architecture: get the pre-filter aggressive enough to eliminate obvious mismatches without discarding real matches. The config-driven strictness system (all thresholds and filters are DB-stored, editable in the UI) means tuning that tradeoff without touching code.

The second interesting problem was the "analyze once" guarantee — making sure a browser refresh never retriggers Claude calls. Session state isn't durable; the solution was moving the analysis timestamp into PostgreSQL and using URL query params to persist login state across refreshes.
