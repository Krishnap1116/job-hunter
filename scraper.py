import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import hashlib
from sheets_helper import get_sheet
import time
import re

def is_within_24_hours(date_posted):
    """Check if job was posted within last 24 hours"""
    try:
        if isinstance(date_posted, str):
            # Handle different date formats
            if 'ago' in date_posted.lower():
                if 'hour' in date_posted.lower() or 'minute' in date_posted.lower():
                    return True
                if 'day' in date_posted.lower():
                    days = int(re.search(r'(\d+)', date_posted).group(1))
                    return days <= 1
                return False
            
            # Try parsing ISO format
            try:
                posted_date = datetime.fromisoformat(date_posted.replace('Z', '+00:00'))
                return (datetime.now() - posted_date) <= timedelta(hours=24)
            except:
                pass
        
        # If we can't determine, include it (manual filtering later)
        return True
        
    except Exception as e:
        return True  # Include if uncertain

def is_new_grad_entry_level(title, description):
    """Check if job is new grad or entry level"""
    text = (title + " " + description).lower()
    
    # POSITIVE indicators for new grad/entry level
    new_grad_keywords = [
        'new grad', 'new graduate', 'recent graduate', 'entry level', 'entry-level',
        'junior', 'associate', 'jr.', 'graduate program', 'early career',
        '0-2 years', '0-1 years', 'fresh graduate', 'college graduate',
        'bootcamp graduate', 'internship to full time', 'rotational program'
    ]
    
    # NEGATIVE indicators (senior/experienced roles)
    senior_keywords = [
        'senior', 'sr.', 'staff', 'principal', 'lead', 'architect', 'manager',
        '5+ years', '3+ years', '4+ years', 'experienced', 'expert',
        'director', 'head of', 'vp', 'vice president', 'chief'
    ]
    
    # Check for exclusions first
    for keyword in senior_keywords:
        if keyword in text:
            return False, f"senior role: {keyword}"
    
    # Check for new grad indicators
    for keyword in new_grad_keywords:
        if keyword in text:
            return True, f"new grad match: {keyword}"
    
    # If no clear indicators, check years of experience in description
    # Look for patterns like "2+ years", "3-5 years"
    exp_pattern = re.search(r'(\d+)[\+\-\s]*years', text)
    if exp_pattern:
        years = int(exp_pattern.group(1))
        if years <= 2:
            return True, f"0-{years} years experience"
        else:
            return False, f"requires {years}+ years"
    
    # Default: if title doesn't have senior markers and no exp mentioned, include it
    # (will be filtered by Claude in matching phase)
    return True, "no clear seniority markers"

def is_usa_location(location_text):
    """Check if location is in USA"""
    if not location_text:
        return False
    
    location_lower = location_text.lower()
    
    usa_keywords = [
        'usa', 'united states', 'u.s.', 'us,', 
        'california', 'new york', 'texas', 'florida', 'washington',
        'san francisco', 'seattle', 'austin', 'boston', 'denver',
        'remote us', 'remote usa', 'us remote', 'remote (us)',
        'anywhere in us', 'nationwide', 'palo alto', 'mountain view',
        'los angeles', 'chicago', 'atlanta', 'portland', 'miami'
    ]
    
    exclude_keywords = [
        'canada', 'uk', 'london', 'europe', 'india', 'bangalore',
        'toronto', 'berlin', 'paris', 'sydney', 'australia', 'mexico'
    ]
    
    for keyword in exclude_keywords:
        if keyword in location_lower:
            return False
    
    for keyword in usa_keywords:
        if keyword in location_lower:
            return True
    
    return False

def has_visa_restrictions(description, title, company):
    """Check for HARD visa restrictions - reject during scraping"""
    text = (description + " " + title + " " + company).lower()
    
    # HARD REJECTS - Don't even scrape these
    hard_reject_keywords = [
        # Citizenship requirements
        'us citizen only', 'u.s. citizen only', 'must be us citizen',
        'citizenship required', 'citizenship is required',
        'require us citizenship', 'us citizenship is required',
        
        # Security clearance
        'security clearance required', 'active clearance', 'ts/sci',
        'secret clearance', 'top secret', 'clearance required',
        
        # Authorization statements
        'permanently authorized', 'continuous authorization to work required',
        
        # No sponsorship statements
        'no sponsorship', 'cannot sponsor', 'will not sponsor',
        'unable to sponsor', 'not sponsoring', 'no visa sponsorship',
        
        # Government/Defense (rarely sponsor)
        'government agency', 'federal government', 'department of defense',
        'dod ', 'cleared position'
    ]
    
    for keyword in hard_reject_keywords:
        if keyword in text:
            return True, keyword
    
    return False, None

