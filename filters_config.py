# filters_config.py
# ML Engineer | 1-2 years experience | Needs H1B sponsorship

# ==================== PRE-FILTER SETTINGS ====================
# These are FREE checks done BEFORE sending to Claude

PRE_FILTER_CONFIG = {
    # Experience threshold (reject jobs requiring this many years or more)
    "max_years_experience": 4,  # Reject "2+ years required"
    
    # Seniority levels to auto-reject
    "reject_seniority_levels": [
        "senior",
        "staff", 
        "principal",
        "lead",
        "manager",
        "director",
        "vp",
        "vice president",
        "head of",
        "chief"
    ],
    
    # Job types to reject based on employment type
    "reject_job_types": [
        "internship",
        "intern",
        "part-time",
        "part time", 
        "freelance",
        "contractor"
    ],
    
    # Specific job titles/roles to ALWAYS reject
    "reject_specific_titles": [
        # Roles you explicitly don't want (from your resume profile) 
        "business analyst",
        "data analyst",
        "support engineer",
        "technical writer",
        "project manager",
        "product manager",
        "sales engineer",
        "solutions engineer",
        "customer success"
    ],
    
    # Whether to check full description or just first 500 chars for experience
    "check_full_description": True,  # Check entire job description
}

# ==================== CLAUDE ANALYSIS SETTINGS ====================
# These are SMART checks done by Claude (costs $0.001 per job)

CLAUDE_FILTER_CONFIG = {
    # === EXPERIENCE VALIDATION ===
    "strict_experience_check": True,      # Strictly enforce experience requirements
    "max_experience_required": 4,          # Auto-reject if job requires ≥ 3 years
    "allow_preferred_experience": True,    # Accept "X years preferred" (not required)
    
    # === SKILL MATCHING ===
    "min_skill_match_percent": 65,  # Need at least 65% of required skills
    "tier1_skill_threshold": 85,     # 85%+ skills = Tier 1 (strong match)
    "tier2_skill_threshold": 65,     # 65-84% skills = Tier 2 (backup)
    
    # === ROLE RELEVANCE ===
    # You want ML/AI Engineer roles - be strict about role matching
    "min_target_role_percentage": 70,  # Job must be ≥70% ML/AI work
    # This means: Frontend jobs with "AI nice to have" will be rejected
    
    # === EMPLOYMENT TYPE ===
    "accept_contract_to_hire": True,   # Accept if converts to full-time
    "accept_contract_w2": False,       # Reject pure W2 contract roles
    "reject_internships": True,        # You want full-time, not internships
    "accept_part_time": False,         # Only full-time roles
    
    # === LOCATION/VISA ===
    "requires_visa_sponsorship": True,  # You need H1B in 2 years
    "reject_clearance_jobs": True,      # Can't get security clearance on H1B
    "accept_remote_only": False,        # Accept both remote and on-site
    
    # === ADDITIONAL FILTERS ===
    # Automatically reject if job description contains these phrases
    "auto_reject_phrases": [
        "us citizen only",
        "u.s. citizen only",
        "citizenship required",
        "security clearance required",
        "active clearance",
        "no visa sponsorship",
        "cannot sponsor",
        "will not sponsor",
        "must be authorized to work without sponsorship"
    ],
}

# ==================== OUTPUT SETTINGS ====================

OUTPUT_CONFIG = {
    # How many top matches to show in summary
    "top_matches_to_display": 5,
    
    # Minimum score to be considered "qualified"
    "min_qualification_score": 60,
    
    # Whether to save rejected jobs to sheet (for debugging)
    "save_rejection_reasons": True,
}

# ==================== COST SETTINGS ====================

COST_CONFIG = {
    # Cost per Claude API call (Haiku pricing)
    "cost_per_job_analysis": 0.001,  # $0.001 per job
    
    # Show cost estimates
    "show_cost_estimates": True,
}

# ==================== HELPER FUNCTIONS ====================

