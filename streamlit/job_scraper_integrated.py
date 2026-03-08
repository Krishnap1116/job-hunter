# job_scraper_integrated.py - JSearch + Adzuna Scraper (On-Demand)

import requests
import hashlib
import time
from datetime import datetime, timedelta


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def generate_job_id(company, title, url):
    """
    Generate unique job ID using company + title + url.
    URL makes it collision-resistant even when two companies
    post the same job title (e.g. 'Software Engineer').
    16 hex chars = 1 in 18 trillion collision chance.
    """
    raw = f"{company.strip().lower()}_{title.strip().lower()}_{url.strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def is_usa_location(location, is_remote=False):
    """Check if location is in USA or explicitly remote."""
    if is_remote:
        return True
    if not location:
        return False

    loc = location.lower()

    # Reject non-US countries explicitly
    non_us = [
        'canada', 'toronto', 'vancouver', 'uk', 'london', 'india',
        'bangalore', 'hyderabad', 'europe', 'germany', 'france',
        'australia', 'sydney', 'mexico', 'china', 'japan', 'singapore',
        'brazil', 'netherlands', 'ireland', 'poland', 'romania'
    ]
    if any(c in loc for c in non_us):
        return False

    # Accept remote
    if 'remote' in loc:
        return True

    # Accept explicit US indicators
    us_indicators = [
        'united states', 'usa', 'u.s.', ', us', '(us)',
        'california', 'new york', 'texas', 'florida', 'washington',
        'massachusetts', 'illinois', 'colorado', 'oregon', 'georgia',
        'virginia', 'north carolina', 'arizona', 'michigan', 'ohio',
        'san francisco', 'sf bay', 'seattle', 'austin', 'boston',
        'chicago', 'new york city', 'nyc', 'los angeles', 'san jose',
        'san diego', 'denver', 'atlanta', 'raleigh', 'minneapolis',
        ' ca,', ' ny,', ' tx,', ' wa,', ' ma,', ' il,', ' co,',
        ' ca ', ' ny ', ' tx ', ' wa ', ' ma ', ' il ', ' co '
    ]
    return any(indicator in loc for indicator in us_indicators)


def clean_description(text):
    """Strip HTML tags and normalize whitespace from job descriptions."""
    if not text:
        return ""
    import re
    text = re.sub(r'<[^>]+>', ' ', text)
    text = (text.replace('&amp;', '&').replace('&lt;', '<')
                .replace('&gt;', '>').replace('&nbsp;', ' ')
                .replace('&#39;', "'").replace('&quot;', '"'))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def deduplicate_jobs(jobs):
    """
    Remove duplicate jobs across sources.
    Two-pass: exact job_id match, then fuzzy company+title match.
    """
    seen_ids = set()
    seen_company_title = set()
    unique = []

    for job in jobs:
        jid = job['job_id']

        # Pass 1: exact ID match
        if jid in seen_ids:
            continue

        # Pass 2: fuzzy company+title (catches same job from different sources)
        company_norm = job.get('company', '').lower().strip()
        title_norm = job.get('title', '').lower().strip()

        # Remove suffixes that vary between sources
        for suffix in [' - remote', ' (remote)', ' | remote', ' - us',
                       ' (us)', ' - united states', ' / remote']:
            title_norm = title_norm.replace(suffix, '')

        # Use first 45 chars of title — enough to catch true dupes
        fuzzy_key = f"{company_norm}|{title_norm[:45]}"

        if fuzzy_key in seen_company_title:
            continue

        seen_ids.add(jid)
        seen_company_title.add(fuzzy_key)
        unique.append(job)

    return unique


# ─────────────────────────────────────────────
# Main Scraper Class
# ─────────────────────────────────────────────

