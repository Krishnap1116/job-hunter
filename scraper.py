# scraper.py - PRODUCTION VERSION

import requests
import os
from datetime import datetime
import hashlib

# ==================== CONFIGURATION ====================

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")

SEARCH_QUERIES = [
    "software engineer new grad",
    "machine learning engineer entry level",
    "AI engineer junior",
    "backend engineer new graduate",
    "full stack engineer entry level"
]

GREENHOUSE_COMPANIES = [
    'stripe', 'ramp', 'notion', 'figma', 'anthropic', 
    'scale', 'discord', 'airtable', 'brex'
]

LEVER_COMPANIES = [
    'rippling', 'plaid', 'retool', 'verkada', 'faire'
]

# Hard blockers (reject during scraping)
VISA_BLOCKERS = [
    'us citizen only',
    'u.s. citizen only',
    'citizenship required',
    'security clearance required',
    'active clearance',
    'no visa sponsorship',
    'cannot sponsor',
    'will not sponsor'
]

# Seniority exclusions (minimal filtering)
SENIOR_KEYWORDS = [
    'staff engineer',
    'principal engineer',
    'senior manager',
    'director of',
    'vp of',
    'vice president',
    'head of engineering',
    'chief'
]

# ==================== HELPER FUNCTIONS ====================

def has_hard_blocker(text):
    """Check for citizenship/clearance requirements"""
    text_lower = text.lower()
    for blocker in VISA_BLOCKERS:
        if blocker in text_lower:
            return True, blocker
    return False, None

def is_clearly_senior(title):
    """Only reject obviously senior roles"""
    title_lower = title.lower()
    return any(kw in title_lower for kw in SENIOR_KEYWORDS)

def is_government(company):
    """Reject government/defense contractors"""
    company_lower = company.lower()
    gov_keywords = [
        'department of', 'federal', 'government',
        'raytheon', 'lockheed', 'northrop', 'booz allen',
        'leidos', 'general dynamics'
    ]
    return any(kw in company_lower for kw in gov_keywords)

# ==================== JOB SOURCES ====================

