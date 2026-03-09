#!/usr/bin/env python3
"""
daily_collect.py — Run by GitHub Actions at 9 AM UTC every day.

Scrapes jobs from all sources → saves to global_raw_jobs in Neon.
All users see the fresh pool when they log in and run analysis.

Usage:
  python streamlit/daily_collect.py

Required env vars:
  DATABASE_URL      — Neon PostgreSQL connection string
  JSEARCH_API_KEY   — RapidAPI key (optional, adds LinkedIn/Indeed/Glassdoor)
  ADZUNA_APP_ID     — Adzuna app ID (optional)
  ADZUNA_API_KEY    — Adzuna API key (optional)
"""

import os
import sys
from datetime import datetime

# ── Broad target roles that cover most ML/AI/SWE profiles ──────────────
# These are generic enough to catch jobs for most users.
# Each user's Claude analysis then filters to their specific profile.
DEFAULT_TARGET_ROLES = [
    "machine learning engineer",
    "data scientist",
    "software engineer",
    "AI engineer",
    "NLP engineer",
    "research engineer",
    "data engineer",
    "backend engineer",
    "MLOps engineer",
    "computer vision engineer",
]

def main():
    print(f"\n{'='*60}")
    print(f"🎯 Daily Job Collection — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # Verify DB is reachable
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL not set. Exiting.")
        sys.exit(1)

    from database_manager import JobHunterDB
    from job_scraper_integrated import IntegratedScraper

    db = JobHunterDB()

    # Purge jobs older than 7 days first
    purged = db.purge_old_global_jobs(days=7)
    print(f"🗑  Purged {purged} old jobs from pool\n")

    # API keys from environment (no user keys needed for scraping)
    api_keys = {
        'jsearch_key': os.getenv("JSEARCH_API_KEY", ""),
        'adzuna_id':   os.getenv("ADZUNA_APP_ID", ""),
        'adzuna_key':  os.getenv("ADZUNA_API_KEY", ""),
        # No anthropic_key needed — scraper doesn't use Claude
    }

    scraper = IntegratedScraper(api_keys)

    print(f"🔍 Scraping for {len(DEFAULT_TARGET_ROLES)} role types...\n")

    try:
        jobs = scraper.scrape_all(
            target_roles=DEFAULT_TARGET_ROLES,
            limit_per_source=50
        )
    except Exception as e:
        print(f"❌ Scraper error: {e}")
        sys.exit(1)

    print(f"\n📥 Saving {len(jobs)} jobs to global pool...")

    saved = 0
    dupes = 0
    for job in jobs:
        if db.save_global_job(job):
            saved += 1
        else:
            dupes += 1

    stats = db.get_global_pool_stats()

    print(f"\n{'='*60}")
    print(f"✅ Done!")
    print(f"   New jobs saved : {saved}")
    print(f"   Duplicates skipped: {dupes}")
    print(f"   Total pool size: {stats['total']}")
    print(f"   Last updated   : {stats['last_scraped']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()