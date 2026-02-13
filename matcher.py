# matcher.py - MULTI-RESUME MATCHER

import anthropic
import json
import argparse
import time
import re
from sheets_helper import get_sheet
from config import ANTHROPIC_API_KEY, RESUME_PROFILES, get_resume_profile, list_available_profiles


def get_unanalyzed_jobs(limit=20):
    """Get jobs with Status='Raw' from TODAY ONLY"""
    from datetime import datetime
    
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
        
        print(f"Found {len(raw_jobs)} unanalyzed jobs from today ({today})")
        
        if not raw_jobs:
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            raw_jobs = [
                job for job in all_data 
                if job.get('Status') == 'Raw' 
                and job.get('Date Found') == yesterday
            ]
            if raw_jobs:
                print(f"  (Found {len(raw_jobs)} from yesterday {yesterday})")
        
        return raw_jobs[:limit]
        
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return []

def analyze_job(job, resume_profile):
    """Claude analyzes job against specific resume profile"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Build dynamic prompt based on resume profile
    prompt = f"""You are an expert staffing recruiter. Analyze if this candidate qualifies for this job.

CANDIDATE PROFILE: "{resume_profile['name']}"
Experience Level: {resume_profile['experience_years']} years
Target Roles: {', '.join(resume_profile['target_roles'])}

CORE SKILLS (MUST HAVE - candidate has these):
{', '.join(resume_profile['core_skills'])}

IMPORTANT SKILLS (candidate has these):
{', '.join(resume_profile['important_skills'])}

NICE-TO-HAVE SKILLS (candidate has these):
{', '.join(resume_profile['nice_skills'])}

FORBIDDEN ROLES (auto-reject):
{', '.join(resume_profile['forbidden_keywords'])}

EMPLOYMENT REQUIREMENTS:
- Location: USA only
- Employment: Full-time only (or contract-to-hire converting to FTE)
- Visa: Will need H1B sponsorship (no citizenship/clearance roles)

JOB POSTING:
Company: {job['Company']}
Title: {job['Title']}
Source: {job.get('Source', 'Unknown')}
Full Description:
{job['Description'][:3000]}

ANALYSIS INSTRUCTIONS:

1. EXPERIENCE ANALYSIS:
   - Does job allow {resume_profile['experience_years']} years?
   - Look for: "new grad", "entry level", "0-2 years", "junior"
   - Check for MULTIPLE tracks (e.g., "5+ years OR new grads")
   - Distinguish "required" vs "preferred"
   - QUALIFY if any track allows ≤3 years OR experience is "preferred"
   - REJECT only if clearly "minimum 5+ years REQUIRED" with no junior option

2. ROLE RELEVANCE:
   - Is this one of the target roles: {', '.join(resume_profile['target_roles'])}?
   - Or related engineering role?
   - NOT forbidden: {', '.join(resume_profile['forbidden_keywords'])}

3. SKILL MATCHING:
   - Count how many CORE skills the job requires
   - Does candidate have MOST of them?
   - ats_safe=true if candidate has ≥60% of required core skills
   - Tier 1: Has ≥80% required skills + interesting company
   - Tier 2: Has ≥60% required skills, good backup

4. EMPLOYMENT TYPE:
   - ACCEPT: Full-time, FTE, Permanent, W2
   - ACCEPT: Contract-to-hire IF converts to FTE
   - REJECT: Internship, part-time, 1099, freelance, temporary

