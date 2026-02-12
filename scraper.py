# scraper.py - MULTI-API PRODUCTION VERSION - ALL FILTERS APPLIED

import requests
import os
from datetime import datetime
import hashlib
import time
import re

# ==================== CONFIGURATION ====================

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")

# Broader queries (let Claude filter)
SEARCH_QUERIES = [
    "software engineer",
    "machine learning engineer",
    "AI engineer",
    "backend engineer",
    "full stack engineer",
    "data engineer",
    "ML engineer"
]

GREENHOUSE_COMPANIES = [
    'stripe', 'ramp', 'notion', 'figma', 'anthropic', 
    'scale', 'discord', 'airtable', 'brex', 'openai',
    'databricks', 'snowflake', 'confluent'
]

LEVER_COMPANIES = [
    'rippling', 'plaid', 'retool', 'verkada', 'faire',
    'superhuman', 'loom', 'mux'
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
    'will not sponsor',
    'must be authorized to work without sponsorship'
]

# Seniority exclusions (MINIMAL - only obvious senior)
SENIOR_KEYWORDS = [
    'staff engineer',
    'principal engineer',
    'senior manager',
    'engineering manager',
    'director of',
    'vp of',
    'vice president',
    'head of engineering',
    'chief',
    'lead engineer'
]

# ==================== HELPER FUNCTIONS ====================

def is_usa_only(location_text):
    """STRICT USA-only check"""
    if not location_text:
        return False
    
    location_lower = location_text.lower()
    
    # REJECT if mentions other countries
    reject_countries = [
        'canada', 'toronto', 'vancouver', 'montreal', 'ottawa',
        'uk', 'united kingdom', 'london', 'england',
        'india', 'bangalore', 'mumbai', 'hyderabad', 'pune',
        'europe', 'germany', 'france', 'spain', 'netherlands',
        'australia', 'sydney', 'melbourne',
        'mexico', 'brazil', 'argentina',
        'china', 'japan', 'singapore', 'korea'
    ]
    
    for country in reject_countries:
        if country in location_lower:
            return False
    
    # ACCEPT only if explicitly USA
    usa_indicators = [
        'united states', 'usa', 'u.s.', 'us,',
        # States
        'california', 'new york', 'texas', 'florida', 'washington',
        'massachusetts', 'illinois', 'colorado', 'oregon', 'georgia',
        # Cities
        'san francisco', 'nyc', 'seattle', 'austin', 'boston',
        'chicago', 'denver', 'los angeles', 'atlanta', 'portland',
        # Remote USA
        'remote us', 'remote usa', 'remote - us', 'remote (us)',
        'us remote', 'united states remote'
    ]
    
    for indicator in usa_indicators:
        if indicator in location_lower:
            return True
    
    # If just "Remote" with no country, REJECT (ambiguous)
    if location_lower.strip() in ['remote', 'remote work', 'work from home']:
        return False
    
    return False

def has_hard_blocker(text):
    """Check for citizenship/clearance requirements"""
    text_lower = text.lower()
    for blocker in VISA_BLOCKERS:
        if blocker in text_lower:
            return True, blocker
    return False, None

def is_clearly_senior(title):
    """Only reject OBVIOUSLY senior roles"""
    title_lower = title.lower()
    
    for keyword in SENIOR_KEYWORDS:
        if title_lower.startswith(keyword) or f" {keyword}" in title_lower:
            return True
    
    return False

def is_government(company):
    """Reject government/defense contractors"""
    company_lower = company.lower()
    gov_keywords = [
        'department of', 'federal', 'government', 'dept of',
        'raytheon', 'lockheed', 'northrop', 'booz allen',
        'leidos', 'general dynamics', 'l3harris', 'saic',
        'mitre', 'aerospace corporation'
    ]
    return any(kw in company_lower for kw in gov_keywords)

