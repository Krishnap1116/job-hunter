# app.py - AI Job Hunter

import streamlit as st
import tempfile
import time
import os
from datetime import datetime

from database_manager import JobHunterDB
from resume_parser import parse_resume_with_claude
from job_scraper_integrated import IntegratedScraper
from job_matcher_integrated import IntegratedMatcher

# ─────────────────────────────────────────────
# Page config FIRST — before any st calls
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="JobHunter AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# Design System — dark theme, no white-on-white
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');

/* ══ BASE ══ */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main, .block-container {
    background-color: #0f1117 !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
.block-container {
    padding: 1.5rem 2rem 3rem !important;
    max-width: 1100px !important;
}

/* ══ SIDEBAR ══ */
[data-testid="stSidebar"] {
    background-color: #0a0d14 !important;
    border-right: 1px solid #1e2535 !important;
}
[data-testid="stSidebar"] *,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    color: #94a3b8 !important;
}
[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 9px 12px !important;
    border-radius: 7px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: all 0.15s !important;
    width: 100% !important;
    display: block !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #1a2235 !important;
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stRadio [data-checked="true"] label,
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input:checked) {
    background: #1e3a5f !important;
    color: #60a5fa !important;
}
[data-testid="stSidebar"] hr { border-color: #1e2535 !important; }

/* ══ ALL TEXT ELEMENTS — force visible ══ */
p, span, label, div, h1, h2, h3, h4, li {
    color: #e2e8f0 !important;
}
.stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: #cbd5e1 !important;
}
.stCaption, .stCaption p { color: #64748b !important; }

/* ══ FORM LABELS — most critical fix ══ */
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stSlider label,
.stCheckbox label,
.stRadio label,
.stFileUploader label,
.stNumberInput label {
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 4px !important;
}
.stCheckbox label, .stRadio label {
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-size: 0.875rem !important;
    color: #cbd5e1 !important;
}

/* ══ INPUTS ══ */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
    background: #1a2235 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 7px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    padding: 10px 14px !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
    outline: none !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder { color: #475569 !important; }

/* ══ SLIDERS ══ */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #3b82f6 !important;
}
[data-testid="stSlider"] div[data-testid="stTickBar"] { color: #475569 !important; }

/* ══ CHECKBOXES ══ */
.stCheckbox [data-testid="stCheckbox"] span {
    background: #1a2235 !important;
    border-color: #2d3748 !important;
}

/* ══ BUTTONS ══ */
.stButton > button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 7px !important;
    font-size: 0.875rem !important;
    transition: all 0.15s !important;
    color: #e2e8f0 !important;
    background: #1a2235 !important;
    border: 1px solid #2d3748 !important;
    padding: 0.45rem 1rem !important;
}
.stButton > button:hover {
    background: #243048 !important;
    border-color: #3b82f6 !important;
    color: #60a5fa !important;
}
.stButton > button[kind="primary"] {
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1d4ed8 !important;
    border-color: #1d4ed8 !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
}
.stButton > button:disabled {
    opacity: 0.4 !important;
    cursor: not-allowed !important;
}
.stLinkButton a {
    background: #1a2235 !important;
    border: 1px solid #2d3748 !important;
    color: #60a5fa !important;
    border-radius: 7px !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
}
.stLinkButton a:hover {
    background: #243048 !important;
    border-color: #3b82f6 !important;
}

/* ══ TABS ══ */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1e2535 !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 10px 18px !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #94a3b8 !important; }
.stTabs [aria-selected="true"] {
    color: #60a5fa !important;
    border-bottom: 2px solid #3b82f6 !important;
    background: transparent !important;
}

/* ══ EXPANDER ══ */
[data-testid="stExpander"] {
    background: #141925 !important;
    border: 1px solid #1e2535 !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary {
    color: #94a3b8 !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 12px 16px !important;
}
[data-testid="stExpander"] summary:hover { color: #e2e8f0 !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0 16px 16px !important;
}

/* ══ PROGRESS ══ */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #2563eb, #7c3aed) !important;
    border-radius: 4px !important;
}
.stProgress > div > div {
    background: #1e2535 !important;
    border-radius: 4px !important;
}

