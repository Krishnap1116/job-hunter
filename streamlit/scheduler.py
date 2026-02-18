# scheduler.py - Background job collection scheduler

import schedule
import time
import threading
from database import JobHunterDB
from job_scraper_integrated import IntegratedScraper
from datetime import datetime

def run_scheduled_collection():
    """Run job collection for all profiles with auto-collect enabled"""
    db = JobHunterDB()
    
    # Get all profiles with auto-collect enabled
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, collection_time FROM profiles 
    WHERE auto_collect_enabled = 1
    ''')
    profiles = cursor.fetchall()
    conn.close()
    
    current_time = datetime.now().strftime('%H:%M')
    
    for profile_id, collection_time in profiles:
        if collection_time == current_time:
            print(f"🔍 Running collection for profile {profile_id}")
            
            # Get profile and API keys
            profile = db.get_profile_by_id(profile_id)
            api_keys = db.get_api_keys(profile_id)
            
            # Run scraper
            scraper = IntegratedScraper(api_keys)
            jobs = scraper.scrape_all(
                target_roles=profile['target_roles'],
                limit_per_source=20
            )
            
            # Save jobs
            saved = 0
            for job in jobs:
                if db.save_raw_job(profile_id, job):
                    saved += 1
            
            # Update last run time
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE profiles SET last_collection_run = ? WHERE id = ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), profile_id))
            conn.commit()
            conn.close()
            
            print(f"✅ Collected {saved} new jobs for profile {profile_id}")

def start_scheduler():
    """Start the background scheduler"""
    schedule.every().minute.do(run_scheduled_collection)
    
    def run_continuously():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    thread = threading.Thread(target=run_continuously, daemon=True)
    thread.start()
    print("⏰ Scheduler started")

# Add this to app.py at the top level:
# from scheduler import start_scheduler
# start_scheduler()