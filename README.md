# AI Job Hunter 🎯

A full-stack AI-powered job matching system that scrapes jobs from 11+ sources daily, analyzes them against your resume using Claude Sonnet, and surfaces only the roles worth applying to — deployed on Streamlit Cloud with a PostgreSQL backend.

---

## What It Does

Most job boards show you hundreds of irrelevant listings. This system runs a two-stage AI pipeline to cut through the noise:

1. **Scrape** — Pulls jobs daily from 11+ sources including Greenhouse ATS, Lever ATS, JSearch API, Adzuna, and RSS feeds (We Work Remotely, Remotive), targeting companies like Anthropic, OpenAI, Scale, Notion, Stripe, and 40+ others
2. **Pre-filter** — Regex-based rules eliminate obvious mismatches (wrong seniority, location, role type) before any AI call — reducing Claude API usage by ~70%
3. **AI Match** — Claude Sonnet 4 analyzes remaining jobs against your parsed resume, scoring fit and flagging dealbreakers
4. **Deliver** — Results surface in a Streamlit web app with match scores, reasoning, and direct apply links

**Result:** Analysis time cut from 7s → 3s per job. 100+ jobs collected daily, filtered to the ones that matter.

---

## Architecture

```
Scrapers (11+ sources)
    ↓
Pre-filter (regex rules, USA-only, seniority gate)
    ↓
Claude Sonnet 4 AI Matching (Anthropic API)
    ↓
PostgreSQL (Render) — 7-day auto-cleanup
    ↓
Streamlit Cloud (password-protected UI)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit, deployed on Streamlit Cloud |
| AI Matching | Claude Sonnet 4 (Anthropic API) |
| Resume Parsing | Claude API — extracts skills, experience, preferences |
| Scraping | Greenhouse API, Lever API, JSearch API, Adzuna API, RSS (feedparser), BeautifulSoup |
| Database | PostgreSQL (psycopg2), hosted on Render |
| Auth | Streamlit secrets-based password auth (HMAC) |
| Language | Python 3.11 |

---

## Key Features

- **Multi-source scraping** — Greenhouse + Lever ATS direct APIs (no scraping fragility), JSearch, Adzuna, RSS feeds
- **Smart pre-filtering** — Strict USA-only location logic, configurable experience caps, role-type matching before any AI call
- **Resume-aware matching** — Upload your resume once; Claude parses it and all subsequent matches are personalized to your profile
- **Multi-user isolation** — Email-based profile separation, each user sees only their own matches
- **Auto-cleanup** — Jobs older than 7 days are automatically purged to manage storage costs
- **Config-driven strictness** — Matching thresholds, experience limits, and skill weights are all configurable without touching core logic

---

## Project Structure

```
├── app.py                      # Streamlit UI, auth, session management
├── job_scraper_integrated.py   # Unified scraper across all sources
├── scraper.py                  # Source-specific scraping logic
├── matcher.py                  # Claude AI matching pipeline
├── database_postgres.py        # PostgreSQL schema, queries, migrations
├── database.py                 # SQLite version (local dev)
└── README.md
```

---

## Setup

### 1. Clone and install
```bash
git clone https://github.com/Krishnap1116/job-hunter.git
cd job-hunter
pip install -r requirements.txt
```

### 2. Set environment variables
```
ANTHROPIC_API_KEY=your_key
DATABASE_URL=postgresql://...
JSEARCH_API_KEY=your_key
ADZUNA_APP_ID=your_id
ADZUNA_API_KEY=your_key
```

### 3. Run locally
```bash
streamlit run app.py
```

---

## Why I Built This

Job searching at scale is a data pipeline problem. I was applying to 10–20 roles a day and spending too much time reading listings that were obviously wrong fits. I built this to automate the filtering layer — so I only spend time on roles that actually match my profile.

The interesting engineering problem was the two-stage matching architecture: using cheap regex rules to eliminate 70% of jobs before hitting the Claude API, while making sure the pre-filter wasn't too aggressive and discarding real matches. The config-driven strictness system lets me tune that tradeoff without redeploying.

---

## Live Demo
https://job-searching.streamlit.app/
> App is password-protected to manage API costs. Happy to do a live walkthrough during interview or provide demo credentials on request.