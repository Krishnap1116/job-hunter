# app.py - AI Job Hunter - Complete Platform

import streamlit as st
import tempfile
import time
import os
from datetime import datetime, timedelta

from database_manager import JobHunterDB
from resume_parser import parse_resume_with_claude
from job_scraper_integrated import IntegratedScraper
from job_matcher_integrated import IntegratedMatcher
import hmac

# ─────────────────────────────────────────────
# Password Gate
# ─────────────────────────────────────────────

def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], st.secrets["app_password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("""
    <div style="max-width:400px;margin:80px auto;text-align:center;">
        <div style="font-size:3rem;margin-bottom:8px;">🎯</div>
        <h2 style="font-family:'Georgia',serif;color:#0f172a;margin-bottom:4px;">AI Job Hunter</h2>
        <p style="color:#64748b;margin-bottom:32px;font-size:0.9rem;">Enter your access password to continue</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("Password", type="password", on_change=password_entered,
                      key="password", label_visibility="collapsed",
                      placeholder="Enter password...")
        if "password_correct" in st.session_state:
            st.error("Incorrect password. Try again.")
    return False

if not check_password():
    st.stop()

# ─────────────────────────────────────────────
# Page Config & Design System
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="AI Job Hunter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #f8fafc !important;
    font-family: 'Sora', sans-serif !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid #1e293b !important;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 10px 14px !important;
    border-radius: 8px !important;
    margin-bottom: 4px !important;
    cursor: pointer !important;
    transition: background 0.15s !important;
    font-size: 0.875rem !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #1e293b !important;
}
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }
[data-testid="stSidebar"] .stButton button {
    background: #1e293b !important;
    color: #94a3b8 !important;
    border: 1px solid #334155 !important;
    font-size: 0.8rem !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #ef4444 !important;
    color: white !important;
    border-color: #ef4444 !important;
}

/* ── Main Content ── */
[data-testid="stMain"] { padding: 0 !important; }
.block-container {
    padding: 2rem 2.5rem !important;
    max-width: 1200px !important;
}

/* ── Page Header ── */
.page-header {
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid #e2e8f0;
}
.page-header h1 {
    font-family: 'Sora', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
}
.page-header p {
    color: #64748b;
    font-size: 0.875rem;
    margin: 0;
}

