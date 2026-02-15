# matcher.py - STRICT CONFIG ENFORCEMENT

import anthropic
import json
import argparse
import time
import re
from sheets_helper import get_sheet
from config import ANTHROPIC_API_KEY, get_resume_profile
from pre_filter import pre_filter_jobs
from filters_config import CLAUDE_FILTER_CONFIG, should_use_strict_role_matching, PRE_FILTER_CONFIG
# At the top after imports

def extract_relevant_sections(description, max_chars=4500):
    """
    Extract only relevant sections for job matching.
    Skips company info, benefits, culture fluff.
    """
    if len(description) <= max_chars:
        return description
    
    lines = description.split('\n')
    
    # Important keywords
    important_kw = [
        'requirement', 'required', 'must have',
        'qualification', 'qualified', 
        'experience', 'years', 'background',
        'skill', 'technical', 'proficiency',
        'education', 'degree', 'bachelor', 'master',
        'responsibility', 'duties', 'you will',
        'preferred', 'desired', 'bonus'
    ]
    
    # Skip keywords
    skip_kw = [
        'about us', 'our company', 'culture', 'mission',
        'values', 'why join', 'perks', 'benefits',
        'we offer', 'compensation', 'salary', 'insurance',
        'equal opportunity', 'diversity'
    ]
    
    important_lines = []
    current_section = []
    is_important = False
    
    for line in lines:
        line_lower = line.lower().strip()
        
        if not line_lower:
            if current_section and is_important:
                important_lines.extend(current_section)
            current_section = []
            is_important = False
            continue
        
        # Check if header
        is_header = (
            len(line_lower) < 100 and
            (line.isupper() or line.endswith(':') or 
             line.startswith('#') or line.startswith('**'))
        )
        
        if is_header:
            if current_section and is_important:
                important_lines.extend(current_section)
            
            current_section = [line]
            is_important = any(kw in line_lower for kw in important_kw)
            
            if any(kw in line_lower for kw in skip_kw):
                is_important = False
        else:
            current_section.append(line)
            if any(kw in line_lower for kw in important_kw):
                is_important = True
    
    if current_section and is_important:
        important_lines.extend(current_section)
    
    extracted = '\n'.join(important_lines)
    
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars] + "\n[Truncated]"
    elif len(extracted) < 200:
        # Fallback
        extracted = description[:2500] + "\n...\n" + description[-1500:]
    
    return extracted
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