class IntegratedScraper:
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or {}

        print("=" * 60)
        print("🔍 Scraper initialized")
        print(f"  JSearch:  {'✅ Ready' if self.api_keys.get('jsearch_key') else '❌ No API key'}")
        print(f"  Adzuna:   {'✅ Ready' if self.api_keys.get('adzuna_id') and self.api_keys.get('adzuna_key') else '❌ No API keys'}")
        print("=" * 60)

    def scrape_all(self, target_roles, limit_per_source=30):
        """
        Main entry point called when user clicks Search.
        Queries JSearch + Adzuna, deduplicates, returns clean list.

        Request budget (free tier safe):
          JSearch:  4 roles × 2 pages = 8 requests
          Adzuna:   3 roles × 1 page  = 3 requests
          Total:    ~11 requests per session
          Monthly:  ~330 requests if searched daily (JSearch free = 200/month)

        To stay within JSearch free tier: search at most once per day.
        """
        if not target_roles:
            print("❌ No target roles provided")
            return []

        all_jobs = []

        print(f"\n🎯 Target roles: {', '.join(target_roles)}")
        print(f"📅 Filter: last 24 hours | US only | Full-time\n")

        # ── Source 1: JSearch
        if self.api_keys.get('jsearch_key'):
            jsearch_jobs = self._scrape_jsearch(target_roles, limit_per_source)
            all_jobs.extend(jsearch_jobs)
            print(f"  ✅ JSearch: {len(jsearch_jobs)} jobs collected")
        else:
            print("  ⚠️  JSearch: skipped (add JSEARCH_API_KEY in Settings)")

        # ── Source 2: Adzuna
        if self.api_keys.get('adzuna_id') and self.api_keys.get('adzuna_key'):
            adzuna_jobs = self._scrape_adzuna(target_roles, limit_per_source)
            all_jobs.extend(adzuna_jobs)
            print(f"  ✅ Adzuna:  {len(adzuna_jobs)} jobs collected")
        else:
            print("  ⚠️  Adzuna:  skipped (add ADZUNA_APP_ID and ADZUNA_API_KEY in Settings)")

        if not all_jobs:
            print("\n❌ No jobs collected. Check your API keys in Settings.")
            return []

        # ── Deduplicate
        before = len(all_jobs)
        all_jobs = deduplicate_jobs(all_jobs)
        dupes_removed = before - len(all_jobs)

        print(f"\n{'=' * 60}")
        print(f"✅ Unique jobs ready for analysis: {len(all_jobs)}")
        if dupes_removed:
            print(f"🔁 Duplicates removed: {dupes_removed}")
        print(f"{'=' * 60}\n")

        return all_jobs

    # ─────────────────────────────────────────
    # JSearch
    # ─────────────────────────────────────────

    def _scrape_jsearch(self, target_roles, limit):
        """
        JSearch via RapidAPI — aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter.

        Strategy:
        - Query up to 4 roles (covers most use cases without blowing request budget)
        - 2 pages per role = 20 results per role
        - date_posted=today ensures last 24h freshness
        - Retry once on timeout, skip on rate limit
        """
        jobs = []
        api_key = self.api_keys['jsearch_key']
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }

        roles_to_query = target_roles[:4]
        pages_per_role = 2  # 2 pages × 10 results = 20 per role

        for role in roles_to_query:
            role_count = 0
            for page in range(1, pages_per_role + 1):
                success = False
                retries = 1

                for attempt in range(retries + 1):
                    try:
                        params = {
                            "query": f"{role} United States",
                            "page": str(page),
                            "num_pages": "1",
                            "date_posted": "today",
                            "employment_types": "FULLTIME",
                            "country": "us",
                            "language": "en_US"
                        }

                        response = requests.get(
                            "https://jsearch.p.rapidapi.com/search",
                            headers=headers,
                            params=params,
                            timeout=20
                        )

                        if response.status_code == 429:
                            print(f"  ⚠️  JSearch rate limit hit — waiting 15s")
                            time.sleep(15)
                            continue

                        if response.status_code == 403:
                            print(f"  ❌ JSearch: Invalid API key")
                            return jobs

                        if response.status_code != 200:
                            print(f"  ❌ JSearch HTTP {response.status_code} for '{role}'")
                            break

                        data = response.json().get('data', [])

                        for item in data:
                            company = (item.get('employer_name') or '').strip() or 'Unknown'
                            title = (item.get('job_title') or '').strip()
                            apply_url = (item.get('job_apply_link') or
                                         item.get('job_google_link') or '')
                            city = item.get('job_city') or ''
                            state = item.get('job_state') or ''
                            location = f"{city} {state}".strip()
                            is_remote = bool(item.get('job_is_remote'))
                            description = clean_description(
                                item.get('job_description') or ''
                            )

                            # Validation
                            if not title:
                                continue
                            if not apply_url or not apply_url.startswith('http'):
                                continue
                            if not is_usa_location(location, is_remote):
                                continue
                            # Skip jobs with no meaningful description
                            # Claude can't analyze them — waste of API calls
                            if len(description) < 150:
                                continue

                            final_location = 'Remote (US)' if is_remote else location

                            jobs.append({
                                'job_id': generate_job_id(company, title, apply_url),
                                'company': company,
                                'title': title,
                                'url': apply_url,
                                'location': final_location,
                                # 6000 chars ≈ 1500 tokens — enough for full JD analysis
                                # Taking from END of description captures requirements
                                # section which is usually at the bottom
                                'description': description[-6000:] if len(description) > 6000 else description,
                                'source': f"JSearch-{item.get('job_publisher', 'Unknown')}"
                            })
                            role_count += 1

                        success = True
                        break  # Successful response, no retry needed

                    except requests.Timeout:
                        if attempt < retries:
                            print(f"  ⚠️  JSearch timeout for '{role}' p{page}, retrying...")
                            time.sleep(3)
                        else:
                            print(f"  ❌ JSearch timeout for '{role}' p{page}, skipping")
                    except Exception as e:
                        print(f"  ❌ JSearch error for '{role}': {str(e)[:80]}")
                        break

                if not success:
                    break  # Stop paging this role if a page failed

                time.sleep(1.5)  # Respectful delay between page requests

            time.sleep(1)  # Delay between roles

        return jobs

    # ─────────────────────────────────────────
    # Adzuna
    # ─────────────────────────────────────────

    def _scrape_adzuna(self, target_roles, limit):
        """
        Adzuna API — free, no monthly cap, good US coverage.
        Different inventory from JSearch so it adds unique jobs.
        max_days_old=1 ensures fresh results.
        """
        jobs = []
        app_id = self.api_keys['adzuna_id']
        app_key = self.api_keys['adzuna_key']

        roles_to_query = target_roles[:3]

        for role in roles_to_query:
            try:
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": min(limit, 50),
                    "what": role,
                    "where": "United States",
                    "max_days_old": 1,
                    "sort_by": "date",
                    "full_time": 1,
                }

                response = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/us/search/1",
                    params=params,
                    timeout=20
                )

                if response.status_code == 401:
                    print(f"  ❌ Adzuna: Invalid credentials")
                    return jobs

                if response.status_code != 200:
                    print(f"  ❌ Adzuna HTTP {response.status_code} for '{role}'")
                    continue

                for item in response.json().get('results', []):
                    company = (item.get('company', {}).get('display_name') or '').strip() or 'Unknown'
                    title = (item.get('title') or '').strip()
                    url = item.get('redirect_url') or ''
                    location = item.get('location', {}).get('display_name') or ''
                    description = clean_description(item.get('description') or '')

                    if not title or not url:
                        continue
                    if not is_usa_location(location):
                        continue
                    if len(description) < 150:
                        continue

                    jobs.append({
                        'job_id': generate_job_id(company, title, url),
                        'company': company,
                        'title': title,
                        'url': url,
                        'location': location,
                        'description': description[-6000:] if len(description) > 6000 else description,
                        'source': 'Adzuna'
                    })

                time.sleep(1)

            except requests.Timeout:
                print(f"  ⚠️  Adzuna timeout for '{role}'")
            except Exception as e:
                print(f"  ❌ Adzuna error for '{role}': {str(e)[:80]}")

        return jobs