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
        
        # Cleanup runs via GitHub Actions daily_collect.py, not on every startup
        # Running DELETE on every app boot causes deadlocks with concurrent sessions
        print("PostgreSQL database ready")
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def init_database(self):
        """Initialize all database tables.
        Each statement runs in its own try/except so a deadlock on one
        index does not roll back the entire table-creation block.
        """
        ddl_statements = [
            # Tables
            '''CREATE TABLE IF NOT EXISTS profiles (
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
                job_lookback_hours INTEGER DEFAULT 24,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS pre_filter_config (
                id SERIAL PRIMARY KEY,
                profile_id INTEGER UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
                max_years_experience INTEGER DEFAULT 4,
                reject_seniority_levels TEXT DEFAULT '["senior","staff","principal","lead","manager","director","vp","head of","chief"]',
                reject_job_types TEXT DEFAULT '["internship","intern","part-time","freelance","contractor"]',
                reject_specific_titles TEXT DEFAULT '["business analyst","data analyst","support engineer","technical writer","project manager","sales engineer"]',
                check_full_description BOOLEAN DEFAULT TRUE
            )''',
            '''CREATE TABLE IF NOT EXISTS claude_filter_config (
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
            )''',
            '''CREATE TABLE IF NOT EXISTS global_raw_jobs (
                id         SERIAL PRIMARY KEY,
                job_id     TEXT UNIQUE,
                company    TEXT,
                title      TEXT,
                url        TEXT,
                location   TEXT,
                description TEXT,
                source     TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS user_job_status (
                id         SERIAL PRIMARY KEY,
                profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
                job_id     TEXT,
                status     TEXT DEFAULT 'pending',
                UNIQUE(profile_id, job_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS raw_jobs (
                id SERIAL PRIMARY KEY,
                profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
                job_id TEXT UNIQUE,
                company TEXT, title TEXT, url TEXT,
                location TEXT, description TEXT, source TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )''',
            '''CREATE TABLE IF NOT EXISTS analyzed_jobs (
                id SERIAL PRIMARY KEY,
                profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
                job_id TEXT, company TEXT, title TEXT, url TEXT,
                tier INTEGER, match_score INTEGER,
                experience_required INTEGER,
                role_match_pct INTEGER, skill_match_pct INTEGER,
                reasoning TEXT,
                tailored_bullets TEXT DEFAULT '[]',
                applied INTEGER DEFAULT 0,
                applied_at TIMESTAMP,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, job_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                profile_id INTEGER UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
                anthropic_key TEXT, openrouter_key TEXT,
                jsearch_key TEXT, adzuna_id TEXT, adzuna_key TEXT
            )''',
        ]

        # Index statements — run separately, each in its own transaction
        # CONCURRENTLY avoids locking the table; IF NOT EXISTS avoids errors on retry
        index_statements = [
            'CREATE INDEX IF NOT EXISTS idx_raw_jobs_profile_status ON raw_jobs(profile_id, status)',
            'CREATE INDEX IF NOT EXISTS idx_raw_jobs_scraped ON raw_jobs(scraped_at)',
            'CREATE INDEX IF NOT EXISTS idx_analyzed_jobs_profile ON analyzed_jobs(profile_id, analyzed_at)',
            'CREATE INDEX IF NOT EXISTS idx_analyzed_jobs_tier ON analyzed_jobs(profile_id, tier, match_score)',
            'CREATE INDEX IF NOT EXISTS idx_global_jobs_scraped ON global_raw_jobs(scraped_at)',
            'CREATE INDEX IF NOT EXISTS idx_user_job_status ON user_job_status(profile_id, job_id)',
        ]

        # Step 1: Create all tables in one transaction
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for stmt in ddl_statements:
                cursor.execute(stmt)
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            print(f"Table creation error: {e}")
        finally:
            conn.close()

        # Step 2: Create each index in its own transaction
        # If one deadlocks or already exists, the others still succeed
        for stmt in index_statements:
            conn = self.get_connection()
            try:
                conn.autocommit = True   # required for CREATE INDEX CONCURRENTLY
                cursor = conn.cursor()
                # Convert to CONCURRENTLY — safe when autocommit=True
                safe_stmt = stmt.replace(
                    'CREATE INDEX IF NOT EXISTS',
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS'
                )
                cursor.execute(safe_stmt)
                cursor.close()
            except Exception as e:
                print(f"Index warning (non-fatal): {e}")
            finally:
                conn.close()

        print("PostgreSQL database initialized")
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

            # Add tailored_bullets to analyzed_jobs if missing
            cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'analyzed_jobs'
            """)
            aj_columns = [row[0] for row in cursor.fetchall()]
            if 'tailored_bullets' not in aj_columns:
                cursor.execute("""
                ALTER TABLE analyzed_jobs
                ADD COLUMN tailored_bullets TEXT DEFAULT '[]'
                """)
                print("✅ Added tailored_bullets column")

            # Add job_lookback_hours to profiles if missing
            cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'profiles'
            """)
            prof_columns = [row[0] for row in cursor.fetchall()]
            # Drop FK constraint on analyzed_jobs(job_id) → raw_jobs if it exists
            # Jobs now come from global_raw_jobs, so this FK breaks inserts
            cursor.execute("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'analyzed_jobs'
                AND constraint_type = 'FOREIGN KEY'
            """)
            fk_constraints = [r[0] for r in cursor.fetchall()]
            for fk in fk_constraints:
                # Only drop the job_id FK, not the profile_id one
                try:
                    cursor.execute(f"""
                        SELECT column_name FROM information_schema.key_column_usage
                        WHERE constraint_name = '{fk}' AND table_name = 'analyzed_jobs'
                    """)
                    cols = [r[0] for r in cursor.fetchall()]
                    if cols == ['job_id']:
                        cursor.execute(f'ALTER TABLE analyzed_jobs DROP CONSTRAINT {fk}')
                        print(f"Dropped FK constraint {fk} from analyzed_jobs")
                except Exception as e:
                    print(f"FK drop warning: {e}")

            # Add UNIQUE constraint to analyzed_jobs if missing
            cursor.execute("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'analyzed_jobs' AND constraint_type = 'UNIQUE'
            """)
            if not cursor.fetchone():
                try:
                    cursor.execute("""
                        ALTER TABLE analyzed_jobs
                        ADD CONSTRAINT analyzed_jobs_profile_job_unique
                        UNIQUE (profile_id, job_id)
                    """)
                    print("Added UNIQUE constraint to analyzed_jobs")
                except Exception:
                    pass  # already exists under different name

            if 'job_lookback_hours' not in prof_columns:
                cursor.execute("ALTER TABLE profiles ADD COLUMN job_lookback_hours INTEGER DEFAULT 24")
                print("✅ Added job_lookback_hours column")

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
            jsearch_key = os.getenv("JSEARCH_API_KEY")  # ← ADD
            adzuna_id = os.getenv("ADZUNA_APP_ID")      # ← ADD
            adzuna_key = os.getenv("ADZUNA_API_KEY")
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
    


    def update_profile_roles_skills(self, profile_id, target_roles, core_skills):
        """Let users edit their target roles and skills from the Settings UI."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE profiles SET target_roles = %s, core_skills = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (json.dumps(target_roles), json.dumps(core_skills), profile_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get_all_target_roles(self):
        """Return the union of target_roles across all user profiles.
        Used by daily_collect.py so the shared pool covers every user's needs.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT target_roles FROM profiles WHERE target_roles IS NOT NULL')
        rows = cursor.fetchall()
        conn.close()

        import json
        seen = set()
        roles = []
        for row in rows:
            try:
                user_roles = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or [])
                for r in user_roles:
                    r_clean = r.strip().lower()
                    if r_clean and r_clean not in seen:
                        seen.add(r_clean)
                        roles.append(r.strip())
            except Exception:
                pass
        return roles

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
    
    def set_last_analyzed(self, profile_id):
        """Record that analysis was just run for this user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE profiles SET last_analyzed_at = CURRENT_TIMESTAMP WHERE id = %s',
            (profile_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get_last_analyzed(self, profile_id):
        """Return last_analyzed_at timestamp string, or None."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT last_analyzed_at FROM profiles WHERE id = %s', (profile_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return str(row[0]) if row and row[0] else None


    def get_job_lookback_hours(self, profile_id):
        """Return how many hours back to look for new jobs for this user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT job_lookback_hours FROM profiles WHERE id = %s', (profile_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row[0]:
            return int(row[0])
        return 24  # default

    def set_job_lookback_hours(self, profile_id, hours):
        """Save the user's preferred lookback window."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE profiles SET job_lookback_hours = %s WHERE id = %s',
            (hours, profile_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

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

    # ─────────────────────────────────────────
    # Global job pool (shared across all users)
    # ─────────────────────────────────────────

    def save_global_job(self, job_data):
        """Save a job to the shared global pool. Returns True if new, False if duplicate."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO global_raw_jobs (job_id, company, title, url, location, description, source, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (job_id) DO NOTHING
            ''', (
                job_data['job_id'], job_data['company'], job_data['title'],
                job_data['url'], job_data.get('location', ''),
                job_data.get('description', ''), job_data.get('source', ''),
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"save_global_job error: {e}")
            return False
        finally:
            conn.close()

    def get_global_jobs_for_user(self, profile_id, hours=24):
        """Get global jobs not yet analyzed or rejected by this user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(hours=hours)
        cursor.execute('''
            SELECT g.* FROM global_raw_jobs g
            WHERE g.scraped_at >= %s
            AND NOT EXISTS (
                SELECT 1 FROM user_job_status u
                WHERE u.profile_id = %s AND u.job_id = g.job_id
            )
            ORDER BY g.scraped_at DESC
        ''', (cutoff, profile_id))
        rows = cursor.fetchall()
        conn.close()
        return [{
            'id': r[0], 'job_id': r[1], 'company': r[2], 'title': r[3],
            'url': r[4], 'location': r[5], 'description': r[6],
            'source': r[7], 'scraped_at': str(r[8]), 'status': 'pending'
        } for r in rows]

    def mark_global_job_status(self, profile_id, job_id, status):
        """Mark a global job as analyzed/rejected for this user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO user_job_status (profile_id, job_id, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (profile_id, job_id) DO UPDATE SET status = EXCLUDED.status
            ''', (profile_id, job_id, status))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"mark_global_job_status error: {e}")
        finally:
            conn.close()

    def get_global_pool_stats(self):
        """How many jobs in the pool and when last scraped."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), MAX(scraped_at) FROM global_raw_jobs')
        row = cursor.fetchone()
        conn.close()
        return {'total': row[0] or 0, 'last_scraped': str(row[1]) if row[1] else None}

    def purge_old_global_jobs(self, days=7):
        """Remove global jobs older than N days."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute('DELETE FROM global_raw_jobs WHERE scraped_at < %s', (cutoff,))
        cursor.execute('DELETE FROM user_job_status WHERE job_id NOT IN (SELECT job_id FROM global_raw_jobs)')
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

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
        """Save analyzed job — looks up details from global_raw_jobs (primary)
        then falls back to legacy raw_jobs table."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Try global_raw_jobs first (current architecture)
        cursor.execute('SELECT company, title, url FROM global_raw_jobs WHERE job_id = %s', (job_id,))
        job = cursor.fetchone()

        # Fall back to legacy raw_jobs
        if not job:
            cursor.execute('SELECT company, title, url FROM raw_jobs WHERE job_id = %s', (job_id,))
            job = cursor.fetchone()

        if job:
            # Use ON CONFLICT so re-runs don't create duplicates
            cursor.execute('''
            INSERT INTO analyzed_jobs (
                profile_id, job_id, company, title, url, tier, match_score,
                experience_required, role_match_pct, skill_match_pct, reasoning,
                tailored_bullets
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (profile_id, job_id) DO UPDATE SET
                tier             = EXCLUDED.tier,
                match_score      = EXCLUDED.match_score,
                experience_required = EXCLUDED.experience_required,
                role_match_pct   = EXCLUDED.role_match_pct,
                skill_match_pct  = EXCLUDED.skill_match_pct,
                reasoning        = EXCLUDED.reasoning,
                tailored_bullets = EXCLUDED.tailored_bullets,
                analyzed_at      = CURRENT_TIMESTAMP
            ''', (
                profile_id, job_id, job[0], job[1], job[2],
                analysis.get('tier'), analysis.get('match_score'),
                analysis.get('experience_required_min'),
                analysis.get('role_match_percentage'),
                analysis.get('core_skills_match_percent'),
                analysis.get('final_reasoning'),
                json.dumps(analysis.get('tailored_bullets', []))
            ))
            conn.commit()
        else:
            print(f"Warning: job_id {job_id} not found in global_raw_jobs or raw_jobs — skipping save")

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
        
        result = []
        for job in jobs:
            job_dict = dict(job)
            # Parse tailored_bullets from JSON string back to list
            raw_bullets = job_dict.get('tailored_bullets', '[]')
            if isinstance(raw_bullets, str):
                try:
                    job_dict['tailored_bullets'] = json.loads(raw_bullets)
                except Exception:
                    job_dict['tailored_bullets'] = []
            result.append(job_dict)
        return result
    
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