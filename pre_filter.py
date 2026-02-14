# pre_filter.py - STRICT CONFIG ENFORCEMENT

import re
from filters_config import PRE_FILTER_CONFIG, get_experience_patterns

def should_analyze(job):
    """
    Universal pre-filter using STRICT config values
    Returns: (should_analyze: bool, reason: str)
    """
    title = job.get('Title', '').lower()
    description = job.get('Description', '').lower()
    
    # 1. CHECK: Seniority level (STRICT - no .get() with defaults)
    seniority_keywords = PRE_FILTER_CONFIG['reject_seniority_levels']
    for keyword in seniority_keywords:
        # Word boundary check to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, title):
            return False, f"Seniority: {keyword}"
    
    # 2. CHECK: Job type (STRICT - no defaults)
    job_types = PRE_FILTER_CONFIG['reject_job_types']
    for job_type in job_types:
        if job_type in title:
            return False, f"Job type: {job_type}"
    
    # 3. CHECK: Specific titles (STRICT - word boundary matching)
    specific_titles = PRE_FILTER_CONFIG['reject_specific_titles']
    for reject_title in specific_titles:
        # Word boundary: "data analyst" won't match "accounting analyst"
        pattern = r'\b' + re.escape(reject_title) + r'\b'
        if re.search(pattern, title):
            return False, f"Specific title: {reject_title}"
    
    # 4. CHECK: Experience requirements (STRICT - exact config value)
    check_full = PRE_FILTER_CONFIG['check_full_description']
    text_to_check = description if check_full else description[:500]
    
    patterns = get_experience_patterns()
    max_years = PRE_FILTER_CONFIG['max_years_experience']  # STRICT - no default
    
    for pattern in patterns:
        matches = re.findall(pattern, text_to_check)
        for match in matches:
            if isinstance(match, tuple):
                years_list = [int(m) for m in match if m.isdigit()]
                min_years = min(years_list) if years_list else 0
            else:
                min_years = int(match) if match.isdigit() else 0
            
            # STRICT: Use EXACT value from config (if config=2, reject 2+)
            if min_years >= max_years:
                return False, f"{min_years}+ years required"
    
    # 5. PASS: Send to Claude
    return True, "Passed pre-filter"

def pre_filter_jobs(jobs):
    """Filter jobs using STRICT config values"""
    filtered = []
    rejected = {}
    
    for job in jobs:
        should_pass, reason = should_analyze(job)
        
        if should_pass:
            filtered.append(job)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1
    
    # Print statistics
    print(f"\n📊 PRE-FILTER RESULTS:")
    print(f"  📥 Total jobs: {len(jobs)}")
    print(f"  ✅ Passed to Claude: {len(filtered)}")
    print(f"  ❌ Rejected (free): {len(jobs) - len(filtered)}")
    
    if rejected:
        print(f"\n  Rejection breakdown:")
        for reason, count in sorted(rejected.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {reason}: {count}")
    
    return filtered, rejected