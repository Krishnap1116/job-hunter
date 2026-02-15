# pre_filter.py - FIXED VERSION WITH ERROR HANDLING

import re
from filters_config import PRE_FILTER_CONFIG, get_experience_patterns

def should_analyze(job):
    """
    Universal pre-filter with error handling
    Returns: (should_analyze: bool, reason: str)
    """
    title = job.get('Title', '').lower()
    description = job.get('Description', '').lower()
    
    # VALIDATE: Ensure we have valid data
    if not title or not isinstance(title, str):
        return False, "Invalid title"
    if not isinstance(description, str):
        description = ""  # Allow empty description
    
    # 1. CHECK: Seniority level
    seniority_keywords = PRE_FILTER_CONFIG['reject_seniority_levels']
    for keyword in seniority_keywords:
        # VALIDATE: Ensure keyword is a string
        if not keyword or not isinstance(keyword, str):
            continue
        try:
            # ✅ FIXED: Use space-padded check instead of regex to avoid special char issues
            if f" {keyword.lower()} " in f" {title} ":
                return False, f"Seniority: {keyword}"
        except Exception:
            # If check fails, skip this keyword
            continue
    
    # 2. CHECK: Job type (internship, part-time, etc.)
    job_types = PRE_FILTER_CONFIG['reject_job_types']
    for job_type in job_types:
        if not job_type or not isinstance(job_type, str):
            continue
        if job_type in title:
            return False, f"Job type: {job_type}"
    
    # 3. CHECK: Specific forbidden titles
    specific_titles = PRE_FILTER_CONFIG['reject_specific_titles']
    for reject_title in specific_titles:
        if not reject_title or not isinstance(reject_title, str):
            continue
        try:
            # ✅ FIXED: Use space-padded check instead of regex
            if f" {reject_title.lower()} " in f" {title} ":
                return False, f"Specific title: {reject_title}"
        except Exception:
            continue
    
    # # 4. CHECK: Must be a technical role (NEW!)
    # # This prevents sales, design, HR jobs from passing
    # engineering_keywords = [
    #     'engineer', 'developer', 'programmer', 'architect',
    #     'software', 'ml', 'ai', 'machine learning', 'data',
    #     'backend', 'frontend', 'full stack', 'devops', 'sre',
    #     'platform', 'scientist', 'researcher', 'technologist'
    # ]
    
    # has_technical_keyword = any(keyword in title for keyword in engineering_keywords)
    # if not has_technical_keyword:
    #     return False, "Not a technical role"
    
    # 5. CHECK: Experience requirements
    check_full = PRE_FILTER_CONFIG['check_full_description']
    text_to_check = description if (check_full and description) else description[:500]
    
    patterns = get_experience_patterns()
    max_years = PRE_FILTER_CONFIG['max_years_experience']
    
    for pattern in patterns:
        try:
            matches = re.findall(pattern, text_to_check)
            for match in matches:
                # Handle range patterns like "5-7 years"
                if isinstance(match, tuple):
                    years_list = [int(m) for m in match if m.isdigit()]
                    min_years = min(years_list) if years_list else 0
                else:
                    min_years = int(match) if match.isdigit() else 0
                
                # If job requires 2+ years and max is 2, reject
                if min_years >= max_years:
                    return False, f"{min_years}+ years required"
        except Exception:
            # If regex fails, skip this pattern
            continue
    
    # PASS: Job passed all filters
    return True, "Passed pre-filter"

def pre_filter_jobs(jobs):
    """Filter jobs using config"""
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
    print(f"  ✅ Passed to OpenRouter: {len(filtered)}")
    print(f"  ❌ Rejected (free): {len(jobs) - len(filtered)}")
    
    if rejected:
        print(f"\n  Rejection breakdown:")
        for reason, count in sorted(rejected.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {reason}: {count}")
    
    return filtered, rejected