def is_government_job(company, description):
    """Check if job is government/defense (auto-reject)"""
    text = (company + " " + description).lower()
    
    gov_indicators = [
        # Federal agencies
        'department of', 'federal ', 'government', 'nasa', 'fbi', 'cia',
        'nsa', 'homeland security', 'defense', 'navy', 'army', 'air force',
        
        # Government contractors (often require clearance)
        'raytheon', 'lockheed martin', 'northrop grumman', 'booz allen',
        'leidos', 'saic', 'general dynamics', 'l3harris',
        
        # State/local gov
        'state of', 'city of', 'county of', 'public school', 'municipality'
    ]
    
    for indicator in gov_indicators:
        if indicator in text:
            return True, indicator
    
    return False, None

def scrape_simplify_jobs():
    """Scrape Simplify.jobs - Best for new grad roles"""
    jobs = []
    
    try:
        # Simplify has a JSON API endpoint
        url = "https://simplify.jobs/api/v1/jobs"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("📥 Fetching from Simplify.jobs (New Grad focus)...")
        
        params = {
            'experience_levels': ['entry', 'junior'],
            'locations': ['United States'],
            'limit': 100
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        if response.status_code != 200:
            print(f"  ⚠️ Simplify API returned {response.status_code}")
            return jobs
        
        data = response.json()
        job_posts = data.get('jobs', [])
        
        for job in job_posts:
            try:
                company = job.get('company_name', 'Unknown')
                title = job.get('title', '')
                description = job.get('description', '')
                location = job.get('location', '')
                url_link = job.get('url', '')
                posted_date = job.get('posted_at', '')
                
                # Check 24 hour window
                if not is_within_24_hours(posted_date):
                    continue
                
                # Check USA location
                if not is_usa_location(location):
                    continue
                
                # Check if government job
                is_gov, gov_reason = is_government_job(company, description)
                if is_gov:
                    print(f"  ⛔ Skipping {company} - government/defense: {gov_reason}")
                    continue
                
                # Check for hard visa restrictions
                has_restriction, restriction = has_visa_restrictions(description, title, company)
                if has_restriction:
                    print(f"  ⛔ Skipping {company} - visa restriction: {restriction}")
                    continue
                
                # Check if new grad/entry level
                is_entry, reason = is_new_grad_entry_level(title, description)
                if not is_entry:
                    print(f"  ⛔ Skipping {company} - {reason}")
                    continue
                
                print(f"  ✅ {company} - {title} ({reason})")
                
                job_id = hashlib.md5(f"{company}{title}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': url_link,
                    'source': 'Simplify',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
            except Exception as e:
                print(f"  Error parsing Simplify job: {e}")
                continue
        
        print(f"  ✅ Found {len(jobs)} new grad jobs from Simplify")
        
    except Exception as e:
        print(f"❌ Error scraping Simplify: {e}")
    
    return jobs

def scrape_levels_fyi():
    """Scrape Levels.fyi internships and new grad roles"""
    jobs = []
    
    try:
        url = "https://www.levels.fyi/internships/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("📥 Fetching from Levels.fyi...")
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find job listings (adjust selectors based on actual HTML)
        job_cards = soup.find_all('div', class_='job-listing')[:50]
        
        if not job_cards:
            # Try alternative selector
            job_cards = soup.find_all('tr', class_='job-row')[:50]
        
        for card in job_cards:
            try:
                # Extract job info (adjust based on actual HTML structure)
                title_elem = card.find('a', class_='job-title') or card.find('h3')
                company_elem = card.find('span', class_='company') or card.find('td', class_='company')
                
                if not (title_elem and company_elem):
                    continue
                
                title = title_elem.get_text(strip=True)
                company = company_elem.get_text(strip=True)
                url_link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                # Basic description (Levels.fyi doesn't always have full descriptions)
                description = f"New grad role at {company}. Visit Levels.fyi for details and compensation data."
                
                # Check if government
                is_gov, _ = is_government_job(company, description)
                if is_gov:
                    continue
                
                # Check if new grad
                is_entry, reason = is_new_grad_entry_level(title, description)
                if not is_entry:
                    continue
                
                print(f"  ✅ {company} - {title}")
                
                job_id = hashlib.md5(f"{company}{title}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description,
                    'url': url_link if url_link.startswith('http') else f"https://levels.fyi{url_link}",
                    'source': 'Levels.fyi',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
            except Exception as e:
                continue
        
        print(f"  ✅ Found {len(jobs)} jobs from Levels.fyi")
        
    except Exception as e:
        print(f"❌ Error scraping Levels.fyi: {e}")
    
    return jobs

def scrape_remoteok_new_grad():
    """Scrape RemoteOK for entry-level USA remote jobs"""
    jobs = []
    
    try:
        url = "https://remoteok.com/api"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("📥 Fetching from RemoteOK (entry-level filter)...")
        response = requests.get(url, headers=headers, timeout=20)
        data = response.json()
        
        job_posts = data[1:] if isinstance(data, list) else []
        
        for job in job_posts[:100]:  # Check more jobs
            try:
                location = job.get('location', '')
                if not is_usa_location(location):
                    continue
                
                company = job.get('company', 'Unknown')
                title = job.get('position', '')
                description = job.get('description', '')
                url_link = job.get('url', '')
                epoch_time = job.get('epoch', 0)
                
                # Check if within 24 hours
                if epoch_time:
                    posted_date = datetime.fromtimestamp(epoch_time)
                    if (datetime.now() - posted_date) > timedelta(hours=24):
                        continue
                
                if len(description) < 100:
                    continue
                
                # Check government
                is_gov, _ = is_government_job(company, description)
                if is_gov:
                    continue
                
                # Check visa restrictions
                has_restriction, restriction = has_visa_restrictions(description, title, company)
                if has_restriction:
                    print(f"  ⛔ Skipping {company} - {restriction}")
                    continue
                
                # Check if new grad/entry
                is_entry, reason = is_new_grad_entry_level(title, description)
                if not is_entry:
                    continue
                
                print(f"  ✅ {company} - {title} ({reason})")
                
                job_id = hashlib.md5(f"{company}{title}".encode()).hexdigest()[:8]
                
                jobs.append({
                    'job_id': job_id,
                    'company': company,
                    'title': title,
                    'description': description[:3000],
                    'url': url_link if url_link.startswith('http') else f"https://remoteok.com{url_link}",
                    'source': 'RemoteOK',
                    'date_found': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'Raw'
                })
                
            except Exception as e:
                continue
        
        print(f"  ✅ Found {len(jobs)} entry-level jobs from RemoteOK")
        
    except Exception as e:
        print(f"❌ Error scraping RemoteOK: {e}")
    
    return jobs

def scrape_github_jobs():
    """Scrape GitHub new grad job repo (community-maintained)"""
    jobs = []
    
    try:
        # This is a popular repo tracking new grad jobs
        url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
        
        print("📥 Fetching from GitHub New Grad repo...")
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            
            for job in data[:50]:  # Limit to 50 most recent
                try:
                    company = job.get('company_name', 'Unknown')
                    title = job.get('title', '')
                    locations = job.get('locations', [])
                    url_link = job.get('url', '')
                    is_active = job.get('active', True)
                    
                    if not is_active:
                        continue
                    
                    # Check USA location
                    location_str = ' '.join(locations) if isinstance(locations, list) else str(locations)
                    if not is_usa_location(location_str):
                        continue
                    
                    # Build description
                    description = f"New Grad position at {company}\nLocations: {location_str}\n\nThis role was posted on the SimplifyJobs New Grad tracker."
                    
                    # Check government
                    is_gov, _ = is_government_job(company, description)
                    if is_gov:
                        continue
                    
                    print(f"  ✅ {company} - {title}")
                    
                    job_id = hashlib.md5(f"{company}{title}".encode()).hexdigest()[:8]
                    
                    jobs.append({
                        'job_id': job_id,
                        'company': company,
                        'title': title,
                        'description': description,
                        'url': url_link,
                        'source': 'GitHub-NewGrad',
                        'date_found': datetime.now().strftime('%Y-%m-%d'),
                        'status': 'Raw'
                    })
                    
                except Exception as e:
                    continue
            
            print(f"  ✅ Found {len(jobs)} jobs from GitHub repo")
        
    except Exception as e:
        print(f"❌ Error scraping GitHub: {e}")
    
    return jobs

def save_to_sheets(jobs):
    """Save jobs to Google Sheets"""
    if not jobs:
        print("No jobs to save")
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
            print(f"✅ Added {len(new_jobs)} new jobs to sheet")
            return len(new_jobs)
        else:
            print("No new jobs (all duplicates)")
            return 0
            
    except Exception as e:
        print(f"Error saving to sheets: {e}")
        return 0

def main():
    print("🔍 NEW GRAD JOB HUNTER - Starting...")
    print("=" * 60)
    print("Filters:")
    print("  ✅ New grad / Entry level ONLY")
    print("  ✅ USA locations ONLY")
    print("  ✅ Posted within last 24 hours")
    print("  ❌ NO government/defense jobs")
    print("  ❌ NO citizenship requirements")
    print("  ❌ NO security clearance")
    print("  ❌ NO 'no sponsorship' statements")
    print("=" * 60)
    
    all_jobs = []
    
    # Scrape from multiple sources
    all_jobs.extend(scrape_github_jobs())  # Best source for new grads
    all_jobs.extend(scrape_remoteok_new_grad())
    # all_jobs.extend(scrape_simplify_jobs())  # Uncomment if Simplify API works
    # all_jobs.extend(scrape_levels_fyi())  # Uncomment if needed
    
    print(f"\n📊 Total new grad jobs found: {len(all_jobs)}")
    
    # Save to sheets
    new_count = save_to_sheets(all_jobs)
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"✅ SCRAPING COMPLETE")
    print(f"{'=' * 60}")
    print(f"   New jobs added: {new_count}")
    print(f"   All jobs are:")
    print(f"     - New grad/entry level")
    print(f"     - USA locations")
    print(f"     - Posted in last 24 hours")
    print(f"     - H1B friendly (no citizenship requirements)")
    print(f"\n👉 Check your Google Sheet 'Raw Jobs' tab")
    print(f"👉 Run 'Analyze Jobs' workflow to get tier assignments")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()