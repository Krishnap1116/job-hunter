# job_scraper_integrated.py - JSearch + Adzuna Scraper (On-Demand)

import requests
import hashlib
import time


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def generate_job_id(company, title, url):
    raw = f"{company.strip().lower()}_{title.strip().lower()}_{url.strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def is_usa_location(location, is_remote=False):
    """
    Returns True for US or remote jobs.
    IMPORTANT: empty/unknown locations are accepted — many legitimate
    remote-friendly US postings omit the location field entirely.
    """
    if is_remote:
        return True
    if not location:
        return True  # Accept unknown — better to over-include

    loc = location.lower().strip()

    # Explicit non-US — reject only when clearly identified
    non_us = [
        'canada', 'toronto', 'vancouver', 'ottawa', 'montreal', 'calgary',
        'united kingdom', ' uk,', '(uk)', 'london', 'manchester', 'edinburgh',
        'india', 'bangalore', 'bengaluru', 'hyderabad', 'mumbai', 'pune', 'delhi',
        'europe', 'germany', 'berlin', 'france', 'paris',
        'netherlands', 'amsterdam', 'ireland', 'dublin',
        'poland', 'warsaw', 'romania', 'bucharest',
        'australia', 'sydney', 'melbourne', 'new zealand', 'auckland',
        'mexico', 'brazil', 'argentina', 'colombia', 'chile',
        'china', 'beijing', 'shanghai', 'japan', 'tokyo',
        'singapore', 'philippines', 'manila',
        'nigeria', 'south africa', 'kenya',
        'israel', 'tel aviv',
    ]
    if any(c in loc for c in non_us):
        return False

    # Anything else passes (includes 'remote', US cities, US states, blank)
    return True


def clean_description(text):
    """Strip HTML tags and normalize whitespace."""
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
    """Two-pass dedup: exact job_id + fuzzy company+title."""
    seen_ids = set()
    seen_ct  = set()
    unique   = []

    for job in jobs:
        jid = job['job_id']
        if jid in seen_ids:
            continue

        co    = job.get('company', '').lower().strip()
        title = job.get('title', '').lower().strip()

        for suffix in [' - remote', ' (remote)', ' | remote', ' - us',
                       ' (us)', ' - united states', ' / remote']:
            title = title.replace(suffix, '')

        key = f"{co}|{title[:50]}"
        if key in seen_ct:
            continue

        seen_ids.add(jid)
        seen_ct.add(key)
        unique.append(job)

    return unique


# ─────────────────────────────────────────────
# Main Scraper
# ─────────────────────────────────────────────