/* ── Metric Cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 2rem;
}
.metric-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    transition: box-shadow 0.2s;
}
.metric-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.metric-card .label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
    color: #0f172a;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
}
.metric-card .value.accent { color: #6366f1; }
.metric-card .value.green { color: #10b981; }
.metric-card .value.amber { color: #f59e0b; }

/* ── Job Cards ── */
.job-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: box-shadow 0.2s, border-color 0.2s;
    position: relative;
}
.job-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    border-color: #c7d2fe;
}
.job-card.tier1 { border-left: 4px solid #6366f1; }
.job-card.tier2 { border-left: 4px solid #10b981; }
.job-card .company {
    font-size: 0.75rem;
    font-weight: 600;
    color: #6366f1;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}
.job-card .title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 12px;
    line-height: 1.3;
}
.job-card .tags {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
}
.tag.score { background: #ede9fe; color: #6d28d9; }
.tag.role { background: #d1fae5; color: #065f46; }
.tag.skills { background: #dbeafe; color: #1e40af; }
.tag.exp { background: #fef3c7; color: #92400e; }
.tag.tier1-badge { background: #6366f1; color: white; }
.tag.tier2-badge { background: #10b981; color: white; }

/* ── Section Cards ── */
.section-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
}
.section-card h3 {
    font-size: 0.875rem;
    font-weight: 600;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
}

/* ── Alerts ── */
.alert {
    padding: 14px 18px;
    border-radius: 10px;
    font-size: 0.875rem;
    margin-bottom: 16px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.alert.warning {
    background: #fffbeb;
    border: 1px solid #fde68a;
    color: #92400e;
}
.alert.info {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af;
}
.alert.success {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #14532d;
}

/* ── Buttons ── */
.stButton button {
    font-family: 'Sora', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.15s !important;
}
.stButton button[kind="primary"] {
    background: #6366f1 !important;
    border-color: #6366f1 !important;
    color: white !important;
}
.stButton button[kind="primary"]:hover {
    background: #4f46e5 !important;
    border-color: #4f46e5 !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.3) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    gap: 4px !important;
    border-bottom: 2px solid #e2e8f0 !important;
    padding-bottom: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 10px 20px !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #64748b !important;
    border: none !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #6366f1 !important;
    border-bottom: 2px solid #6366f1 !important;
}

/* ── Form Elements ── */
.stSlider label, .stCheckbox label,
.stTextInput label, .stTextArea label,
.stSelectbox label {
    font-family: 'Sora', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}
.stTextInput input, .stTextArea textarea {
    border-radius: 8px !important;
    border-color: #e2e8f0 !important;
    font-family: 'Sora', sans-serif !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}

/* ── Progress ── */
.stProgress > div > div {
    background: #6366f1 !important;
    border-radius: 4px !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    font-family: 'Sora', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
    background: #f8fafc !important;
    border-radius: 8px !important;
}

/* ── Dividers ── */
hr { border-color: #f1f5f9 !important; }

/* ── Source status pills ── */
.source-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
    margin-right: 8px;
    margin-bottom: 8px;
}
.source-pill.active { background: #d1fae5; color: #065f46; }
.source-pill.inactive { background: #f1f5f9; color: #94a3b8; }

/* ── Onboarding steps ── */
.step-indicator {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
}
.step {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8rem;
    font-weight: 500;
    color: #94a3b8;
}
.step.active { color: #6366f1; }
.step.done { color: #10b981; }
.step-num {
    width: 24px; height: 24px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 700;
    background: #f1f5f9; color: #94a3b8;
}
.step.active .step-num { background: #6366f1; color: white; }
.step.done .step-num { background: #10b981; color: white; }
.step-connector { flex: 1; height: 1px; background: #e2e8f0; max-width: 40px; }

/* ── Bullets ── */
.bullet-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    padding: 16px;
    margin-top: 12px;
}
.bullet-box .bullet-header {
    font-size: 0.75rem;
    font-weight: 600;
    color: #6366f1;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
}
.bullet-item {
    font-size: 0.875rem;
    color: #374151;
    padding: 6px 0;
    border-bottom: 1px solid #f1f5f9;
    line-height: 1.5;
}
.bullet-item:last-child { border-bottom: none; }

/* ── Login page ── */
.login-container {
    max-width: 480px;
    margin: 60px auto;
}
.login-logo {
    text-align: center;
    margin-bottom: 40px;
}
.login-logo .logo-icon {
    width: 56px; height: 56px;
    background: #6366f1;
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.75rem;
    margin: 0 auto 16px;
}
.login-logo h1 {
    font-size: 1.75rem; font-weight: 700;
    color: #0f172a; margin: 0 0 6px;
    letter-spacing: -0.02em;
}
.login-logo p { color: #64748b; font-size: 0.875rem; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────

db = JobHunterDB()

for key, val in [
    ('profile_id', None),
    ('page', 'setup'),
    ('analyzing', False),
    ('manual_collect', False),
    ('resume_parsed', False),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding:20px 0 8px;display:flex;align-items:center;gap:10px;">
        <div style="background:#6366f1;border-radius:10px;width:36px;height:36px;
                    display:flex;align-items:center;justify-content:center;font-size:1.1rem;">🎯</div>
        <div>
            <div style="font-size:1rem;font-weight:700;color:white;letter-spacing:-0.01em;">Job Hunter</div>
            <div style="font-size:0.7rem;color:#475569;">AI-powered matching</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.session_state.profile_id:
        profile = db.get_profile_by_id(st.session_state.profile_id)

        st.markdown(f"""
        <div style="background:#1e293b;border-radius:10px;padding:14px 16px;margin-bottom:16px;">
            <div style="font-size:0.8rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">
                {profile['name']}
            </div>
            <div style="font-size:0.72rem;color:#64748b;">{profile['email']}</div>
            <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;">
                <span style="background:#312e81;color:#a5b4fc;padding:2px 8px;border-radius:10px;
                             font-size:0.68rem;font-weight:500;">{profile.get('experience_level','').title()}</span>
                <span style="background:#064e3b;color:#6ee7b7;padding:2px 8px;border-radius:10px;
                             font-size:0.68rem;font-weight:500;">{profile.get('experience_years','')} yrs</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        nav_options = [
            "📊  Dashboard",
            "🔍  Collect Jobs",
            "🤖  Analyze Jobs",
            "🎯  View Matches",
            "⚙️  Settings",
        ]
        page = st.radio("Navigation", nav_options, label_visibility="collapsed")
        st.session_state.page = page

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.profile_id = None
            st.session_state.page = 'setup'
            st.rerun()

# ─────────────────────────────────────────────
# LOGGED OUT — Onboarding
# ─────────────────────────────────────────────

if st.session_state.profile_id is None:

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-logo">
            <div class="logo-icon">🎯</div>
            <h1>AI Job Hunter</h1>
            <p>Upload your resume once. Get matched jobs daily.</p>
        </div>
        """, unsafe_allow_html=True)

        tab_create, tab_login = st.tabs(["  Create Account  ", "  Sign In  "])

        # ── Create Account ──────────────────────────────
        with tab_create:
            st.markdown("""
            <div class="step-indicator">
                <div class="step active"><div class="step-num">1</div>Resume</div>
                <div class="step-connector"></div>
                <div class="step"><div class="step-num">2</div>Confirm</div>
                <div class="step-connector"></div>
                <div class="step"><div class="step-num">3</div>Configure</div>
            </div>
            """, unsafe_allow_html=True)

            uploaded_file = st.file_uploader(
                "Upload Resume (PDF)",
                type=['pdf'],
                help="Claude will extract your skills, roles, and experience automatically"
            )

            if uploaded_file and 'temp_profile' not in st.session_state:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    tmp.write(uploaded_file.read())
                    resume_path = tmp.name

                with st.spinner("Analyzing resume with Claude..."):
                    profile_data = parse_resume_with_claude(resume_path)
                    if profile_data:
                        st.session_state.temp_profile = profile_data
                        st.rerun()
                    else:
                        st.error("Could not parse resume. Please try again.")

            if 'temp_profile' in st.session_state:
                profile = st.session_state.temp_profile

                st.markdown("""
                <div class="step-indicator">
                    <div class="step done"><div class="step-num">✓</div>Resume</div>
                    <div class="step-connector"></div>
                    <div class="step active"><div class="step-num">2</div>Confirm</div>
                    <div class="step-connector"></div>
                    <div class="step"><div class="step-num">3</div>Configure</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown('<div class="section-card"><h3>Extracted Profile</h3>', unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Experience:** {profile.get('experience_years','?')} years")
                    st.markdown(f"**Level:** {profile.get('experience_level','?').title()}")
                with c2:
                    roles = profile.get('target_roles', [])
                    st.markdown(f"**Target Roles:** {', '.join(roles[:3])}")

                with st.expander(f"Core Skills ({len(profile.get('core_skills',[]))} extracted)"):
                    skills = profile.get('core_skills', [])
                    st.write(", ".join(skills[:25]))
                    if len(skills) > 25:
                        st.caption(f"...and {len(skills) - 25} more")

                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("**Your Details**")
                name = st.text_input("Full Name", value=profile.get('name', ''), placeholder="Your full name")
                email = st.text_input("Email Address", placeholder="you@example.com")

                if st.button("Create Account →", type="primary", use_container_width=True):
                    if not name.strip():
                        st.error("Please enter your name.")
                    elif not email.strip() or "@" not in email:
                        st.error("Please enter a valid email address.")
                    else:
                        profile_id = db.create_profile(name.strip(), email.strip(), profile)
                        if profile_id:
                            st.session_state.profile_id = profile_id
                            st.session_state.page = "⚙️  Settings"
                            st.session_state.show_setup_wizard = True
                            del st.session_state.temp_profile
                            st.rerun()
                        else:
                            st.error("Email already in use. Sign in instead.")

        # ── Sign In ──────────────────────────────
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            email_login = st.text_input("Email Address ", placeholder="you@example.com",
                                         key="login_email")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sign In →", type="primary", use_container_width=True):
                found = db.get_profile_by_email(email_login.strip())
                if found:
                    st.session_state.profile_id = found['id']
                    st.session_state.page = "📊  Dashboard"
                    st.rerun()
                else:
                    st.error("No account found for that email.")

# ─────────────────────────────────────────────
# LOGGED IN
# ─────────────────────────────────────────────

else:
    profile_id = st.session_state.profile_id
    profile = db.get_profile_by_id(profile_id)
    api_keys = db.get_api_keys(profile_id)

    # ══════════════════════════════════════════
    # DASHBOARD
    # ══════════════════════════════════════════
    if st.session_state.page == "📊  Dashboard":
        st.markdown("""
        <div class="page-header">
            <h1>Dashboard</h1>
            <p>Overview of your job search activity</p>
        </div>
        """, unsafe_allow_html=True)

        stats = db.get_stats(profile_id)
        pending_count = len(db.get_jobs_last_24h(profile_id))

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="label">Total Scraped</div>
                <div class="value">{stats['total_jobs']}</div>
            </div>
            <div class="metric-card">
                <div class="label">Pending Analysis</div>
                <div class="value accent">{pending_count}</div>
            </div>
            <div class="metric-card">
                <div class="label">Tier 1 Matches</div>
                <div class="value green">{stats['tier1']}</div>
            </div>
            <div class="metric-card">
                <div class="label">Tier 2 Matches</div>
                <div class="value amber">{stats['tier2']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Setup check
        pre_filter = db.get_pre_filter_config(profile_id)
        claude_filter = db.get_claude_filter_config(profile_id)
        setup_ok = api_keys.get('anthropic_key') and pre_filter and claude_filter

        if not setup_ok:
            st.markdown("""
            <div class="alert warning">
                <span>⚠️</span>
                <div><strong>Setup incomplete.</strong> Add your Anthropic API key and configure filters in Settings before analyzing jobs.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Go to Settings →"):
                st.session_state.page = "⚙️  Settings"
                st.rerun()
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔍  Collect New Jobs", use_container_width=True):
                    st.session_state.page = "🔍  Collect Jobs"
                    st.rerun()
            with c2:
                label = f"🤖  Analyze {pending_count} Jobs" if pending_count > 0 else "🤖  Analyze Jobs"
                if st.button(label, type="primary" if pending_count > 0 else "secondary",
                             use_container_width=True, disabled=pending_count == 0):
                    st.session_state.page = "🤖  Analyze Jobs"
                    st.rerun()
            with c3:
                total_matches = stats['tier1'] + stats['tier2']
                if st.button(f"🎯  View {total_matches} Matches", use_container_width=True,
                             disabled=total_matches == 0):
                    st.session_state.page = "🎯  View Matches"
                    st.rerun()

            st.markdown("---")

            # Profile quick view
            st.markdown('<div class="section-card"><h3>Your Profile</h3>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Target Roles:** {', '.join(profile.get('target_roles', []))}")
                st.markdown(f"**Experience:** {profile.get('experience_years', 'N/A')} years ({profile.get('experience_level', '').title()})")
            with c2:
                top_skills = profile.get('core_skills', [])[:8]
                st.markdown(f"**Top Skills:** {', '.join(top_skills)}")
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # COLLECT JOBS
    # ══════════════════════════════════════════
    elif st.session_state.page == "🔍  Collect Jobs":
        st.markdown("""
        <div class="page-header">
            <h1>Collect Jobs</h1>
            <p>Scrape fresh job postings from the last 24 hours</p>
        </div>
        """, unsafe_allow_html=True)

        # Auto-sync API keys from env if needed
        env_jsearch = os.getenv("JSEARCH_API_KEY")
        env_adzuna_id = os.getenv("ADZUNA_APP_ID")
        env_adzuna_key = os.getenv("ADZUNA_API_KEY")
        current_keys = db.get_api_keys(profile_id)

        needs_refresh = (
            (env_jsearch and not current_keys.get('jsearch_key')) or
            (env_adzuna_id and not current_keys.get('adzuna_id')) or
            (env_adzuna_key and not current_keys.get('adzuna_key'))
        )

        if needs_refresh:
            st.markdown("""
            <div class="alert info">
                <span>ℹ️</span>
                <div><strong>New API keys detected in Streamlit Secrets.</strong> Click below to sync them to your profile.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Sync API Keys from Secrets", type="primary"):
                db.update_api_keys(profile_id, {
                    'anthropic_key': os.getenv("ANTHROPIC_API_KEY"),
                    'jsearch_key': env_jsearch,
                    'adzuna_id': env_adzuna_id,
                    'adzuna_key': env_adzuna_key
                })
                st.success("API keys synced!")
                time.sleep(1)
                st.rerun()

        # Source status
        st.markdown('<div class="section-card"><h3>Data Sources</h3>', unsafe_allow_html=True)

        jsearch_ok = bool(api_keys.get('jsearch_key'))
        adzuna_ok = bool(api_keys.get('adzuna_id') and api_keys.get('adzuna_key'))

        st.markdown(f"""
        <div>
            <span class="source-pill {'active' if jsearch_ok else 'inactive'}">
                {'✓' if jsearch_ok else '○'} JSearch API
            </span>
            <span class="source-pill {'active' if adzuna_ok else 'inactive'}">
                {'✓' if adzuna_ok else '○'} Adzuna API
            </span>
        </div>
        <p style="margin-top:12px;font-size:0.8rem;color:#64748b;">
            {'Both sources active — full coverage.' if jsearch_ok and adzuna_ok else
             'Add API keys in Settings to enable more sources. JSearch covers LinkedIn, Indeed, Glassdoor, and ZipRecruiter.'}
        </p>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if not jsearch_ok and not adzuna_ok:
            st.markdown("""
            <div class="alert warning">
                <span>⚠️</span>
                <div><strong>No API keys configured.</strong> Add JSearch and/or Adzuna keys in Settings → API Keys to collect jobs.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("⚙️ Go to Settings"):
                st.session_state.page = "⚙️  Settings"
                st.rerun()
        else:
            st.markdown("""
            <div class="alert info">
                <span>📅</span>
                <div>Collects full-time US jobs from the last 24 hours matching your target roles.</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔍  Collect Jobs Now", type="primary", use_container_width=True):
                st.session_state.manual_collect = True

            if st.session_state.get('manual_collect'):
                with st.spinner("Fetching jobs from all sources..."):
                    scraper = IntegratedScraper(api_keys)
                    jobs = scraper.scrape_all(
                        target_roles=profile['target_roles'],
                        limit_per_source=30
                    )
                    saved = sum(1 for job in jobs if db.save_raw_job(profile_id, job))
                    st.session_state.manual_collect = False

                if saved > 0:
                    st.markdown(f"""
                    <div class="alert success">
                        <span>✓</span>
                        <div><strong>{saved} new jobs collected</strong> and ready for analysis.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Analyze These Jobs →", type="primary"):
                        st.session_state.page = "🤖  Analyze Jobs"
                        st.rerun()
                else:
                    st.info("No new jobs found. All recent jobs may already be in your database.")

    # ══════════════════════════════════════════
    # ANALYZE JOBS
    # ══════════════════════════════════════════
    elif st.session_state.page == "🤖  Analyze Jobs":
        st.markdown("""
        <div class="page-header">
            <h1>Analyze Jobs</h1>
            <p>AI-powered matching against your resume and filters</p>
        </div>
        """, unsafe_allow_html=True)

        pending_jobs = db.get_jobs_last_24h(profile_id)

        if not pending_jobs:
            st.markdown("""
            <div class="alert info">
                <span>ℹ️</span>
                <div><strong>No jobs pending analysis.</strong> Collect jobs first in the Collect Jobs section.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔍 Go to Collect Jobs"):
                st.session_state.page = "🔍  Collect Jobs"
                st.rerun()

        elif not api_keys.get('anthropic_key'):
            st.markdown("""
            <div class="alert warning">
                <span>⚠️</span>
                <div><strong>Anthropic API key required.</strong> Add it in Settings → API Keys.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("⚙️ Go to Settings"):
                st.session_state.page = "⚙️  Settings"
                st.rerun()

        else:
            st.markdown(f"""
            <div class="alert success">
                <span>✓</span>
                <div><strong>{len(pending_jobs)} jobs</strong> ready for analysis.</div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns([3, 1])
            with c1:
                analyze_limit = st.slider(
                    "Jobs to analyze",
                    min_value=1,
                    max_value=len(pending_jobs),
                    value=min(30, len(pending_jobs)),
                    help="Each job costs ~$0.002 in Claude API usage"
                )
                est_secs = analyze_limit * 2
                st.caption(f"⏱ Estimated time: ~{est_secs // 60}m {est_secs % 60}s  •  "
                           f"💰 Est. cost: ~${analyze_limit * 0.002:.2f}")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                start = st.button("🚀  Start Analysis", type="primary", use_container_width=True)
                if start:
                    st.session_state.analyzing = True

            if st.session_state.get('analyzing'):
                claude_filter_config = db.get_claude_filter_config(profile_id)

                matcher = IntegratedMatcher(
                    anthropic_api_key=api_keys['anthropic_key'],
                    profile=profile,
                    filter_config=claude_filter_config
                )

                jobs_to_analyze = pending_jobs[:analyze_limit]

                # Step 1: Pre-filter
                with st.expander("Step 1: Pre-filter", expanded=True):
                    filtered_jobs, rejected_reasons = matcher.pre_filter(jobs_to_analyze)
                    passed = len(filtered_jobs)
                    rejected_pre = len(jobs_to_analyze) - passed
                    st.markdown(f"✅ **{passed} passed** pre-filter &nbsp;|&nbsp; ❌ **{rejected_pre} rejected**")
                    if rejected_reasons:
                        for reason, count in sorted(rejected_reasons.items(),
                                                     key=lambda x: x[1], reverse=True):
                            st.caption(f"  • {reason}: {count}")

                # Step 2: AI Analysis
                st.markdown("**Step 2: AI Analysis**")
                progress_bar = st.progress(0)
                status_text = st.empty()

                tier1 = tier2 = rejected = 0

                for i, job in enumerate(filtered_jobs):
                    # Update UI every 3 jobs
                    if i % 3 == 0 or i == len(filtered_jobs) - 1:
                        status_text.caption(
                            f"Analyzing {i+1}/{len(filtered_jobs)}: "
                            f"{job['company']} — {job['title'][:45]}..."
                        )
                        progress_bar.progress((i + 1) / max(len(filtered_jobs), 1))

                    analysis = matcher.analyze_job(job)

                    if analysis and matcher.is_qualified(analysis):
                        # Generate tailored bullets for Tier 2 only
                        if analysis.get('tier') == 2:
                            bullets = matcher.generate_tailored_bullets(job, analysis)
                            analysis['tailored_bullets'] = bullets
                        else:
                            analysis['tailored_bullets'] = []

                        db.save_analyzed_job(profile_id, job['job_id'], analysis)

                        if analysis.get('tier') == 1:
                            tier1 += 1
                        elif analysis.get('tier') == 2:
                            tier2 += 1
                    else:
                        db.mark_job_rejected(job['job_id'])
                        rejected += 1

                    progress_bar.progress((i + 1) / max(len(filtered_jobs), 1))
                    time.sleep(0.4)

                progress_bar.progress(1.0)
                status_text.empty()
                st.session_state.analyzing = False

                st.markdown(f"""
                <div class="alert success">
                    <span>✓</span>
                    <div>
                        <strong>Analysis complete!</strong><br>
                        🌟 Tier 1 (Best match): <strong>{tier1}</strong> &nbsp;|&nbsp;
                        ⭐ Tier 2 (Good match): <strong>{tier2}</strong> &nbsp;|&nbsp;
                        ❌ Rejected: <strong>{rejected}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if tier1 + tier2 > 0:
                    if st.button("View Your Matches →", type="primary"):
                        st.session_state.page = "🎯  View Matches"
                        st.rerun()

    # ══════════════════════════════════════════
    # VIEW MATCHES
    # ══════════════════════════════════════════
    elif st.session_state.page == "🎯  View Matches":
        st.markdown("""
        <div class="page-header">
            <h1>Job Matches</h1>
            <p>Jobs matched to your profile, ranked by fit</p>
        </div>
        """, unsafe_allow_html=True)

        tier1_jobs = db.get_analyzed_jobs(profile_id, tier=1)
        tier2_jobs = db.get_analyzed_jobs(profile_id, tier=2)
        total = len(tier1_jobs) + len(tier2_jobs)

        if total == 0:
            pending = len(db.get_jobs_last_24h(profile_id))
            if pending > 0:
                st.markdown(f"""
                <div class="alert info">
                    <span>ℹ️</span>
                    <div>No matches yet. You have <strong>{pending} jobs</strong> waiting to be analyzed.</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("🤖 Analyze Now", type="primary"):
                    st.session_state.page = "🤖  Analyze Jobs"
                    st.rerun()
            else:
                st.markdown("""
                <div class="alert info">
                    <span>ℹ️</span>
                    <div>No matches yet. Collect jobs first, then run analysis.</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Summary bar
            st.markdown(f"""
            <div style="display:flex;gap:16px;margin-bottom:24px;align-items:center;">
                <div style="font-size:0.875rem;color:#64748b;">{total} total matches</div>
                <span class="tag tier1-badge">🌟 {len(tier1_jobs)} Tier 1</span>
                <span class="tag tier2-badge">⭐ {len(tier2_jobs)} Tier 2</span>
            </div>
            """, unsafe_allow_html=True)

            tab_t1, tab_t2 = st.tabs([
                f"🌟  Tier 1 — Best Matches ({len(tier1_jobs)})",
                f"⭐  Tier 2 — Good Matches ({len(tier2_jobs)})"
            ])

            def display_job(job):
                tier_class = "tier1" if job['tier'] == 1 else "tier2"
                tier_badge = (f'<span class="tag tier1-badge">🌟 Tier 1</span>'
                              if job['tier'] == 1
                              else '<span class="tag tier2-badge">⭐ Tier 2</span>')

                st.markdown(f"""
                <div class="job-card {tier_class}">
                    <div class="company">{job['company']}</div>
                    <div class="title">{job['title']}</div>
                    <div class="tags">
                        {tier_badge}
                        <span class="tag score">⚡ {job['match_score']}/100</span>
                        <span class="tag role">🎯 Role {job['role_match_pct']}%</span>
                        <span class="tag skills">💡 Skills {job['skill_match_pct']}%</span>
                        <span class="tag exp">💼 {job['experience_required']}+ yrs</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns([4, 1])
                with c1:
                    with st.expander("Why this matches"):
                        st.write(job.get('reasoning', 'No analysis available.'))

                    bullets = job.get('tailored_bullets', [])
                    if job['tier'] == 2 and bullets:
                        with st.expander("✏️ Tailored Resume Bullets"):
                            st.markdown("""
                            <div class="bullet-box">
                                <div class="bullet-header">Copy these for your application — reworded to match this JD</div>
                            """, unsafe_allow_html=True)
                            for b in bullets:
                                st.markdown(f"""
                                <div class="bullet-item">{b}</div>
                                """, unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            st.caption("⚠️ Review before using — these reflect your actual experience reworded.")

                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.link_button("Apply →", job['url'], use_container_width=True)

                st.markdown("<hr style='margin:12px 0;border-color:#f1f5f9;'>", unsafe_allow_html=True)

            with tab_t1:
                if not tier1_jobs:
                    st.info("No Tier 1 matches yet.")
                else:
                    for job in tier1_jobs:
                        display_job(job)

            with tab_t2:
                if not tier2_jobs:
                    st.info("No Tier 2 matches yet.")
                else:
                    for job in tier2_jobs:
                        display_job(job)

    # ══════════════════════════════════════════
    # SETTINGS
    # ══════════════════════════════════════════
    elif st.session_state.page == "⚙️  Settings":
        st.markdown("""
        <div class="page-header">
            <h1>Settings</h1>
            <p>Configure your filters, API keys, and profile</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get('show_setup_wizard'):
            st.markdown("""
            <div class="alert info">
                <span>👋</span>
                <div><strong>Welcome!</strong> Complete your setup below — add your API key and configure your filters to start matching jobs.</div>
            </div>
            """, unsafe_allow_html=True)

        tab_api, tab_pre, tab_ai, tab_profile = st.tabs([
            "🔑  API Keys",
            "⚡  Pre-Filters",
            "🤖  AI Filters",
            "👤  Profile",
        ])

        # ── API Keys ────────────────────────────
        with tab_api:
            st.markdown('<div class="section-card"><h3>Required</h3>', unsafe_allow_html=True)
            st.caption("Anthropic API key is required for AI job analysis.")

            anthropic_key = st.text_input(
                "Anthropic API Key",
                value=api_keys.get('anthropic_key') or '',
                type="password",
                placeholder="sk-ant-...",
                help="Get from console.anthropic.com"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Job Sources</h3>', unsafe_allow_html=True)
            st.caption("JSearch covers LinkedIn, Indeed, Glassdoor & ZipRecruiter. Adzuna is a free supplement.")

            c1, c2 = st.columns(2)
            with c1:
                jsearch_key = st.text_input(
                    "JSearch API Key",
                    value=api_keys.get('jsearch_key') or '',
                    type="password",
                    placeholder="RapidAPI key",
                    help="rapidapi.com → search 'JSearch'"
                )
            with c2:
                adzuna_id = st.text_input(
                    "Adzuna App ID",
                    value=api_keys.get('adzuna_id') or '',
                    type="password"
                )
                adzuna_key = st.text_input(
                    "Adzuna API Key",
                    value=api_keys.get('adzuna_key') or '',
                    type="password"
                )
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾  Save API Keys", type="primary"):
                db.update_api_keys(profile_id, {
                    'anthropic_key': anthropic_key,
                    'jsearch_key': jsearch_key,
                    'adzuna_id': adzuna_id,
                    'adzuna_key': adzuna_key
                })
                api_keys = db.get_api_keys(profile_id)
                st.success("API keys saved!")
                st.session_state.show_setup_wizard = False

        # ── Pre-Filters ──────────────────────────
        with tab_pre:
            pre_filter = db.get_pre_filter_config(profile_id)
            if not pre_filter:
                db.create_default_pre_filter(profile_id)
                pre_filter = db.get_pre_filter_config(profile_id)

            st.markdown("""
            <div class="alert info">
                <span>⚡</span>
                <div>Pre-filters run instantly before AI analysis — no API cost. Use them to eliminate obvious non-matches.</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Experience Cap</h3>', unsafe_allow_html=True)
            max_years = st.slider(
                "Reject jobs requiring more than N years",
                0, 15, pre_filter['max_years_experience'],
                help="Hard requirement only — 'preferred' is allowed through"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Seniority Levels to Reject</h3>', unsafe_allow_html=True)
            default_seniority = pre_filter['reject_seniority_levels']

            c1, c2, c3, c4 = st.columns(4)
            senior = c1.checkbox("Senior", "senior" in default_seniority)
            staff = c1.checkbox("Staff", "staff" in default_seniority)
            principal = c2.checkbox("Principal", "principal" in default_seniority)
            lead = c2.checkbox("Lead", "lead" in default_seniority)
            manager = c3.checkbox("Manager", "manager" in default_seniority)
            director = c3.checkbox("Director", "director" in default_seniority)
            vp = c4.checkbox("VP", "vp" in default_seniority)
            chief = c4.checkbox("Chief / Head", "chief" in default_seniority)

            custom_seniority = st.text_input(
                "Additional seniority keywords (comma-separated)",
                placeholder="e.g. architect, tech lead, distinguished"
            )

            reject_seniority = []
            if senior: reject_seniority.append("senior")
            if staff: reject_seniority.append("staff")
            if principal: reject_seniority.append("principal")
            if lead: reject_seniority.append("lead")
            if manager: reject_seniority.append("manager")
            if director: reject_seniority.append("director")
            if vp: reject_seniority.extend(["vp", "vice president"])
            if chief: reject_seniority.extend(["chief", "head of"])
            if custom_seniority:
                reject_seniority.extend([x.strip().lower() for x in custom_seniority.split(',') if x.strip()])

            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Job Types to Reject</h3>', unsafe_allow_html=True)
            default_types = pre_filter['reject_job_types']

            c1, c2 = st.columns(2)
            internship = c1.checkbox("Internship", "internship" in default_types)
            part_time = c1.checkbox("Part-time", "part-time" in default_types)
            freelance = c2.checkbox("Freelance", "freelance" in default_types)
            contractor = c2.checkbox("Contractor", "contractor" in default_types)

            custom_job_types = st.text_input(
                "Additional job types to reject (comma-separated)",
                placeholder="e.g. temporary, seasonal, volunteer"
            )

            reject_types = []
            if internship: reject_types.extend(["internship", "intern"])
            if part_time: reject_types.extend(["part-time", "part time"])
            if freelance: reject_types.append("freelance")
            if contractor: reject_types.append("contractor")
            if custom_job_types:
                reject_types.extend([x.strip().lower() for x in custom_job_types.split(',') if x.strip()])

            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Job Titles to Always Reject</h3>', unsafe_allow_html=True)
            reject_titles_text = st.text_area(
                "One title per line",
                value="\n".join(pre_filter['reject_specific_titles']),
                height=120,
                label_visibility="collapsed"
            )
            reject_titles = [l.strip() for l in reject_titles_text.split('\n') if l.strip()]
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾  Save Pre-Filter Settings", type="primary"):
                db.update_pre_filter_config(profile_id, {
                    'max_years_experience': max_years,
                    'reject_seniority_levels': reject_seniority,
                    'reject_job_types': reject_types,
                    'reject_specific_titles': reject_titles,
                    'check_full_description': True
                })
                st.success("Pre-filter settings saved!")

        # ── AI Filters ───────────────────────────
        with tab_ai:
            claude_filter = db.get_claude_filter_config(profile_id)
            if not claude_filter:
                db.create_default_claude_filter(profile_id)
                claude_filter = db.get_claude_filter_config(profile_id)

            st.markdown("""
            <div class="alert info">
                <span>🤖</span>
                <div>These rules are sent to Claude with every job. They determine qualification and tier assignment.</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Experience</h3>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            max_exp_required = c1.slider(
                "Max years required (hard limit)",
                0, 15, claude_filter['max_experience_required']
            )
            allow_preferred = c2.checkbox(
                "Accept 'preferred' experience (not required)",
                claude_filter['allow_preferred_experience']
            )
            strict_check = c2.checkbox(
                "Strict experience check",
                claude_filter['strict_experience_check']
            )
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Skill Matching & Tiers</h3>', unsafe_allow_html=True)
            st.caption("Tier 1 = best matches. Tier 2 = good matches with tailored resume bullets.")
            c1, c2, c3 = st.columns(3)
            min_skill = c1.slider("Min skill match %", 0, 100, claude_filter['min_skill_match_percent'])
            tier1_skill = c2.slider("Tier 1 threshold %", 0, 100, claude_filter['tier1_skill_threshold'])
            tier2_skill = c3.slider("Tier 2 threshold %", 0, 100, claude_filter['tier2_skill_threshold'])

            min_role = st.slider(
                "Min role relevance %",
                0, 100, claude_filter['min_target_role_percentage'],
                help="What % of the job's work should match your target roles"
            )
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Employment Type</h3>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            contract_to_hire = c1.checkbox("Accept contract-to-hire", claude_filter['accept_contract_to_hire'])
            contract_w2 = c1.checkbox("Accept W2 contract", claude_filter['accept_contract_w2'])
            reject_internships = c2.checkbox("Reject internships", claude_filter['reject_internships'])
            part_time_ai = c2.checkbox("Accept part-time", claude_filter['accept_part_time'])

            st.markdown("**Custom employment types**")
            c1, c2 = st.columns(2)
            custom_accept_str = c1.text_input(
                "Also accept (comma-separated)",
                value=", ".join(claude_filter.get('custom_accept_employment', [])),
                placeholder="e.g. temp-to-hire"
            )
            custom_reject_str = c2.text_input(
                "Also reject (comma-separated)",
                value=", ".join(claude_filter.get('custom_reject_employment', [])),
                placeholder="e.g. 1099, gig, per diem"
            )
            custom_accept_list = [x.strip().lower() for x in custom_accept_str.split(',') if x.strip()]
            custom_reject_list = [x.strip().lower() for x in custom_reject_str.split(',') if x.strip()]
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Location & Visa</h3>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            requires_visa = c1.checkbox("I need visa sponsorship", claude_filter['requires_visa_sponsorship'])
            reject_clearance = c1.checkbox("Reject security clearance jobs", claude_filter['reject_clearance_jobs'])
            remote_only = c2.checkbox("Remote jobs only", claude_filter['accept_remote_only'])
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Auto-Reject Phrases</h3>', unsafe_allow_html=True)
            st.caption("Any job description containing these phrases is instantly rejected.")
            reject_phrases_text = st.text_area(
                "One phrase per line",
                value="\n".join(claude_filter['auto_reject_phrases']),
                height=120,
                label_visibility="collapsed"
            )
            auto_reject_phrases = [l.strip() for l in reject_phrases_text.split('\n') if l.strip()]
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾  Save AI Filter Settings", type="primary"):
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
                    'accept_part_time': part_time_ai,
                    'requires_visa_sponsorship': requires_visa,
                    'reject_clearance_jobs': reject_clearance,
                    'accept_remote_only': remote_only,
                    'auto_reject_phrases': auto_reject_phrases,
                    'custom_accept_employment': custom_accept_list,
                    'custom_reject_employment': custom_reject_list
                })
                st.success("AI filter settings saved!")

        # ── Profile ──────────────────────────────
        with tab_profile:
            st.markdown('<div class="section-card"><h3>Account</h3>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.markdown(f"**Name:** {profile['name']}")
            c1.markdown(f"**Email:** {profile['email']}")
            c2.markdown(f"**Experience:** {profile.get('experience_years','N/A')} years")
            c2.markdown(f"**Level:** {profile.get('experience_level','N/A').title()}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Target Roles</h3>', unsafe_allow_html=True)
            for role in profile.get('target_roles', []):
                st.markdown(f"• {role}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-card"><h3>Core Skills</h3>', unsafe_allow_html=True)
            skills = profile.get('core_skills', [])
            st.write(", ".join(skills[:30]))
            if len(skills) > 30:
                st.caption(f"...and {len(skills) - 30} more")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="alert info">
                <span>ℹ️</span>
                <div>To update your profile, create a new account with your updated resume.</div>
            </div>
            """, unsafe_allow_html=True)