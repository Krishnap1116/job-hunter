# app.py - Complete Self-Service Platform with Scheduling

import streamlit as st
import tempfile
import time
from datetime import datetime, timedelta
import threading
# import schedule

# from database import JobHunterDB
from database_manager import JobHunterDB
from resume_parser import parse_resume_with_claude
from job_scraper_integrated import IntegratedScraper
from job_matcher_integrated import IntegratedMatcher

import streamlit as st
import hmac

def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["app_password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # Return True if password is already validated
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    
    return False

# Check password before showing app
if not check_password():
    st.stop() 
# Page config
st.set_page_config(
    page_title="AI Job Hunter",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .info-box {
        padding: 1rem;
        border-radius: 10px;
        background: #e8f4f8;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 10px;
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
db = JobHunterDB()

# Session state
if 'profile_id' not in st.session_state:
    st.session_state.profile_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'setup'

# Sidebar
with st.sidebar:
    st.title("🎯 Job Hunter")
    st.markdown("---")
    
    if st.session_state.profile_id:
        profile = db.get_profile_by_id(st.session_state.profile_id)
        
        st.success(f"**{profile['name']}**")
        st.caption(f"📧 {profile['email']}")
        
        st.markdown("---")
        
        # Navigation
        page = st.radio("**Navigate**", [
            "📊 Dashboard",
            "⚙️ Settings",
            "🤖 Analyze Jobs",
            "🎯 View Matches"
        ], label_visibility="collapsed")
        
        st.session_state.page = page
        
        st.markdown("---")
        
        # Schedule status
        # if profile.get('auto_collect_enabled'):
        #     st.success(f"⏰ Auto-collect: {profile.get('collection_time', '09:00')}")
        # else:
        #     st.warning("⏰ Auto-collect: OFF")
        
        st.markdown("---")
        
        if st.button("🚪 Logout"):
            st.session_state.profile_id = None
            st.rerun()

# Main content
if st.session_state.profile_id is None:
    # ============= SETUP PAGE (ONE-TIME) =============
    st.markdown('<h1 class="main-header">🎯 AI Job Hunter</h1>', unsafe_allow_html=True)
    st.markdown("**One-time setup • Automated daily collection • AI-powered matching**")
    
    tab1, tab2 = st.tabs(["📝 Create Profile", "🔑 Login"])
    
    with tab1:
        st.subheader("Step 1: Upload Resume")
        
        uploaded_file = st.file_uploader(
            "Upload Resume (PDF)",
            type=['pdf'],
            help="Upload your resume to auto-extract your profile"
        )
        
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(uploaded_file.read())
                resume_path = tmp.name
            
            if 'resume_parsed' not in st.session_state:
                with st.spinner("🤖 Analyzing resume with Claude..."):
                    profile_data = parse_resume_with_claude(resume_path)
                    
                    if profile_data:
                        st.session_state.resume_parsed = True
                        st.session_state.temp_profile = profile_data
                        st.success("✅ Resume parsed successfully!")
                    else:
                        st.error("❌ Failed to parse resume")
        
        if 'temp_profile' in st.session_state:
            st.markdown("---")
            st.subheader("Step 2: Confirm Your Profile")
            
            profile = st.session_state.temp_profile
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name", value=profile.get('name', ''))
                email = st.text_input("Email", placeholder="your.email@example.com")
            
            with col2:
                st.write("**Experience:**", profile.get('experience_years', 'N/A'))
                st.write("**Level:**", profile.get('experience_level', 'N/A'))
            
            with st.expander("🎯 Target Roles"):
                st.write(", ".join(profile.get('target_roles', [])))
            
            with st.expander("💡 Core Skills"):
                skills = profile.get('core_skills', [])
                st.write(", ".join(skills[:20]))
                if len(skills) > 20:
                    st.caption(f"...and {len(skills) - 20} more")
            
            st.markdown("---")
            
            if st.button("✅ Continue to Setup", type="primary", use_container_width=True):
                if not email:
                    st.error("Please enter your email")
                else:
                    profile_id = db.create_profile(name, email, profile)
                    
                    if profile_id:
                        st.session_state.profile_id = profile_id
                        st.session_state.page = "⚙️ Settings"
                        st.session_state.show_setup_wizard = True
                        del st.session_state.resume_parsed
                        del st.session_state.temp_profile
                        st.success("✅ Profile created! Please complete setup...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Email already exists. Try logging in instead.")
    
    with tab2:
        st.subheader("Login")
        
        email = st.text_input("Email Address")
        
        if st.button("🔓 Login", type="primary", use_container_width=True):
            profile = db.get_profile_by_email(email)
            
            if profile:
                st.session_state.profile_id = profile['id']
                st.success("✅ Logged in!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Profile not found")

else:
    # ============= LOGGED IN =============
    profile_id = st.session_state.profile_id
    profile = db.get_profile_by_id(profile_id)
    api_keys = db.get_api_keys(profile_id)
    
    # ============= DASHBOARD =============
    if st.session_state.page == "📊 Dashboard":
        st.title("📊 Dashboard")
        
        stats = db.get_stats(profile_id)
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📥 Total Scraped", stats['total_jobs'])
        with col2:
            pending_24h = len(db.get_jobs_last_24h(profile_id))
            st.metric("⏰ Last 24h (Pending)", pending_24h)
        with col3:
            st.metric("🌟 Tier 1", stats['tier1'])
        with col4:
            st.metric("⭐ Tier 2", stats['tier2'])
        
        st.markdown("---")
        
        # Setup status
        pre_filter = db.get_pre_filter_config(profile_id)
        claude_filter = db.get_claude_filter_config(profile_id)
        
        setup_complete = all([
            api_keys.get('anthropic_key'),
            pre_filter is not None,
            claude_filter is not None
        ])
        
        if not setup_complete:
            st.markdown('<div class="warning-box">', unsafe_allow_html=True)
            st.warning("⚠️ **Setup Incomplete**")
            st.write("Please complete the following:")
            
            if not api_keys.get('anthropic_key'):
                st.write("• ❌ Add Anthropic API key in Settings")
            if not pre_filter:
                st.write("• ❌ Configure filters in Settings")
            
            if st.button("⚙️ Go to Settings"):
                st.session_state.page = "⚙️ Settings"
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # Quick actions
            st.subheader("⚡ Quick Actions")
            
            col1, col2 = st.columns(2)
            
            with col1:
                pending = len(db.get_jobs_last_24h(profile_id))
                if pending > 0:
                    if st.button(f"🤖 Analyze {pending} Jobs", type="primary", use_container_width=True):
                        st.session_state.page = "🤖 Analyze Jobs"
                        st.rerun()
                else:
                    st.info("No jobs to analyze from last 24 hours")
            
            with col2:
                if stats['tier1'] + stats['tier2'] > 0:
                    if st.button(f"🎯 View {stats['tier1'] + stats['tier2']} Matches", use_container_width=True):
                        st.session_state.page = "🎯 View Matches"
                        st.rerun()
                else:
                    st.info("No matches yet")
            
            st.markdown("---")
            
            # Schedule info
            # st.subheader("📅 Collection Schedule")
            
            # if profile.get('auto_collect_enabled'):
            #     st.markdown('<div class="info-box">', unsafe_allow_html=True)
            #     st.write(f"✅ **Auto-collection enabled**")
            #     st.write(f"⏰ Daily at: **{profile.get('collection_time', '09:00')}**")
            #     st.write(f"📡 Last run: {profile.get('last_collection_run', 'Never')}")
            #     st.markdown('</div>', unsafe_allow_html=True)
            # else:
            #     st.warning("⏰ Auto-collection is disabled. Enable in Settings.")
            # Collection info
            st.subheader("📅 Job Collection")
            st.info("💡 **Tip:** Go to Settings → Collect Jobs to manually scrape new jobs anytime!")
    
    # ============= SETTINGS (COMPLETE SETUP) =============
    elif st.session_state.page == "⚙️ Settings":
        st.title("⚙️ Settings")
        
        # Show wizard for new users
        if st.session_state.get('show_setup_wizard'):
            st.info("👋 **Welcome! Let's complete your setup in 3 steps**")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 Pre-Filters",
            "🤖 AI Filters",
            "🔍 Collect Jobs",
            "👤 Profile"
        ])
        
        # ===== TAB 1: API KEYS =====
        # with tab1:
        #     st.subheader("🔑 API Keys")
            
        #     st.markdown('<div class="warning-box">', unsafe_allow_html=True)
        #     st.warning("⚠️ **Required:** Anthropic API key is needed for job analysis")
        #     st.markdown("Get your key from: https://console.anthropic.com/")
        #     st.markdown('</div>', unsafe_allow_html=True)
            
        #     anthropic_key = st.text_input(
        #         "Anthropic API Key (Required)",
        #         value=api_keys.get('anthropic_key') or '',
        #         type="password",
        #         help="Used for AI-powered job matching"
        #     )
            
        #     st.markdown("---")
        #     st.subheader("Optional: Job Board APIs")
        #     st.caption("Add these to collect more jobs. Leave blank to use free sources only.")
            
        #     col1, col2 = st.columns(2)
            
        #     with col1:
        #         jsearch_key = st.text_input(
        #             "JSearch API Key",
        #             value=api_keys.get('jsearch_key') or '',
        #             type="password",
        #             help="Get from: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch"
        #         )
            
        #     with col2:
        #         adzuna_id = st.text_input(
        #             "Adzuna App ID",
        #             value=api_keys.get('adzuna_id') or '',
        #             type="password"
        #         )
                
        #         adzuna_key = st.text_input(
        #             "Adzuna API Key",
        #             value=api_keys.get('adzuna_key') or '',
        #             type="password"
        #         )
            
        #     if st.button("💾 Save API Keys", type="primary"):
        #         db.update_api_keys(profile_id, {
        #             'anthropic_key': anthropic_key,
        #             'jsearch_key': jsearch_key,
        #             'adzuna_id': adzuna_id,
        #             'adzuna_key': adzuna_key
        #         })
        #         st.success("✅ API keys saved!")
        #         time.sleep(1)
        #         st.rerun()
        
        # ===== TAB 2: PRE-FILTERS =====
        with tab1:  # Pre-Filters (now first tab after removing API Keys)
            st.subheader("🎯 Pre-Filter Settings")
            st.caption("These filters run BEFORE AI analysis (free, instant)")
            
            pre_filter = db.get_pre_filter_config(profile_id)
            
            if not pre_filter:
                db.create_default_pre_filter(profile_id)
                pre_filter = db.get_pre_filter_config(profile_id)
            
            st.markdown("---")
            st.subheader("Experience")
            
            max_years = st.slider(
                "Maximum Years Required",
                0, 15, pre_filter['max_years_experience'],
                help="Auto-reject jobs requiring this many years or more"
            )
            
            st.markdown("---")
            st.subheader("Auto-Reject Seniority Levels")
            
            default_seniority = pre_filter['reject_seniority_levels']
            
            col1, col2 = st.columns(2)
            
            with col1:
                senior = st.checkbox("Senior", "senior" in default_seniority)
                staff = st.checkbox("Staff", "staff" in default_seniority)
                principal = st.checkbox("Principal", "principal" in default_seniority)
                lead = st.checkbox("Lead", "lead" in default_seniority)
            
            with col2:
                manager = st.checkbox("Manager", "manager" in default_seniority)
                director = st.checkbox("Director", "director" in default_seniority)
                vp = st.checkbox("VP", "vp" in default_seniority)
                chief = st.checkbox("Chief/Head", "chief" in default_seniority or "head of" in default_seniority)
            
            # ✅ NEW: Custom seniority levels
            st.markdown("**Add Custom Seniority Levels** (comma-separated)")
            custom_seniority = st.text_input(
                "Custom levels",
                placeholder="e.g., architect, principal engineer, tech lead",
                help="Add any other seniority keywords you want to auto-reject"
            )
            
            # Build final list
            reject_seniority = []
            if senior: reject_seniority.append("senior")
            if staff: reject_seniority.append("staff")
            if principal: reject_seniority.append("principal")
            if lead: reject_seniority.append("lead")
            if manager: reject_seniority.append("manager")
            if director: reject_seniority.append("director")
            if vp: reject_seniority.extend(["vp", "vice president"])
            if chief: reject_seniority.extend(["chief", "head of"])
            
            # Add custom entries
            if custom_seniority:
                custom_list = [item.strip().lower() for item in custom_seniority.split(',') if item.strip()]
                reject_seniority.extend(custom_list)
            
            st.markdown("---")
            st.subheader("Auto-Reject Job Types")
            
            default_types = pre_filter['reject_job_types']
            
            col1, col2 = st.columns(2)
            
            with col1:
                internship = st.checkbox("Internship", "internship" in default_types)
                part_time = st.checkbox("Part-time", "part-time" in default_types or "part time" in default_types)
            
            with col2:
                freelance = st.checkbox("Freelance", "freelance" in default_types)
                contractor = st.checkbox("Contractor", "contractor" in default_types)
            
            # ✅ NEW: Custom job types
            st.markdown("**Add Custom Job Types to Reject** (comma-separated)")
            custom_job_types = st.text_input(
                "Custom types",
                placeholder="e.g., temporary, seasonal, volunteer",
                help="Add any other job types you want to auto-reject"
            )
            
            # Build final list
            reject_types = []
            if internship: reject_types.extend(["internship", "intern"])
            if part_time: reject_types.extend(["part-time", "part time"])
            if freelance: reject_types.append("freelance")
            if contractor: reject_types.append("contractor")
            
            # Add custom entries
            if custom_job_types:
                custom_list = [item.strip().lower() for item in custom_job_types.split(',') if item.strip()]
                reject_types.extend(custom_list)
            
            st.markdown("---")
            st.subheader("Auto-Reject Specific Titles")
            st.caption("Add job titles you never want to see")
            
            reject_titles_text = st.text_area(
                "Job titles (one per line)",
                value="\n".join(pre_filter['reject_specific_titles']),
                height=150,
                help="Each line is a separate job title to reject"
            )
            
            reject_titles = [line.strip() for line in reject_titles_text.split('\n') if line.strip()]
            
            st.markdown("---")
            
            if st.button("💾 Save Pre-Filter Settings", type="primary"):
                db.update_pre_filter_config(profile_id, {
                    'max_years_experience': max_years,
                    'reject_seniority_levels': reject_seniority,
                    'reject_job_types': reject_types,
                    'reject_specific_titles': reject_titles,
                    'check_full_description': True
                })
                st.success("✅ Pre-filter settings saved!")
                time.sleep(1)
                st.rerun()
        
        # ===== TAB 3: AI FILTERS =====
        with tab2:
            st.subheader("🤖 AI Filter Settings")
            st.caption("Claude AI analyzes jobs against these criteria")
            
            claude_filter = db.get_claude_filter_config(profile_id)
            
            if not claude_filter:
                # Create default
                db.create_default_claude_filter(profile_id)
                claude_filter = db.get_claude_filter_config(profile_id)
            
            st.markdown("---")
            st.subheader("Experience Validation")
            
            col1, col2 = st.columns(2)
            
            with col1:
                max_exp_required = st.slider(
                    "Max Experience Required",
                    0, 15, claude_filter['max_experience_required'],
                    help="Reject if job requires this many years or more"
                )
                
                strict_check = st.checkbox(
                    "Strict Experience Check",
                    claude_filter['strict_experience_check']
                )
            
            with col2:
                allow_preferred = st.checkbox(
                    "Allow 'Preferred' Experience",
                    claude_filter['allow_preferred_experience'],
                    help="Accept 'X years preferred' (not required)"
                )
            
            st.markdown("---")
            st.subheader("Skill Matching")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                min_skill = st.slider(
                    "Min Skill Match %",
                    0, 100, claude_filter['min_skill_match_percent'],
                    help="Need at least this % of required skills"
                )
            
            with col2:
                tier1_skill = st.slider(
                    "Tier 1 Threshold %",
                    0, 100, claude_filter['tier1_skill_threshold'],
                    help="Skill match % for Tier 1"
                )
            
            with col3:
                tier2_skill = st.slider(
                    "Tier 2 Threshold %",
                    0, 100, claude_filter['tier2_skill_threshold'],
                    help="Skill match % for Tier 2"
                )
            
            st.markdown("---")
            st.subheader("Role Relevance")
            
            min_role = st.slider(
                "Minimum Role Match %",
                0, 100, claude_filter['min_target_role_percentage'],
                help="Job must be at least this % your target role work"
            )
            
            st.markdown("---")
            st.subheader("Employment Type")

            col1, col2 = st.columns(2)

            with col1:
                contract_to_hire = st.checkbox(
                    "Accept Contract-to-Hire",
                    claude_filter['accept_contract_to_hire']
                )
                
                reject_internships = st.checkbox(
                    "Reject Internships",
                    claude_filter['reject_internships']
                )

            with col2:
                contract_w2 = st.checkbox(
                    "Accept W2 Contract",
                    claude_filter['accept_contract_w2']
                )
                
                part_time = st.checkbox(
                    "Accept Part-time",
                    claude_filter['accept_part_time']
                )

            # ✅ Custom employment types
            st.markdown("---")
            st.markdown("**Custom Employment Types**")

            col1, col2 = st.columns(2)

            with col1:
                st.caption("Additional types to ACCEPT (comma-separated)")
                custom_accept_str = st.text_input(
                    "Accept custom types",
                    value=", ".join(claude_filter.get('custom_accept_employment', [])),
                    placeholder="e.g., contract-to-permanent, temp-to-hire",
                    help="Employment types you want to accept beyond the standard options"
                )

            with col2:
                st.caption("Additional types to REJECT (comma-separated)")
                custom_reject_str = st.text_input(
                    "Reject custom types",
                    value=", ".join(claude_filter.get('custom_reject_employment', [])),
                    placeholder="e.g., 1099, gig, per diem, seasonal",
                    help="Employment types you want to auto-reject"
                )

            # Parse comma-separated strings to lists
            custom_accept_list = [item.strip().lower() for item in custom_accept_str.split(',') if item.strip()]
            custom_reject_list = [item.strip().lower() for item in custom_reject_str.split(',') if item.strip()]
            st.markdown("---")
            st.subheader("Location & Visa")
            
            col1, col2 = st.columns(2)
            
            with col1:
                requires_visa = st.checkbox(
                    "Requires Visa Sponsorship",
                    claude_filter['requires_visa_sponsorship']
                )
                
                reject_clearance = st.checkbox(
                    "Reject Security Clearance Jobs",
                    claude_filter['reject_clearance_jobs']
                )
            
            with col2:
                remote_only = st.checkbox(
                    "Remote Jobs Only",
                    claude_filter['accept_remote_only']
                )
            
            st.markdown("---")
            st.subheader("Auto-Reject Phrases")
            st.caption("Jobs containing these phrases will be automatically rejected")
            
            reject_phrases_text = st.text_area(
                "Phrases (one per line)",
                value="\n".join(claude_filter['auto_reject_phrases']),
                height=150,
                help="e.g., 'US citizen only', 'no visa sponsorship'"
            )
            
            auto_reject_phrases = [line.strip() for line in reject_phrases_text.split('\n') if line.strip()]
            
            st.markdown("---")
            
            if st.button("💾 Save AI Filter Settings", type="primary"):
                db.update_claude_filter_config(profile_id, {
                    'strict_experience_check': strict_check,
                    'max_experience_required': max_exp_required,
                    'allow_preferred_experience': allow_preferred,
                    'min_skill_match_percent': min_skill,
                    'tier1_skill_threshold': tier1_skill,
                    'tier2_skill_threshold': tier2_skill,
                    'min_target_role_percentage': min_role,
                    'accept_contract_to_hire': contract_to_hire,
                    'accept_contract_w2': contract_w2,
                    'reject_internships': reject_internships,
                    'accept_part_time': part_time,
                    'requires_visa_sponsorship': requires_visa,
                    'reject_clearance_jobs': reject_clearance,
                    'accept_remote_only': remote_only,
                    'auto_reject_phrases': auto_reject_phrases,
                    'custom_accept_employment': custom_accept_list,  # ✅ NEW
                    'custom_reject_employment': custom_reject_list   # ✅ NEW
                })
                st.success("✅ AI filter settings saved!")
                time.sleep(1)
                st.rerun()
        
        # ===== TAB 4: SCHEDULE =====
        with tab3:
            st.subheader("🔍 Collect Jobs")
            
            st.info("Manually collect jobs from job boards. Click the button below to scrape fresh jobs.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                limit_per_source = st.number_input(
                    "Jobs per source",
                    min_value=5,
                    max_value=50,
                    value=20,
                    help="How many jobs to collect from each source"
                )
            
            with col2:
                st.write("")
                st.write("")
                if st.button("🔍 Collect Jobs Now", type="primary", use_container_width=True):
                    st.session_state.manual_collect = True
            
            if st.session_state.get('manual_collect'):
                with st.spinner("Collecting jobs..."):
                    # Run scraper
                    scraper = IntegratedScraper(api_keys)
                    jobs = scraper.scrape_all(
                        target_roles=profile['target_roles'],
                        limit_per_source=limit_per_source
                    )
                    
                    saved = 0
                    for job in jobs:
                        if db.save_raw_job(profile_id, job):
                            saved += 1
                    
                    st.success(f"✅ Collected {saved} new jobs!")
                    st.session_state.manual_collect = False
                    
                    if st.button("🤖 Analyze These Jobs"):
                        st.session_state.page = "🤖 Analyze Jobs"
                        st.rerun()
        
        # ===== TAB 4: COLLECT JOBS =====
        with tab4:
            st.subheader("👤 Your Profile")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Name:**", profile['name'])
                st.write("**Email:**", profile['email'])
                st.write("**Experience:**", profile['experience_years'])
            
            with col2:
                st.write("**Level:**", profile.get('experience_level', 'N/A'))
            
            with st.expander("🎯 Target Roles"):
                for role in profile['target_roles']:
                    st.write(f"• {role}")
            
            with st.expander("💡 Core Skills (Top 30)"):
                skills = profile['core_skills'][:30]
                st.write(", ".join(skills))
                if len(profile['core_skills']) > 30:
                    st.caption(f"...and {len(profile['core_skills']) - 30} more")
            
            st.markdown("---")
            st.caption("To update your profile, upload a new resume and create a new account.")

    
    # ============= ANALYZE JOBS (ON-DEMAND) =============
    elif st.session_state.page == "🤖 Analyze Jobs":
        st.title("🤖 Analyze Jobs")
        
        # Get pending jobs from last 24 hours
        pending_jobs = db.get_jobs_last_24h(profile_id)
        
        if len(pending_jobs) == 0:
            st.info("📋 No jobs collected in the last 24 hours")
            
            st.markdown('<div class="info-box">', unsafe_allow_html=True)
            st.write("**What to do:**")
            st.write("1. Wait for auto-collection to run (check schedule in Settings)")
            st.write("2. Or manually collect jobs now in Settings → Schedule tab")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("⚙️ Go to Settings"):
                st.session_state.page = "⚙️ Settings"
                st.rerun()
        else:
            st.success(f"📊 Found **{len(pending_jobs)} jobs** from last 24 hours ready to analyze")
            
            # Check API key
            if not api_keys.get('anthropic_key'):
                st.error("❌ Please add your Anthropic API key in Settings first!")
                
                if st.button("⚙️ Go to Settings"):
                    st.session_state.page = "⚙️ Settings"
                    st.rerun()
            else:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    analyze_limit = st.slider(
                        "Number of jobs to analyze",
                        min_value=1,
                        max_value=len(pending_jobs),
                        value=min(20, len(pending_jobs)),
                        help="Start with a smaller number to test"
                    )
                    
                    estimated_time = analyze_limit * 2
                    st.caption(f"⏱️ Estimated time: ~{estimated_time // 60} min {estimated_time % 60} sec")
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
                        st.session_state.analyzing = True
                
                if st.session_state.get('analyzing'):
                    # Get configs
                    pre_filter_config = db.get_pre_filter_config(profile_id)
                    claude_filter_config = db.get_claude_filter_config(profile_id)
                    
                    # Initialize matcher
                    from job_matcher_integrated import IntegratedMatcher
                    
                    matcher = IntegratedMatcher(
                        anthropic_api_key=api_keys['anthropic_key'],
                        profile=profile,
                        filter_config=claude_filter_config
                    )
                    
                    # Get jobs to analyze
                    jobs_to_analyze = pending_jobs[:analyze_limit]
                    
                    # Pre-filter
                    st.write("🔍 **Step 1: Pre-filtering...**")
                    filtered_jobs, rejected_reasons = matcher.pre_filter(jobs_to_analyze)
                    
                    st.write(f"✅ {len(filtered_jobs)} jobs passed • {len(jobs_to_analyze) - len(filtered_jobs)} rejected")
                    
                    if rejected_reasons:
                        with st.expander("View pre-filter rejections"):
                            for reason, count in rejected_reasons.items():
                                st.write(f"• {reason}: {count} jobs")
                    
                    st.markdown("---")
                    
                    # AI Analysis
                    st.write("🤖 **Step 2: AI Analysis...**")
                    st.info(f"⏱️ Estimated time: ~{len(filtered_jobs) * 2} seconds")
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.empty()
                    
                    tier1 = 0
                    tier2 = 0
                    rejected = 0
                    
                    for i, job in enumerate(filtered_jobs):
                        # Only update UI every 5 jobs
                        if i % 5 == 0 or i == len(filtered_jobs) - 1:
                            status_text.text(f"Analyzing {i+1}/{len(filtered_jobs)}: {job['company']} - {job['title'][:50]}...")
                            progress_bar.progress((i + 1) / len(filtered_jobs))
                        
                        analysis = matcher.analyze_job(job)
                        
                        if analysis and matcher.is_qualified(analysis):
                            # Save matched job
                            db.save_analyzed_job(profile_id, job['job_id'], analysis)
                            
                            if analysis['tier'] == 1:
                                tier1 += 1
                            elif analysis['tier'] == 2:
                                tier2 += 1
                        else:
                            # Mark as rejected
                            db.mark_job_rejected(job['job_id'])
                            rejected += 1
                        
                        progress_bar.progress((i + 1) / len(filtered_jobs))
                        time.sleep(0.5)  # Rate limiting
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Complete!")
                    
                    st.markdown("---")
                    
                    # Results
                    st.success(f"""
                    **Analysis Complete!**
                    
                    🌟 **Tier 1 (Best Matches):** {tier1}
                    ⭐ **Tier 2 (Good Matches):** {tier2}
                    ❌ **Rejected:** {rejected}
                    """)
                    
                    st.session_state.analyzing = False
                    
                    if tier1 + tier2 > 0:
                        if st.button("🎯 View Your Matches", type="primary", use_container_width=True):
                            st.session_state.page = "🎯 View Matches"
                            st.rerun()
    
    # ============= VIEW MATCHES =============
    elif st.session_state.page == "🎯 View Matches":
        st.title("🎯 Your Job Matches")
        
        tier1_jobs = db.get_analyzed_jobs(profile_id, tier=1)
        tier2_jobs = db.get_analyzed_jobs(profile_id, tier=2)
        
        if len(tier1_jobs) == 0 and len(tier2_jobs) == 0:
            st.info("📋 No matches yet!")
            
            pending = len(db.get_jobs_last_24h(profile_id))
            
            if pending > 0:
                st.write(f"You have **{pending} jobs** waiting to be analyzed.")
                
                if st.button("🤖 Analyze Jobs Now", type="primary"):
                    st.session_state.page = "🤖 Analyze Jobs"
                    st.rerun()
            else:
                st.write("Wait for auto-collection or manually collect jobs in Settings.")
        else:
            # Summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Matches", len(tier1_jobs) + len(tier2_jobs))
            with col2:
                st.metric("🌟 Tier 1", len(tier1_jobs))
            with col3:
                st.metric("⭐ Tier 2", len(tier2_jobs))
            
            st.markdown("---")
            
            # Tabs
            tab1, tab2 = st.tabs([
                f"🌟 Tier 1 Jobs ({len(tier1_jobs)})",
                f"⭐ Tier 2 Jobs ({len(tier2_jobs)})"
            ])
            
            def display_job(job):
                """Display job card"""
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"### {job['company']} - {job['title']}")
                        
                        tier_emoji = "🌟" if job['tier'] == 1 else "⭐"
                        st.markdown(f"{tier_emoji} **Tier {job['tier']}** • Match Score: **{job['match_score']}/100**")
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.caption(f"💼 Exp: {job['experience_required']} yrs")
                        with col_b:
                            st.caption(f"🎯 Role: {job['role_match_pct']}%")
                        with col_c:
                            st.caption(f"💡 Skills: {job['skill_match_pct']}%")
                        
                        with st.expander("🤖 Why this matches"):
                            st.write(job['reasoning'])
                    
                    with col2:
                        st.write("")
                        st.write("")
                        st.link_button("🔗 Apply Now", job['url'], use_container_width=True)
                    
                    st.markdown("---")
            
            with tab1:
                if len(tier1_jobs) == 0:
                    st.info("No Tier 1 jobs yet")
                else:
                    for job in tier1_jobs:
                        display_job(job)
            
            with tab2:
                if len(tier2_jobs) == 0:
                    st.info("No Tier 2 jobs yet")
                else:
                    for job in tier2_jobs:
                        display_job(job)

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: gray; padding: 1rem;">🎯 AI Job Hunter • Powered by Claude AI • All data stored locally</div>',
    unsafe_allow_html=True
)