# job_scraper_integrated.py - Complete Multi-Source Scraper

import requests
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime, timedelta
import time
import feedparser

def generate_job_id(company, title):
    """Generate unique job ID"""
    return hashlib.md5(f"{company}_{title}".encode()).hexdigest()[:8]

def is_usa_location(location):
    """Check if location is in USA"""
    if not location:
        return False
    
    location_lower = location.lower()
    
    # Reject other countries
    reject = ['canada', 'toronto', 'uk', 'london', 'india', 'europe', 'germany', 'france', 'australia', 'mexico', 'china', 'japan']
    if any(country in location_lower for country in reject):
        return False
    
    # Accept USA
    usa_indicators = ['united states', 'usa', 'u.s.', 'us,', 'california', 'new york', 'texas', 'florida', 
                     'washington', 'massachusetts', 'illinois', 'colorado', 'oregon', 'georgia',
                     'san francisco', 'seattle', 'austin', 'boston', 'chicago', 'remote us', 'remote usa']
    
    return any(indicator in location_lower for indicator in usa_indicators)

class IntegratedScraper:
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or {}
        
        # ✅ DEBUG: Print what keys we received
        print("=" * 60)
        print("🔍 DEBUG: API Keys Received by Scraper")
        print(f"Anthropic: {'✅ Present' if self.api_keys.get('anthropic_key') else '❌ Missing'}")
        print(f"OpenRouter: {'✅ Present' if self.api_keys.get('openrouter_key') else '❌ Missing'}")
        print(f"JSearch: {'✅ Present' if self.api_keys.get('jsearch_key') else '❌ Missing'}")
        print(f"Adzuna ID: {'✅ Present' if self.api_keys.get('adzuna_id') else '❌ Missing'}")
        print(f"Adzuna Key: {'✅ Present' if self.api_keys.get('adzuna_key') else '❌ Missing'}")
        print("=" * 60)
    
    def scrape_all(self, target_roles, limit_per_source=20):
        """Scrape jobs from ALL available sources"""
        all_jobs = []
        
        print("\n🎯 Starting job collection from all sources...")
        print(f"Target roles: {', '.join(target_roles)}")
        print(f"Limit per source: {limit_per_source}")
        print("=" * 60)
        
        # LAYER 1: Paid APIs (if keys available)
        if self.api_keys.get('jsearch_key'):
            all_jobs.extend(self.scrape_jsearch(target_roles, limit_per_source))
        else:
            print("⚠️  JSearch: Skipped (no API key)")
        
        if self.api_keys.get('adzuna_id') and self.api_keys.get('adzuna_key'):
            all_jobs.extend(self.scrape_adzuna(target_roles, limit_per_source))
        else:
            print("⚠️  Adzuna: Skipped (no API keys)")
        
        # LAYER 2: Free APIs
        all_jobs.extend(self.scrape_remoteok(target_roles, limit_per_source))
        all_jobs.extend(self.scrape_himalayas(limit_per_source))
        all_jobs.extend(self.scrape_rss_feeds(limit_per_source))
        
        # LAYER 3: Company APIs
        all_jobs.extend(self.scrape_google_jobs(limit_per_source))
        all_jobs.extend(self.scrape_apple_jobs(limit_per_source))
        all_jobs.extend(self.scrape_amazon_jobs(limit_per_source))
        
        # LAYER 4: ATS Systems
        all_jobs.extend(self.scrape_greenhouse(limit_per_source))
        all_jobs.extend(self.scrape_lever(limit_per_source))
        all_jobs.extend(self.scrape_simplify(limit_per_source))
        
        print("\n" + "=" * 60)
        print(f"✅ Total jobs collected: {len(all_jobs)}")
        print("=" * 60)
        
        return all_jobs
    
    # ==================== PAID APIs ====================
    
    def scrape_jsearch(self, target_roles, limit):
        """JSearch API"""
        jobs = []
        api_key = self.api_keys.get('jsearch_key')
        
        print("\n📡 JSearch API...")
        
        for role in target_roles[:3]:
            try:
                url = "https://jsearch.p.rapidapi.com/search"
                params = {
                    "query": f"{role} United States",
                    "page": "1",
                    "date_posted": "today",
                    "employment_types": "FULLTIME"
                }
                headers = {
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    for job in response.json().get('data', [])[:limit]:
                        company = job.get('employer_name', 'Unknown')
                        title = job.get('job_title', '')
                        url = job.get('job_apply_link', '')
                        location = f"{job.get('job_city', '')} {job.get('job_state', '')}"
                        
                        if not url or not url.startswith('http'):
                            continue
                        if not is_usa_location(location):
                            continue
                        
                        jobs.append({
                            'job_id': generate_job_id(company, title),
                            'company': company,
                            'title': title,
                            'url': url,
                            'location': location,
                            'description': job.get('job_description', '')[:5000],
                            'source': 'JSearch'
                        })
                
                time.sleep(1)
            except Exception as e:
                print(f"  ❌ {role}: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from JSearch")
        return jobs
    
    def scrape_adzuna(self, target_roles, limit):
        """Adzuna API"""
        jobs = []
        app_id = self.api_keys.get('adzuna_id')
        app_key = self.api_keys.get('adzuna_key')
        
        print("\n📡 Adzuna API...")
        
        for role in target_roles[:3]:
            try:
                url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": limit,
                    "what": role,
                    "where": "USA",
                    "max_days_old": 1,
                    "sort_by": "date"
                }
                
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    for job in response.json().get('results', []):
                        company = job.get('company', {}).get('display_name', 'Unknown')
                        title = job.get('title', '')
                        url = job.get('redirect_url', '')
                        location = job.get('location', {}).get('display_name', '')
                        
                        if not url or not is_usa_location(location):
                            continue
                        
                        jobs.append({
                            'job_id': generate_job_id(company, title),
                            'company': company,
                            'title': title,
                            'url': url,
                            'location': location,
                            'description': job.get('description', '')[:5000],
                            'source': 'Adzuna'
                        })
                
                time.sleep(1)
            except Exception as e:
                print(f"  ❌ {role}: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from Adzuna")
        return jobs
    
    # ==================== FREE APIs ====================
    
    def scrape_remoteok(self, target_roles, limit):
        """RemoteOK"""
        jobs = []
        print("\n📡 RemoteOK API...")
        
        try:
            url = "https://remoteok.com/api"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()[1:]  # Skip metadata
                role_keywords = [role.lower() for role in target_roles]
                count = 0
                
                for job in data:
                    if count >= limit:
                        break
                    
                    position = job.get('position', '').lower()
                    if any(keyword in position for keyword in role_keywords):
                        # Check if posted in last 24h
                        epoch = job.get('epoch', 0)
                        if epoch:
                            posted = datetime.fromtimestamp(epoch)
                            if (datetime.now() - posted).days > 1:
                                continue
                        
                        jobs.append({
                            'job_id': job.get('id', generate_job_id(job.get('company', 'Unknown'), job.get('position', ''))),
                            'company': job.get('company', 'Unknown'),
                            'title': job.get('position', ''),
                            'url': job.get('url', ''),
                            'location': 'Remote',
                            'description': job.get('description', '')[:5000],
                            'source': 'RemoteOK'
                        })
                        count += 1
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from RemoteOK")
        return jobs
    
    def scrape_himalayas(self, limit):
        """Himalayas Jobs"""
        jobs = []
        print("\n📡 Himalayas API...")
        
        try:
            url = "https://himalayas.app/jobs/api"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                for job in response.json().get('jobs', [])[:limit]:
                    company = job.get('company', {}).get('name', 'Unknown')
                    title = job.get('title', '')
                    url = job.get('url', '')
                    locations = job.get('locations', [])
                    location_str = ' '.join(locations)
                    
                    if not url or not is_usa_location(location_str):
                        continue
                    
                    jobs.append({
                        'job_id': generate_job_id(company, title),
                        'company': company,
                        'title': title,
                        'url': url,
                        'location': location_str,
                        'description': job.get('description', '')[:5000],
                        'source': 'Himalayas'
                    })
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from Himalayas")
        return jobs
    
    def scrape_rss_feeds(self, limit):
        """RSS Feeds"""
        jobs = []
        print("\n📡 RSS Feeds...")
        
        feeds = {
            'remotive': 'https://remotive.com/api/remote-jobs',
            'weworkremotely': 'https://weworkremotely.com/remote-jobs.rss'
        }
        
        for name, url in feeds.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit]:
                    title_parts = entry.title.split(' - ') if ' - ' in entry.title else [entry.title]
                    company = title_parts[0] if len(title_parts) > 1 else 'Unknown'
                    title = title_parts[1] if len(title_parts) > 1 else title_parts[0]
                    
                    jobs.append({
                        'job_id': generate_job_id(company, title),
                        'company': company,
                        'title': title,
                        'url': entry.link,
                        'location': 'Remote',
                        'description': entry.get('summary', '')[:5000],
                        'source': f'RSS-{name}'
                    })
            except Exception as e:
                print(f"  ❌ {name}: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from RSS")
        return jobs
    
    # ==================== COMPANY APIs ====================
    
    def scrape_google_jobs(self, limit):
        """Google Careers"""
        jobs = []
        print("\n📡 Google Careers...")
        
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
                for job in response.json().get('jobs', [])[:limit]:
                    jobs.append({
                        'job_id': generate_job_id('Google', job['title']),
                        'company': 'Google',
                        'title': job['title'],
                        'url': f"https://careers.google.com/jobs/results/{job['id']}/",
                        'location': ', '.join(job.get('locations', [])),
                        'description': job.get('description', '')[:5000],
                        'source': 'Google-Direct'
                    })
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from Google")
        return jobs
    
    def scrape_apple_jobs(self, limit):
        """Apple Careers"""
        jobs = []
        print("\n📡 Apple Careers...")
        
        try:
            url = "https://jobs.apple.com/api/role/search"
            params = {
                'location': 'United-States-USA',
                'team': 'apps-and-frameworks'
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                for job in response.json().get('searchResults', [])[:limit]:
                    jobs.append({
                        'job_id': generate_job_id('Apple', job['postingTitle']),
                        'company': 'Apple',
                        'title': job['postingTitle'],
                        'url': f"https://jobs.apple.com/en-us/details/{job['positionId']}",
                        'location': job.get('locations', ''),
                        'description': job.get('jobSummary', '')[:5000],
                        'source': 'Apple-Direct'
                    })
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from Apple")
        return jobs
    
    def scrape_amazon_jobs(self, limit):
        """Amazon Jobs"""
        jobs = []
        print("\n📡 Amazon Jobs...")
        
        try:
            url = "https://www.amazon.jobs/en/search.json"
            params = {
                'base_query': 'software engineer',
                'loc_query': 'United States',
                'result_limit': limit
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                for job in response.json().get('jobs', []):
                    jobs.append({
                        'job_id': generate_job_id('Amazon', job['title']),
                        'company': 'Amazon',
                        'title': job['title'],
                        'url': f"https://www.amazon.jobs{job['job_path']}",
                        'location': job.get('location', ''),
                        'description': job.get('description', '')[:5000],
                        'source': 'Amazon-Direct'
                    })
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from Amazon")
        return jobs
    
    # ==================== ATS Systems ====================
    
    def scrape_greenhouse(self, limit):
        """Greenhouse ATS"""
        jobs = []
        print("\n📡 Greenhouse...")
        
        companies = ['stripe', 'notion', 'figma', 'anthropic', 'scale', 'airtable']
        
        for company_id in companies:
            try:
                url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    for job in response.json().get('jobs', [])[:5]:
                        title = job.get('title', '')
                        url = job.get('absolute_url', '')
                        location = job.get('location', {}).get('name', '')
                        
                        if not url or not is_usa_location(location):
                            continue
                        
                        jobs.append({
                            'job_id': generate_job_id(company_id.title(), title),
                            'company': company_id.title(),
                            'title': title,
                            'url': url,
                            'location': location,
                            'description': f"Location: {location}. View details at job URL.",
                            'source': 'Greenhouse'
                        })
                
                time.sleep(0.5)
            except Exception as e:
                continue
        
        print(f"  ✅ {len(jobs)} jobs from Greenhouse")
        return jobs
    
    def scrape_lever(self, limit):
        """Lever ATS"""
        jobs = []
        print("\n📡 Lever...")
        
        companies = ['rippling', 'plaid', 'retool', 'verkada', 'superhuman']
        
        for company_id in companies:
            try:
                url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    for job in response.json()[:5]:
                        title = job.get('text', '')
                        url = job.get('hostedUrl', '')
                        location = job.get('categories', {}).get('location', '')
                        
                        if not url or not is_usa_location(location):
                            continue
                        
                        jobs.append({
                            'job_id': generate_job_id(company_id.title(), title),
                            'company': company_id.title(),
                            'title': title,
                            'url': url,
                            'location': location,
                            'description': job.get('description', '')[:5000] or f"Location: {location}",
                            'source': 'Lever'
                        })
                
                time.sleep(0.5)
            except Exception as e:
                continue
        
        print(f"  ✅ {len(jobs)} jobs from Lever")
        return jobs
    
    def scrape_simplify(self, limit):
        """SimplifyJobs GitHub"""
        jobs = []
        print("\n📡 SimplifyJobs...")
        
        try:
            url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                current_time = time.time()
                
                for job in response.json()[:limit * 2]:
                    # Check date first
                    date_posted = job.get('date_posted', 0)
                    if date_posted:
                        hours_ago = (current_time - date_posted) / 3600
                        if hours_ago > 24:
                            continue
                    
                    # Check active and USA
                    if not job.get('active', False):
                        continue
                    
                    location_str = ' '.join(job.get('locations', [])).lower()
                    if 'usa' not in location_str and 'united states' not in location_str:
                        continue
                    
                    jobs.append({
                        'job_id': generate_job_id(job.get('company_name', 'Unknown'), job.get('title', '')),
                        'company': job.get('company_name', 'Unknown'),
                        'title': job.get('title', ''),
                        'url': job.get('url', ''),
                        'location': ', '.join(job.get('locations', [])),
                        'description': f"New grad position. Locations: {', '.join(job.get('locations', []))}",
                        'source': 'SimplifyJobs'
                    })
                    
                    if len(jobs) >= limit:
                        break
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")
        
        print(f"  ✅ {len(jobs)} jobs from SimplifyJobs")
        return jobs