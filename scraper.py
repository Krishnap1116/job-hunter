# import requests
# from bs4 import BeautifulSoup
# from datetime import datetime
# import hashlib
# from sheets_helper import get_sheet
# # from email_helper import send_email
# import time

# def scrape_ycombinator():
#     jobs = []
#     url = "https://www.ycombinator.com/jobs"
#     headers = {"User-Agent": "Mozilla/5.0"}

#     response = requests.get(url, headers=headers, timeout=15)
#     soup = BeautifulSoup(response.text, "html.parser")

#     # YC job links always contain /jobs/
#     links = soup.select("a[href*='/jobs/']")

#     seen = set()

#     for link in links:
#         href = link.get("href", "")
#         if "/companies/" not in href:
#             continue

#         job_url = "https://www.ycombinator.com" + href
#         if job_url in seen:
#             continue
#         seen.add(job_url)

#         text = link.get_text(" ", strip=True)
#         if not text or len(text) < 10:
#             continue

#         try:
#             company = href.split("/companies/")[1].split("/")[0]
#             job_id = hashlib.md5(job_url.encode()).hexdigest()[:8]

#             jobs.append({
#                 "job_id": job_id,
#                 "company": company.replace("-", " ").title(),
#                 "title": text,
#                 "description": f"See full details at {job_url}",
#                 "url": job_url,
#                 "source": "YCombinator",
#                 "date_found": datetime.now().strftime("%Y-%m-%d"),
#                 "status": "Raw"
#             })
#         except Exception:
#             continue

#         if len(jobs) >= 25:
#             break

#     print(f"Found {len(jobs)} jobs from YCombinator")
#     return jobs
# def scrape_wellfound():
#     jobs = []
#     url = "https://wellfound.com/jobs"
#     headers = {"User-Agent": "Mozilla/5.0"}

#     response = requests.get(url, headers=headers, timeout=15)
#     soup = BeautifulSoup(response.text, "html.parser")

#     cards = soup.select("a[href*='/company/'][href*='/jobs/']")

#     for card in cards[:25]:
#         try:
#             href = card.get("href")
#             job_url = "https://wellfound.com" + href
#             text = card.get_text(" ", strip=True)

#             if not text:
#                 continue

#             company = href.split("/company/")[1].split("/")[0]
#             job_id = hashlib.md5(job_url.encode()).hexdigest()[:8]

#             jobs.append({
#                 "job_id": job_id,
#                 "company": company.replace("-", " ").title(),
#                 "title": text,
#                 "description": f"See full details at {job_url}",
#                 "url": job_url,
#                 "source": "Wellfound",
#                 "date_found": datetime.now().strftime("%Y-%m-%d"),
#                 "status": "Raw"
#             })
#         except Exception:
#             continue

#     print(f"Found {len(jobs)} jobs from Wellfound")
#     return jobs
# def scrape_greenhouse_boards():
#     jobs = []
#     boards = [
#         "https://boards.greenhouse.io/openai",
#         "https://boards.greenhouse.io/anthropic",
#         "https://boards.greenhouse.io/scaleai",
#         "https://boards.greenhouse.io/stripe"
#     ]

#     headers = {"User-Agent": "Mozilla/5.0"}

#     for board in boards:
#         try:
#             response = requests.get(board, headers=headers, timeout=15)
#             soup = BeautifulSoup(response.text, "html.parser")

#             postings = soup.select("a[href*='/jobs/']")

#             for post in postings:
#                 title = post.get_text(strip=True)
#                 href = post.get("href")

#                 if not title or not href:
#                     continue

#                 job_url = board.split("/boards")[0] + href
#                 company = board.split("//")[1].split(".")[0].title()
#                 job_id = hashlib.md5(job_url.encode()).hexdigest()[:8]

#                 jobs.append({
#                     "job_id": job_id,
#                     "company": company,
#                     "title": title,
#                     "description": f"See full details at {job_url}",
#                     "url": job_url,
#                     "source": "Greenhouse",
#                     "date_found": datetime.now().strftime("%Y-%m-%d"),
#                     "status": "Raw"
#                 })
#         except Exception:
#             continue

#     print(f"Found {len(jobs)} jobs from Greenhouse")
#     return jobs


# def save_to_sheets(jobs):
#     """Save jobs to Google Sheets"""
#     if not jobs:
#         print("No jobs to save")
#         return 0
    
#     try:
#         sheet = get_sheet()
#         worksheet = sheet.worksheet("Raw Jobs")
        
#         # Get existing job IDs
#         existing_data = worksheet.get_all_values()
#         existing_ids = [row[0] for row in existing_data[1:]] if len(existing_data) > 1 else []
        
#         # Filter new jobs
#         new_jobs = []
#         for job in jobs:
#             if job['job_id'] not in existing_ids:
#                 new_jobs.append([
#                     job['job_id'],
#                     job['company'],
#                     job['title'],
#                     job['description'],
#                     job['url'],
#                     job['source'],
#                     job['date_found'],
#                     job['status']
#                 ])
        
#         if new_jobs:
#             worksheet.append_rows(new_jobs)
#             print(f"✅ Added {len(new_jobs)} new jobs to sheet")
#             return len(new_jobs)
#         else:
#             print("No new jobs (all duplicates)")
#             return 0
            
#     except Exception as e:
#         print(f"Error saving to sheets: {e}")
#         return 0

# def main():
#     print("🔍 Starting job collection...")

#     all_jobs = []

#     all_jobs.extend(scrape_ycombinator())
#     all_jobs.extend(scrape_wellfound())
#     all_jobs.extend(scrape_greenhouse_boards())

#     new_count = save_to_sheets(all_jobs)

