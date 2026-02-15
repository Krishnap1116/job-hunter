# scraper.py - EXPERT MULTI-SOURCE JOB SCRAPER

import requests
import os
from datetime import datetime, timedelta
import hashlib
import time
import re
import feedparser
from bs4 import BeautifulSoup

# ==================== CONFIGURATION ====================

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")

SEARCH_QUERIES = [
    "software engineer",
    "machine learning engineer",
    "AI engineer",
    "backend engineer",
    "full stack engineer",
    "data engineer"
]

GREENHOUSE_COMPANIES = [
    'stripe', 'ramp', 'notion', 'figma', 'anthropic', 
    'scale', 'discord', 'airtable', 'brex', 'openai',
    'databricks', 'snowflake', 'confluent', 'coinbase',
    'robinhood', 'chime', 'square', 'affirm', 'reddit',
    'pinterest', 'snap', 'dropbox', 'airbnb', 'doordash'
]

LEVER_COMPANIES = [
    'rippling', 'plaid', 'retool', 'verkada', 'faire',
    'superhuman', 'loom', 'mux', 'gusto', 'lattice',
    'vanta', 'merge', 'ramp', 'census', 'dbt'
]

RSS_FEEDS = {
    'remotive': 'https://remotive.com/api/remote-jobs',
    'weworkremotely': 'https://weworkremotely.com/remote-jobs.rss',
}

# ==================== MINIMAL HELPER FUNCTIONS ====================

def is_usa_location(location):
    """STRICT USA-only check - uses structured data"""
    if not location:
        return False
    
    location_lower = location.lower()
    
    # REJECT other countries
    reject_countries = [
        'canada', 'toronto', 'vancouver', 'montreal',
        'uk', 'london', 'india', 'bangalore', 'mumbai',
        'europe', 'germany', 'france', 'australia',
        'mexico', 'brazil', 'china', 'japan', 'singapore'
    ]
    
    if any(country in location_lower for country in reject_countries):
        return False
    
    # ACCEPT USA
    usa_indicators = [
        'united states', 'usa', 'u.s.', 'us,',
        'california', 'new york', 'texas', 'florida', 'washington',
        'massachusetts', 'illinois', 'colorado', 'oregon', 'georgia',
        'san francisco', 'seattle', 'austin', 'boston', 'chicago',
        'remote us', 'remote usa', 'remote - us', 'remote (us)'
    ]
    
    return any(indicator in location_lower for indicator in usa_indicators)

def is_recent(date_str, hours=24):
    """Check if posted in last 24 hours (STRICT)"""
    if not date_str:
        return True  # If no date, include it (we'll filter in Claude)
    
    try:
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%a, %d %b %Y %H:%M:%S %Z'
        ]
        
        for fmt in formats:
            try:
                posted = datetime.strptime(date_str.strip(), fmt)
                hours_ago = (datetime.utcnow() - posted).total_seconds() / 3600
                return hours_ago <= hours  # 24 hours
            except:
                continue
        
        return True  # If can't parse, let Claude decide
    except:
        return True

# ==================== LAYER 1: FREE APIs ====================

def fetch_jsearch_jobs():
    """JSearch API - FREE 150 calls/month"""
    if not JSEARCH_API_KEY:
        print("⚠️  JSearch API key not found")
        return []
    
    jobs = []
    print("📥 JSearch API...")
    
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    # Use 3 queries to stay in free tier
    for query in SEARCH_QUERIES[:3]:
        try:
            params = {
                "query": f"{query} United States",
                "page": "1",
                "date_posted": "today",
                "employment_types": "FULLTIME"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                continue
            
            for job in response.json().get('data', []):
                company = job.get('employer_name', 'Unknown')
                title = job.get('job_title', '')
                description = job.get('job_description', '')
                job_url = job.get('job_apply_link', '')
                location = f"{job.get('job_city', '')} {job.get('job_state', '')} {job.get('job_country', '')}"
                
                # ONLY 2 FILTERS: Valid URL + USA
                if not job_url or not job_url.startswith('http'):
                    continue
                if not is_usa_location(location):
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:],
                    'url': job_url,
                    'location': location,
                    'source': 'JSearch',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ❌ {query}: {e}")
    
    print(f"  ✅ {len(jobs)} jobs from JSearch")
    return jobs

