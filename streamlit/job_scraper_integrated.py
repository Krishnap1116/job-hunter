# job_scraper_integrated.py - Integrated Job Scraper

import requests
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
import time

def generate_job_id(company, title):
    """Generate unique job ID"""
    return hashlib.md5(f"{company}_{title}".encode()).hexdigest()[:8]

class IntegratedScraper:
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or {}
    
    def scrape_all(self, target_roles, limit_per_source=20):
        """Scrape jobs from all available sources"""
        all_jobs = []
        
        # Source 1: JSearch API (if key available)
        if self.api_keys.get('jsearch_key'):
            print("📡 Scraping JSearch...")
            all_jobs.extend(self.scrape_jsearch(target_roles, limit_per_source))
        
        # Source 2: Adzuna API (if keys available)
        if self.api_keys.get('adzuna_id') and self.api_keys.get('adzuna_key'):
            print("📡 Scraping Adzuna...")
            all_jobs.extend(self.scrape_adzuna(target_roles, limit_per_source))
        
        # Source 3: RemoteOK (no API key needed)
        print("📡 Scraping RemoteOK...")
        all_jobs.extend(self.scrape_remoteok(target_roles, limit_per_source))
        
        # Source 4: SimplifyJobs GitHub
        print("📡 Scraping SimplifyJobs...")
        all_jobs.extend(self.scrape_simplify(limit_per_source))
        
        return all_jobs
    
    def scrape_jsearch(self, target_roles, limit):
        """Scrape JSearch API"""
        jobs = []
        api_key = self.api_keys.get('jsearch_key')
        
        for role in target_roles[:3]:  # Limit to 3 roles to avoid rate limits
            try:
                url = "https://jsearch.p.rapidapi.com/search"
                params = {
                    "query": f"{role} USA",
                    "page": "1",
                    "num_pages": "1",
                    "date_posted": "today"
                }
                headers = {
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json().get('data', [])
                    
                    for job in data[:limit]:
                        jobs.append({
                            'job_id': generate_job_id(job.get('employer_name', 'Unknown'), job.get('job_title', '')),
                            'company': job.get('employer_name', 'Unknown'),
                            'title': job.get('job_title', ''),
                            'url': job.get('job_apply_link', ''),
                            'location': f"{job.get('job_city', '')}, {job.get('job_state', '')}",
                            'description': job.get('job_description', ''),
                            'source': 'JSearch'
                        })
                
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"❌ JSearch error: {e}")
                continue
        
        return jobs
    
    def scrape_adzuna(self, target_roles, limit):
        """Scrape Adzuna API"""
        jobs = []
        app_id = self.api_keys.get('adzuna_id')
        app_key = self.api_keys.get('adzuna_key')
        
        for role in target_roles[:3]:
            try:
                url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": limit,
                    "what": role,
                    "content-type": "application/json",
                    "max_days_old": 1
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json().get('results', [])
                    
                    for job in data:
                        jobs.append({
                            'job_id': generate_job_id(job.get('company', {}).get('display_name', 'Unknown'), job.get('title', '')),
                            'company': job.get('company', {}).get('display_name', 'Unknown'),
                            'title': job.get('title', ''),
                            'url': job.get('redirect_url', ''),
                            'location': f"{job.get('location', {}).get('display_name', '')}",
                            'description': job.get('description', ''),
                            'source': 'Adzuna'
                        })
                
                time.sleep(1)
            except Exception as e:
                print(f"❌ Adzuna error: {e}")
                continue
        
        return jobs
    
    def scrape_remoteok(self, target_roles, limit):
        """Scrape RemoteOK"""
        jobs = []
        
        try:
            url = "https://remoteok.com/api"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()[1:]  # Skip first item (metadata)
                
                role_keywords = [role.lower() for role in target_roles]
                count = 0
                
                for job in data:
                    if count >= limit:
                        break
                    
                    position = job.get('position', '').lower()
                    
                    # Check if any target role matches
                    if any(keyword in position for keyword in role_keywords):
                        jobs.append({
                            'job_id': job.get('id', generate_job_id(job.get('company', 'Unknown'), job.get('position', ''))),
                            'company': job.get('company', 'Unknown'),
                            'title': job.get('position', ''),
                            'url': job.get('url', ''),
                            'location': 'Remote',
                            'description': job.get('description', ''),
                            'source': 'RemoteOK'
                        })
                        count += 1
        except Exception as e:
            print(f"❌ RemoteOK error: {e}")
        
        return jobs
    
    def scrape_simplify(self, limit):
        """Scrape SimplifyJobs GitHub"""
        jobs = []
        
        try:
            url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                current_time = time.time()
                
                for job in data[:limit * 2]:  # Get more to filter
                    # Filter by date (last 24 hours)
                    date_posted = job.get('date_posted', 0)
                    hours_ago = (current_time - date_posted) / 3600
                    
                    if hours_ago > 24:
                        continue
                    
                    # Filter by active and USA
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
                        'description': f"Locations: {', '.join(job.get('locations', []))}",
                        'source': 'SimplifyJobs'
                    })
                    
                    if len(jobs) >= limit:
                        break
        except Exception as e:
            print(f"❌ SimplifyJobs error: {e}")
        
        return jobs