#     print(f"✅ Job collection complete. Added {new_count} new jobs.")

    
#     # Send email notification
#     if new_count > 0:
#         subject = "Job Hunter: New Jobs Found!"
#         message = f"""Job Collection Complete

# Found {new_count} new jobs from YCombinator

# Next Steps:
# 1. Open your Google Sheet to see the jobs
# 2. Go to GitHub Actions to run "Analyze Jobs"

# Your Job Hunter Bot
# """
#         # send_email(subject, message)
#         print(f"✅ Job collection complete. Added {new_count} new jobs.")
#     else:
#         subject = "Job Hunter: No New Jobs Today"
#         message = """Job collection ran successfully, but no new jobs were found.

# This could mean:
# - All jobs are duplicates
# - YCombinator hasn't posted new roles yet

# The system will check again tomorrow.

# Your Job Hunter Bot
# """
#         # send_email(subject, message)
#         print(f"✅ Job collection complete. Added {new_count} new jobs.")
    
#     print(f"✅ Done! {new_count} new jobs added")

# if __name__ == "__main__":
#     main()


import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
from sheets_helper import get_sheet
import time
import re

def is_usa_location(location_text):
    """Check if location is in USA"""
    if not location_text:
        return False
    
    location_lower = location_text.lower()
    
    # USA indicators
    usa_keywords = [
        'usa', 'united states', 'u.s.', 'us,', 
        'california', 'new york', 'texas', 'florida', 'washington',
        'san francisco', 'seattle', 'austin', 'boston', 'denver',
        'remote us', 'remote usa', 'us remote', 'remote (us)',
        'anywhere in us', 'nationwide'
    ]
    
    # Non-USA locations to exclude
    exclude_keywords = [
        'canada', 'uk', 'london', 'europe', 'india', 'bangalore',
        'toronto', 'berlin', 'paris', 'sydney', 'australia'
    ]
    
    # Check exclusions first
    for keyword in exclude_keywords:
        if keyword in location_lower:
            return False
    
    # Check USA indicators
    for keyword in usa_keywords:
        if keyword in location_lower:
            return True
    
    return False

def check_visa_friendly(description, title):
    """Check if job mentions visa restrictions or sponsorship"""
    text = (description + " " + title).lower()
    
    # RED FLAGS - Auto reject
    reject_keywords = [
        'us citizen', 'u.s. citizen', 'citizenship required',
        'security clearance', 'clearance required', 'ts/sci',
        'must be authorized to work', 'no sponsorship',
        'cannot sponsor', 'will not sponsor', 'us authorization required'
    ]
    
    for keyword in reject_keywords:
        if keyword in text:
            return 'REJECT', keyword
    
    # GREEN FLAGS - Good for H1B
    sponsor_keywords = [
        'visa sponsor', 'h1b sponsor', 'will sponsor', 'can sponsor',
        'sponsorship available', 'visa transfer', 'immigration support'
    ]
    
    for keyword in sponsor_keywords:
        if keyword in text:
            return 'SPONSOR', keyword
    
    return 'UNKNOWN', None

def scrape_remoteok():
    """Scrape RemoteOK for USA remote jobs"""
    jobs = []
    
    try:
        url = "https://remoteok.com/api"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("📥 Fetching from RemoteOK...")
        response = requests.get(url, headers=headers, timeout=20)
        data = response.json()
        
        # Skip first item (it's metadata)
        job_posts = data[1:] if isinstance(data, list) else []
        
        for job in job_posts[:50]:  # Check first 50
            try:
                # Check location
                location = job.get('location', '')
                if not is_usa_location(location):
                    continue
                
                company = job.get('company', 'Unknown')
                title = job.get('position', '')
                description = job.get('description', '')
                url_link = job.get('url', '')
                
                # Skip if no description
                if len(description) < 100:
                    continue
                
                # Check visa friendliness
                visa_status, keyword = check_visa_friendly(description, title)
                
                if visa_status == 'REJECT':
                    print(f"  ⛔ Skipping {company} - requires: {keyword}")
                    continue
                
                job_id = hashlib.md5(
                    f"{company}{title}".encode()
                ).hexdigest()[:8]
                
                # Add visa info to description
                if visa_status == 'SPONSOR':
                    description = f"[VISA SPONSORSHIP MENTIONED: {keyword}]\n\n{description}"
                
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
                print(f"  Error parsing RemoteOK job: {e}")
                continue
        
        print(f"  ✅ Found {len(jobs)} USA jobs from RemoteOK")
        
    except Exception as e:
        print(f"❌ Error scraping RemoteOK: {e}")
    
    return jobs

def save_to_sheets(jobs):
    """Save jobs to Google Sheets"""
    if not jobs:
        print("No jobs to save")
        return 0
    
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet("Raw Jobs")
        
        # Get existing job IDs
        existing_data = worksheet.get_all_values()
        existing_ids = [row[0] for row in existing_data[1:]] if len(existing_data) > 1 else []
        
        # Filter new jobs
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
    print("🔍 Starting job collection (USA only, H1B friendly)...")
    
    all_jobs = []
    
    # Scrape from RemoteOK
    all_jobs.extend(scrape_remoteok())
    
    print(f"\n📊 Total jobs found: {len(all_jobs)}")
    
    # Save to sheets
    new_count = save_to_sheets(all_jobs)
    
    # Just print summary (no email)
    print(f"\n✅ Job collection complete!")
    print(f"   - New jobs added: {new_count}")
    print(f"   - USA locations only")
    print(f"   - No citizenship/clearance requirements")
    print(f"   - Visa sponsorship flagged when mentioned")
    print(f"\n👉 Check your Google Sheet to see the jobs")
    print(f"👉 Run 'Analyze Jobs' workflow when ready")

if __name__ == "__main__":
    main()