def fetch_jsearch_jobs():
    """JSearch API - Aggregates Google Jobs, LinkedIn, ZipRecruiter"""
    if not JSEARCH_API_KEY:
        print("⚠️  JSearch API key not found")
        return []
    
    jobs = []
    
    print("📥 Fetching from JSearch API...")
    
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    for query in SEARCH_QUERIES:
        try:
            params = {
                "query": f"{query} United States",
                "page": "1",
                "num_pages": "1",
                "date_posted": "today",
                "employment_types": "FULLTIME",
                "job_requirements": "under_3_years_experience"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            
            for job in data.get('data', []):
                company = job.get('employer_name', 'Unknown')
                title = job.get('job_title', '')
                description = job.get('job_description', '')
                job_url = job.get('job_apply_link', '')
                
                # Skip if no URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # Government check
                if is_government(company):
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue
                
                # Hard visa blockers
                has_blocker, blocker = has_hard_blocker(title + ' ' + description)
                if has_blocker:
                    print(f"  ⛔ {company} - {blocker}")
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': job_url,
                    'source': 'JSearch',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  ❌ Query '{query}' failed: {e}")
            continue
    
    print(f"  ✅ {len(jobs)} jobs from JSearch")
    return jobs

def fetch_greenhouse_jobs():
    """Greenhouse company boards"""
    jobs = []
    
    print("📥 Fetching from Greenhouse...")
    
    for company_id in GREENHOUSE_COMPANIES:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            
            for job in data.get('jobs', []):
                title = job.get('title', '')
                job_url = job.get('absolute_url', '')
                location = job.get('location', {}).get('name', '')
                
                # USA check
                if location and 'United States' not in location and 'Remote' not in location:
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue
                
                print(f"  ✅ {company_id.title()} - {title}")
                
                job_id = hashlib.md5(f"{company_id}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company_id.title(),
                    'title': title,
                    'description': f"Location: {location}",
                    'url': job_url,
                    'source': 'Greenhouse',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(0.5)
            
        except Exception as e:
            continue
    
    print(f"  ✅ {len(jobs)} jobs from Greenhouse")
    return jobs

def fetch_lever_jobs():
    """Lever company boards"""
    jobs = []
    
    print("📥 Fetching from Lever...")
    
    for company_id in LEVER_COMPANIES:
        try:
            url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                continue
            
            company_jobs = response.json()
            
            for job in company_jobs:
                title = job.get('text', '')
                job_url = job.get('hostedUrl', '')
                location = job.get('categories', {}).get('location', '')
                
                # USA check
                if location and 'United States' not in location and 'Remote' not in location:
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue
                
                print(f"  ✅ {company_id.title()} - {title}")
                
                job_id = hashlib.md5(f"{company_id}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company_id.title(),
                    'title': title,
                    'description': f"Location: {location}",
                    'url': job_url,
                    'source': 'Lever',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(0.5)
            
        except Exception as e:
            continue
    
    print(f"  ✅ {len(jobs)} jobs from Lever")
    return jobs

def fetch_simplify_github():
    """SimplifyJobs curated list"""
    jobs = []
    
    print("📥 Fetching from SimplifyJobs GitHub...")
    
    try:
        url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return jobs
        
        data = response.json()
        
        for job in data[:50]:  # Limit to 50 most recent
            company = job.get('company_name', '')
            title = job.get('title', '')
            locations = job.get('locations', [])
            job_url = job.get('url', '')
            active = job.get('active', True)
            
            if not active or not job_url:
                continue
            
            # USA check
            location_str = ' '.join(locations) if isinstance(locations, list) else str(locations)
            if 'United States' not in location_str and 'Remote' not in location_str:
                continue
            
            # Government check
            if is_government(company):
                continue
            
            print(f"  ✅ {company} - {title}")
            
            job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
            
            jobs.append({
                'job_id': job_id,
                'company': company,
                'title': title,
                'description': f"Locations: {location_str}\nCurated by SimplifyJobs",
                'url': job_url,
                'source': 'SimplifyJobs',
                'date_found': datetime.now().strftime('%Y-%m-%d'),
                'status': 'Raw'
            })
        
        print(f"  ✅ {len(jobs)} jobs from SimplifyJobs")
        
    except Exception as e:
        print(f"  ❌ SimplifyJobs error: {e}")
    
    return jobs

# ==================== MAIN ====================

def save_to_sheets(jobs):
    """Save to Google Sheets - NO URL VALIDATION"""
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
    print("🎯 NEW GRAD JOB HUNTER - Production Edition")
    print("=" * 80)
    print("Sources:")
    print("  • JSearch API (Google Jobs, LinkedIn, ZipRecruiter)")
    print("  • Greenhouse (Top tech companies)")
    print("  • Lever (Startups)")
    print("  • SimplifyJobs (Curated new grad list)")
    print("\nFiltering:")
    print("  • Minimal seniority filter (only obviously senior roles)")
    print("  • Hard visa blockers only (citizenship, clearance, no sponsorship)")
    print("  • No URL validation (trusted sources)")
    print("  • Claude handles precision filtering")
    print("=" * 80)
    
    all_jobs = []
    
    # Fetch from all sources
    all_jobs.extend(fetch_jsearch_jobs())
    all_jobs.extend(fetch_greenhouse_jobs())
    all_jobs.extend(fetch_lever_jobs())
    all_jobs.extend(fetch_simplify_github())
    
    print(f"\n📊 Total jobs collected: {len(all_jobs)}")
    
    # Save (no URL validation)
    new_count = save_to_sheets(all_jobs)
    
    print("\n" + "=" * 80)
    print("✅ SCRAPING COMPLETE")
    print("=" * 80)
    print(f"Jobs added: {new_count}")
    print("\n👉 Check Google Sheet 'Raw Jobs' tab")
    print("👉 Run 'Analyze Jobs' for Claude matching")
    print("=" * 80)

if __name__ == "__main__":
    import time
    main()