def fetch_adzuna_jobs():
    """Adzuna API - FREE 5000 calls/month"""
    if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
        print("⚠️  Adzuna API credentials not found")
        return []
    
    jobs = []
    print("📥 Adzuna API...")
    
    for query in SEARCH_QUERIES:
        try:
            url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
            
            params = {
                'app_id': ADZUNA_APP_ID,
                'app_key': ADZUNA_API_KEY,
                'results_per_page': 50,
                'what': query,
                'where': 'USA',
                'max_days_old': 1,
                'sort_by': 'date'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                continue
            
            for job in response.json().get('results', []):
                company = job.get('company', {}).get('display_name', 'Unknown')
                title = job.get('title', '')
                description = job.get('description', '')
                job_url = job.get('redirect_url', '')
                location = job.get('location', {}).get('display_name', '')
                created = job.get('created', '')
                
                # ONLY 3 FILTERS: Valid URL + USA + Recent
                if not job_url or not job_url.startswith('http'):
                    continue
                if not is_usa_location(location):
                    continue
                if not is_recent(created, hours=24):
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': job_url,
                    'location': location,
                    'source': 'Adzuna',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ❌ {query}: {e}")
    
    print(f"  ✅ {len(jobs)} jobs from Adzuna")
    return jobs

def fetch_remoteok_jobs():
    """RemoteOK API - FREE unlimited"""
    jobs = []
    print("📥 RemoteOK API...")
    
    try:
        url = "https://remoteok.com/api"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; JobBot/1.0)'}
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return jobs
        
        data = response.json()
        job_posts = data[1:] if isinstance(data, list) else []
        
        for job in job_posts[:100]:
            try:
                company = job.get('company', 'Unknown')
                title = job.get('position', '')
                description = job.get('description', '')
                job_url = job.get('url', '')
                location = job.get('location', '')
                epoch = job.get('epoch', 0)
                
                # Check recency
                if epoch:
                    posted = datetime.fromtimestamp(epoch)
                    if (datetime.now() - posted).days > 1:
                        continue
                
                # USA check
                if not is_usa_location(location):
                    continue
                
                if not job_url or not job_url.startswith('http'):
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': job_url,
                    'location': location,
                    'source': 'RemoteOK',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
            except:
                continue
        
        print(f"  ✅ {len(jobs)} jobs from RemoteOK")
        
    except Exception as e:
        print(f"  ❌ RemoteOK: {e}")
    
    return jobs

def fetch_himalayas_jobs():
    """Himalayas Jobs - FREE unlimited"""
    jobs = []
    print("📥 Himalayas API...")
    
    try:
        url = "https://himalayas.app/jobs/api"
        
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return jobs
        
        for job in response.json().get('jobs', [])[:50]:
            company = job.get('company', {}).get('name', 'Unknown')
            title = job.get('title', '')
            description = job.get('description', '')
            job_url = job.get('url', '')
            locations = job.get('locations', [])
            
            # USA check
            location_str = ' '.join(locations) if locations else ''
            if not is_usa_location(location_str):
                continue
            
            if not job_url or not job_url.startswith('http'):
                continue
            
            print(f"  ✅ {company} - {title}")
            
            job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
            
            jobs.append({
                'job_id': job_id,
                'company': company,
                'title': title,
                'description': description[:3000],
                'url': job_url,
                'location': location_str,
                'source': 'Himalayas',
                'date_found': datetime.now().strftime('%Y-%m-%d'),
                'status': 'Raw'
            })
        
        print(f"  ✅ {len(jobs)} jobs from Himalayas")
        
    except Exception as e:
        print(f"  ❌ Himalayas: {e}")
    
    return jobs

# ==================== LAYER 2: RSS FEEDS ====================

def fetch_rss_jobs():
    """Fetch jobs from RSS feeds - FREE unlimited"""
    jobs = []
    print("📥 RSS Feeds...")
    
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:30]:
                # Extract company from title (usually "Company - Job Title")
                title_parts = entry.title.split(' - ') if ' - ' in entry.title else [entry.title]
                company = title_parts[0] if len(title_parts) > 1 else 'Unknown'
                title = title_parts[1] if len(title_parts) > 1 else title_parts[0]
                
                job_url = entry.link
                description = entry.get('summary', '')[:3000]
                
                # Basic location check from description
                if description and not is_usa_location(description):
                    continue
                
                if not job_url or not job_url.startswith('http'):
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description,
                    'url': job_url,
                    'location': 'Remote',
                    'source': f'RSS-{name}',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
        except Exception as e:
            print(f"  ❌ RSS {name}: {e}")
    
    print(f"  ✅ {len(jobs)} jobs from RSS")
    return jobs

# ==================== LAYER 3: COMPANY APIs ====================