def build_strict_prompt(job, resume_profile):
    """Build prompt using STRICT config values (NO defaults)"""
    
    # STRICT: Get values directly from config - NO .get() with defaults
    cfg = CLAUDE_FILTER_CONFIG
    max_exp = cfg['max_experience_required']  # STRICT
    min_skill = cfg['min_skill_match_percent']  # STRICT
    tier1_threshold = cfg['tier1_skill_threshold']  # STRICT
    tier2_threshold = cfg['tier2_skill_threshold']  # STRICT
    job_description = extract_relevant_sections(job.get('Description', ''))
    use_strict_role, min_role_pct = should_use_strict_role_matching(resume_profile)
    
    # Build STRICT experience rules
    # If max_exp=3, accepts 0-2 years (not 0-3)
    # Build STRICT experience rules
    exp_rules = f"""CRITICAL - EXPERIENCE (STRICT):

AUTOMATIC REJECTION if job contains:
- "minimum {max_exp} years" or higher
- "{max_exp}+ years required" or higher
- "requires {max_exp} years" or higher

ONLY QUALIFY if:
- "0-{max_exp-1} years" (example: "0-3 years" if max={max_exp})
- "entry level" or "junior" or "new grad"
- "{max_exp-1} years preferred" (NOT required)
- Multiple tracks available (e.g., "PhD OR Master's+2 OR Bachelor's+4")

FLEXIBLE REQUIREMENTS:
- If job says "PhD OR Master's with 2 years OR Bachelor's with 4 years"
  AND candidate has Bachelor's with 3 years → CONSIDER QUALIFIED
- "Preferred" or "desired" (not "required") → MORE LENIENT

Candidate: {resume_profile.get('experience_years')} (max claim: {max_exp-1} years)
Config max: {max_exp} years

RULE: 
- Hard requirement ≥ {max_exp} → REJECT
- Flexible requirement with {max_exp-1} to {max_exp} range → EVALUATE case-by-case
"""

    # Build role rules
    target_roles = resume_profile.get('target_roles', [])
    
    if use_strict_role and min_role_pct:
        role_rules = f"""ROLE RELEVANCE (STRICT {min_role_pct}%):

Target: {', '.join(target_roles)}
Calculate: what % of job is target role work
REJECT if < {min_role_pct}%
"""
    else:
        role_rules = f"""Target: {', '.join(target_roles)}
ACCEPT if related or uses core skills
"""
    
    # Forbidden keywords
    forbidden = resume_profile.get('forbidden_keywords', [])
    if forbidden:
        role_rules += f"\nAUTO-REJECT if title contains: {', '.join(forbidden)}"
    
    # Employment rules (STRICT - no .get() with defaults)
    employment_types = ["Full-time", "FTE", "Permanent"]
    if cfg['accept_contract_to_hire']:
        employment_types.append("Contract-to-hire (converts to FTE)")
    if cfg['accept_contract_w2']:
        employment_types.append("W2 Contract")
    if cfg['accept_part_time']:
        employment_types.append("Part-time")
    
    reject_types = []
    if cfg['reject_internships']:
        reject_types.append("Internship")
    reject_types.extend(["1099", "Freelance", "Temporary"])
    
    employment_rules = f"""ACCEPT: {', '.join(employment_types)}
REJECT: {', '.join(reject_types)}"""
    
    # Visa rules (STRICT)
    if cfg['requires_visa_sponsorship']:
        auto_reject_phrases = cfg['auto_reject_phrases']
        visa_rules = "AUTO-REJECT if job contains:\n" + '\n'.join(f'   - "{phrase}"' for phrase in auto_reject_phrases)
        visa_rules += "\nACCEPT: Everything else"
    else:
        visa_rules = "Candidate has work authorization"
    
    # Location rules (STRICT)
    location_rules = ""
    if cfg['accept_remote_only']:
        location_rules = "\nREJECT if not 100% remote"
    
    # Build full prompt
    prompt = f"""Analyze if candidate qualifies. Use STRICT config values BUT evaluate flexible requirements.

CANDIDATE:
Name: {resume_profile.get('name')}
Experience: {resume_profile.get('experience_years')} (can claim up to 3 years)
Core Skills: {', '.join(resume_profile.get('core_skills', [])[:])}
Target: {', '.join(target_roles)}

JOB:
Company: {job.get('Company')}
Title: {job.get('Title')}
Description: {job_description}

STRICT RULES:

1. EXPERIENCE:
{exp_rules}

SPECIAL CASES TO ACCEPT:
- "PhD OR Master's+2 OR Bachelor's+4" where candidate has Bachelor's+3
- "4 years preferred" (not required)
- "3-4 years" range where candidate has 3 years
- "Architect" title does NOT automatically mean senior (check actual requirements)

2. ROLE:
{role_rules}

3. SKILLS:
Min: {min_skill}%
Tier 1: >= {tier1_threshold}%
Tier 2: >= {tier2_threshold}%

4. EMPLOYMENT:
{employment_rules}

5. VISA:
{visa_rules}{location_rules}

Return ONLY JSON:
{{
  "experience_required_min": number,
  "candidate_qualifies_experience": boolean,
  "experience_reasoning": "why",
  
  "employment_type": "string",
  "candidate_qualifies_employment": boolean,
  
  "visa_friendly": boolean,
  "candidate_qualifies_visa": boolean,
  
  "role_match_percentage": number,
  "primary_role": "string",
  "relevant": boolean,
  
  "core_skills_match_percent": number,
  "ats_safe": boolean,
  
  "overall_qualified": boolean,
  "tier": 1 or 2 or null,
  "final_reasoning": "summary"
}}

LOGIC:
- experience_required_min >= {max_exp} AND hard requirement → candidate_qualifies_experience = false
- experience_required_min == {max_exp} BUT flexible/preferred → EVALUATE (may accept)
- "Architect" in title → Check description for actual years, don't auto-reject
"""
    
    return prompt
def has_flexible_experience_requirements(job_description):
    """
    Detect if job has flexible experience requirements like:
    - "PhD OR Master's+2 OR Bachelor's+4"
    - "3-5 years preferred"
    - "4 years desired"
    """
    desc = job_description.lower()
    
    # Check for multiple education paths
    has_multiple_paths = (
        ('bachelor' in desc or 'master' in desc or 'phd' in desc) and
        ' or ' in desc and
        ('+' in desc or 'with' in desc)
    )
    
    # Check for "preferred" or "desired" language
    has_preferred_language = any(word in desc for word in [
        'preferred', 'desired', 'ideal', 'plus', 'nice to have'
    ])
    
    return has_multiple_paths or has_preferred_language