5. VISA/CITIZENSHIP:
   - REJECT: "US citizen only", "security clearance", "no visa sponsorship"
   - ACCEPT: Everything else (most don't mention it)

Return ONLY valid JSON (no markdown):
{{
  "experience_required_min": 0-10,
  "experience_type": "required / preferred / not_mentioned",
  "has_new_grad_track": true/false,
  "candidate_qualifies_experience": true/false,
  "experience_reasoning": "why",
  
  "employment_type": "full-time / contract-to-hire / contract / internship / part-time",
  "candidate_qualifies_employment": true/false,
  
  "visa_friendly": true/false,
  "visa_notes": "explanation",
  "candidate_qualifies_visa": true/false,
  
  "role_match": "exact / related / not_relevant",
  "is_forbidden_role": true/false,
  
  "core_skills_required": ["skill1", "skill2"],
  "core_skills_candidate_has": ["skill1", "skill2"],
  "core_skills_match_percent": 0-100,
  "ats_safe": true/false,
  
  "relevant": true/false,
  "match_score": 0-100,
  "tier": 1 or 2 or null,
  "why_strong": "if tier 1",
  "risks": "gaps to address",
  
  "overall_qualified": true/false,
  "final_reasoning": "summary"
}}

LOGIC:
- is_forbidden_role=true → overall_qualified=false
- overall_qualified = experience AND employment AND visa AND relevant AND ats_safe AND (not is_forbidden_role)
"""
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        # Clean JSON
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = re.sub(r'^\*+\s*', '', text)
        
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace+1]
        
        result = json.loads(text)
        
        # Validate
        required = ['overall_qualified', 'relevant', 'ats_safe', 'match_score', 'tier']
        for field in required:
            if field not in result:
                result[field] = False if field != 'match_score' else 0
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON error: {e}")
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return None
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def save_analysis(job, analysis, resume_profile_name):
    """Save to Analyzed Jobs sheet with profile info"""
    try:
        sheet = get_sheet()
        
        if not analysis:
            return False
        
        # REJECT if not qualified
        if not analysis.get('overall_qualified'):
            raw_sheet = sheet.worksheet("Raw Jobs")
            cell = raw_sheet.find(job['Job ID'])
            if cell:
                raw_sheet.update_cell(cell.row, 8, 'Rejected')
            
            reasons = []
            if analysis.get('is_forbidden_role'):
                reasons.append("Forbidden role type")
            if not analysis.get('candidate_qualifies_experience'):
                reasons.append(f"Exp: {analysis.get('experience_reasoning', 'too senior')}")
            if not analysis.get('candidate_qualifies_employment'):
                reasons.append(f"Employment: {analysis.get('employment_type')}")
            if not analysis.get('candidate_qualifies_visa'):
                reasons.append(f"Visa: {analysis.get('visa_notes')}")
            if not analysis.get('relevant'):
                reasons.append("Not relevant")
            if not analysis.get('ats_safe'):
                reasons.append(f"Skills: {analysis.get('core_skills_match_percent', 0)}% match")
            
            print(f"  ❌ Rejected: {'; '.join(reasons)}")
            return False
        
        # ACCEPT - Save
        analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
        # Combine notes
        notes = []
        notes.append(f"Profile: {resume_profile_name}")
        notes.append(f"Experience: {analysis.get('experience_reasoning', '')}")
        notes.append(f"Skills Match: {analysis.get('core_skills_match_percent', 0)}%")
        notes.append(f"Required: {', '.join(analysis.get('core_skills_required', []))}")
        notes.append(f"Has: {', '.join(analysis.get('core_skills_candidate_has', []))}")
        notes.append(f"Employment: {analysis.get('employment_type', '')}")
        notes.append(f"Visa: {analysis.get('visa_notes', '')}")
        notes.append(f"Risks: {analysis.get('risks', '')}")
        
        combined_notes = '\n'.join([n for n in notes if n and not n.endswith(': ')])
        
        row = [
            job['Job ID'],
            job['Company'],
            job['Title'],
            job['URL'],
            analysis.get('tier', ''),
            analysis.get('match_score', 0),
            analysis.get('why_strong', ''),
            combined_notes,
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
        
        tier = analysis.get('tier', 'N/A')
        score = analysis.get('match_score', 0)
        skills_pct = analysis.get('core_skills_match_percent', 0)
        print(f"  ✅ Tier {tier} - Score: {score}/100 - Skills: {skills_pct}%")
        return True
        
    except Exception as e:
        print(f"  ❌ Error saving: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Analyze jobs against resume profile')
    parser.add_argument('--limit', type=int, default=20, help='Max jobs to analyze')
    parser.add_argument('--profile', type=str, 
                       help='Resume profile to use (run with --list to see available profiles)')
    parser.add_argument('--list', action='store_true', 
                       help='List all available resume profiles')
    args = parser.parse_args()
    
    # List profiles if requested
    if args.list:
        list_available_profiles()
        return
    
    # Get resume profile
    resume_profile = get_resume_profile(args.profile)
    
    print("=" * 80)
    print(f"🤖 ANALYZING JOBS - Profile: {resume_profile['name']}")
    print("=" * 80)
    print(f"Description: {resume_profile['description']}")
    print(f"Experience: {resume_profile.get('experience_years', 'N/A')}")
    print(f"Core Skills ({len(resume_profile.get('core_skills', []))}): {', '.join(resume_profile.get('core_skills', [])[:10])}...")
    print(f"Target Roles: {', '.join(resume_profile.get('target_roles', []))}")
    print("=" * 80)
    
    
    jobs = get_unanalyzed_jobs(limit=args.limit)
    
    if not jobs:
        print("\n❌ No unanalyzed jobs from today")
        print("   Run 'Collect Jobs' first")
        return
    
    tier1_count = 0
    tier2_count = 0
    rejected_count = 0
    tier1_jobs = []
    
    for i, job in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] {job['Company']} - {job['Title']}")
        
        analysis = analyze_job(job, resume_profile)
        
        if analysis:
            saved = save_analysis(job, analysis, resume_profile['name'])
            
            if saved:
                tier = analysis.get('tier')
                if tier == 1:
                    tier1_count += 1
                    tier1_jobs.append({
                        'company': job['Company'],
                        'title': job['Title'],
                        'score': analysis.get('match_score', 0),
                        'skills_match': analysis.get('core_skills_match_percent', 0),
                        'why': analysis.get('why_strong', '')
                    })
                elif tier == 2:
                    tier2_count += 1
            else:
                rejected_count += 1
        else:
            rejected_count += 1
        
        time.sleep(2)
    
    # Summary
    print("\n" + "=" * 80)
    print(f"✅ ANALYSIS COMPLETE - Profile: {resume_profile['name']}")
    print("=" * 80)
    print(f"\n📊 RESULTS:")
    print(f"   ✨ Tier 1 (Strong Matches): {tier1_count} jobs")
    print(f"   ✅ Tier 2 (Backup Options): {tier2_count} jobs")
    print(f"   ❌ Rejected: {rejected_count} jobs")
    
    if tier1_jobs:
        print(f"\n🎯 TOP TIER 1 MATCHES:")
        print("-" * 80)
        
        for job in sorted(tier1_jobs, key=lambda x: x['score'], reverse=True)[:5]:
            print(f"\n   {job['company']} - {job['title']}")
            print(f"   Overall Score: {job['score']}/100")
            print(f"   Skills Match: {job['skills_match']}%")
            print(f"   Why: {job['why']}")
    
    print("\n" + "=" * 80)
    print("📋 NEXT STEPS:")
    print("   1. Open Google Sheet → 'Analyzed Jobs'")
    print("   2. Filter by Profile in Notes column")
    print("   3. Sort by Tier (1 first)")
    print("   4. Apply to best matches!")
    print("=" * 80)

if __name__ == "__main__":
    main()