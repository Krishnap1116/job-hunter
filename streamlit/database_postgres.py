# database_postgres.py - PostgreSQL Database Manager for Cloud Deployment

import os
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

class JobHunterDB:
    def __init__(self):
        """Initialize database connection and setup"""
        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise Exception("DATABASE_URL not found in environment variables")
        
        # Fix Heroku/Render postgres:// URL format
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        # Parse URL
        result = urlparse(self.database_url)
        self.db_config = {
            'host': result.hostname,
            'port': result.port or 5432,
            'database': result.path[1:],
            'user': result.username,
            'password': result.password,
            'sslmode': 'require'
        }
        
        # Step 1: Create tables if they don't exist
        self.init_database()
        
        # Step 2: Add any missing columns (for future updates)
        self.migrate_database()
        
        # Step 3: Clean up old data to save storage
        self.cleanup_old_jobs(days=7)
        
        print("✅ PostgreSQL database ready")
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # User profiles with scheduling
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            experience_years TEXT,
            experience_level TEXT,
            core_skills TEXT,
            target_roles TEXT,
            forbidden_keywords TEXT,
            
            collection_time TEXT DEFAULT '09:00',
            timezone TEXT DEFAULT 'America/New_York',
            auto_collect_enabled BOOLEAN DEFAULT TRUE,
            last_collection_run TIMESTAMP,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # PRE-FILTER settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pre_filter_config (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
            
            max_years_experience INTEGER DEFAULT 4,
            reject_seniority_levels TEXT DEFAULT '["senior","staff","principal","lead","manager","director","vp","head of","chief"]',
            reject_job_types TEXT DEFAULT '["internship","intern","part-time","freelance","contractor"]',
            reject_specific_titles TEXT DEFAULT '["business analyst","data analyst","support engineer","technical writer","project manager","sales engineer"]',
            check_full_description BOOLEAN DEFAULT TRUE
        )
        ''')
        
        # CLAUDE ANALYSIS settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS claude_filter_config (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
            
            strict_experience_check BOOLEAN DEFAULT TRUE,
            max_experience_required INTEGER DEFAULT 4,
            allow_preferred_experience BOOLEAN DEFAULT TRUE,
            
            min_skill_match_percent INTEGER DEFAULT 65,
            tier1_skill_threshold INTEGER DEFAULT 85,
            tier2_skill_threshold INTEGER DEFAULT 65,
            
            min_target_role_percentage INTEGER DEFAULT 70,
            
            accept_contract_to_hire BOOLEAN DEFAULT TRUE,
            accept_contract_w2 BOOLEAN DEFAULT FALSE,
            reject_internships BOOLEAN DEFAULT TRUE,
            accept_part_time BOOLEAN DEFAULT FALSE,
            
            requires_visa_sponsorship BOOLEAN DEFAULT TRUE,
            reject_clearance_jobs BOOLEAN DEFAULT TRUE,
            accept_remote_only BOOLEAN DEFAULT FALSE,
            
            auto_reject_phrases TEXT DEFAULT '["us citizen only","security clearance required","no visa sponsorship"]',
            custom_accept_employment TEXT DEFAULT '[]',
            custom_reject_employment TEXT DEFAULT '[]'
        )
        ''')
        
        # Raw jobs (scraped, waiting for analysis)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_jobs (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
            job_id TEXT UNIQUE,
            company TEXT,
            title TEXT,
            url TEXT,
            location TEXT,
            description TEXT,
            source TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
        ''')
        
        # Analyzed jobs (matched and displayed to user)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyzed_jobs (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
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
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # API keys
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
            anthropic_key TEXT,
            openrouter_key TEXT,
            jsearch_key TEXT,
            adzuna_id TEXT,
            adzuna_key TEXT
        )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_jobs_profile_status ON raw_jobs(profile_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_jobs_scraped ON raw_jobs(scraped_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyzed_jobs_profile ON analyzed_jobs(profile_id, analyzed_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyzed_jobs_tier ON analyzed_jobs(profile_id, tier, match_score)')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ PostgreSQL database initialized")
    def migrate_database(self):
        """Migrate database to add new columns if they don't exist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if custom employment columns exist
            cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'claude_filter_config'
            """)
            
            columns = [row[0] for row in cursor.fetchall()]
            
            # Add custom_accept_employment if missing
            if 'custom_accept_employment' not in columns:
                cursor.execute("""
                ALTER TABLE claude_filter_config 
                ADD COLUMN custom_accept_employment TEXT DEFAULT '[]'
                """)
                print("✅ Added custom_accept_employment column")
            
            # Add custom_reject_employment if missing
            if 'custom_reject_employment' not in columns:
                cursor.execute("""
                ALTER TABLE claude_filter_config 
                ADD COLUMN custom_reject_employment TEXT DEFAULT '[]'
                """)
                print("✅ Added custom_reject_employment column")
            
            conn.commit()
            
        except Exception as e:
            print(f"⚠️ Migration error: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    def cleanup_old_jobs(self, days=7):
        """Delete analyzed jobs older than X days to save storage"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Delete old analyzed jobs
            cursor.execute('''
            DELETE FROM analyzed_jobs 
            WHERE analyzed_at < %s
            ''', (cutoff_date,))
            
            deleted_analyzed = cursor.rowcount
            
            # Delete old raw jobs (keep only last 30 days)
            raw_cutoff = datetime.now() - timedelta(days=30)
            cursor.execute('''
            DELETE FROM raw_jobs 
            WHERE scraped_at < %s AND status != 'pending'
            ''', (raw_cutoff,))
            
            deleted_raw = cursor.rowcount
            
            conn.commit()
            
            if deleted_analyzed > 0 or deleted_raw > 0:
                print(f"🧹 Cleanup: Deleted {deleted_analyzed} analyzed jobs, {deleted_raw} old raw jobs")
            
            return deleted_analyzed, deleted_raw
            
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            conn.rollback()
            return 0, 0
        finally:
            cursor.close()
            conn.close()
    
    # ==================== PROFILE METHODS ====================
    
    def create_profile(self, name, email, resume_data):
        """Create new profile"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO profiles (name, email, experience_years, experience_level, core_skills, target_roles)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (
                name, email,
                resume_data.get('experience_years', '0-2'),
                resume_data.get('experience_level', 'junior'),
                json.dumps(resume_data.get('core_skills', [])),
                json.dumps(resume_data.get('target_roles', []))
            ))
            
            profile_id = cursor.fetchone()[0]
            
            # Create default configs
            cursor.execute('INSERT INTO pre_filter_config (profile_id) VALUES (%s)', (profile_id,))
            cursor.execute('INSERT INTO claude_filter_config (profile_id) VALUES (%s)', (profile_id,))
            
            # Auto-populate API keys from environment
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            cursor.execute('''
            INSERT INTO api_keys (profile_id, anthropic_key, openrouter_key)
            VALUES (%s, %s, %s)
            ''', (profile_id, anthropic_key, openrouter_key))
            
            conn.commit()
            return profile_id
            
        except psycopg2.IntegrityError:
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_profile_by_email(self, email):
        """Get profile by email"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT id, name, email FROM profiles WHERE email = %s', (email,))
        profile = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return dict(profile) if profile else None
    
    def get_profile_by_id(self, profile_id):
        """Get profile by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM profiles WHERE id = %s', (profile_id,))
        profile = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if profile:
            profile_dict = dict(profile)
            profile_dict['core_skills'] = json.loads(profile_dict['core_skills']) if profile_dict.get('core_skills') else []
            profile_dict['target_roles'] = json.loads(profile_dict['target_roles']) if profile_dict.get('target_roles') else []
            profile_dict['forbidden_keywords'] = json.loads(profile_dict['forbidden_keywords']) if profile_dict.get('forbidden_keywords') else []
            return profile_dict
        
        return None
    
    # ==================== FILTER CONFIG METHODS ====================
    
    def get_pre_filter_config(self, profile_id):
        """Get pre-filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM pre_filter_config WHERE profile_id = %s', (profile_id,))
        config = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if config:
            config_dict = dict(config)
            config_dict['reject_seniority_levels'] = json.loads(config_dict['reject_seniority_levels'])
            config_dict['reject_job_types'] = json.loads(config_dict['reject_job_types'])
            config_dict['reject_specific_titles'] = json.loads(config_dict['reject_specific_titles'])
            return config_dict
        
        return None
    
    def update_pre_filter_config(self, profile_id, config):
        """Update pre-filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE pre_filter_config SET
            max_years_experience = %s,
            reject_seniority_levels = %s,
            reject_job_types = %s,
            reject_specific_titles = %s,
            check_full_description = %s
        WHERE profile_id = %s
        ''', (
            config['max_years_experience'],
            json.dumps(config['reject_seniority_levels']),
            json.dumps(config['reject_job_types']),
            json.dumps(config['reject_specific_titles']),
            config['check_full_description'],
            profile_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def create_default_pre_filter(self, profile_id):
        """Create default pre-filter config"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO pre_filter_config (profile_id) VALUES (%s)', (profile_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_claude_filter_config(self, profile_id):
        """Get Claude filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM claude_filter_config WHERE profile_id = %s', (profile_id,))
        config = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if config:
            config_dict = dict(config)
            config_dict['auto_reject_phrases'] = json.loads(config_dict['auto_reject_phrases'])
            config_dict['custom_accept_employment'] = json.loads(config_dict.get('custom_accept_employment', '[]'))
            config_dict['custom_reject_employment'] = json.loads(config_dict.get('custom_reject_employment', '[]'))
            return config_dict
        
        return None
    
    def update_claude_filter_config(self, profile_id, config):
        """Update Claude filter configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE claude_filter_config SET
            strict_experience_check = %s, max_experience_required = %s,
            allow_preferred_experience = %s, min_skill_match_percent = %s,
            tier1_skill_threshold = %s, tier2_skill_threshold = %s,
            min_target_role_percentage = %s, accept_contract_to_hire = %s,
            accept_contract_w2 = %s, reject_internships = %s,
            accept_part_time = %s, requires_visa_sponsorship = %s,
            reject_clearance_jobs = %s, accept_remote_only = %s,
            auto_reject_phrases = %s, custom_accept_employment = %s,
            custom_reject_employment = %s
        WHERE profile_id = %s
        ''', (
            config['strict_experience_check'], config['max_experience_required'],
            config['allow_preferred_experience'], config['min_skill_match_percent'],
            config['tier1_skill_threshold'], config['tier2_skill_threshold'],
            config['min_target_role_percentage'], config['accept_contract_to_hire'],
            config['accept_contract_w2'], config['reject_internships'],
            config['accept_part_time'], config['requires_visa_sponsorship'],
            config['reject_clearance_jobs'], config['accept_remote_only'],
            json.dumps(config['auto_reject_phrases']),
            json.dumps(config.get('custom_accept_employment', [])),
            json.dumps(config.get('custom_reject_employment', [])),
            profile_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def create_default_claude_filter(self, profile_id):
        """Create default Claude filter config"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO claude_filter_config (profile_id) VALUES (%s)', (profile_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    # ==================== API KEYS METHODS ====================
    
    def get_api_keys(self, profile_id):
        """Get API keys"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM api_keys WHERE profile_id = %s', (profile_id,))
        keys = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return dict(keys) if keys else {}
    
    def update_api_keys(self, profile_id, keys):
        """Update API keys"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE api_keys SET 
            anthropic_key = %s, openrouter_key = %s,
            jsearch_key = %s, adzuna_id = %s, adzuna_key = %s
        WHERE profile_id = %s
        ''', (
            keys.get('anthropic_key'), keys.get('openrouter_key'),
            keys.get('jsearch_key'), keys.get('adzuna_id'), 
            keys.get('adzuna_key'), profile_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    # ==================== SCHEDULE METHODS ====================
    
    def update_schedule_settings(self, profile_id, collection_time, auto_collect_enabled):
        """Update schedule settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE profiles SET collection_time = %s, auto_collect_enabled = %s
        WHERE id = %s
        ''', (collection_time, auto_collect_enabled, profile_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    # ==================== JOBS METHODS ====================
    
    def save_raw_job(self, profile_id, job_data):
        """Save raw job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO raw_jobs (profile_id, job_id, company, title, url, location, description, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                profile_id, job_data['job_id'], job_data['company'], job_data['title'],
                job_data['url'], job_data.get('location', ''), job_data.get('description', ''),
                job_data.get('source', ''), 'pending'
            ))
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_jobs_last_24h(self, profile_id):
        """Get jobs from last 24 hours"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        yesterday = datetime.now() - timedelta(hours=24)
        
        cursor.execute('''
        SELECT * FROM raw_jobs 
        WHERE profile_id = %s AND status = 'pending' AND scraped_at >= %s
        ORDER BY scraped_at DESC
        ''', (profile_id, yesterday))
        
        jobs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return [dict(job) for job in jobs]
    
    def mark_job_rejected(self, job_id):
        """Mark job as rejected"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE raw_jobs SET status = %s WHERE job_id = %s', ('rejected', job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def save_analyzed_job(self, profile_id, job_id, analysis):
        """Save analyzed job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get job details
        cursor.execute('SELECT company, title, url FROM raw_jobs WHERE job_id = %s', (job_id,))
        job = cursor.fetchone()
        
        if job:
            cursor.execute('''
            INSERT INTO analyzed_jobs (
                profile_id, job_id, company, title, url, tier, match_score,
                experience_required, role_match_pct, skill_match_pct, reasoning
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                profile_id, job_id, job[0], job[1], job[2],
                analysis.get('tier'), analysis.get('match_score'),
                analysis.get('experience_required_min'),
                analysis.get('role_match_percentage'),
                analysis.get('core_skills_match_percent'),
                analysis.get('final_reasoning')
            ))
            
            cursor.execute('UPDATE raw_jobs SET status = %s WHERE job_id = %s', ('analyzed', job_id))
            
            conn.commit()
        
        cursor.close()
        conn.close()
    
    def get_analyzed_jobs(self, profile_id, tier=None):
        """Get analyzed jobs"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if tier:
            cursor.execute('''
            SELECT * FROM analyzed_jobs 
            WHERE profile_id = %s AND tier = %s
            ORDER BY match_score DESC
            ''', (profile_id, tier))
        else:
            cursor.execute('''
            SELECT * FROM analyzed_jobs 
            WHERE profile_id = %s
            ORDER BY tier ASC, match_score DESC
            ''', (profile_id,))
        
        jobs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return [dict(job) for job in jobs]
    
    def get_stats(self, profile_id):
        """Get statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM raw_jobs WHERE profile_id = %s', (profile_id,))
        total_jobs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = %s', (profile_id,))
        analyzed = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = %s AND tier = 1', (profile_id,))
        tier1 = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analyzed_jobs WHERE profile_id = %s AND tier = 2', (profile_id,))
        tier2 = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            'total_jobs': total_jobs,
            'analyzed': analyzed,
            'tier1': tier1,
            'tier2': tier2
        }