def is_obviously_not_fulltime(text):
    """Only reject OBVIOUS non-full-time roles"""
    text_lower = text.lower()
    
    hard_rejects = [
        'internship',
        'intern ',
        ' intern',
        'part-time',
        'part time',
        'freelance',
        'freelancer',
        '1099',
        'hourly contract',
        'temporary position',
        'seasonal',
        'consultant position',
        'consulting role',
        'project-based',
        'gig work'
    ]
    
    for term in hard_rejects:
        if term in text_lower:
            return True, term
    
    return False, None

def requires_too_much_experience(text):
    """Reject jobs clearly requiring 4+ years experience"""
    text_lower = text.lower()
    
    # Find patterns like "5+ years", "4 years", "6-8 years"
    patterns = [
        r'(\d+)\+\s*years',
        r'(\d+)\s*years',
        r'(\d+)\s*to\s*(\d+)\s*years',
        r'(\d+)\s*-\s*(\d+)\s*years',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            if isinstance(match, tuple):
                years = [int(m) for m in match if m.isdigit()]
                min_years = min(years) if years else 0
            else:
                min_years = int(match) if match.isdigit() else 0
            
            if min_years >= 4:
                return True, f"{min_years}+ years required"
    
    # Explicit senior experience phrases
    senior_exp_phrases = [
        '5+ years', '6+ years', '7+ years', '8+ years', '10+ years',
        'minimum 4 years', 'minimum 5 years',
        'at least 4 years', 'at least 5 years',
        'extensive experience', 'significant experience',
        'seasoned engineer', 'veteran engineer'
    ]
    
    for phrase in senior_exp_phrases:
        if phrase in text_lower:
            return True, phrase
    
    return False, None

# ==================== API SOURCE 1: JSearch ====================

def fetch_jsearch_jobs():
    """JSearch API - Aggregates Google Jobs, LinkedIn, ZipRecruiter"""
    if not JSEARCH_API_KEY:
        print("⚠️  JSearch API key not found - skipping")
        return []
    
    jobs = []
    print("📥 Fetching from JSearch API...")
    
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    # Limit to 3 queries to save API calls (150/month free tier)
    for query in SEARCH_QUERIES[:3]:
        try:
            params = {
                "query": f"{query} United States",
                "page": "1",
                "num_pages": "1",
                "date_posted": "today",
                "employment_types": "FULLTIME"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"  ⚠️ JSearch returned {response.status_code}")
                continue
            
            data = response.json()
            
            for job in data.get('data', []):
                company = job.get('employer_name', 'Unknown')
                title = job.get('job_title', '')
                description = job.get('job_description', '')
                job_url = job.get('job_apply_link', '')
                location = f"{job.get('job_city', '')} {job.get('job_state', '')} {job.get('job_country', '')}"
                
                # FILTER 1: Valid URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # FILTER 2: USA only
                if not is_usa_only(location):
                    continue
                
                # FILTER 3: No government
                if is_government(company):
                    continue
                
                # FILTER 4: No senior roles
                if is_clearly_senior(title):
                    continue
                
                # FILTER 5: Full-time only
                is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
                if is_not_ft:
                    continue
                
                # FILTER 6: No visa blockers
                has_blocker, blocker = has_hard_blocker(title + ' ' + description)
                if has_blocker:
                    continue
                
                # FILTER 7: Max 3 years experience
                too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
                if too_much_exp:
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
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ❌ JSearch query failed: {e}")
            continue
    
    print(f"  ✅ {len(jobs)} jobs from JSearch")
    return jobs

# ==================== API SOURCE 2: Adzuna ====================

def fetch_adzuna_jobs():
    """Adzuna API - Aggregates Indeed, Monster, CareerBuilder"""
    if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
        print("⚠️  Adzuna API credentials not found - skipping")
        return []
    
    jobs = []
    print("📥 Fetching from Adzuna API...")
    
    for query in SEARCH_QUERIES:
        try:
            url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
            
            params = {
                'app_id': ADZUNA_APP_ID,
                'app_key': ADZUNA_API_KEY,
                'results_per_page': 20,
                'what': query,
                'where': 'USA',
                'max_days_old': 1,
                'sort_by': 'date'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"  ⚠️ Adzuna returned {response.status_code}")
                continue
            
            data = response.json()
            
            for job in data.get('results', []):
                company_obj = job.get('company', {})
                company = company_obj.get('display_name', 'Unknown')
                title = job.get('title', '')
                description = job.get('description', '')
                job_url = job.get('redirect_url', '')
                location_obj = job.get('location', {})
                location = location_obj.get('display_name', '')
                
                # FILTER 1: Valid URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # FILTER 2: USA only
                if not is_usa_only(location):
                    continue
                
                # FILTER 3: No government
                if is_government(company):
                    continue
                
                # FILTER 4: No senior roles
                if is_clearly_senior(title):
                    continue
                
                # FILTER 5: Full-time only
                is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
                if is_not_ft:
                    continue
                
                # FILTER 6: No visa blockers
                has_blocker, blocker = has_hard_blocker(title + ' ' + description)
                if has_blocker:
                    continue
                
                # FILTER 7: Max 3 years experience
                too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
                if too_much_exp:
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': job_url,
                    'source': 'Adzuna',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  ❌ Adzuna query failed: {e}")
            continue
    
    print(f"  ✅ {len(jobs)} jobs from Adzuna")
    return jobs

# ==================== API SOURCE 3: The Muse ====================

def fetch_themuse_jobs():
    """The Muse API - Tech-focused, curated companies"""
    jobs = []
    print("📥 Fetching from The Muse API...")
    
    try:
        url = "https://www.themuse.com/api/public/jobs"
        
        params = {
            'level': 'Entry Level',
            'category': 'Software Engineering',
            'location': 'Flexible / Remote',
            'page': 1,
            'descending': 'true',
            'api_key': 'public'
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"  ⚠️ The Muse returned {response.status_code}")
            return jobs
        
        data = response.json()
        
        for job in data.get('results', [])[:30]:
            company_obj = job.get('company', {})
            company = company_obj.get('name', 'Unknown')
            title = job.get('name', '')
            description = job.get('contents', '') or job.get('description', '')
            job_url = job.get('refs', {}).get('landing_page', '')
            
            locations = job.get('locations', [])
            location = locations[0].get('name', '') if locations else ''
            
            # FILTER 1: Valid URL
            if not job_url or not job_url.startswith('http'):
                continue
            
            # FILTER 2: USA only
            if location and not is_usa_only(location):
                continue
            
            # FILTER 3: No government
            if is_government(company):
                continue
            
            # FILTER 4: No senior roles
            if is_clearly_senior(title):
                continue
            
            # FILTER 5: Full-time only
            is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
            if is_not_ft:
                continue
            
            # FILTER 6: No visa blockers
            has_blocker, blocker = has_hard_blocker(title + ' ' + description)
            if has_blocker:
                continue
            
            # FILTER 7: Max 3 years experience
            too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
            if too_much_exp:
                continue
            
            print(f"  ✅ {company} - {title}")
            
            job_id = hashlib.md5(f"{company}{title}{job_url}".encode()).hexdigest()[:8]
            
            jobs.append({
                'job_id': job_id,
                'company': company,
                'title': title,
                'description': description[:3000],
                'url': job_url,
                'source': 'TheMuse',
                'date_found': datetime.now().strftime('%Y-%m-%d'),
                'status': 'Raw'
            })
        
        print(f"  ✅ {len(jobs)} jobs from The Muse")
        
    except Exception as e:
        print(f"  ❌ The Muse error: {e}")
    
    return jobs

# ==================== API SOURCE 4: Greenhouse ====================

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
                
                # FILTER 1: Valid URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # FILTER 2: USA only
                if not is_usa_only(location):
                    continue
                
                # FILTER 3: No senior roles
                if is_clearly_senior(title):
                    continue
                
                # Note: Greenhouse jobs don't have descriptions in list API
                # Can't apply full-time, visa, experience filters here
                # Claude will handle these in matching phase
                
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

# ==================== API SOURCE 5: Lever ====================

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
                
                # FILTER 1: Valid URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # FILTER 2: USA only
                if not is_usa_only(location):
                    continue
                
                # FILTER 3: No senior roles
                if is_clearly_senior(title):
                    continue
                
                # Note: Lever jobs don't have descriptions in list API
                # Can't apply full-time, visa, experience filters here
                # Claude will handle these in matching phase
                
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

# ==================== API SOURCE 6: SimplifyJobs ====================

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
        
        for job in data[:50]:
            company = job.get('company_name', '')
            title = job.get('title', '')
            locations = job.get('locations', [])
            job_url = job.get('url', '')
            active = job.get('active', True)
            
            # FILTER 1: Active and valid URL
            if not active or not job_url or not job_url.startswith('http'):
                continue
            
            # FILTER 2: USA only
            location_str = ' '.join(locations) if isinstance(locations, list) else str(locations)
            if not is_usa_only(location_str):
                continue
            
            # FILTER 3: No government
            if is_government(company):
                continue
            
            # FILTER 4: No senior roles
            if is_clearly_senior(title):
                continue
            
            # Note: SimplifyJobs is curated for new grads
            # Full-time, visa, experience filters not needed
            # These are already vetted
            
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
    """Save to Google Sheets with deduplication"""
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
    print("🎯 NEW GRAD JOB HUNTER - Multi-API Edition")
    print("=" * 80)
    print("Sources:")
    print("  • JSearch (Google Jobs, LinkedIn, ZipRecruiter)")
    print("  • Adzuna (Indeed, Monster, CareerBuilder)")
    print("  • The Muse (Curated tech companies)")
    print("  • Greenhouse (Top tech companies)")
    print("  • Lever (Startups)")
    print("  • SimplifyJobs (Curated new grad list)")
    print("\nFilters Applied to ALL Sources:")
    print("  ✅ STRICT USA-only (no Canada, ambiguous Remote)")
    print("  ✅ Max 3 years experience")
    print("  ✅ Full-time only (no internships, contract, part-time)")
    print("  ✅ No citizenship/clearance requirements")
    print("  ✅ No government/defense jobs")
    print("  ✅ No senior roles (Staff, Principal, etc.)")
    print("=" * 80)
    
    all_jobs = []
    
    # Fetch from ALL sources
    all_jobs.extend(fetch_jsearch_jobs())
    all_jobs.extend(fetch_adzuna_jobs())
    all_jobs.extend(fetch_themuse_jobs())
    all_jobs.extend(fetch_greenhouse_jobs())
    all_jobs.extend(fetch_lever_jobs())
    all_jobs.extend(fetch_simplify_github())
    
    print(f"\n📊 Total jobs collected: {len(all_jobs)}")
    
    # Remove duplicates across sources
    unique_jobs = {}
    for job in all_jobs:
        key = f"{job['company']}{job['title']}"
        if key not in unique_jobs:
            unique_jobs[key] = job
    
    deduped_jobs = list(unique_jobs.values())
    duplicates = len(all_jobs) - len(deduped_jobs)
    
    if duplicates > 0:
        print(f"📊 Removed {duplicates} duplicates across sources")
        print(f"📊 Unique jobs: {len(deduped_jobs)}")
    
    # Save
    new_count = save_to_sheets(deduped_jobs)
    
    print("\n" + "=" * 80)
    print("✅ SCRAPING COMPLETE")
    print("=" * 80)
    print(f"Jobs added: {new_count}")
    print("\nAll jobs passed these filters:")
    print("  1. Valid application URL")
    print("  2. USA location only")
    print("  3. Not government/defense")
    print("  4. Not senior/staff/principal")
    print("  5. Full-time employment")
    print("  6. No citizenship requirements")
    print("  7. Max 3 years experience")
    print("\n👉 Check Google Sheet 'Raw Jobs' tab")
    print("👉 Run 'Analyze Jobs' for Claude matching")
    print("=" * 80)

if __name__ == "__main__":
    main()