/* ══ FILE UPLOADER ══ */
[data-testid="stFileUploader"] {
    background: #141925 !important;
    border: 1.5px dashed #2d3748 !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploader"]:hover { border-color: #3b82f6 !important; }
[data-testid="stFileUploader"] * { color: #94a3b8 !important; }

/* ══ ALERTS / CALLOUTS ══ */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-width: 1px !important;
}

/* ══ SPINNER ══ */
[data-testid="stSpinner"] * { color: #60a5fa !important; }

/* ══ DIVIDER ══ */
hr { border-color: #1e2535 !important; }

/* ══ SCROLLBAR ══ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3b82f6; }

/* ══ CUSTOM COMPONENTS ══ */

/* Stat cards */
.stat-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.stat-card {
    background: #141925;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 18px 20px;
}
.stat-card .s-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.stat-card .s-value {
    font-size: 1.9rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
    color: #e2e8f0;
}
.stat-card .s-value.blue { color: #60a5fa; }
.stat-card .s-value.green { color: #34d399; }
.stat-card .s-value.amber { color: #fbbf24; }

/* Step flow */
.step-flow {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 28px;
    background: #141925;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 16px 20px;
}
.step-item {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
}
.step-dot {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem;
    font-weight: 700;
    flex-shrink: 0;
    background: #1e2535;
    color: #475569;
    border: 1.5px solid #2d3748;
}
.step-dot.done { background: #065f46; color: #34d399; border-color: #34d399; }
.step-dot.active { background: #1e3a5f; color: #60a5fa; border-color: #3b82f6; }
.step-text { font-size: 0.8rem; font-weight: 500; color: #475569; }
.step-text.done { color: #34d399; }
.step-text.active { color: #60a5fa; }
.step-arrow { color: #2d3748; font-size: 0.75rem; margin: 0 12px; }

/* Job card */
.jcard {
    background: #141925;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}
.jcard:hover { border-color: #2d3748; }
.jcard.t1 { border-left: 3px solid #3b82f6; }
.jcard.t2 { border-left: 3px solid #34d399; }
.jcard .jc-co {
    font-size: 0.7rem;
    font-weight: 600;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 3px;
}
.jcard .jc-title {
    font-size: 1rem;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 10px;
    line-height: 1.3;
}
.jcard .jc-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.pill {
    display: inline-flex; align-items: center;
    padding: 3px 9px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
}
.pill.blue { background: #1e3a5f; color: #60a5fa; }
.pill.green { background: #065f46; color: #34d399; }
.pill.purple { background: #2e1065; color: #a78bfa; }
.pill.amber { background: #451a03; color: #fbbf24; }
.pill.t1 { background: #1e3a5f; color: #93c5fd; }
.pill.t2 { background: #064e3b; color: #6ee7b7; }

/* Section header */
.sec-hdr {
    font-size: 0.7rem;
    font-weight: 600;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e2535;
}

/* Info panel */
.info-panel {
    background: #141925;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

/* Bullet box */
.bx {
    background: #0f1823;
    border: 1px solid #1e3a5f;
    border-left: 3px solid #3b82f6;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 10px;
}
.bx-hdr {
    font-size: 0.68rem;
    font-weight: 600;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}
.bx-item {
    font-size: 0.85rem;
    color: #94a3b8;
    padding: 5px 0;
    border-bottom: 1px solid #1e2535;
    line-height: 1.55;
}
.bx-item:last-child { border-bottom: none; }

/* Key status row */
.key-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid #1e2535;
    font-size: 0.875rem;
}
.key-row:last-child { border-bottom: none; }
.key-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.key-dot.ok { background: #34d399; }
.key-dot.missing { background: #ef4444; }
.key-name { color: #94a3b8; flex: 1; }
.key-status-ok { color: #34d399; font-size: 0.75rem; font-weight: 600; }
.key-status-missing { color: #ef4444; font-size: 0.75rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Password Gate
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Init DB + Session State
# ─────────────────────────────────────────────
db = JobHunterDB()

DEFAULTS = {
    'profile_id': None,
    'page': 'home',
    'manual_collect': False,
    'collect_done': False,
    'last_collect_saved': 0,
    'analyzing': False,
    'show_setup_wizard': False,
    'auto_analyzed': False,
    'auto_analyzing': False,
    'manual_refresh': False,
    'manual_collect_done_pending': False,
    'manual_collect_new_count': 0,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# Persist login across browser refreshes
# st.query_params survives refresh; session_state does not.
# On refresh: query_params still has pid=X → restore session.
# On sign-out: query_params is cleared.
# ─────────────────────────────────────────────
if st.session_state.profile_id is None:
    try:
        pid_str = st.query_params.get('pid')
        if pid_str:
            pid = int(pid_str)
            # Verify the profile actually exists in DB
            check = db.get_profile_by_id(pid)
            if check:
                st.session_state.profile_id = pid
    except Exception:
        pass  # Bad param — ignore, stay logged out

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 4px 16px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;">
            <div style="background:#2563eb;border-radius:8px;width:32px;height:32px;
                        display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">🎯</div>
            <div>
                <div style="font-size:0.95rem;font-weight:700;color:#f1f5f9;">JobHunter AI</div>
                <div style="font-size:0.68rem;color:#334155;">AI-powered job matching</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.profile_id:
        profile = db.get_profile_by_id(st.session_state.profile_id)
        api_keys = db.get_api_keys(st.session_state.profile_id)

        # User card
        st.markdown(f"""
        <div style="background:#141925;border:1px solid #1e2535;border-radius:9px;
                    padding:12px 14px;margin-bottom:16px;">
            <div style="font-size:0.85rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">
                {profile['name']}
            </div>
            <div style="font-size:0.72rem;color:#475569;margin-bottom:8px;">{profile['email']}</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;
                             border-radius:10px;font-size:0.68rem;font-weight:600;">
                    {profile.get('experience_level','').title()}
                </span>
                <span style="background:#064e3b;color:#34d399;padding:2px 8px;
                             border-radius:10px;font-size:0.68rem;font-weight:600;">
                    {profile.get('experience_years','')} yrs exp
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        pages = {
            "home":     "🏠  Home",
            "matches":  "🎯  My Matches",
            "settings": "⚙️  Settings",
        }
        for key, label in pages.items():
            active = st.session_state.page == key
            if st.button(label,
                         use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"nav_{key}"):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")

        # API key status in sidebar
        st.markdown('<div class="sec-hdr">Sources</div>', unsafe_allow_html=True)
        all_sources = [
            ("Greenhouse", True,  "Free"),
            ("Lever",      True,  "Free"),
            ("RemoteOK",   True,  "Free"),
            ("Jobicy",     True,  "Free"),
            ("JSearch",    bool(api_keys.get('jsearch_key')), "Connected" if api_keys.get('jsearch_key') else "No key"),
            ("Adzuna",     bool(api_keys.get('adzuna_id')),  "Connected" if api_keys.get('adzuna_id')  else "No key"),
        ]
        for name, ok, status in all_sources:
            dot = "ok" if ok else "missing"
            st.markdown(f"""
            <div class="key-row">
                <div class="key-dot {dot}"></div>
                <div class="key-name">{name}</div>
                <div class="key-status-{'ok' if ok else 'missing'}">{status}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.query_params.clear()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# ═══════════════════════════════════════════════════════════
# LOGGED OUT — Onboarding
# ═══════════════════════════════════════════════════════════
if st.session_state.profile_id is None:
    c1, c2, c3 = st.columns([1, 1.6, 1])
    with c2:
        st.markdown("""
        <div style="text-align:center;padding:48px 0 32px;">
            <div style="font-size:2.5rem;margin-bottom:14px;">🎯</div>
            <div style="font-size:1.6rem;font-weight:700;color:#f1f5f9;
                        letter-spacing:-0.02em;margin-bottom:8px;">JobHunter AI</div>
            <div style="font-size:0.9rem;color:#475569;margin-bottom:32px;">
                Upload your resume. Get matched jobs daily. Apply smarter.
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab_new, tab_in = st.tabs(["  Create Account  ", "  Sign In  "])

        # ── Create ──────────────────────────────
        with tab_new:
            # Step 1 — API key first (persisted in session_state so it survives reruns)
            st.markdown("**🤖 Anthropic API Key**")
            st.caption("Required to read your resume and analyse jobs. Get yours free at [console.anthropic.com](https://console.anthropic.com)")
            reg_anthropic_key = st.text_input(
                "Anthropic API Key", type="password",
                placeholder="sk-ant-...",
                label_visibility="collapsed",
                key="reg_api_key"
            )
            # Save to session_state immediately so it survives st.rerun()
            if reg_anthropic_key.strip():
                st.session_state.reg_anthropic_key = reg_anthropic_key.strip()

            active_key = st.session_state.get('reg_anthropic_key', '')

            # Step 2 — file uploader only appears once key is present
            # and only shown if resume not yet parsed (avoids widget flicker loop)
            if active_key and 'temp_profile' not in st.session_state:
                st.markdown("<br>", unsafe_allow_html=True)
                uploaded = st.file_uploader(
                    "Upload your resume (PDF)",
                    type=['pdf'],
                    help="Claude will extract your skills, roles and experience"
                )
                if uploaded:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                        tmp.write(uploaded.read())
                        path = tmp.name
                    with st.spinner("Reading resume with Claude..."):
                        try:
                            data = parse_resume_with_claude(path, api_key=active_key)
                            if data:
                                st.session_state.temp_profile = data
                                st.rerun()
                            else:
                                st.error("Could not parse resume. Please try a different file.")
                        except Exception as e:
                            if "auth" in str(e).lower() or "401" in str(e) or "invalid" in str(e).lower():
                                st.error("❌ Invalid Anthropic API key. Please check and try again.")
                                st.session_state.pop('reg_anthropic_key', None)
                            else:
                                st.error(f"Error reading resume: {e}")

            elif not active_key:
                st.caption("↑ Enter your API key above to continue.")

            # Step 3 — name / email / create (shown after resume parsed)
            if 'temp_profile' in st.session_state:
                p = st.session_state.temp_profile
                saved_key = st.session_state.get('reg_anthropic_key', '')

                st.markdown("""
                <div style="background:#141925;border:1px solid #1e2535;border-radius:10px;
                            padding:16px 20px;margin:16px 0 20px;">
                    <div class="sec-hdr">Extracted from your resume</div>
                """, unsafe_allow_html=True)
                c_a, c_b = st.columns(2)
                c_a.markdown(f"**Experience:** {p.get('experience_years','?')} yrs")
                c_a.markdown(f"**Level:** {p.get('experience_level','?').title()}")
                c_b.markdown(f"**Roles:** {', '.join(p.get('target_roles',[])[:2])}")
                c_b.markdown(f"**Skills:** {len(p.get('core_skills',[]))} extracted")
                st.markdown("</div>", unsafe_allow_html=True)

                name  = st.text_input("Full Name", value=p.get('name', ''))
                email = st.text_input("Email Address", placeholder="you@example.com")

                if st.button("Create Account →", type="primary", use_container_width=True):
                    if not name.strip():
                        st.error("Please enter your name.")
                    elif not email.strip() or "@" not in email:
                        st.error("Please enter a valid email.")
                    elif not saved_key:
                        st.error("Session expired — please refresh and try again.")
                    else:
                        pid = db.create_profile(name.strip(), email.strip(), p)
                        if pid:
                            db.update_api_keys(pid, {
                                'anthropic_key': saved_key,
                                'jsearch_key':   os.getenv("JSEARCH_API_KEY", ""),
                                'adzuna_id':     os.getenv("ADZUNA_APP_ID", ""),
                                'adzuna_key':    os.getenv("ADZUNA_API_KEY", ""),
                            })
                            st.session_state.profile_id = pid
                            st.session_state.page = "home"
                            st.session_state.pop('temp_profile', None)
                            st.session_state.pop('reg_anthropic_key', None)
                            st.query_params['pid'] = str(pid)
                            st.rerun()
                        else:
                            st.error("Email already registered. Sign in instead.")

        # ── Sign In ─────────────────────────────
        with tab_in:
            st.markdown("<br>", unsafe_allow_html=True)
            email_in = st.text_input("Email", placeholder="you@example.com", key="login_email",
                                      label_visibility="collapsed")
            if st.button("Sign In →", type="primary", use_container_width=True):
                found = db.get_profile_by_email(email_in.strip())
                if found:
                    st.session_state.profile_id = found['id']
                    st.session_state.page = "home"
                    st.query_params['pid'] = str(found['id'])
                    st.rerun()
                else:
                    st.error("No account found. Create one first.")

            st.markdown("---")
            st.markdown('<div class="sec-hdr" style="margin-top:8px;">Change Your Anthropic API Key</div>',
                        unsafe_allow_html=True)
            st.caption("Enter your email and new key to update it.")
            chg_email = st.text_input("Email", placeholder="you@example.com",
                                       key="chg_email", label_visibility="collapsed")
            chg_key   = st.text_input("New Anthropic API Key", type="password",
                                       placeholder="sk-ant-...", key="chg_key")
            if st.button("🔑  Update API Key", use_container_width=True):
                if not chg_email.strip() or "@" not in chg_email:
                    st.error("Enter a valid email.")
                elif not chg_key.strip().startswith("sk-"):
                    st.error("That doesn't look like a valid Anthropic key (should start with sk-).")
                else:
                    acct = db.get_profile_by_email(chg_email.strip())
                    if not acct:
                        st.error("No account found with that email.")
                    else:
                        existing = db.get_api_keys(acct['id'])
                        db.update_api_keys(acct['id'], {
                            'anthropic_key': chg_key.strip(),
                            'jsearch_key':   existing.get('jsearch_key', ''),
                            'adzuna_id':     existing.get('adzuna_id', ''),
                            'adzuna_key':    existing.get('adzuna_key', ''),
                        })
                        st.success("✅ API key updated! Sign in to continue.")

# ═══════════════════════════════════════════════════════════
# LOGGED IN
# ═══════════════════════════════════════════════════════════
else:
    profile_id    = st.session_state.profile_id
    profile       = db.get_profile_by_id(profile_id)
    api_keys      = db.get_api_keys(profile_id)
    stats         = db.get_stats(profile_id)
    user_lookback = db.get_job_lookback_hours(profile_id)

    # Ensure every profile has at least one resume (migrates old profiles)
    db.ensure_default_resume(profile_id)
    all_resumes    = db.get_resumes(profile_id)
    active_resume  = db.get_active_resume(profile_id)
    active_resume_id = active_resume['id'] if active_resume else None

    # ══════════════════════════════════════════
    # HOME — Smart auto-analyze dashboard
    # ══════════════════════════════════════════
    if st.session_state.page == "home":

        # resume switcher and add wizard rendered below stats row

        pending_jobs  = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)
        pending_count = len(pending_jobs)
        pool_stats    = db.get_global_pool_stats()
        has_anthropic = bool(api_keys.get('anthropic_key'))

        # ── Auto-sync keys from environment on first load ─────
        env_jsearch   = os.getenv("JSEARCH_API_KEY")
        env_az_id     = os.getenv("ADZUNA_APP_ID")
        env_az_key    = os.getenv("ADZUNA_API_KEY")
        env_anthropic = os.getenv("ANTHROPIC_API_KEY")
        needs_sync = (
            (env_jsearch   and not api_keys.get('jsearch_key'))  or
            (env_az_id     and not api_keys.get('adzuna_id'))    or
            (env_az_key    and not api_keys.get('adzuna_key'))   or
            (env_anthropic and not api_keys.get('anthropic_key'))
        )
        if needs_sync:
            db.update_api_keys(profile_id, {
                'anthropic_key': env_anthropic or api_keys.get('anthropic_key'),
                'jsearch_key':   env_jsearch   or api_keys.get('jsearch_key'),
                'adzuna_id':     env_az_id     or api_keys.get('adzuna_id'),
                'adzuna_key':    env_az_key    or api_keys.get('adzuna_key'),
            })
            api_keys      = db.get_api_keys(profile_id)
            has_anthropic = bool(api_keys.get('anthropic_key'))

        # ── Top stats row ─────────────────────
        last_scraped_str = "Never"
        if pool_stats.get('last_scraped'):
            try:
                from dateutil import parser as dateparser
                ls = dateparser.parse(str(pool_stats['last_scraped']))
                last_scraped_str = ls.strftime("%-d %b %H:%M")
            except Exception:
                last_scraped_str = str(pool_stats['last_scraped'])[:16]

        stats = db.get_stats(profile_id)

        st.markdown(f"""
        <div class="stat-row">
            <div class="stat-card">
                <div class="s-label">Jobs in Pool</div>
                <div class="s-value">{pool_stats['total']}</div>
            </div>
            <div class="stat-card">
                <div class="s-label">New for You</div>
                <div class="s-value blue">{pending_count}</div>
            </div>
            <div class="stat-card">
                <div class="s-label">Tier 1 Matches</div>
                <div class="s-value green">{stats['tier1']}</div>
            </div>
            <div class="stat-card">
                <div class="s-label">Tier 2 Matches</div>
                <div class="s-value amber">{stats['tier2']}</div>
            </div>
        </div>
        <div style="font-size:0.72rem;color:#475569;margin-bottom:20px;">
            🕐 Pool last updated: <strong style="color:#64748b;">{last_scraped_str}</strong>
            &nbsp;·&nbsp; Jobs refresh daily at <strong style="color:#64748b;">9 AM UTC</strong>
            &nbsp;·&nbsp; Sources: Greenhouse · Lever · RemoteOK · Jobicy
            {'&nbsp;·&nbsp; JSearch · Adzuna' if api_keys.get('jsearch_key') or api_keys.get('adzuna_id') else ''}
        </div>
        """, unsafe_allow_html=True)

        # ── Resume switcher — sits below stats, clear of Streamlit toolbar ──
        if len(all_resumes) > 0:
            resume_labels = {r['id']: f"{'✅  ' if r['is_active'] else '○  '}{r['label']}" for r in all_resumes}
            col_res, col_add = st.columns([5, 1])
            with col_res:
                selected_resume_id = st.selectbox(
                    "📄 Active Resume",
                    options=[r['id'] for r in all_resumes],
                    format_func=lambda rid: resume_labels[rid],
                    index=next((i for i, r in enumerate(all_resumes) if r['is_active']), 0),
                    key="resume_switcher",
                )
            with col_add:
                btn_disabled = len(all_resumes) >= 3
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("＋ Resume", use_container_width=True,
                             disabled=btn_disabled,
                             help="Maximum 3 resumes" if btn_disabled else "Add a new resume"):
                    st.session_state.show_add_resume = True

            if selected_resume_id != active_resume_id:
                db.set_active_resume(profile_id, selected_resume_id)
                st.session_state.auto_analyzed = False
                st.session_state.auto_analyzing = False
                st.rerun()

            # Add resume wizard
            if st.session_state.get('show_add_resume'):
                with st.expander("➕ Add New Resume", expanded=True):
                    new_label    = st.text_input("Label (e.g. 'ML Engineer', 'PM Resume')", key="new_res_label")
                    uploaded_res = st.file_uploader("Upload Resume PDF", type=["pdf"], key="new_res_pdf")
                    st.caption("Claude will auto-parse target roles and skills (~$0.01 cost)")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Parse & Add", type="primary", key="parse_add_btn"):
                            if not new_label.strip():
                                st.error("Please enter a label.")
                            elif not uploaded_res:
                                st.error("Please upload a PDF.")
                            elif not api_keys.get('anthropic_key'):
                                st.error("Anthropic API key required.")
                            else:
                                with st.spinner("Parsing with Claude..."):
                                    try:
                                        from resume_parser import ResumeParser
                                        parser    = ResumeParser(api_key=api_keys['anthropic_key'])
                                        pdf_bytes = uploaded_res.read()
                                        parsed    = parser.parse_resume(pdf_bytes)
                                        db.create_resume(
                                            profile_id, new_label.strip(),
                                            parsed.get('target_roles', []),
                                            parsed.get('core_skills', []),
                                            parsed.get('resume_text', ''),
                                            make_active=True
                                        )
                                        st.session_state.show_add_resume = False
                                        st.session_state.auto_analyzed   = False
                                        st.session_state.auto_analyzing  = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Parse error: {e}")
                    with c2:
                        if st.button("Cancel", key="cancel_add_res"):
                            st.session_state.show_add_resume = False
                            st.rerun()

        if not has_anthropic:
            st.warning("⚠️ Add your **Anthropic API key** in Settings to enable AI analysis.")

        # ══ AUTO-ANALYZE on login ═════════════════════════════
        # If there are new jobs AND the user has an API key AND we haven't
        # auto-analyzed this session yet → run automatically, no click needed.
        # ─────────────────────────────────────────────────────
        pass  # run_analysis defined at page scope below

    def run_analysis(jobs_to_run, label=""):
        """Shared analysis runner — uses active resume's roles/skills for matching."""
        claude_cfg = db.get_claude_filter_config(profile_id)
        # Build profile dict from active resume so each resume gets its own match scoring
        active_res = db.get_active_resume(profile_id)
        analysis_profile = dict(profile)
        if active_res:
            analysis_profile['target_roles'] = active_res.get('target_roles', profile.get('target_roles', []))
            analysis_profile['core_skills']  = active_res.get('core_skills',  profile.get('core_skills', []))
        matcher = IntegratedMatcher(
            anthropic_api_key=api_keys['anthropic_key'],
            profile=analysis_profile,
            filter_config=claude_cfg
        )

        # Pre-filter (instant, no API cost)
        filtered, reasons = matcher.pre_filter(jobs_to_run)
        passed   = len(filtered)
        rejected_pf = len(jobs_to_run) - passed

        # Mark pre-filter rejects immediately
        filtered_ids = {j['job_id'] for j in filtered}
        for job in jobs_to_run:
            if job['job_id'] not in filtered_ids:
                db.mark_global_job_status(profile_id, job['job_id'], 'rejected', resume_id=active_resume_id)

        if not filtered:
            return 0, 0, rejected_pf, reasons

        # AI analysis with progress bar
        bar    = st.progress(0)
        status = st.empty()
        t1 = t2 = rej = 0
        total  = max(len(filtered), 1)

        for i, job in enumerate(filtered):
            status.caption(f"{'🤖 ' + label + ' · ' if label else ''}{i+1}/{len(filtered)} — {job['company']}: {job['title'][:45]}")
            bar.progress((i + 1) / total)

            analysis = matcher.analyze_job(job)

            if analysis and matcher.is_qualified(analysis):
                if analysis.get('tier') == 2:
                    analysis['tailored_bullets'] = matcher.generate_tailored_bullets(job, analysis)
                else:
                    analysis['tailored_bullets'] = []
                db.save_analyzed_job(profile_id, job['job_id'], analysis, resume_id=active_resume_id)
                db.mark_global_job_status(profile_id, job['job_id'], 'analyzed', resume_id=active_resume_id)
                if analysis.get('tier') == 1: t1 += 1
                elif analysis.get('tier') == 2: t2 += 1
            else:
                db.mark_global_job_status(profile_id, job['job_id'], 'rejected', resume_id=active_resume_id)
                rej += 1

            time.sleep(0.35)

        bar.progress(1.0)
        status.empty()
        return t1, t2, rej + rejected_pf, reasons

    if st.session_state.page == "home":
        pending_jobs_placeholder = None  # re-fetched below

        # ── Auto-analyze: fires ONCE after new jobs arrive since last analysis ──
        # We use last_analyzed_at from the DB (not session_state) so browser
        # refreshes never re-trigger analysis and waste money.
        last_analyzed_at = db.get_last_analyzed(profile_id)

        # Determine if there are genuinely NEW jobs since last analysis
        new_since_analysis = False
        if pending_count > 0:
            if last_analyzed_at is None:
                new_since_analysis = True   # Never analyzed before
            else:
                # Check if any pending jobs were scraped after last analysis
                try:
                    from dateutil import parser as dateparser
                    last_ts = dateparser.parse(str(last_analyzed_at))
                    for job in pending_jobs:
                        scraped = job.get('scraped_at') or job.get('analyzed_at') or ''
                        if scraped:
                            job_ts = dateparser.parse(str(scraped))
                            if job_ts > last_ts:
                                new_since_analysis = True
                                break
                except Exception:
                    new_since_analysis = pending_count > 0  # fallback

        should_auto_analyze = (
            new_since_analysis
            and has_anthropic
            and not st.session_state.get('auto_analyzing')
            and not st.session_state.get('manual_collect_done_pending')  # wait for user confirm after manual collect
        )

        if should_auto_analyze and not st.session_state.get('auto_analyzing'):
            st.session_state.auto_analyzing = True
            st.rerun()

        if st.session_state.get('auto_analyzing'):
            fresh_pending = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)
            batch = fresh_pending[:30]  # cap at 30 — ~$0.06 per run

            st.markdown(f"### 🤖 Analyzing {len(batch)} new jobs for you...")
            st.caption("Pre-filtering first (instant, no cost), then Claude checks each match.")

            t1, t2, rej, reasons = run_analysis(batch, label="Auto-analyzing")

            # Persist that analysis ran — survives browser refresh
            db.set_last_analyzed(profile_id)
            st.session_state.auto_analyzing = False

            if t1 + t2 > 0:
                st.success(f"✓ Done — 🌟 **{t1} Tier 1** · ⭐ **{t2} Tier 2** · {rej} filtered out")
                time.sleep(1.2)
                st.session_state.page = "matches"
                st.rerun()
            else:
                st.info(f"Analysis complete — no strong matches in this batch ({rej} filtered out). Pool refreshes daily at 9 AM UTC.")
                with st.expander("Pre-filter breakdown"):
                    for reason, cnt in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
                        st.caption(f"  · {reason}: {cnt}")

        # ── Dashboard when idle (no new jobs or already analyzed) ──
        else:
            # Even in idle state, if there are unanalyzed jobs show the button first
            if pending_count > 0 and has_anthropic and not st.session_state.get('analyzing'):
                st.markdown(f"**{pending_count} unanalyzed jobs** are waiting in the pool.")
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1:
                    analyze_limit = st.number_input(
                        "Jobs to analyze",
                        min_value=1, max_value=pending_count,
                        value=min(30, pending_count), step=5,
                        key="idle_analyze_num_input"
                    )
                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    est = analyze_limit * 2
                    st.caption(f"⏱ ~{est//60}m {est%60}s &nbsp;&nbsp; 💰 ~${analyze_limit*0.002:.2f} API cost")
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🤖  Analyze Jobs", type="primary", use_container_width=True, key="idle_analyze_btn"):
                        st.session_state.analyzing = True
                        st.session_state.pending_analyze_limit = analyze_limit
                        st.rerun()

            if st.session_state.get('analyzing'):
                limit = st.session_state.pop('pending_analyze_limit', 30)
                jobs_to_run = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)[:limit]
                if jobs_to_run:
                    t1, t2, rej, reasons = run_analysis(jobs_to_run, label="Analyzing")
                    st.session_state.analyzing = False
                    if t1 + t2 > 0:
                        st.success(f"✓ Done — 🌟 **{t1} Tier 1** · ⭐ **{t2} Tier 2** · {rej} filtered out")
                        time.sleep(1.2)
                        st.session_state.page = "matches"
                        st.rerun()
                    else:
                        st.info(f"No strong matches in this batch ({rej} filtered). {pending_count - limit} jobs still waiting.")
                        st.rerun()

            st.markdown("---")
            # ── Manual collect section ─────────────────────────
            col_l, col_r = st.columns([3, 1])
            with col_l:
                st.markdown("### Job Pool")
                st.caption("Updated daily by GitHub Actions at 9 AM UTC. Use the button to pull fresh jobs mid-day.")
            with col_r:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔍  Refresh Now", type="primary", use_container_width=True,
                             help="Scrape Greenhouse, Lever, RemoteOK, Jobicy + any API keys you've added"):
                    st.session_state.manual_collect = True
                    st.session_state.collect_done   = False

            if st.session_state.get('manual_collect'):
                with st.spinner("Fetching from all sources — takes about 60–90 seconds..."):
                    try:
                        fresh_keys = db.get_api_keys(profile_id)
                        scraper    = IntegratedScraper(fresh_keys)
                        jobs       = scraper.scrape_all(
                            target_roles=profile['target_roles'],
                            limit_per_source=30
                        )
                        saved = sum(1 for j in jobs if db.save_global_job(j))
                        st.session_state.last_collect_saved = saved
                    except Exception as e:
                        st.error(f"Collection error: {e}")
                        st.session_state.last_collect_saved = 0
                    finally:
                        st.session_state.manual_collect  = False
                        st.session_state.collect_done    = True
                        st.session_state.auto_analyzed   = False  # allow re-analyze after fresh collect
                        pending_jobs  = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)
                        pending_count = len(pending_jobs)
                        st.rerun()

            if st.session_state.get('collect_done'):
                saved = st.session_state.get('last_collect_saved', 0)
                if saved > 0:
                    st.success(f"✓ {saved} new jobs added to pool.")
                    # Show an explicit analyze button — don't auto-trigger to avoid surprise charges
                    st.session_state.manual_collect_done_pending = True
                    st.session_state.manual_collect_new_count    = saved
                    st.session_state.collect_done = False
                else:
                    st.info("No new jobs found (all already in pool). Try again later or add JSearch/Adzuna keys for more volume.")
                    st.session_state.collect_done = False

            # After manual collect: show confirm-to-analyze button
            if st.session_state.get('manual_collect_done_pending'):
                new_ct = st.session_state.get('manual_collect_new_count', 0)
                fresh_pending_ct = len(db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id))
                st.markdown(f"**{new_ct} new jobs collected.** {fresh_pending_ct} unanalyzed jobs ready.")
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1:
                    alimit = st.number_input("Jobs to analyze", min_value=1,
                                             max_value=max(fresh_pending_ct, 1),
                                             value=min(30, max(fresh_pending_ct, 1)), step=5,
                                             key="post_collect_limit")
                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    est = alimit * 2
                    st.caption(f"⏱ ~{est//60}m {est%60}s &nbsp;&nbsp; 💰 ~${alimit*0.002:.2f} API cost")
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🤖  Analyze Now", type="primary", use_container_width=True, key="post_collect_analyze"):
                        st.session_state.manual_collect_done_pending = False
                        batch = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)[:alimit]
                        st.markdown("**Running AI analysis...**")
                        t1, t2, rej, reasons = run_analysis(batch)
                        db.set_last_analyzed(profile_id)
                        st.success(f"✓ Done — 🌟 **{t1} Tier 1** · ⭐ **{t2} Tier 2** · {rej} filtered")
                        if t1 + t2 > 0:
                            time.sleep(0.8)
                            st.session_state.page = "matches"
                            st.rerun()
                    if st.button("Skip", use_container_width=True, key="post_collect_skip"):
                        st.session_state.manual_collect_done_pending = False
                        st.rerun()

            st.markdown("---")

            # ── Status: what's ready ────────────────────────────
            existing_matches = stats['tier1'] + stats['tier2']

            if existing_matches > 0:
                st.markdown(f"""
                <div class="info-panel" style="display:flex;align-items:center;justify-content:space-between;">
                    <div>
                        <div style="font-size:0.875rem;color:#94a3b8;margin-bottom:4px;">
                            You have <strong style="color:#f1f5f9;">{existing_matches} matched jobs</strong> waiting.
                        </div>
                        <div style="font-size:0.75rem;color:#475569;">
                            🌟 {stats['tier1']} Tier 1 best matches &nbsp;·&nbsp; ⭐ {stats['tier2']} Tier 2 good matches
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("🎯  View My Matches →", type="primary"):
                    st.session_state.page = "matches"
                    st.rerun()

            elif pending_count > 0 and has_anthropic:
                # Jobs in pool not yet analyzed — always show manual option
                # (auto-analyze only runs 30 at a time; remaining jobs always need manual trigger)
                st.markdown(f"**{pending_count} unanalyzed jobs** are waiting in the pool.")
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1:
                    analyze_limit = st.number_input(
                        "Jobs to analyze",
                        min_value=1, max_value=pending_count,
                        value=min(30, pending_count), step=5
                    )
                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    est = analyze_limit * 2
                    st.caption(f"⏱ ~{est//60}m {est%60}s &nbsp;&nbsp; 💰 ~${analyze_limit*0.002:.2f} API cost")
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🤖  Analyze Jobs", type="primary", use_container_width=True):
                        st.session_state.analyzing = True

                if st.session_state.get('analyzing'):
                    jobs_to_run = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)[:analyze_limit]
                    st.markdown("**Running AI analysis...**")
                    t1, t2, rej, reasons = run_analysis(jobs_to_run)
                    st.session_state.analyzing     = False
                    st.session_state.auto_analyzed = True
                    st.success(f"✓ Analysis complete — 🌟 **{t1} Tier 1** · ⭐ **{t2} Tier 2** · ❌ {rej} filtered out")
                    if t1 + t2 > 0:
                        time.sleep(0.8)
                        st.session_state.page = "matches"
                        st.rerun()

            elif not has_anthropic:
                st.warning("⚠️ Add your **Anthropic API key** in Settings → API Keys to enable AI matching.")

            else:
                st.markdown("""
                <div class="info-panel" style="color:#475569;font-size:0.875rem;text-align:center;padding:24px;">
                    🎉 You're all caught up! No new jobs to analyze.<br>
                    <span style="font-size:0.75rem;">The pool refreshes daily at 9 AM UTC — check back tomorrow.</span>
                </div>
                """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # MATCHES
    # ══════════════════════════════════════════
    elif st.session_state.page == "matches":
        t1_jobs = db.get_analyzed_jobs(profile_id, tier=1, resume_id=active_resume_id)
        t2_jobs = db.get_analyzed_jobs(profile_id, tier=2, resume_id=active_resume_id)
        total   = len(t1_jobs) + len(t2_jobs)

        # Check if new unanalyzed jobs are available
        new_pending = db.get_global_jobs_for_user(profile_id, hours=user_lookback, resume_id=active_resume_id)
        new_count   = len(new_pending)

        # Header row
        hc1, hc2, hc3 = st.columns([3, 1, 1])
        with hc1:
            st.markdown("## My Matches")
            st.caption(f"{total} jobs matched · {new_count} new unanalyzed in pool")
        with hc2:
            if new_count > 0 and bool(api_keys.get('anthropic_key')):
                if st.button(f"🤖 Analyze {new_count} New", type="primary", use_container_width=True):
                    batch = new_pending[:30]
                    t1c, t2c, rejc, _ = run_analysis(batch, label="Matches")
                    db.set_last_analyzed(profile_id)
                    st.success(f"✅ Done — {t1c} Tier 1, {t2c} Tier 2, {rejc} rejected")
                    st.rerun()
        with hc3:
            if st.button("← Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()

        if total == 0:
            st.markdown("""
            <div class="info-panel">
                <div style="font-size:0.875rem;color:#475569;text-align:center;padding:20px 0;">
                    No matches yet — new jobs will be analyzed automatically when you log in.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Summary pills
            st.markdown(f"""
            <div style="display:flex;gap:8px;margin-bottom:20px;align-items:center;">
                <span class="pill t1">🌟 {len(t1_jobs)} Tier 1 — Best Match</span>
                <span class="pill t2">⭐ {len(t2_jobs)} Tier 2 — Good Match</span>
            </div>
            """, unsafe_allow_html=True)

            tab_t1, tab_t2 = st.tabs([
                f"🌟  Tier 1  ({len(t1_jobs)})",
                f"⭐  Tier 2  ({len(t2_jobs)})"
            ])

            def show_job(job):
                tier_cls = "t1" if job['tier'] == 1 else "t2"
                tier_pill = (f'<span class="pill t1">🌟 Tier 1</span>'
                             if job['tier'] == 1
                             else '<span class="pill t2">⭐ Tier 2</span>')

                applied_badge = '<span class="pill green">✅ Applied</span>' if job.get('applied') else ''

                # Format the date the job was added to the pool
                date_badge = ''
                if job.get('analyzed_at'):
                    try:
                        from dateutil import parser as dateparser
                        d = dateparser.parse(str(job['analyzed_at']))
                        date_badge = f'<span class="pill" style="background:#1e2535;color:#64748b;">📅 Added {d.strftime("%-d %b")}</span>'
                    except Exception:
                        pass

                st.markdown(f"""
                <div class="jcard {tier_cls}">
                    <div class="jc-co">{job['company']}</div>
                    <div class="jc-title">{job['title']}</div>
                    <div class="jc-tags">
                        {tier_pill}
                        <span class="pill blue">⚡ {job['match_score']}/100</span>
                        <span class="pill purple">🎯 Role {job['role_match_pct']}%</span>
                        <span class="pill green">💡 Skills {job['skill_match_pct']}%</span>
                        <span class="pill amber">💼 {job['experience_required']}+ yrs</span>
                        {date_badge}
                        {applied_badge}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                rc1, rc2, rc3 = st.columns([4, 1, 1])
                with rc1:
                    with st.expander("Why this matches"):
                        st.markdown(
                            f'<p style="color:#94a3b8;font-size:0.875rem;line-height:1.6;">'
                            f'{job.get("reasoning","No analysis available.")}</p>',
                            unsafe_allow_html=True
                        )
                    bullets = job.get('tailored_bullets', [])
                    if job['tier'] == 2 and bullets:
                        with st.expander("✏️ Tailored Resume Bullets"):
                            bhtml = "".join(
                                f'<div class="bx-item">{b}</div>' for b in bullets
                            )
                            st.markdown(f"""
                            <div class="bx">
                                <div class="bx-hdr">Reworded to match this JD — review before using</div>
                                {bhtml}
                            </div>
                            """, unsafe_allow_html=True)
                with rc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.link_button("Apply →", job['url'], use_container_width=True)
                with rc3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if job.get('applied'):
                        if st.button("↩ Undo", key=f"undo_{job['job_id']}", use_container_width=True):
                            db.unmark_job_applied(job['job_id'])
                            st.rerun()
                    else:
                        if st.button("✅ Applied", key=f"applied_{job['job_id']}", use_container_width=True):
                            db.mark_job_applied(job['job_id'])
                            st.rerun()

                st.markdown("<hr>", unsafe_allow_html=True)

            with tab_t1:
                if not t1_jobs:
                    st.caption("No Tier 1 matches yet.")
                for job in t1_jobs:
                    show_job(job)

            with tab_t2:
                if not t2_jobs:
                    st.caption("No Tier 2 matches yet.")
                for job in t2_jobs:
                    show_job(job)

    # ══════════════════════════════════════════
    # SETTINGS
    # ══════════════════════════════════════════
    elif st.session_state.page == "settings":
        hc1, hc2 = st.columns([3, 1])
        with hc1:
            st.markdown("## Settings")
            st.caption("Configure API keys, filters, and your profile")
        with hc2:
            if st.button("← Back to Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()

        if st.session_state.get('show_setup_wizard'):
            st.info("👋 Welcome! Add your API keys below to get started.")

        tab_keys, tab_pre, tab_ai, tab_schedule, tab_profile = st.tabs([
            "🔑  API Keys",
            "⚡  Pre-Filters",
            "🤖  AI Filters",
            "🕐  Schedule",
            "👤  Profile",
        ])

        # ── API KEYS ─────────────────────────
        with tab_keys:
            st.caption("Your API keys are stored securely and never displayed.")

            # Status indicators — just connected/not connected, no values shown
            key_status_items = [
                ("Anthropic API Key", bool(api_keys.get('anthropic_key')), "Required — powers all AI analysis"),
                ("JSearch API Key",   bool(api_keys.get('jsearch_key')),   "Optional — LinkedIn, Indeed, Glassdoor, ZipRecruiter"),
                ("Adzuna",            bool(api_keys.get('adzuna_id')),     "Optional — Adzuna job source"),
            ]
            for label, connected, desc in key_status_items:
                dot = "ok" if connected else "missing"
                status_txt = "Connected" if connected else "Not set"
                st.markdown(f"""
                <div class="key-row">
                    <div class="key-dot {dot}"></div>
                    <div style="flex:1;">
                        <div class="key-name">{label}</div>
                        <div style="font-size:0.75rem;color:#64748b;">{desc}</div>
                    </div>
                    <div class="key-status-{'ok' if connected else 'missing'}">{status_txt}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown('<div class="sec-hdr">Update API Keys</div>', unsafe_allow_html=True)
            st.caption("Leave any field blank to keep its current value.")

            new_anthropic = st.text_input(
                "Anthropic API Key",
                type="password",
                placeholder="sk-ant-... (leave blank to keep current)",
                help="Get yours at console.anthropic.com"
            )
            st.caption("✅ **Greenhouse, Lever, RemoteOK, Jobicy** run for free — no keys needed.")
            c1, c2 = st.columns(2)
            with c1:
                new_jsearch = st.text_input("JSearch API Key", type="password",
                                             placeholder="Leave blank to keep current")
            with c2:
                new_adzuna_id  = st.text_input("Adzuna App ID",  type="password",
                                                placeholder="Leave blank to keep current")
                new_adzuna_key = st.text_input("Adzuna API Key", type="password",
                                                placeholder="Leave blank to keep current")

            if st.button("💾  Save API Keys", type="primary"):
                updated = {
                    'anthropic_key': new_anthropic.strip() or api_keys.get('anthropic_key', ''),
                    'jsearch_key':   new_jsearch.strip()   or api_keys.get('jsearch_key', ''),
                    'adzuna_id':     new_adzuna_id.strip() or api_keys.get('adzuna_id', ''),
                    'adzuna_key':    new_adzuna_key.strip() or api_keys.get('adzuna_key', ''),
                }
                db.update_api_keys(profile_id, updated)
                api_keys = db.get_api_keys(profile_id)
                st.session_state.show_setup_wizard = False
                st.success("✅ API keys updated!")
                st.rerun()

        # ── PRE-FILTERS ───────────────────────
        with tab_pre:
            pf = db.get_pre_filter_config(profile_id)
            if not pf:
                db.create_default_pre_filter(profile_id)
                pf = db.get_pre_filter_config(profile_id)

            st.caption("These run before AI analysis — instant, no API cost.")

            max_years = st.slider(
                "Reject jobs requiring more than N years experience",
                0, 15, pf['max_years_experience']
            )

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Reject these seniority levels</div>',
                        unsafe_allow_html=True)
            ds = pf['reject_seniority_levels']
            c1, c2, c3, c4 = st.columns(4)
            senior    = c1.checkbox("Senior",    "senior"    in ds)
            staff     = c1.checkbox("Staff",     "staff"     in ds)
            principal = c2.checkbox("Principal", "principal" in ds)
            lead      = c2.checkbox("Lead",      "lead"      in ds)
            manager   = c3.checkbox("Manager",   "manager"   in ds)
            director  = c3.checkbox("Director",  "director"  in ds)
            vp        = c4.checkbox("VP",        "vp"        in ds)
            chief     = c4.checkbox("Chief/Head","chief"     in ds)

            custom_sen = st.text_input("Additional seniority keywords (comma-separated)",
                                        placeholder="architect, tech lead...")

            seniority = []
            if senior:    seniority.append("senior")
            if staff:     seniority.append("staff")
            if principal: seniority.append("principal")
            if lead:      seniority.append("lead")
            if manager:   seniority.append("manager")
            if director:  seniority.append("director")
            if vp:        seniority.extend(["vp", "vice president"])
            if chief:     seniority.extend(["chief", "head of"])
            if custom_sen:
                seniority.extend([x.strip().lower() for x in custom_sen.split(',') if x.strip()])

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Reject these job types</div>',
                        unsafe_allow_html=True)
            dt = pf['reject_job_types']
            c1, c2 = st.columns(2)
            intern_cb   = c1.checkbox("Internship", "internship" in dt)
            parttime_cb = c1.checkbox("Part-time",  "part-time"  in dt)
            freelance_cb= c2.checkbox("Freelance",  "freelance"  in dt)
            contract_cb = c2.checkbox("Contractor", "contractor" in dt)
            custom_types = st.text_input("Additional types to reject (comma-separated)",
                                          placeholder="temporary, seasonal...")

            types = []
            if intern_cb:   types.extend(["internship", "intern"])
            if parttime_cb: types.extend(["part-time", "part time"])
            if freelance_cb:types.append("freelance")
            if contract_cb: types.append("contractor")
            if custom_types:
                types.extend([x.strip().lower() for x in custom_types.split(',') if x.strip()])

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Always reject these job titles</div>',
                        unsafe_allow_html=True)
            reject_text = st.text_area("One title per line",
                                        value="\n".join(pf['reject_specific_titles']),
                                        height=100, label_visibility="collapsed")
            reject_titles = [l.strip() for l in reject_text.split('\n') if l.strip()]

            if st.button("💾  Save Pre-Filters", type="primary"):
                db.update_pre_filter_config(profile_id, {
                    'max_years_experience':    max_years,
                    'reject_seniority_levels': seniority,
                    'reject_job_types':        types,
                    'reject_specific_titles':  reject_titles,
                    'check_full_description':  True,
                })
                st.success("Pre-filter settings saved!")

        # ── AI FILTERS ────────────────────────
        with tab_ai:
            cf = db.get_claude_filter_config(profile_id)
            if not cf:
                db.create_default_claude_filter(profile_id)
                cf = db.get_claude_filter_config(profile_id)

            st.caption("These rules are sent to Claude with each job to determine qualification and tier.")

            st.markdown('<div class="sec-hdr">Experience</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            max_exp     = c1.slider("Max years required (hard limit)", 0, 15, cf['max_experience_required'])
            allow_pref  = c2.checkbox("Allow 'preferred' experience (not required)", cf['allow_preferred_experience'])
            strict      = c2.checkbox("Strict experience check", cf['strict_experience_check'])

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Skill Matching & Tiers</div>',
                        unsafe_allow_html=True)
            st.caption("Tier 1 = best match. Tier 2 = good match (gets tailored resume bullets).")
            c1, c2, c3 = st.columns(3)
            min_skill   = c1.slider("Min skill match %",  0, 100, cf['min_skill_match_percent'])
            tier1_thr   = c2.slider("Tier 1 threshold %", 0, 100, cf['tier1_skill_threshold'])
            tier2_thr   = c3.slider("Tier 2 threshold %", 0, 100, cf['tier2_skill_threshold'])
            min_role    = st.slider("Min role relevance %", 0, 100, cf['min_target_role_percentage'])

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Employment Type</div>',
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c2h     = c1.checkbox("Accept contract-to-hire", cf['accept_contract_to_hire'])
            c2w     = c1.checkbox("Accept W2 contract",      cf['accept_contract_w2'])
            rej_int = c2.checkbox("Reject internships",      cf['reject_internships'])
            ptime   = c2.checkbox("Accept part-time",        cf['accept_part_time'])

            c1, c2 = st.columns(2)
            acc_str = c1.text_input("Also accept (comma-separated)",
                                     value=", ".join(cf.get('custom_accept_employment',[])),
                                     placeholder="temp-to-hire, contract-to-permanent")
            rej_str = c2.text_input("Also reject (comma-separated)",
                                     value=", ".join(cf.get('custom_reject_employment',[])),
                                     placeholder="1099, gig, per diem")

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Visa & Location</div>',
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            visa    = c1.checkbox("I need visa sponsorship",         cf['requires_visa_sponsorship'])
            clear   = c1.checkbox("Reject security clearance jobs",  cf['reject_clearance_jobs'])
            remote  = c2.checkbox("Remote jobs only",                cf['accept_remote_only'])

            st.markdown('<div class="sec-hdr" style="margin-top:16px;">Auto-Reject Phrases</div>',
                        unsafe_allow_html=True)
            st.caption("Jobs containing any of these phrases are instantly rejected.")
            phrases_txt = st.text_area("One phrase per line",
                                        value="\n".join(cf['auto_reject_phrases']),
                                        height=100, label_visibility="collapsed")
            phrases = [l.strip() for l in phrases_txt.split('\n') if l.strip()]

            if st.button("💾  Save AI Filters", type="primary"):
                db.update_claude_filter_config(profile_id, {
                    'strict_experience_check':   strict,
                    'max_experience_required':   max_exp,
                    'allow_preferred_experience':allow_pref,
                    'min_skill_match_percent':   min_skill,
                    'tier1_skill_threshold':     tier1_thr,
                    'tier2_skill_threshold':     tier2_thr,
                    'min_target_role_percentage':min_role,
                    'accept_contract_to_hire':   c2h,
                    'accept_contract_w2':        c2w,
                    'reject_internships':        rej_int,
                    'accept_part_time':          ptime,
                    'requires_visa_sponsorship': visa,
                    'reject_clearance_jobs':     clear,
                    'accept_remote_only':        remote,
                    'auto_reject_phrases':       phrases,
                    'custom_accept_employment':  [x.strip().lower() for x in acc_str.split(',') if x.strip()],
                    'custom_reject_employment':  [x.strip().lower() for x in rej_str.split(',') if x.strip()],
                })
                st.success("AI filter settings saved!")

        # ── SCHEDULE ─────────────────────────
        with tab_schedule:
            cur_lookback = db.get_job_lookback_hours(profile_id)

            st.markdown('<div class="sec-hdr">Job Lookback Window</div>', unsafe_allow_html=True)
            st.caption("How far back to look for new jobs each time you open the app. Shorter = fewer, fresher jobs. Longer = more jobs but more Claude cost.")

            lookback_options = {
                6:  "6 hours   — ultra-fresh, fewest jobs",
                12: "12 hours  — good for twice-daily check-ins",
                24: "24 hours  — recommended (matches daily collection)",
                48: "48 hours  — catch up after skipping a day",
                72: "72 hours  — catch up after a weekend",
            }

            col_a, col_b = st.columns(2)
            with col_a:
                selected_lookback = st.selectbox(
                    "Lookback window",
                    options=list(lookback_options.keys()),
                    index=list(lookback_options.keys()).index(cur_lookback) if cur_lookback in lookback_options else 2,
                    format_func=lambda h: lookback_options[h],
                )
            with col_b:
                st.markdown("<br>", unsafe_allow_html=True)
                est_cost = selected_lookback * 0.003
                st.caption(f"Currently saved: **{cur_lookback}h** · Est. ~${est_cost:.2f} per analysis run")

            st.markdown("---")
            st.caption("ℹ️ Jobs are collected once daily via GitHub Actions. The collection time is global and set in the workflow file — it is not configurable per user.")

            if st.button("Save", type="primary"):
                prev_lookback = cur_lookback
                db.set_job_lookback_hours(profile_id, selected_lookback)
                # If user widened the window, reset last_analyzed_at so the next
                # login re-analyzes jobs that were previously outside the window
                if selected_lookback > prev_lookback:
                    conn = db.get_connection()
                    cur  = conn.cursor()
                    ph   = '%s' if hasattr(db, 'db_config') else '?'
                    cur.execute(f'UPDATE profiles SET last_analyzed_at = NULL WHERE id = {ph}', (profile_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    # Reset auto_analyzed so home page triggers fresh analysis immediately
                    st.session_state.auto_analyzed = False
                    st.session_state.auto_analyzing = False
                    st.session_state.page = 'home'
                    st.rerun()
                else:
                    st.success(f"✅ Saved — looking back {selected_lookback}h for new jobs.")

        # ── PROFILE ───────────────────────────
        with tab_profile:
            # ── Account info (read-only) ──────────────────────
            st.markdown(f"""
            <div class="info-panel">
                <div class="sec-hdr">Account</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:0.875rem;">
                    <div>
                        <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">Name</div>
                        <div style="color:#e2e8f0;">{profile['name']}</div>
                    </div>
                    <div>
                        <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">Email</div>
                        <div style="color:#e2e8f0;">{profile['email']}</div>
                    </div>
                    <div>
                        <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">Experience</div>
                        <div style="color:#e2e8f0;">{profile.get('experience_years','?')} years · {profile.get('experience_level','?').title()}</div>
                    </div>
                    <div>
                        <div style="color:#475569;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">Resumes</div>
                        <div style="color:#e2e8f0;">{len(all_resumes)}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown('<div class="sec-hdr">Manage Resumes</div>', unsafe_allow_html=True)
            st.caption("Each resume has its own target roles, skills, and match history. Switch between them from the Home page dropdown.")

            for res in all_resumes:
                active_badge = " 🟢 Active" if res['is_active'] else ""
                with st.expander(f"{res['label']}{active_badge}", expanded=res['is_active']):
                    r_label  = st.text_input("Label", value=res['label'], key=f"rlabel_{res['id']}")
                    r_roles  = st.text_area("Target roles (one per line)",
                                            value="\n".join(res.get('target_roles', [])),
                                            height=120, key=f"rroles_{res['id']}")
                    r_skills = st.text_area("Core skills (comma-separated)",
                                            value=", ".join(res.get('core_skills', [])),
                                            height=80, key=f"rskills_{res['id']}")

                    ca, cb, cc = st.columns(3)
                    with ca:
                        if st.button("💾 Save", key=f"rsave_{res['id']}", type="primary"):
                            new_roles  = [r.strip() for r in r_roles.split("\n")  if r.strip()]
                            new_skills = [s.strip() for s in r_skills.split(",") if s.strip()]
                            db.update_resume(res['id'], r_label.strip(), new_roles, new_skills)
                            if res['is_active']:
                                db.set_active_resume(profile_id, res['id'])  # resets last_analyzed_at
                            st.success("Saved.")
                            st.rerun()
                    with cb:
                        if not res['is_active']:
                            if st.button("✅ Set Active", key=f"ract_{res['id']}"):
                                db.set_active_resume(profile_id, res['id'])
                                st.session_state.auto_analyzed = False
                                st.rerun()
                    with cc:
                        if len(all_resumes) > 1:
                            if st.button("🗑 Delete", key=f"rdel_{res['id']}"):
                                db.delete_resume(profile_id, res['id'])
                                st.rerun()