def analyze_job(job, resume_profile):
    """Analyze with STRICT prompt and error handling"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = build_strict_prompt(job, resume_profile)
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Extract JSON
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace+1]
        
        result = json.loads(text)
        
        # ✅ FIX: Handle None/missing values from Claude
        # If job has no description, Claude might return null
        if result.get('experience_required_min') is None:
            result['experience_required_min'] = 0
        if result.get('experience_required_max') is None:
            result['experience_required_max'] = 0
        if result.get('core_skills_match_percent') is None:
            result['core_skills_match_percent'] = 0
        if result.get('role_match_percentage') is None:
            result['role_match_percentage'] = 0
        
        # FORCE VALIDATION - Override Claude if wrong
        max_exp = CLAUDE_FILTER_CONFIG['max_experience_required']
        exp_min = result.get('experience_required_min', 0)

        desc = job.get('Description', '')
        is_flexible = has_flexible_experience_requirements(desc)
        
        if exp_min >= max_exp and result.get('candidate_qualifies_experience'):
            if is_flexible:
                print(f"    ℹ️  {exp_min} years with FLEXIBLE requirements - Accepting Claude's decision")
            else:
                print(f"    ⚠️  OVERRIDE: {exp_min}+ years HARD requirement - REJECTING")
                result['candidate_qualifies_experience'] = False
                result['overall_qualified'] = False
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON Parse Error: {str(e)[:50]}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:50]}")
        return None
# matcher.py - ADD THIS FUNCTION after analyze_job()

def calculate_overall_score(analysis):
    """
    Calculate overall match score 0-100 based on multiple factors
    """
    if not analysis:
        return 0
    
    score = 0
    
    # 1. Skills match (40% weight)
    skills_pct = analysis.get('core_skills_match_percent', 0)
    score += (skills_pct * 0.4)
    
    # 2. Role relevance (30% weight)
    role_pct = analysis.get('role_match_percentage', 0)
    score += (role_pct * 0.3)
    
    # 3. Experience qualification (20% weight)
    if analysis.get('candidate_qualifies_experience', False):
        score += 20
    
    # 4. Visa friendly (5% weight)
    if analysis.get('candidate_qualifies_visa', False):
        score += 5
    
    # 5. Employment type (5% weight)
    if analysis.get('candidate_qualifies_employment', False):
        score += 5
    
    return int(score)
def save_analysis(job, analysis, resume_profile_name):
    """Save results with STRICT validation override"""
    try:
        sheet = get_sheet()
        
        # ✅ STRICT VALIDATION: Don't trust Claude's overall_qualified
        if analysis:
            # Check ALL conditions manually
            passes_experience = analysis.get('candidate_qualifies_experience', False)
            passes_role = analysis.get('relevant', False)
            passes_skills = analysis.get('ats_safe', False)
            passes_visa = analysis.get('candidate_qualifies_visa', False)
            passes_employment = analysis.get('candidate_qualifies_employment', False)
            
            # ALL must be true
            is_actually_qualified = (
                passes_experience and
                passes_role and
                passes_skills and
                passes_visa and
                passes_employment
            )
            
            # Override Claude if it made a mistake
            if not is_actually_qualified and analysis.get('overall_qualified'):
                print(f"    ⚠️  OVERRIDE: Claude said qualified but failed checks - REJECTING")
                analysis['overall_qualified'] = False
        
        if not analysis or not analysis.get('overall_qualified'):
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
                if not analysis.get('candidate_qualifies_visa'):
                    reasons.append("Visa")
                if not analysis.get('candidate_qualifies_employment'):
                    reasons.append("Employment")
                print(f"  ❌ {'; '.join(reasons)}")
            
            return False
        
        # Calculate score
        overall_score = calculate_overall_score(analysis)
        
        # Save to "Analyzed Jobs" sheet
        analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
        row = [
            job['Job ID'],
            job['Company'],
            job['Title'],
            job['URL'],
            analysis.get('tier', ''),
            overall_score,
            '',
            analysis.get('final_reasoning', ''),
            job.get('Date Found', ''),
            '',
            ''
        ]
        
        analyzed_sheet.append_row(row)
        
        # Update status in "Raw Jobs"
        raw_sheet = sheet.worksheet("Raw Jobs")
        cell = raw_sheet.find(job['Job ID'])
        if cell:
            raw_sheet.update_cell(cell.row, 8, 'Analyzed')
        
        print(f"  ✅ Tier {analysis.get('tier')} - Score: {overall_score}/100")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--profile', type=str)
    args = parser.parse_args()
    
    resume_profile = get_resume_profile(args.profile)
    
    # Display STRICT config values being used
    print("=" * 80)
    print(f"🤖 STRICT MATCHER - Profile: {resume_profile.get('name')}")
    print(f"Target: {', '.join(resume_profile.get('target_roles', [])[:3])}")
    print("\nSTRICT CONFIG VALUES:")
    print(f"  Pre-filter max exp: {PRE_FILTER_CONFIG['max_years_experience']} years")
    print(f"  Claude max exp: {CLAUDE_FILTER_CONFIG['max_experience_required']} years")
    print(f"  Min skill match: {CLAUDE_FILTER_CONFIG['min_skill_match_percent']}%")
    print(f"  Role match: {CLAUDE_FILTER_CONFIG['min_target_role_percentage']}%")
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
    
    print(f"\n🤖 ANALYZING {len(jobs_to_analyze)} jobs...")
    
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