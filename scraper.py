# scraper.py - PRODUCTION VERSION - FIXED

import requests
import os
from datetime import datetime
import hashlib
import time

# ==================== CONFIGURATION ====================

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")

# UPDATED: Broader queries (let Claude filter)
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
    'scale', 'discord', 'airtable', 'brex', 'openai'
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
    'lead engineer'  # But NOT "Software Engineer, Lead" (title order matters)
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
    
    # Check if senior keyword is at START of title (more strict)
    for keyword in SENIOR_KEYWORDS:
        # "Staff Engineer" = reject
        # "Engineering Staff" = don't reject
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
    
    # Hard rejects (definitely not full-time)
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
    
    # Pattern: "X+ years" or "X years" where X >= 4
    import re
    
    # Find patterns like "5+ years", "4 years", "6-8 years"
    patterns = [
        r'(\d+)\+?\s*years',  # "5+ years" or "5 years"
        r'(\d+)\s*to\s*(\d+)\s*years',  # "5 to 7 years"
        r'(\d+)\s*-\s*(\d+)\s*years',  # "5-7 years"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            # Handle different match types
            if isinstance(match, tuple):
                # Range like "5-7 years"
                years = [int(m) for m in match if m.isdigit()]
                min_years = min(years) if years else 0
            else:
                # Single number like "5+ years"
                min_years = int(match) if match.isdigit() else 0
            
            # Reject if minimum required is 4+
            if min_years >= 4:
                return True, f"{min_years}+ years required"
    
    # Also check for explicit senior language
    senior_exp_phrases = [
        '5+ years',
        '6+ years',
        '7+ years',
        '8+ years',
        '10+ years',
        'minimum 4 years',
        'minimum 5 years',
        'at least 4 years',
        'at least 5 years',
        'extensive experience',
        'significant experience',
        'seasoned engineer',
        'veteran engineer'
    ]
    
    for phrase in senior_exp_phrases:
        if phrase in text_lower:
            return True, phrase
    
    return False, None
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
                "employment_types": "FULLTIME"
                # REMOVED: job_requirements filter (let Claude decide)
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"  ⚠️ JSearch returned {response.status_code} for '{query}'")
                continue
            
            data = response.json()
            
            for job in data.get('data', []):
                company = job.get('employer_name', 'Unknown')
                title = job.get('job_title', '')
                description = job.get('job_description', '')
                job_url = job.get('job_apply_link', '')
                location = job.get('job_city', '') + ', ' + job.get('job_state', '')
                
                # Skip if no URL
                if not job_url or not job_url.startswith('http'):
                    continue
                
                # STRICT USA check
                full_location = location + ' ' + job.get('job_country', '')
                if not is_usa_only(full_location):
                    continue
                
                # Government check
                if is_government(company):
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue
                
                is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
                if is_not_ft:
                    print(f"  ⛔ {company} - not full-time: {reason}")
                    continue
                # Hard visa blockers
                has_blocker, blocker = has_hard_blocker(title + ' ' + description)
                if has_blocker:
                    print(f"  ⛔ {company} - {blocker}")
                    continue
                

                too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
                if too_much_exp:
                    print(f"  ⛔ {company} - {reason}")
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
                company = job.get('employer_name', 'Unknown')
                description = job.get('job_description', '')
                
                # STRICT USA check
                if not is_usa_only(location):
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue

                is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
                if is_not_ft:
                    print(f"  ⛔ {company} - not full-time: {reason}")
                    continue
                

                too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
                if too_much_exp:
                    print(f"  ⛔ {company} - {reason}")
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
                company = job.get('employer_name', 'Unknown')
                description = job.get('job_description', '')
                
                # STRICT USA check
                if not is_usa_only(location):
                    continue
                
                # Clearly senior check
                if is_clearly_senior(title):
                    continue
                is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
                if is_not_ft:
                    print(f"  ⛔ {company} - not full-time: {reason}")
                    continue

                too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
                if too_much_exp:
                    print(f"  ⛔ {company} - {reason}")
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
            description = job.get('job_description', '')
            
            if not active or not job_url:
                continue
            
            # STRICT USA check
            location_str = ' '.join(locations) if isinstance(locations, list) else str(locations)
            if not is_usa_only(location_str):
                continue
            
            # Government check
            if is_government(company):
                continue
            
            is_not_ft, reason = is_obviously_not_fulltime(title + ' ' + description)
            if is_not_ft:
                print(f"  ⛔ {company} - not full-time: {reason}")
                continue
            print(f"  ✅ {company} - {title}")
            too_much_exp, reason = requires_too_much_experience(title + ' ' + description)
            if too_much_exp:
                print(f"  ⛔ {company} - {reason}")
                continue
            
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
    print("🎯 NEW GRAD JOB HUNTER - Fixed Edition")
    print("=" * 80)
    print("Sources:")
    print("  • JSearch API (Google Jobs, LinkedIn, ZipRecruiter)")
    print("  • Greenhouse (Top tech companies)")
    print("  • Lever (Startups)")
    print("  • SimplifyJobs (Curated new grad list)")
    print("\nFiltering:")
    print("  • STRICT USA-only (no Canada, no ambiguous 'Remote')")
    print("  • Minimal seniority filter (only obvious senior roles)")
    print("  • Hard visa blockers (citizenship, clearance, no sponsorship)")
    print("  • Claude handles employment type & skill matching")
    print("=" * 80)
    
    all_jobs = []
    
    # Fetch from all sources
    all_jobs.extend(fetch_jsearch_jobs())
    all_jobs.extend(fetch_greenhouse_jobs())
    all_jobs.extend(fetch_lever_jobs())
    all_jobs.extend(fetch_simplify_github())
    
    print(f"\n📊 Total jobs collected: {len(all_jobs)}")
    
    # Save
    new_count = save_to_sheets(all_jobs)
    
    print("\n" + "=" * 80)
    print("✅ SCRAPING COMPLETE")
    print("=" * 80)
    print(f"Jobs added: {new_count}")
    print("\n👉 Check Google Sheet 'Raw Jobs' tab")
    print("👉 Run 'Analyze Jobs' for Claude matching")
    print("=" * 80)

if __name__ == "__main__":
    main()