# matcher.py - UNIVERSAL JOB MATCHER

import anthropic
import json
import argparse
import time
import re
from sheets_helper import get_sheet
from config import ANTHROPIC_API_KEY, RESUME_PROFILES, get_resume_profile
from pre_filter import pre_filter_jobs
from filters_config import (
    CLAUDE_FILTER_CONFIG, 
    should_use_strict_role_matching, 
    COST_CONFIG,
    OUTPUT_CONFIG
)

def get_unanalyzed_jobs(limit=None):
    """Get jobs with Status='Raw' from today"""
    from datetime import datetime, timedelta
    
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet("Raw Jobs")
        all_data = worksheet.get_all_records()
        today = datetime.now().strftime('%Y-%m-%d')
        
        raw_jobs = [
            job for job in all_data 
            if job.get('Status') == 'Raw' 
            and job.get('Date Found') == today
        ]
        
        print(f"📋 Found {len(raw_jobs)} unanalyzed jobs from today")
        
        if not raw_jobs:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            raw_jobs = [
                job for job in all_data 
                if job.get('Status') == 'Raw' 
                and job.get('Date Found') == yesterday
            ]
            if raw_jobs:
                print(f"  (Found {len(raw_jobs)} from yesterday)")
        
        if limit and limit < len(raw_jobs):
            return raw_jobs[:limit]
        
        return raw_jobs
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def build_dynamic_prompt(job, resume_profile):
    """Build universally applicable prompt based on config"""
    
    cfg = CLAUDE_FILTER_CONFIG
    max_exp = cfg.get('max_experience_required', 5)
    min_skill = cfg.get('min_skill_match_percent', 60)
    use_strict_role, min_role_pct = should_use_strict_role_matching(resume_profile)
    
    # Build experience rules
    exp_rules = f"""Analyze experience requirements:
   
   REJECT if job requires >= {max_exp} years and states it as REQUIRED
   ACCEPT if:
   - States 0-{max_exp-1} years
   - Says "X years preferred" (not required) where X <= {max_exp+1}
   - Has multiple tracks with one being entry/junior level
   
   Candidate experience: {resume_profile.get('experience_years', 'N/A')}
   If minimum requirement >= {max_exp} years → set candidate_qualifies_experience = false
"""

    # Build role matching rules
    target_roles = resume_profile.get('target_roles', [])
    if use_strict_role and min_role_pct:
        role_rules = f"""Target roles: {', '.join(target_roles)}
   
   Calculate what % of job responsibilities match these target roles.
   REJECT if role_match_percentage < {min_role_pct}%
   
   Example: If target is "Marketing Manager" but job is 80% Sales + 20% Marketing → REJECT
"""
    else:
        role_rules = f"""Target roles: {', '.join(target_roles)}
   
   ACCEPT if job is related to target roles or uses candidate's core skills
   REJECT if job is completely unrelated
"""
    
    # Check for forbidden keywords
    forbidden = resume_profile.get('forbidden_keywords', [])
    if forbidden:
        role_rules += f"\n   AUTO-REJECT if job title contains: {', '.join(forbidden)}"
    
    # Build employment rules
    employment_types = ["Full-time", "FTE", "Permanent"]
    if cfg.get('accept_contract_to_hire', False):
        employment_types.append("Contract-to-hire (converts to FTE)")
    if cfg.get('accept_contract_w2', False):
        employment_types.append("W2 Contract")
    if cfg.get('accept_part_time', False):
        employment_types.append("Part-time")
    
    reject_types = []
    if cfg.get('reject_internships', True):
        reject_types.append("Internship")
    reject_types.extend(["1099 contractor", "Freelance", "Temporary"])
    
    employment_rules = f"""ACCEPT: {', '.join(employment_types)}
   REJECT: {', '.join(reject_types)}"""
    
    # Build visa rules
    if cfg.get('requires_visa_sponsorship', True):
        visa_rules = """REJECT if job states:
   - "US citizenship required"
   - "Security clearance required"  
   - "No visa sponsorship"
   - "Cannot sponsor"
   
   ACCEPT: Everything else (assume sponsorship possible if not mentioned)"""
    else:
        visa_rules = """Candidate has work authorization - no visa restrictions
   Can accept jobs with clearance requirements if qualified"""
    
    # Build location rules
    if cfg.get('accept_remote_only', False):
        location_rules = "\nREJECT if not fully remote (must be 100% remote position)"
    else:
        location_rules = ""
    
    # Full prompt
    prompt = f"""Analyze if this candidate qualifies for this job.

CANDIDATE PROFILE:
Name: {resume_profile.get('name', 'N/A')}
Experience: {resume_profile.get('experience_years', 'N/A')}
Description: {resume_profile.get('description', 'N/A')}
Core Skills: {', '.join(resume_profile.get('core_skills', [])[:15])}
Target Roles: {', '.join(target_roles)}

JOB POSTING:
Company: {job['Company']}
Title: {job['Title']}
Description: {job['Description'][:3000]}

QUALIFICATION CRITERIA:

1. EXPERIENCE:
{exp_rules}

2. ROLE MATCH:
{role_rules}

3. SKILLS:
   Minimum required: {min_skill}% of job's required skills
   Tier 1: >= {cfg.get('tier1_skill_threshold', 80)}% match
   Tier 2: >= {cfg.get('tier2_skill_threshold', 60)}% match

4. EMPLOYMENT TYPE:
{employment_rules}

5. VISA/LOCATION:
{visa_rules}{location_rules}

Return ONLY JSON:
{{
  "experience_required_min": number,
  "candidate_qualifies_experience": boolean,
  "experience_reasoning": "explanation",
  
  "employment_type": "string",
  "candidate_qualifies_employment": boolean,
  
  "visa_friendly": boolean,
  "candidate_qualifies_visa": boolean,
  
  "role_match_percentage": number 0-100,
  "primary_role": "main job function",
  "relevant": boolean,
  
  "core_skills_match_percent": number 0-100,
  "ats_safe": boolean,
  
  "overall_qualified": boolean,
  "tier": 1 or 2 or null,
  "final_reasoning": "summary"
}}

overall_qualified = experience AND employment AND visa AND relevant AND ats_safe
"""
    
    return prompt