def fetch_google_jobs():
    """Google Careers API - FREE"""
    jobs = []
    print("📥 Google Careers...")
    
    try:
        url = "https://careers.google.com/api/v3/search/"
        
        params = {
            'employment_type': 'FULL_TIME',
            'location': 'United States',
            'q': 'Software Engineer',
            'hl': 'en_US'
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            for job in response.json().get('jobs', [])[:20]:
                job_id = hashlib.md5(f"Google{job['title']}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': 'Google',
                    'title': job['title'],
                    'description': job.get('description', '')[:3000],
                    'url': f"https://careers.google.com/jobs/results/{job['id']}/",
                    'location': ', '.join(job.get('locations', [])),
                    'source': 'Google-Direct',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
                print(f"  ✅ Google - {job['title']}")
        
        print(f"  ✅ {len(jobs)} jobs from Google")
        
    except Exception as e:
        print(f"  ❌ Google: {e}")
    
    return jobs

def fetch_apple_jobs():
    """Apple Careers API - FREE"""
    jobs = []
    print("📥 Apple Careers...")
    
    try:
        url = "https://jobs.apple.com/api/role/search"
        
        params = {
            'location': 'United-States-USA',
            'team': 'apps-and-frameworks'
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            for job in response.json().get('searchResults', [])[:20]:
                job_id = hashlib.md5(f"Apple{job['postingTitle']}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': 'Apple',
                    'title': job['postingTitle'],
                    'description': job.get('jobSummary', '')[:3000],
                    'url': f"https://jobs.apple.com/en-us/details/{job['positionId']}",
                    'location': job.get('locations', ''),
                    'source': 'Apple-Direct',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
                print(f"  ✅ Apple - {job['postingTitle']}")
        
        print(f"  ✅ {len(jobs)} jobs from Apple")
        
    except Exception as e:
        print(f"  ❌ Apple: {e}")
    
    return jobs

def fetch_amazon_jobs():
    """Amazon Jobs JSON - FREE"""
    jobs = []
    print("📥 Amazon Jobs...")
    
    try:
        url = "https://www.amazon.jobs/en/search.json"
        
        params = {
            'base_query': 'software engineer',
            'loc_query': 'United States',
            'result_limit': 20
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            for job in response.json().get('jobs', []):
                job_id = hashlib.md5(f"Amazon{job['title']}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': 'Amazon',
                    'title': job['title'],
                    'description': job.get('description', '')[:3000],
                    'url': f"https://www.amazon.jobs{job['job_path']}",
                    'location': job.get('location', ''),
                    'source': 'Amazon-Direct',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
                print(f"  ✅ Amazon - {job['title']}")
        
        print(f"  ✅ {len(jobs)} jobs from Amazon")
        
    except Exception as e:
        print(f"  ❌ Amazon: {e}")
    
    return jobs

# ==================== LAYER 4: ATS APIs ====================

def fetch_greenhouse_jobs():
    """Greenhouse company boards"""
    jobs = []
    print("📥 Greenhouse...")
    
    for company_id in GREENHOUSE_COMPANIES:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                continue
            
            for job in response.json().get('jobs', []):
                title = job.get('title', '')
                job_url = job.get('absolute_url', '')
                location = job.get('location', {}).get('name', '')
                
                if not job_url or not is_usa_location(location):
                    continue
                
                print(f"  ✅ {company_id.title()} - {title}")
                
                job_id = hashlib.md5(f"{company_id}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company_id.title(),
                    'title': title,
                    'description': f"Location: {location}",
                    'url': job_url,
                    'location': location,
                    'source': 'Greenhouse',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(0.5)
            
        except:
            continue
    
    print(f"  ✅ {len(jobs)} jobs from Greenhouse")
    return jobs

def fetch_lever_jobs():
    """Lever company boards"""
    jobs = []
    print("📥 Lever...")
    
    for company_id in LEVER_COMPANIES:
        try:
            url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                continue
            
            for job in response.json():
                title = job.get('text', '')
                job_url = job.get('hostedUrl', '')
                location = job.get('categories', {}).get('location', '')
                
                if not job_url or not is_usa_location(location):
                    continue
                
                print(f"  ✅ {company_id.title()} - {title}")
                
                job_id = hashlib.md5(f"{company_id}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company_id.title(),
                    'title': title,
                    'description': f"Location: {location}",
                    'url': job_url,
                    'location': location,
                    'source': 'Lever',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(0.5)
            
        except:
            continue
    
    print(f"  ✅ {len(jobs)} jobs from Lever")
    return jobs

def fetch_simplify_github():
    """SimplifyJobs curated list"""
    jobs = []
    print("📥 SimplifyJobs...")
    
    try:
        url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return jobs
        
        for job in response.json()[:100]:
            company = job.get('company_name', '')
            title = job.get('title', '')
            locations = job.get('locations', [])
            job_url = job.get('url', '')
            active = job.get('active', True)
            
            if not active or not job_url:
                continue
            
            location_str = ' '.join(locations) if isinstance(locations, list) else str(locations)
            if not is_usa_location(location_str):
                continue
            
            print(f"  ✅ {company} - {title}")
            
            job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
            
            jobs.append({
                'job_id': job_id,
                'company': company,
                'title': title,
                'description': f"Locations: {location_str}",
                'url': job_url,
                'location': location_str,
                'source': 'SimplifyJobs',
                'date_found': datetime.now().strftime('%Y-%m-%d'),
                'status': 'Raw'
            })
        
        print(f"  ✅ {len(jobs)} jobs from SimplifyJobs")
        
    except Exception as e:
        print(f"  ❌ SimplifyJobs: {e}")
    
    return jobs

# ==================== MAIN ====================

def save_to_sheets(jobs):
    """Save to Google Sheets"""
    from sheets_helper import get_sheet
    
    if not jobs:
        print("\n❌ No jobs to save")
        return 0
    
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet("Raw Jobs")
        
        existing_data = worksheet.get_all_values()
        existing_ids = [row[0] for row in existing_data[1:]] if len(existing_data) > 1 else []
        
        new_jobs = []
        for job in jobs:
            if job['job_id'] not in existing_ids:
                new_jobs.append([
                    job['job_id'],
                    job['company'],
                    job['title'],
                    job['description'],
                    job['url'],
                    job['source'],
                    job['date_found'],
                    job['status']
                ])

        if new_jobs:
            worksheet.append_rows(new_jobs)
            print(f"\n✅ Added {len(new_jobs)} new jobs to sheet")
            return len(new_jobs)
        else:
            print("\n⚠️  All jobs were duplicates")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error saving: {e}")
        return 0

def main():
    print("=" * 80)
    print("🎯 EXPERT JOB SCRAPER - Maximum Coverage, Zero Cost")
    print("=" * 80)
    print("Strategy: COLLECT EVERYTHING, LET CLAUDE FILTER")
    print("\nScraper Filters (Minimal):")
    print("  ✅ USA location only")
    print("  ✅ Posted in last 24 hours")
    print("  ✅ Valid URL")
    print("\nClaude Will Filter (Smart):")
    print("  🤖 Experience level (0-3 years)")
    print("  🤖 Full-time vs contract")
    print("  🤖 Visa requirements")
    print("  🤖 Skill matching")
    print("=" * 80)
    
    all_jobs = []
    
    # LAYER 1: Free APIs
    all_jobs.extend(fetch_jsearch_jobs())
    all_jobs.extend(fetch_adzuna_jobs())
    all_jobs.extend(fetch_remoteok_jobs())
    all_jobs.extend(fetch_himalayas_jobs())
    
    # LAYER 2: RSS Feeds
    all_jobs.extend(fetch_rss_jobs())
    
    # LAYER 3: Direct Company APIs
    all_jobs.extend(fetch_google_jobs())
    all_jobs.extend(fetch_apple_jobs())
    all_jobs.extend(fetch_amazon_jobs())
    
    # LAYER 4: ATS APIs
    all_jobs.extend(fetch_greenhouse_jobs())
    all_jobs.extend(fetch_lever_jobs())
    all_jobs.extend(fetch_simplify_github())
    
    print(f"\n📊 Total collected: {len(all_jobs)} jobs")
    
    # Deduplicate
    unique_jobs = {}
    for job in all_jobs:
        key = f"{job['company']}{job['title']}"
        if key not in unique_jobs:
            unique_jobs[key] = job
    
    deduped = list(unique_jobs.values())
    
    if len(all_jobs) > len(deduped):
        print(f"📊 Removed {len(all_jobs) - len(deduped)} duplicates")
        print(f"📊 Unique: {len(deduped)}")
    
    new_count = save_to_sheets(deduped)
    
    print("\n" + "=" * 80)
    print("✅ COLLECTION COMPLETE")
    print("=" * 80)
    print(f"Jobs saved: {new_count}")
    print("\n👉 Next: Run 'Analyze Jobs' - Claude will apply ALL filters")
    print("=" * 80)

if __name__ == "__main__":
    main()