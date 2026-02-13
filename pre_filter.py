# pre_filter.py - UNIVERSAL PRE-FILTER

import re
from filters_config import PRE_FILTER_CONFIG, get_experience_patterns

def should_analyze(job):
    """
    Universal pre-filter that works for ANY profession
    Returns: (should_analyze: bool, reason: str)
    """
    title = job.get('Title', '').lower()
    description = job.get('Description', '').lower()
    
    # 1. CHECK: Seniority level
    seniority_keywords = PRE_FILTER_CONFIG.get('reject_seniority_levels', [])
    for keyword in seniority_keywords:
        # Check if keyword appears as a standalone word in title
        if f" {keyword} " in f" {title} " or title.startswith(keyword) or title.endswith(keyword):
            return False, f"Seniority: {keyword}"
    
    # 2. CHECK: Job type (internship, part-time, etc.)
    job_types = PRE_FILTER_CONFIG.get('reject_job_types', [])
    for job_type in job_types:
        if job_type in title:
            return False, f"Job type: {job_type}"
    
    # 3. CHECK: Specific titles user wants to reject
    specific_titles = PRE_FILTER_CONFIG.get('reject_specific_titles', [])
    for reject_title in specific_titles:
        if reject_title in title:
            return False, f"Specific title: {reject_title}"
    
    # 4. CHECK: Experience requirements
    if PRE_FILTER_CONFIG.get('check_full_description', True):
        text_to_check = description
    else:
        text_to_check = description[:500]
    
    patterns = get_experience_patterns()
    max_years = PRE_FILTER_CONFIG.get('max_years_experience', 5)
    
    for pattern in patterns:
        matches = re.findall(pattern, text_to_check)
        for match in matches:
            # Handle tuple matches from range patterns
            if isinstance(match, tuple):
                years_list = [int(m) for m in match if m.isdigit()]
                min_years = min(years_list) if years_list else 0
            else:
                min_years = int(match) if match.isdigit() else 0
            
            if min_years >= max_years:
                return False, f"{min_years}+ years required"
    
    # 5. PASS: Send to Claude for intelligent analysis
    return True, "Passed pre-filter"

def pre_filter_jobs(jobs):
    """Filter jobs using universal config"""
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
    
    from filters_config import COST_CONFIG
    if COST_CONFIG.get('show_cost_estimates', True):
        savings_pct = ((len(jobs) - len(filtered)) / len(jobs) * 100) if jobs else 0
        cost_saved = (len(jobs) - len(filtered)) * COST_CONFIG.get('cost_per_job_analysis', 0.001)
        print(f"\n  💰 Savings: ${cost_saved:.2f} ({savings_pct:.1f}% filtered free)")
    
    return filtered, rejected