def analyze_job(job, resume_profile):
    """Analyze job with Claude"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = build_dynamic_prompt(job, resume_profile)
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace+1]
        
        return json.loads(text)
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def save_analysis(job, analysis, resume_profile_name):
    """Save analysis results"""
    try:
        sheet = get_sheet()
        
        if not analysis or not analysis.get('overall_qualified'):
            # Mark as rejected
            raw_sheet = sheet.worksheet("Raw Jobs")
            cell = raw_sheet.find(job['Job ID'])
            if cell:
                raw_sheet.update_cell(cell.row, 8, 'Rejected')
            
            if analysis:
                reasons = []
                if not analysis.get('candidate_qualifies_experience'):
                    reasons.append(f"Exp: {analysis.get('experience_required_min', '?')}+yrs")
                if not analysis.get('relevant'):
                    reasons.append(f"Role: {analysis.get('role_match_percentage', 0)}%")
                if not analysis.get('ats_safe'):
                    reasons.append(f"Skills: {analysis.get('core_skills_match_percent', 0)}%")
                print(f"  ❌ Rejected: {'; '.join(reasons)}")
            
            return False
        
        # Save qualified job
        analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
        row = [
            job['Job ID'],
            job['Company'],
            job['Title'],
            job['URL'],
            analysis.get('tier', ''),
            analysis.get('core_skills_match_percent', 0),
            '',
            analysis.get('final_reasoning', ''),
            job.get('Date Found', ''),
            '',
            ''
        ]
        
        analyzed_sheet.append_row(row)
        
        # Update status
        raw_sheet = sheet.worksheet("Raw Jobs")
        cell = raw_sheet.find(job['Job ID'])
        if cell:
            raw_sheet.update_cell(cell.row, 8, 'Analyzed')
        
        print(f"  ✅ Tier {analysis.get('tier')} - {analysis.get('core_skills_match_percent')}% match")
        return True
        
    except Exception as e:
        print(f"  ❌ Save error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--profile', type=str)
    args = parser.parse_args()
    
    resume_profile = get_resume_profile(args.profile)
    
    print("=" * 80)
    print(f"🤖 JOB MATCHER - Profile: {resume_profile.get('name')}")
    print(f"Target: {', '.join(resume_profile.get('target_roles', [])[:3])}")
    print("=" * 80)
    
    jobs = get_unanalyzed_jobs(args.limit if args.limit > 0 else None)
    
    if not jobs:
        print("\n❌ No jobs to analyze")
        return
    
    print("\n🔍 PRE-FILTERING...")
    jobs_to_analyze, _ = pre_filter_jobs(jobs)
    
    if not jobs_to_analyze:
        print("\n❌ All rejected by pre-filter")
        return
    
    cost = len(jobs_to_analyze) * COST_CONFIG.get('cost_per_job_analysis', 0.001)
    print(f"\n🤖 ANALYZING {len(jobs_to_analyze)} jobs (${cost:.2f})...")
    
    tier1, tier2, rejected = 0, 0, 0
    
    for i, job in enumerate(jobs_to_analyze):
        print(f"\n[{i+1}/{len(jobs_to_analyze)}] {job['Company']} - {job['Title']}")
        
        analysis = analyze_job(job, resume_profile)
        
        if analysis and save_analysis(job, analysis, resume_profile.get('name')):
            tier = analysis.get('tier')
            if tier == 1:
                tier1 += 1
            elif tier == 2:
                tier2 += 1
        else:
            rejected += 1
        
        time.sleep(2)
    
    print("\n" + "=" * 80)
    print(f"✅ COMPLETE - Tier 1: {tier1} | Tier 2: {tier2} | Rejected: {rejected}")
    print("=" * 80)

if __name__ == "__main__":
    main()