def get_experience_patterns():
    """
    Regex patterns for detecting experience requirements
    These catch variations like "minimum of 7 years", "7+ years required", etc.
    """
    return [
        r'(\d+)\+?\s*years?\s+required',           # "7+ years required"
        r'minimum\s+of\s+(\d+)\s*years?',          # "minimum of 7 years" ✅ Fixed
        r'minimum\s+(\d+)\s*years?',               # "minimum 7 years"
        r'at least\s+(\d+)\s*years?',              # "at least 7 years"
        r'requires?\s+(\d+)\+?\s*years?',          # "requires 7+ years"
        r'(\d+)\+\s*years?\s+of\s+experience',     # "7+ years of experience"
        r'(\d+)\s*to\s*(\d+)\s*years?',            # "5 to 7 years"
        r'(\d+)-(\d+)\s*years?',                   # "5-7 years"
        r'(\d+)\s*\+\s*years',                     # "7 + years"
    ]

def should_use_strict_role_matching(resume_profile):
    """
    You have 6 specific target roles (ML Engineer, AI Engineer, etc.)
    → Use STRICT matching (70% of job must be ML/AI work)
    """
    target_roles = resume_profile.get('target_roles', [])
    
    # You have 6 target roles - all very specific to ML/AI
    # → Use strict matching
    if len(target_roles) <= 6:
        min_pct = CLAUDE_FILTER_CONFIG.get('min_target_role_percentage', 70)
        return True, min_pct
    
    # Fallback for other users
    return False, None

# ==================== YOUR SPECIFIC CONFIGURATION SUMMARY ====================

"""
KRISHNA'S JOB SEARCH CONFIGURATION:

Profile:
- Role: ML/AI Engineer
- Experience: 1-2 years (junior level)
- Skills: Python, PyTorch, LLMs, LangChain, RAG, AWS, Docker
- Location: USA only
- Visa: Needs H1B sponsorship in 2 years

What Gets REJECTED (Pre-filter - FREE):
✗ Jobs requiring 5+ years experience
✗ Senior/Staff/Principal/Lead roles
✗ Internships, Part-time, Freelance
✗ Data Scientist, Business Analyst, Support roles
✗ Sales Engineer, Solutions Engineer

What Gets REJECTED (Claude - $0.001 per job):
✗ Jobs requiring 4+ years experience
✗ Jobs that are <70% ML/AI work (e.g., Frontend with "AI nice to have")
✗ Jobs requiring <60% skill match
✗ Citizenship/Clearance requirements
✗ "No visa sponsorship" jobs
✗ Pure contract roles (not converting to FTE)

What Gets ACCEPTED:
✓ ML Engineer, AI Engineer, Research Engineer roles
✓ 0-3 years experience required (or "preferred")
✓ Full-time or contract-to-hire (converting to FTE)
✓ ≥60% skill match with your resume
✓ ≥70% of job is actual ML/AI work
✓ Sponsors H1B or doesn't mention visa requirements

Expected Results:
- Daily collection: 150-200 jobs
- Pre-filter removes: ~100 jobs (free)
- Claude analyzes: ~50-100 jobs ($0.05-0.10/day)
- Qualified matches: ~20-40 jobs
- Tier 1 (strong): ~5-10 jobs
- Tier 2 (backup): ~15-30 jobs

Monthly Cost: ~$3-4
"""

# ==================== CUSTOMIZATION NOTES ====================

"""
If you want to ADJUST your filters, edit these values:

Make filters MORE STRICT (fewer jobs, higher quality):
- PRE_FILTER_CONFIG["max_years_experience"] = 3  # Instead of 5
- CLAUDE_FILTER_CONFIG["max_experience_required"] = 3  # Instead of 4
- CLAUDE_FILTER_CONFIG["min_skill_match_percent"] = 70  # Instead of 60
- CLAUDE_FILTER_CONFIG["min_target_role_percentage"] = 80  # Instead of 70

Make filters MORE FLEXIBLE (more jobs, lower quality):
- PRE_FILTER_CONFIG["max_years_experience"] = 7
- CLAUDE_FILTER_CONFIG["max_experience_required"] = 5
- CLAUDE_FILTER_CONFIG["min_skill_match_percent"] = 50
- CLAUDE_FILTER_CONFIG["min_target_role_percentage"] = 50

Accept contract roles:
- CLAUDE_FILTER_CONFIG["accept_contract_w2"] = True

If you get US work authorization later:
- CLAUDE_FILTER_CONFIG["requires_visa_sponsorship"] = False
- CLAUDE_FILTER_CONFIG["reject_clearance_jobs"] = False
- CLAUDE_FILTER_CONFIG["auto_reject_phrases"] = []  # Clear visa restrictions
"""