# pre_filter.py - Quick filtering before Claude analysis

import re

def should_analyze(job):
    """
    Quick cheap checks that don't need Claude
    Returns: (should_analyze: bool, reason: str)
    """
    title = job.get('Title', '').lower()
    description = job.get('Description', '').lower()
    company = job.get('Company', '').lower()
    
    # 1. REJECT: Obvious senior roles (by title only)
    senior_title_keywords = [
        'senior software engineer',
        'senior engineer',
        'staff engineer',
        'staff software engineer',
        'principal engineer',
        'principal software engineer',
        'lead engineer',
        'engineering manager',
        'engineering director',
        'director of engineering',
        'vp of engineering',
        'head of engineering',
        'chief technology officer',
        'chief engineer'
    ]
    
    for keyword in senior_title_keywords:
        if keyword in title:
            return False, f"Senior role: {keyword}"
    
    # 2. REJECT: Obvious non-engineering roles
    non_eng_titles = [
        'sales engineer',
        'solutions engineer', 
        'sales',
        'marketing',
        'recruiter',
        'account manager',
        'customer success',
        'support specialist',
        'support engineer',
        'technical writer',
        'business analyst',
        'data analyst',
        'coordinator',
        'administrator',
        'project manager',
        'product manager'
    ]
    
    for keyword in non_eng_titles:
        if keyword in title:
            return False, f"Non-engineering: {keyword}"
    
    # 3. REJECT: Internships
    if 'intern' in title or 'internship' in title:
        return False, "Internship"
    
    # 4. REJECT: Part-time, contract, freelance (in title)
    if any(word in title for word in ['part-time', 'part time', 'freelance', 'contractor']):
        return False, "Not full-time (title)"
    
    # 5. REJECT: Obvious high experience in FIRST 500 characters of description
    # (This is a quick check - Claude will do deeper analysis)
    description_start = description[:500]
    
    # Look for "X+ years required" or "minimum X years" patterns
    strict_exp_patterns = [
        r'(\d+)\+?\s*years?\s+required',
        r'minimum\s+(\d+)\s*years?',
        r'at least\s+(\d+)\s*years?',
        r'requires?\s+(\d+)\+?\s*years?'
    ]
    
    for pattern in strict_exp_patterns:
        matches = re.findall(pattern, description_start)
        for match in matches:
            years = int(match)
            if years >= 5:  # Only reject if clearly 5+ years REQUIRED
                return False, f"{years}+ years required"
    
    # 6. ACCEPT: Everything else goes to Claude for smart analysis
    return True, "Passed pre-filter"

def pre_filter_jobs(jobs):
    """
    Filter jobs before sending to Claude
    Returns: (filtered_jobs, rejection_stats)
    """
    filtered = []
    rejected = {}
    
    for job in jobs:
        should_analyze_job, reason = should_analyze(job)
        
        if should_analyze_job:
            filtered.append(job)
        else:
            # Track rejection reasons
            rejected[reason] = rejected.get(reason, 0) + 1
    
    # Print statistics
    print(f"\n📊 PRE-FILTER RESULTS:")
    print(f"  📥 Total jobs: {len(jobs)}")
    print(f"  ✅ Passed to Claude: {len(filtered)}")
    print(f"  ❌ Rejected (cheap filters): {len(jobs) - len(filtered)}")
    
    if rejected:
        print(f"\n  Rejection breakdown:")
        for reason, count in sorted(rejected.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {reason}: {count}")
    
    savings_pct = ((len(jobs) - len(filtered)) / len(jobs) * 100) if jobs else 0
    cost_saved = (len(jobs) - len(filtered)) * 0.001
    
    print(f"\n  💰 Cost savings: ${cost_saved:.2f} (filtered {savings_pct:.1f}% for free)")
    
    return filtered, rejected