class IntegratedScraper:
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or {}
        print("=" * 60)
        print("🔍 Scraper initialized")
        print(f"  RemoteOK:   ✅ Free (no key needed)")
        print(f"  Jobicy:     ✅ Free (no key needed)")
        print(f"  Greenhouse: ✅ Free (official public API)")
        print(f"  Lever:      ✅ Free (official public API)")
        print(f"  JSearch:    {'✅ Ready' if self.api_keys.get('jsearch_key') else '⚠️  No key (add in Settings)'}")
        print(f"  Adzuna:     {'✅ Ready' if self.api_keys.get('adzuna_id') else '⚠️  No key (add in Settings)'}")
        print("=" * 60)

    # ── Company lists for ATS scraping ────────────────────────────
    # These are real AI/ML/tech companies verified to use each ATS.
    # Board tokens are the slug used in their public ATS URL.
    # Greenhouse: https://boards.greenhouse.io/{token}
    # Lever:      https://jobs.lever.co/{token}

    GREENHOUSE_COMPANIES = [
        # Big Tech / AI Labs
        "anthropic", "openai", "deepmind", "inflection",
        "cohere", "adept", "runway", "huggingface",
        # Tech
        "airbnb", "stripe", "figma", "notion", "linear",
        "vercel", "planetscale", "supabase", "retool",
        "brex", "ramp", "rippling", "lattice", "deel",
        "scale", "snorkel", "clarifai", "weights-biases",
        "databricks", "pinecone", "weaviate", "chroma",
        "modal", "replicate", "together", "mistral",
        "covariant", "wayve", "comma", "cruise",
        "relativityspace", "astranis", "axiom-space",
        "reddit", "twitch", "discord", "duolingo",
        "canva", "figma", "miro", "loom",
        "gusto", "justworks", "mercury", "plaid",
        "palantir", "c3dotai", "dataiku", "alteryx",
        "snowflake", "dbt-labs", "fivetran", "airbyte",
        "elastic", "neo4j", "tigergraph",
    ]

    LEVER_COMPANIES = [
        # Big Tech / AI
        "netflix", "dropbox", "anduril", "scale-ai",
        "xai", "perplexity", "mistral-ai",
        "cerebras", "sambanova", "groq", "tenstorrent",
        "together-ai", "fireworks-ai", "baseten",
        # Tech
        "robinhood", "coinbase", "kraken", "polygon",
        "amplitude", "mixpanel", "segment", "heap",
        "asana", "monday", "clickup", "notion",
        "carta", "airtable", "webflow", "zapier",
        "cloudflare", "hashicorp", "datadog", "new-relic",
        "pagerduty", "opsgenie", "incident-io",
        "lyft", "doordash", "instacart", "gopuff",
        "nuro", "aurora", "motional", "torc",
        "shield-ai", "joby-aviation", "zipline",
        "recursion", "insitro", "valo-health",
    ]

    def scrape_all(self, target_roles, limit_per_source=50):
        """
        6 sources total — all work on Streamlit Cloud:

        FREE (no key, official public APIs — cloud-safe):
          1. Greenhouse ATS  — official public Job Board API, no auth
          2. Lever ATS       — official public postings API, no auth
          3. RemoteOK        — public JSON API feed
          4. Jobicy          — public JSON API, US filter

        WITH API KEY (add in Settings for more volume):
          5. JSearch         — aggregates LinkedIn/Indeed/Glassdoor/ZipRecruiter
          6. Adzuna          — independent job board with good US coverage

        NOTE on python-jobspy / direct LinkedIn/Indeed scraping:
        NOT included because Streamlit Cloud runs on shared AWS IPs that are
        permanently flagged by LinkedIn and throttled by Indeed. Would return
        0 results or 403s in production even if it works locally.
        """
        if not target_roles:
            return []

        all_jobs = []
        print(f"\n🎯 Roles: {', '.join(target_roles)}")

        # ── ATS sources (official APIs, always run) ────────────
        gh = self._scrape_greenhouse(target_roles)
        all_jobs.extend(gh)
        print(f"  Greenhouse: {len(gh)} collected")

        lv = self._scrape_lever(target_roles)
        all_jobs.extend(lv)
        print(f"  Lever:      {len(lv)} collected")

        # ── Remote board sources (always run) ──────────────────
        r = self._scrape_remoteok(target_roles)
        all_jobs.extend(r)
        print(f"  RemoteOK:   {len(r)} collected")

        j2 = self._scrape_jobicy(target_roles)
        all_jobs.extend(j2)
        print(f"  Jobicy:     {len(j2)} collected")

        # ── API key sources ────────────────────────────────────
        if self.api_keys.get('jsearch_key'):
            j = self._scrape_jsearch(target_roles, limit_per_source)
            all_jobs.extend(j)
            print(f"  JSearch:    {len(j)} collected")
        else:
            print("  JSearch:    skipped (add key in Settings)")

        if self.api_keys.get('adzuna_id') and self.api_keys.get('adzuna_key'):
            a = self._scrape_adzuna(target_roles, limit_per_source)
            all_jobs.extend(a)
            print(f"  Adzuna:     {len(a)} collected")
        else:
            print("  Adzuna:     skipped (add key in Settings)")

        if not all_jobs:
            print("❌ No jobs collected.")
            return []

        before   = len(all_jobs)
        all_jobs = deduplicate_jobs(all_jobs)
        print(f"✅ {len(all_jobs)} unique jobs ({before - len(all_jobs)} dupes removed)")
        return all_jobs

    # ─────────────────────────────────────────
    # Greenhouse ATS  (free, official public API)
    # ─────────────────────────────────────────

    def _scrape_greenhouse(self, target_roles):
        """
        Greenhouse Job Board API — https://developers.greenhouse.io/job-board.html
        Official public API, no auth required, no scraping.
        Works on Streamlit Cloud because it's a legitimate API call.

        Strategy:
        - Hit each company's jobs endpoint in parallel (with threading)
        - Filter jobs where title matches any target role keyword
        - Fetch full description for matched jobs only (to limit requests)
        - Skip companies that 404 (board token no longer valid)
        - Respect a short delay between company fetches
        """
        import re
        from concurrent.futures import ThreadPoolExecutor, as_completed

        jobs     = []
        seen_ids = set()

        # Build keyword set from target roles
        role_keywords = self._build_role_keywords(target_roles)

        def fetch_company(token):
            """Fetch all jobs for one company, return matching ones."""
            company_jobs = []
            try:
                resp = requests.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    params={"content": "false"},  # titles+location only, no description yet
                    timeout=10
                )
                if resp.status_code in (404, 410):
                    return []  # Company no longer on Greenhouse
                if resp.status_code != 200:
                    return []

                data      = resp.json()
                all_jobs  = data.get('jobs', [])

                for item in all_jobs:
                    title    = (item.get('title') or '').strip()
                    location = (item.get('location', {}) or {}).get('name', '') or ''
                    url      = item.get('absolute_url') or ''
                    job_id_gh = str(item.get('id', ''))
                    updated  = item.get('updated_at') or ''

                    if not title or not url:
                        continue

                    # Only keep jobs where title matches our target roles
                    if not any(kw in title.lower() for kw in role_keywords):
                        continue

                    # Filter out obvious seniority mismatches in title
                    title_l = title.lower()
                    if any(s in title_l for s in ['vp ', 'vice president', 'chief ', ' cto', ' cpo']):
                        continue

                    # Use company name from token (cleaned up)
                    company = token.replace('-', ' ').title()

                    company_jobs.append({
                        '_gh_id':    job_id_gh,
                        '_token':    token,
                        'company':   company,
                        'title':     title,
                        'url':       url,
                        'location':  location or 'United States',
                        'updated':   updated,
                    })

            except Exception:
                pass
            return company_jobs

        def fetch_description(job):
            """Fetch full job description for a matched job."""
            try:
                token = job.pop('_token')
                gh_id = job.pop('_gh_id')
                resp  = requests.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{gh_id}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data    = resp.json()
                    raw_desc = data.get('content') or ''
                    desc    = clean_description(raw_desc)
                    job['description'] = desc[-6000:] if len(desc) > 6000 else desc
                else:
                    job['description'] = f"See full posting at: {job['url']}"
            except Exception:
                job['description'] = f"See full posting at: {job['url']}"
            job.pop('updated', None)
            return job

        # Phase 1: Fetch job lists concurrently (IO-bound, safe to parallelize)
        matched_stubs = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_company, t): t for t in self.GREENHOUSE_COMPANIES}
            for fut in as_completed(futures):
                matched_stubs.extend(fut.result())

        # Phase 2: Fetch descriptions for matched jobs (sequential, rate-limiting)
        for stub in matched_stubs:
            jid = generate_job_id(stub['company'], stub['title'], stub['url'])
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            job = fetch_description(stub)
            job['job_id'] = jid
            job['source'] = 'Greenhouse'

            if len(job.get('description', '')) < 50:
                job['description'] = f"Apply at: {job['url']}"

            jobs.append(job)
            time.sleep(0.3)  # Polite delay between description fetches

        return jobs

    # ─────────────────────────────────────────
    # Lever ATS  (free, official public API)
    # ─────────────────────────────────────────

    def _scrape_lever(self, target_roles):
        """
        Lever Postings API — https://hire.lever.co/developer/postings
        Official public API, no auth required.
        Works on Streamlit Cloud — legitimate API call.

        Lever returns all postings for a company at once (no pagination).
        We filter by title keyword match.
        Description is included in the listing response — no second fetch needed.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        jobs     = []
        seen_ids = set()

        role_keywords = self._build_role_keywords(target_roles)

        def fetch_company(token):
            company_jobs = []
            try:
                resp = requests.get(
                    f"https://api.lever.co/v0/postings/{token}",
                    params={
                        "mode":  "json",
                        "limit": 250,
                    },
                    timeout=12
                )
                if resp.status_code in (404, 410):
                    return []
                if resp.status_code != 200:
                    return []

                postings = resp.json()
                if not isinstance(postings, list):
                    return []

                for item in postings:
                    title     = (item.get('text') or '').strip()
                    url       = item.get('hostedUrl') or item.get('applyUrl') or ''
                    location  = ''
                    categories = item.get('categories') or {}
                    if isinstance(categories, dict):
                        location = categories.get('location') or categories.get('allLocations') or ''
                        if isinstance(location, list):
                            location = ', '.join(location)
                    commitment = (categories.get('commitment') or '').lower()

                    if not title or not url:
                        continue

                    # Filter by title keyword
                    if not any(kw in title.lower() for kw in role_keywords):
                        continue

                    # Skip non-fulltime where we can detect it
                    if commitment and commitment not in ('full-time', 'fulltime', ''):
                        if 'intern' in commitment or 'part' in commitment:
                            continue

                    # Skip senior/exec roles
                    title_l = title.lower()
                    if any(s in title_l for s in ['vp ', 'vice president', 'chief ', ' cto']):
                        continue

                    # Get description from the posting
                    description_html = ''
                    lists = item.get('lists') or []
                    for lst in lists:
                        description_html += (lst.get('text') or '') + '\n'
                        for content in (lst.get('content') or []):
                            if isinstance(content, str):
                                description_html += content + '\n'
                    additional = item.get('additional') or item.get('descriptionPlain') or ''
                    description_html += additional

                    desc = clean_description(description_html)
                    if len(desc) < 80:
                        desc = f"Apply at: {url}"

                    company = token.replace('-', ' ').title()

                    company_jobs.append({
                        'company':     company,
                        'title':       title,
                        'url':         url,
                        'location':    location or 'United States',
                        'description': desc[-6000:] if len(desc) > 6000 else desc,
                    })

            except Exception:
                pass
            return company_jobs

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_company, t): t for t in self.LEVER_COMPANIES}
            for fut in as_completed(futures):
                for job in fut.result():
                    jid = generate_job_id(job['company'], job['title'], job['url'])
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    job['job_id'] = jid
                    job['source'] = 'Lever'
                    jobs.append(job)

        return jobs

    # ─────────────────────────────────────────
    # Shared helper
    # ─────────────────────────────────────────

    def _build_role_keywords(self, target_roles):
        """
        Build a flat set of lowercase keywords from target roles.
        Used to filter ATS listings by title.
        """
        keywords = set()

        # Add each word from each role (skip short noise words)
        for role in target_roles:
            keywords.add(role.lower())
            for word in role.lower().split():
                if len(word) > 2:
                    keywords.add(word)

        # Add common synonyms/abbreviations
        synonym_groups = [
            {'machine learning', 'ml', 'deep learning'},
            {'natural language processing', 'nlp', 'language model', 'llm'},
            {'artificial intelligence', 'ai'},
            {'data science', 'data scientist'},
            {'computer vision', 'cv engineer'},
            {'reinforcement learning', 'rl'},
            {'generative ai', 'genai', 'gen ai'},
            {'large language model', 'llm', 'foundation model'},
        ]
        for group in synonym_groups:
            if keywords & group:          # if we already have one from this group
                keywords.update(group)    # add all of them

        return keywords

    # ─────────────────────────────────────────
    # RemoteOK  (free, no API key)
    # ─────────────────────────────────────────

    def _scrape_remoteok(self, target_roles):
        """
        RemoteOK public API — https://remoteok.com/api
        No key required. Returns ~300 most recent remote jobs.
        We filter by matching any target role keyword in title or tags.
        Attribution required: link back to remoteok.com.
        """
        jobs = []
        try:
            resp = requests.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "JobHunterApp/1.0 (personal job search tool)"},
                timeout=20
            )
            if resp.status_code != 200:
                print(f"  RemoteOK HTTP {resp.status_code}")
                return jobs

            data = resp.json()
            # First item is a metadata object, skip it
            listings = [item for item in data if isinstance(item, dict) and item.get('id')]

            # Build keyword set from target roles for matching
            role_keywords = set()
            for role in target_roles:
                for word in role.lower().split():
                    if len(word) > 2:  # skip short words like 'ai', 'ml'
                        role_keywords.add(word)
                role_keywords.add(role.lower())  # also add full phrase

            # Also add common synonyms
            synonym_map = {
                'machine learning': ['ml', 'deep learning', 'ai', 'neural'],
                'ml engineer':      ['machine learning', 'ai engineer', 'deep learning'],
                'data scientist':   ['data science', 'analytics', 'ml', 'ai'],
                'data engineer':    ['data pipeline', 'etl', 'analytics'],
                'nlp':              ['natural language', 'llm', 'language model'],
                'ai engineer':      ['ml', 'machine learning', 'llm', 'genai'],
                'software engineer':['software developer', 'backend', 'fullstack'],
                'devops':           ['sre', 'platform', 'infrastructure', 'cloud'],
            }
            for role in target_roles:
                role_lower = role.lower()
                for key, synonyms in synonym_map.items():
                    if key in role_lower:
                        role_keywords.update(synonyms)

            for item in listings:
                title    = (item.get('position') or '').strip()
                company  = (item.get('company') or '').strip() or 'Unknown'
                url      = item.get('url') or item.get('apply_url') or ''
                tags     = [t.lower() for t in (item.get('tags') or [])]
                description = clean_description(item.get('description') or '')

                if not title or not url:
                    continue
                if not url.startswith('http'):
                    url = f"https://remoteok.com{url}"
                if len(description) < 100:
                    continue

                # Match: title or tags must contain at least one role keyword
                title_lower = title.lower()
                searchable  = title_lower + ' ' + ' '.join(tags)
                if not any(kw in searchable for kw in role_keywords):
                    continue

                jobs.append({
                    'job_id':      generate_job_id(company, title, url),
                    'company':     company,
                    'title':       title,
                    'url':         url,
                    'location':    'Remote (US)',
                    'description': description[-6000:] if len(description) > 6000 else description,
                    'source':      'RemoteOK',
                })

        except requests.Timeout:
            print("  RemoteOK: timeout")
        except Exception as e:
            print(f"  RemoteOK error: {str(e)[:80]}")

        return jobs

    # ─────────────────────────────────────────
    # Jobicy  (free, no API key)
    # ─────────────────────────────────────────

    def _scrape_jobicy(self, target_roles):
        """
        Jobicy public API — https://jobicy.com/api/v2/remote-jobs
        No key required. Supports tag + geo=usa filter.
        Returns up to 50 results per call. We query per role.
        """
        jobs     = []
        seen_ids = set()  # local dedup within this source

        # Map target roles to Jobicy industry categories where relevant
        industry_map = {
            'data scientist':    'data-science',
            'machine learning':  'data-science',
            'ml engineer':       'data-science',
            'ai engineer':       'data-science',
            'data engineer':     'data-science',
            'software engineer': 'dev',
            'frontend':          'dev',
            'backend':           'dev',
            'fullstack':         'dev',
            'devops':            'dev',
            'nlp':               'data-science',
        }

        for role in target_roles:
            role_lower = role.lower()
            industry   = None
            for key, cat in industry_map.items():
                if key in role_lower:
                    industry = cat
                    break

            try:
                params = {
                    'count': 50,
                    'geo':   'usa',
                    'tag':   role,
                }
                if industry:
                    params['industry'] = industry

                resp = requests.get(
                    "https://jobicy.com/api/v2/remote-jobs",
                    params=params,
                    timeout=20
                )

                if resp.status_code != 200:
                    print(f"  Jobicy HTTP {resp.status_code} for '{role}'")
                    continue

                data = resp.json()
                listings = data.get('jobs', [])

                for item in listings:
                    title    = (item.get('jobTitle') or '').strip()
                    company  = (item.get('companyName') or '').strip() or 'Unknown'
                    url      = item.get('url') or ''
                    description = clean_description(
                        (item.get('jobDescription') or item.get('jobExcerpt') or '')
                    )

                    if not title or not url:
                        continue
                    if len(description) < 100:
                        continue

                    # Jobicy can return non-US even with geo=usa, double-check
                    job_geo = (item.get('jobGeo') or '').lower()
                    if job_geo and job_geo not in ('usa', 'us', 'united states',
                                                    'worldwide', 'anywhere', ''):
                        # Allow worldwide/anywhere — these are remote roles open to US
                        if not any(x in job_geo for x in ['usa', 'us ', 'america', 'worldwide', 'anywhere']):
                            continue

                    jid = generate_job_id(company, title, url)
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)

                    jobs.append({
                        'job_id':      jid,
                        'company':     company,
                        'title':       title,
                        'url':         url,
                        'location':    'Remote (US)',
                        'description': description[-6000:] if len(description) > 6000 else description,
                        'source':      'Jobicy',
                    })

                time.sleep(0.5)

            except requests.Timeout:
                print(f"  Jobicy timeout for '{role}'")
            except Exception as e:
                print(f"  Jobicy error '{role}': {str(e)[:80]}")

        return jobs

    # ─────────────────────────────────────────
    # JSearch
    # ─────────────────────────────────────────

    def _scrape_jsearch(self, target_roles, limit):
        jobs    = []
        headers = {
            "X-RapidAPI-Key":  self.api_keys['jsearch_key'],
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }

        # Build broadened query list
        queries = list(target_roles)

        broad_map = {
            'machine learning':   ['ML engineer', 'AI engineer', 'deep learning'],
            'ml engineer':        ['machine learning engineer', 'AI engineer'],
            'data scientist':     ['data science', 'applied scientist', 'research scientist'],
            'data engineer':      ['analytics engineer', 'data pipeline'],
            'software engineer':  ['software developer', 'backend engineer'],
            'frontend':           ['frontend developer', 'UI engineer', 'react developer'],
            'backend':            ['backend developer', 'API engineer'],
            'nlp':                ['NLP engineer', 'LLM engineer', 'language model'],
            'ai engineer':        ['ML engineer', 'LLM engineer', 'generative AI'],
            'research engineer':  ['research scientist', 'applied scientist'],
            'devops':             ['platform engineer', 'SRE', 'site reliability'],
            'fullstack':          ['full stack developer', 'full-stack engineer'],
        }

        for role in target_roles:
            role_lower = role.lower()
            for key, variants in broad_map.items():
                if key in role_lower:
                    queries.extend(variants)
                    break

        # Deduplicate queries
        seen_q, unique_queries = set(), []
        for q in queries:
            if q.lower() not in seen_q:
                seen_q.add(q.lower())
                unique_queries.append(q)

        for role in unique_queries:
            for page in range(1, 4):  # 3 pages × 10 = 30 results/role
                try:
                    params = {
                        "query":            f"{role} United States",
                        "page":             str(page),
                        "num_pages":        "1",
                        "date_posted":      "3days",   # ← wider window
                        "employment_types": "FULLTIME",
                        "country":          "us",
                        "language":         "en_US",
                    }

                    resp = requests.get(
                        "https://jsearch.p.rapidapi.com/search",
                        headers=headers,
                        params=params,
                        timeout=25
                    )

                    if resp.status_code == 429:
                        print("  ⚠️  JSearch rate limit — pausing 20s")
                        time.sleep(20)
                        continue
                    if resp.status_code == 403:
                        print("  ❌ JSearch: invalid API key")
                        return jobs
                    if resp.status_code != 200:
                        print(f"  JSearch {resp.status_code} for '{role}'")
                        break

                    data = resp.json().get('data', [])

                    for item in data:
                        company     = (item.get('employer_name') or '').strip() or 'Unknown'
                        title       = (item.get('job_title') or '').strip()
                        apply_url   = (item.get('job_apply_link') or
                                       item.get('job_google_link') or '')
                        city        = item.get('job_city') or ''
                        state       = item.get('job_state') or ''
                        location    = f"{city}, {state}".strip(', ')
                        is_remote   = bool(item.get('job_is_remote'))
                        description = clean_description(item.get('job_description') or '')

                        if not title:
                            continue
                        if not apply_url or not apply_url.startswith('http'):
                            continue
                        if not is_usa_location(location, is_remote):
                            continue
                        if len(description) < 100:  # ← was 150
                            continue

                        loc_display = 'Remote (US)' if is_remote else (location or 'United States')

                        jobs.append({
                            'job_id':      generate_job_id(company, title, apply_url),
                            'company':     company,
                            'title':       title,
                            'url':         apply_url,
                            'location':    loc_display,
                            'description': description[-6000:] if len(description) > 6000 else description,
                            'source':      f"JSearch-{item.get('job_publisher', 'Unknown')}",
                        })

                    time.sleep(1.2)

                except requests.Timeout:
                    print(f"  Timeout JSearch '{role}' p{page}")
                    break
                except Exception as e:
                    print(f"  Error JSearch '{role}': {str(e)[:80]}")
                    break

            time.sleep(0.8)

        return jobs

    # ─────────────────────────────────────────
    # Adzuna
    # ─────────────────────────────────────────

    def _scrape_adzuna(self, target_roles, limit):
        jobs    = []
        app_id  = self.api_keys['adzuna_id']
        app_key = self.api_keys['adzuna_key']

        for role in target_roles:
            for page in [1, 2]:  # ← added page 2
                try:
                    params = {
                        "app_id":           app_id,
                        "app_key":          app_key,
                        "results_per_page": min(limit, 50),
                        "what":             role,
                        "where":            "United States",
                        "max_days_old":     3,   # ← was 1
                        "sort_by":          "date",
                        "full_time":        1,
                    }

                    resp = requests.get(
                        f"https://api.adzuna.com/v1/api/jobs/us/search/{page}",
                        params=params,
                        timeout=25
                    )

                    if resp.status_code == 401:
                        print("  ❌ Adzuna: invalid credentials")
                        return jobs
                    if resp.status_code != 200:
                        print(f"  Adzuna {resp.status_code} for '{role}'")
                        break

                    results = resp.json().get('results', [])
                    if not results:
                        break

                    for item in results:
                        company     = (item.get('company', {}).get('display_name') or '').strip() or 'Unknown'
                        title       = (item.get('title') or '').strip()
                        url         = item.get('redirect_url') or ''
                        location    = item.get('location', {}).get('display_name') or ''
                        description = clean_description(item.get('description') or '')

                        if not title or not url:
                            continue
                        if not is_usa_location(location):
                            continue
                        if len(description) < 100:
                            continue

                        jobs.append({
                            'job_id':      generate_job_id(company, title, url),
                            'company':     company,
                            'title':       title,
                            'url':         url,
                            'location':    location or 'United States',
                            'description': description[-6000:] if len(description) > 6000 else description,
                            'source':      'Adzuna',
                        })

                    time.sleep(1)

                except requests.Timeout:
                    print(f"  Timeout Adzuna '{role}' p{page}")
                    break
                except Exception as e:
                    print(f"  Error Adzuna '{role}': {str(e)[:80]}")
                    break

        return jobs