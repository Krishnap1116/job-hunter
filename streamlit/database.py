# database.py - Complete Database Manager

import sqlite3
import json
from datetime import datetime, timedelta

class JobHunterDB:
    def __init__(self, db_path='job_hunter.db'):
        self.db_path = db_path
        self.init_database()
        self.migrate_database()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # User profiles with scheduling
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            experience_years TEXT,
            experience_level TEXT,
            core_skills TEXT,
            target_roles TEXT,
            forbidden_keywords TEXT,
            
            collection_time TEXT DEFAULT '09:00',
            timezone TEXT DEFAULT 'America/New_York',
            auto_collect_enabled BOOLEAN DEFAULT 1,
            last_collection_run TIMESTAMP,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # PRE-FILTER settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pre_filter_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER UNIQUE,
            max_years_experience INTEGER DEFAULT 4,
            reject_seniority_levels TEXT DEFAULT '["senior","staff","principal","lead","manager","director","vp","head of","chief"]',
            reject_job_types TEXT DEFAULT '["internship","intern","part-time","freelance","contractor"]',
            reject_specific_titles TEXT DEFAULT '["business analyst","data analyst","support engineer","technical writer","project manager","sales engineer"]',
            check_full_description BOOLEAN DEFAULT 1,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        ''')
        
        # CLAUDE ANALYSIS settings
        # CLAUDE ANALYSIS settings (user-controlled)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS claude_filter_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER UNIQUE,
            
            strict_experience_check BOOLEAN DEFAULT 1,
            max_experience_required INTEGER DEFAULT 4,
            allow_preferred_experience BOOLEAN DEFAULT 1,
            
            min_skill_match_percent INTEGER DEFAULT 65,
            tier1_skill_threshold INTEGER DEFAULT 85,
            tier2_skill_threshold INTEGER DEFAULT 65,
            
            min_target_role_percentage INTEGER DEFAULT 70,
            
            accept_contract_to_hire BOOLEAN DEFAULT 1,
            accept_contract_w2 BOOLEAN DEFAULT 0,
            reject_internships BOOLEAN DEFAULT 1,
            accept_part_time BOOLEAN DEFAULT 0,
            
            requires_visa_sponsorship BOOLEAN DEFAULT 1,
            reject_clearance_jobs BOOLEAN DEFAULT 1,
            accept_remote_only BOOLEAN DEFAULT 0,
            
            auto_reject_phrases TEXT DEFAULT '["us citizen only","security clearance required","no visa sponsorship"]',
            
            custom_accept_employment TEXT DEFAULT '[]',
            custom_reject_employment TEXT DEFAULT '[]',
            
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        ''')
        
        # Raw jobs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER,
            job_id TEXT UNIQUE,
            company TEXT,
            title TEXT,
            url TEXT,
            location TEXT,
            description TEXT,
            source TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        ''')
        
        # Analyzed jobs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyzed_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER,
            job_id TEXT,
            company TEXT,
            title TEXT,
            url TEXT,
            tier INTEGER,
            match_score INTEGER,
            experience_required INTEGER,
            role_match_pct INTEGER,
            skill_match_pct INTEGER,
            reasoning TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES raw_jobs(job_id)
        )
        ''')
        
        # API keys
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER UNIQUE,
            anthropic_key TEXT,
            jsearch_key TEXT,
            adzuna_id TEXT,
            adzuna_key TEXT,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        ''')
        
        conn.commit()
        conn.close()
    def migrate_database(self):
        """Migrate database to add new columns"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if custom employment columns exist
            cursor.execute("PRAGMA table_info(claude_filter_config)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'custom_accept_employment' not in columns:
                cursor.execute('''
                ALTER TABLE claude_filter_config 
                ADD COLUMN custom_accept_employment TEXT DEFAULT '[]'
                ''')
                print("✅ Added custom_accept_employment column")
            
            if 'custom_reject_employment' not in columns:
                cursor.execute('''
                ALTER TABLE claude_filter_config 
                ADD COLUMN custom_reject_employment TEXT DEFAULT '[]'
                ''')
                print("✅ Added custom_reject_employment column")
            
            conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")
        finally:
            conn.close()
    # Profile methods
    def create_profile(self, name, email, resume_data):
        """Create new profile"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO profiles (
                name, email, experience_years, experience_level,
                core_skills, target_roles
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                name, email,
                resume_data.get('experience_years', '0-2'),
                resume_data.get('experience_level', 'junior'),
                json.dumps(resume_data.get('core_skills', [])),
                json.dumps(resume_data.get('target_roles', []))
            ))
            
            profile_id = cursor.lastrowid
            
            # Create default configs
            cursor.execute('INSERT INTO pre_filter_config (profile_id) VALUES (?)', (profile_id,))
            cursor.execute('INSERT INTO claude_filter_config (profile_id) VALUES (?)', (profile_id,))
            
            # ✅ NEW: Auto-populate API keys from environment
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            
            cursor.execute('''
            INSERT INTO api_keys (profile_id, anthropic_key, openrouter_key)
            VALUES (?, ?, ?)
            ''', (profile_id, anthropic_key, openrouter_key))
            
            conn.commit()
            return profile_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()
    
    def get_profile_by_id(self, profile_id):
        """Get profile by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE id = ?', (profile_id,))
        profile = cursor.fetchone()
        conn.close()
        
        if profile:
            return {
                'id': profile[0],
                'name': profile[1],
                'email': profile[2],
                'experience_years': profile[3],
                'experience_level': profile[4],
                'core_skills': json.loads(profile[5]) if profile[5] else [],
                'target_roles': json.loads(profile[6]) if profile[6] else [],
                'forbidden_keywords': json.loads(profile[7]) if profile[7] else [],
                'collection_time': profile[8],
                'timezone': profile[9],
                'auto_collect_enabled': bool(profile[10]),
                'last_collection_run': profile[11]
            }
        return None
    
    def get_profile_by_email(self, email):
        """Get profile by email"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE email = ?', (email,))
        profile = cursor.fetchone()
        conn.close()
        
        if profile:
            return {
                'id': profile[0],
                'name': profile[1],
                'email': profile[2]
            }
        return None
    
    # Filter config methods
    def get_pre_filter_config(self, profile_id):
        """Get pre-filter config"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pre_filter_config WHERE profile_id = ?', (profile_id,))
        config = cursor.fetchone()
        conn.close()
        
        if config:
            return {
                'max_years_experience': config[2],
                'reject_seniority_levels': json.loads(config[3]),
                'reject_job_types': json.loads(config[4]),
                'reject_specific_titles': json.loads(config[5]),
                'check_full_description': bool(config[6])
            }
        return None
    
    def update_pre_filter_config(self, profile_id, config):
        """Update pre-filter config"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE pre_filter_config SET
            max_years_experience = ?, reject_seniority_levels = ?,
            reject_job_types = ?, reject_specific_titles = ?,
            check_full_description = ?
        WHERE profile_id = ?
        ''', (
            config['max_years_experience'], json.dumps(config['reject_seniority_levels']),
            json.dumps(config['reject_job_types']), json.dumps(config['reject_specific_titles']),
            int(config['check_full_description']), profile_id
        ))
        conn.commit()
        conn.close()
    
    def create_default_pre_filter(self, profile_id):
        """Create default pre-filter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO pre_filter_config (profile_id) VALUES (?)', (profile_id,))
        conn.commit()
        conn.close()
    
    def get_claude_filter_config(self, profile_id):
        """Get Claude filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM claude_filter_config WHERE profile_id = ?', (profile_id,))
        config = cursor.fetchone()
        conn.close()
        
        if config:
            return {
                'strict_experience_check': bool(config[2]),
                'max_experience_required': config[3],
                'allow_preferred_experience': bool(config[4]),
                'min_skill_match_percent': config[5],
                'tier1_skill_threshold': config[6],
                'tier2_skill_threshold': config[7],
                'min_target_role_percentage': config[8],
                'accept_contract_to_hire': bool(config[9]),
                'accept_contract_w2': bool(config[10]),
                'reject_internships': bool(config[11]),
                'accept_part_time': bool(config[12]),
                'requires_visa_sponsorship': bool(config[13]),
                'reject_clearance_jobs': bool(config[14]),
                'accept_remote_only': bool(config[15]),
                'auto_reject_phrases': json.loads(config[16]),
                'custom_accept_employment': json.loads(config[17]) if len(config) > 17 else [],  # ✅ NEW
                'custom_reject_employment': json.loads(config[18]) if len(config) > 18 else []   # ✅ NEW
            }
        return None
    
    def update_claude_filter_config(self, profile_id, config):
        """Update Claude filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE claude_filter_config SET
            strict_experience_check = ?, max_experience_required = ?,
            allow_preferred_experience = ?, min_skill_match_percent = ?,
            tier1_skill_threshold = ?, tier2_skill_threshold = ?,
            min_target_role_percentage = ?, accept_contract_to_hire = ?,
            accept_contract_w2 = ?, reject_internships = ?,
            accept_part_time = ?, requires_visa_sponsorship = ?,
            reject_clearance_jobs = ?, accept_remote_only = ?,
            auto_reject_phrases = ?, custom_accept_employment = ?, custom_reject_employment = ?
        WHERE profile_id = ?
        ''', (
            int(config['strict_experience_check']), config['max_experience_required'],
            int(config['allow_preferred_experience']), config['min_skill_match_percent'],
            config['tier1_skill_threshold'], config['tier2_skill_threshold'],
            config['min_target_role_percentage'], int(config['accept_contract_to_hire']),
            int(config['accept_contract_w2']), int(config['reject_internships']),
            int(config['accept_part_time']), int(config['requires_visa_sponsorship']),
            int(config['reject_clearance_jobs']), int(config['accept_remote_only']),
            json.dumps(config['auto_reject_phrases']), 
            json.dumps(config.get('custom_accept_employment', [])),  # ✅ NEW
            json.dumps(config.get('custom_reject_employment', [])),  # ✅ NEW
            profile_id
        ))
        
        conn.commit()
        conn.close()
    
    def create_default_claude_filter(self, profile_id):
        """Create default Claude filter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO claude_filter_config (profile_id) VALUES (?)', (profile_id,))
        conn.commit()
        conn.close()
    
    # API keys
    def get_api_keys(self, profile_id):
        """Get API keys"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM api_keys WHERE profile_id = ?', (profile_id,))
        keys = cursor.fetchone()
        conn.close()
        
        if keys:
            return {
                'anthropic_key': keys[2],
                'jsearch_key': keys[3],
                'adzuna_id': keys[4],
                'adzuna_key': keys[5]
            }
        return {}
    
    def update_api_keys(self, profile_id, keys):
        """Update API keys"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE api_keys SET anthropic_key = ?, jsearch_key = ?, adzuna_id = ?, adzuna_key = ?
        WHERE profile_id = ?
        ''', (keys.get('anthropic_key'), keys.get('jsearch_key'),
              keys.get('adzuna_id'), keys.get('adzuna_key'), profile_id))
        conn.commit()
        conn.close()
    
    # Schedule
    def update_schedule_settings(self, profile_id, collection_time, auto_collect_enabled):
        """Update schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE profiles SET collection_time = ?, auto_collect_enabled = ?
        WHERE id = ?
        ''', (collection_time, int(auto_collect_enabled), profile_id))
        conn.commit()
        conn.close()
    
    # Jobs
    def save_raw_job(self, profile_id, job_data):
        """Save raw job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO raw_jobs (profile_id, job_id, company, title, url, location, description, source, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (profile_id, job_data['job_id'], job_data['company'], job_data['title'],
                  job_data['url'], job_data.get('location', ''), job_data.get('description', ''),
                  job_data.get('source', ''), 'pending'))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_jobs_last_24h(self, profile_id):
        """Get jobs from last 24h"""
        conn = self.get_connection()
        cursor = conn.cursor()
        yesterday = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        SELECT * FROM raw_jobs WHERE profile_id = ? AND status = 'pending'
        AND scraped_at >= ? ORDER BY scraped_at DESC
        ''', (profile_id, yesterday))
        jobs = cursor.fetchall()
        conn.close()
        
        return [{
            'id': job[0], 'job_id': job[2], 'company': job[3], 'title': job[4],
            'url': job[5], 'location': job[6], 'description': job[7],
            'source': job[8], 'scraped_at': job[9], 'status': job[10]
        } for job in jobs]
    
    def mark_job_rejected(self, job_id):
        """Mark job rejected"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE raw_jobs SET status = ? WHERE job_id = ?', ('rejected', job_id))
        conn.commit()
        conn.close()
    
    def save_analyzed_job(self, profile_id, job_id, analysis):
        """Save analyzed job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT company, title, url FROM raw_jobs WHERE job_id = ?', (job_id,))
        job = cursor.fetchone()
        
        if job:
            cursor.execute('''
            INSERT INTO analyzed_jobs (profile_id, job_id, company, title, url, tier, match_score,
            experience_required, role_match_pct, skill_match_pct, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (profile_id, job_id, job[0], job[1], job[2], analysis.get('tier'),
                  analysis.get('match_score'), analysis.get('experience_required_min'),
                  analysis.get('role_match_percentage'), analysis.get('core_skills_match_percent'),
                  analysis.get('final_reasoning')))
            
            cursor.execute('UPDATE raw_jobs SET status = ? WHERE job_id = ?', ('analyzed', job_id))
            conn.commit()
        conn.close()
    
    def get_analyzed_jobs(self, profile_id, tier=None):
        """Get analyzed jobs"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if tier:
            cursor.execute('''
            SELECT * FROM analyzed_jobs WHERE profile_id = ? AND tier = ?
            ORDER BY match_score DESC
            ''', (profile_id, tier))
        else:
            cursor.execute('''
            SELECT * FROM analyzed_jobs WHERE profile_id = ?
            ORDER BY tier ASC, match_score DESC
            ''', (profile_id,))
        
        jobs = cursor.fetchall()
        conn.close()
        
        return [{
            'id': job[0], 'job_id': job[2], 'company': job[3], 'title': job[4],
            'url': job[5], 'tier': job[6], 'match_score': job[7],
            'experience_required': job[8], 'role_match_pct': job[9],
            'skill_match_pct': job[10], 'reasoning': job[11], 'analyzed_at': job[12]
        } for job in jobs]
    
    def get_stats(self, profile_id):
        """Get stats"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM raw_jobs WHERE profile_id = ?', (profile_id,))
        total_jobs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = ?', (profile_id,))
        analyzed = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = ? AND tier = 1', (profile_id,))
        tier1 = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = ? AND tier = 2', (profile_id,))
        tier2 = cursor.fetchone()[0]
        
        conn.close()
        
        return {'total_jobs': total_jobs, 'analyzed': analyzed, 'tier1': tier1, 'tier2': tier2}