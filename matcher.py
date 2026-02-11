import anthropic
import json
import argparse
import time
import re 
from sheets_helper import get_sheet
from config import ANTHROPIC_API_KEY, RESUME_PROFILE

def get_unanalyzed_jobs(limit=20):
    """Get jobs with Status='Raw' from TODAY ONLY"""
    from datetime import datetime
    
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet("Raw Jobs")
        
        all_data = worksheet.get_all_records()
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Filter: Status='Raw' AND Date Found = today
        raw_jobs = [
            job for job in all_data 
            if job.get('Status') == 'Raw' 
            and job.get('Date Found') == today
        ]
        
        print(f"Found {len(raw_jobs)} unanalyzed jobs from today ({today})")
        
        # If no jobs today, check yesterday (in case of timezone issues)
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

def analyze_job(job):
    """Analyze single job with Claude - Experience & Full-Time filters"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""Analyze this job for a CANDIDATE with 0-2 years experience.

MY PROFILE:
Experience Level: New grad to 2 years (NOT eligible for 3+ years roles)
Core Skills (must-have): {', '.join(RESUME_PROFILE['core_skills'])}
Important: {', '.join(RESUME_PROFILE['important_skills'])}
Nice-to-have: {', '.join(RESUME_PROFILE['nice_skills'])}

JOB:
Company: {job['Company']}
Title: {job['Title']}
Description: {job['Description'][:2000]}

CRITICAL EXPERIENCE RULES:
- ACCEPT: "0-2 years", "1-3 years", "2-3 years", "new grad", "entry level", "junior"
- ACCEPT: "Experience preferred" (not required)
- ACCEPT: "Experience building X" (if no specific year count)
- REJECT: "3+ years required", "4+ years", "5+ years", "minimum 3 years"
- REJECT: "Senior level", "Mid-level", "Experienced engineer"
- If description says "3 years" but also says "new grad considered", ACCEPT

CRITICAL EMPLOYMENT RULES:
- ACCEPT: Full-time, Permanent, FTE, W2 employee, Salaried position
- ACCEPT: Contract-to-hire (if explicitly states conversion to full-time)
- ACCEPT: Contract (if W2 contract through employer, not 1099)
- REJECT: Part-time, Internship, Freelance, 1099, Consulting, Temporary
- REJECT: Contract (if 1099 or no mention of conversion)

Return JSON only (no markdown):
{{
  "experience_required": "0-2 years / 2-3 years / 3+ years / unclear",
  "experience_acceptable": true if 0-3 years OR unclear/flexible,
  "employment_type": "full-time / contract-to-hire / contract / part-time / internship / unclear",
  "employment_acceptable": true if full-time or contract-to-hire with FTE conversion,
  "relevant": true if ML/AI/Software role matching my skills,
  "ats_safe": true if I have core skills,
  "visa_friendly": true,
  "visa_notes": "pre-screened for H1B friendliness",
  "match_score": 0-100,
  "tier": 1 if strong technical match else 2,
  "why_strong": "reason if tier 1",
  "risks": "skills to learn OR experience gap"
}}

Rules:
- experience_acceptable=false → relevant MUST be false (reject the job)
- employment_acceptable=false → relevant MUST be false (reject the job)
- If "3 years preferred" but "new grads encouraged", mark experience_acceptable=true
- visa_friendly is ALWAYS true (already filtered)
- ats_safe=false ONLY if missing core technical skills
- Tier 1: Strong match on ML/AI skills, interesting company, 0-2 years
- Tier 2: Acceptable match, 0-3 years (stretch), good backup option
- Forbidden roles: {', '.join(RESUME_PROFILE['forbidden_keywords'])}
"""
        
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        # AGGRESSIVE CLEANING - Remove all common junk
        
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Remove leading/trailing asterisks, stars, etc.
        text = re.sub(r'^\*+\s*', '', text)
        text = re.sub(r'\s*\*+$', '', text)
        
        # Find the actual JSON (between first { and last })
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace+1]
        
        # Final cleanup
        text = text.strip()
        
        # Try to parse
        result = json.loads(text)
        
        # Validate required fields
        required_fields = ['relevant', 'ats_safe', 'visa_friendly', 'match_score', 'tier']
        for field in required_fields:
            if field not in result:
                print(f"  ⚠️ Missing field '{field}', setting default")
                if field == 'relevant' or field == 'ats_safe' or field == 'visa_friendly':
                    result[field] = False
                elif field == 'match_score':
                    result[field] = 0
                elif field == 'tier':
                    result[field] = None
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error for {job['Company']}: {e}")
        print(f"     Raw response: {text[:300] if 'text' in locals() else 'N/A'}")
        
        # Try one more time with even more aggressive cleaning
        try:
            # Extract everything between first { and last }
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                clean_json = match.group(0)
                result = json.loads(clean_json)
                print(f"  ✅ Recovered from bad formatting")
                return result
        except:
            pass
        
        return None
        
    except Exception as e:
        print(f"  ❌ Error analyzing {job['Company']}: {e}")
        return None

def save_analysis(job, analysis):
    """Save to Analyzed Jobs sheet"""
    try:
        sheet = get_sheet()
        
        if not analysis:
            return False
        
        # Check experience requirement
        if not analysis.get('experience_acceptable'):
            raw_sheet = sheet.worksheet("Raw Jobs")
            cell = raw_sheet.find(job['Job ID'])
            if cell:
                raw_sheet.update_cell(cell.row, 8, 'Rejected')
            
            exp_required = analysis.get('experience_required', 'unknown')
            print(f"  ❌ Rejected: too much experience required ({exp_required})")
            return False
        
        # Check employment type
        if not analysis.get('employment_acceptable'):
            raw_sheet = sheet.worksheet("Raw Jobs")
            cell = raw_sheet.find(job['Job ID'])
            if cell:
                raw_sheet.update_cell(cell.row, 8, 'Rejected')
            
            emp_type = analysis.get('employment_type', 'unknown')
            print(f"  ❌ Rejected: not full-time ({emp_type})")
            return False
        
        # Check relevance, ATS, visa
        if not analysis.get('relevant') or not analysis.get('ats_safe') or not analysis.get('visa_friendly'):
            raw_sheet = sheet.worksheet("Raw Jobs")
            cell = raw_sheet.find(job['Job ID'])
            if cell:
                raw_sheet.update_cell(cell.row, 8, 'Rejected')
            
            reject_reason = []
            if not analysis.get('relevant'):
                reject_reason.append("not relevant")
            if not analysis.get('ats_safe'):
                reject_reason.append("missing core skills")
            if not analysis.get('visa_friendly'):
                reject_reason.append(f"visa issue")
            
            print(f"  ❌ Rejected: {', '.join(reject_reason)}")
            return False
        
        # Save to Analyzed Jobs (rest of function stays the same)
        analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
        risks_text = analysis.get('risks', '')
        visa_text = analysis.get('visa_notes', '')
        exp_text = analysis.get('experience_required', '')
        
        combined_risks = f"{risks_text}\nVisa: {visa_text}\nExp: {exp_text}"
        
        row = [
            job['Job ID'],
            job['Company'],
            job['Title'],
            job['URL'],
            analysis.get('tier', ''),
            analysis.get('match_score', 0),
            analysis.get('why_strong', ''),
            combined_risks,
            job.get('Date Found', ''),
            '',  # Apply checkbox
            ''   # Applied date
        ]
        
        analyzed_sheet.append_row(row)
        
        # Update Raw Jobs status
        raw_sheet = sheet.worksheet("Raw Jobs")
        cell = raw_sheet.find(job['Job ID'])
        if cell:
            raw_sheet.update_cell(cell.row, 8, 'Analyzed')
        
        print(f"  ✅ Tier {analysis.get('tier')} - Score: {analysis.get('match_score')}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error saving analysis: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    
    print(f"🤖 Analyzing up to {args.limit} jobs (H1B friendly filter ON)...")
    
    jobs = get_unanalyzed_jobs(limit=args.limit)
    
    if not jobs:
        print("❌ No unanalyzed jobs found.")
        print("   Either all jobs analyzed or no new jobs collected.")
        print("   Run 'Collect Jobs' first, then try again.")
        return
    
    tier1_count = 0
    tier2_count = 0
    rejected_count = 0
    tier1_jobs = []
    
    for i, job in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] {job['Company']} - {job['Title']}")
        
        analysis = analyze_job(job)
        
        if analysis:
            saved = save_analysis(job, analysis)
            
            if saved:
                tier = analysis.get('tier')
                if tier == 1:
                    tier1_count += 1
                    tier1_jobs.append({
                        'company': job['Company'],
                        'title': job['Title'],
                        'score': analysis.get('match_score', 0),
                        'why': analysis.get('why_strong', ''),
                        'visa': analysis.get('visa_notes', '')
                    })
                elif tier == 2:
                    tier2_count += 1
            else:
                rejected_count += 1
        else:
            rejected_count += 1
        
        # Rate limit: 2 seconds between requests
        time.sleep(2)
    
    # Print summary (no email)
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE (H1B Friendly)")
    print("="*60)
    print(f"\n📊 SUMMARY:")
    print(f"   ✨ Tier 1 (Strong Match): {tier1_count} jobs")
    print(f"   ✅ Tier 2 (Safe Backup): {tier2_count} jobs")
    print(f"   ❌ Rejected: {rejected_count} jobs")
    print(f"      (reasons: citizenship required, clearance, or skill mismatch)")
    
    if tier1_jobs:
        print(f"\n🎯 TOP TIER 1 MATCHES:")
        print("-" * 60)
        
        for job in sorted(tier1_jobs, key=lambda x: x['score'], reverse=True)[:3]:
            print(f"\n   {job['company']} - {job['title']}")
            print(f"   Score: {job['score']}/100")
            print(f"   Why: {job['why']}")
            print(f"   Visa: {job['visa']}")
    
    print("\n" + "="*60)
    print("📋 NEXT STEPS:")
    print("   1. Open your Google Sheet")
    print("   2. Go to 'Analyzed Jobs' tab")
    print("   3. Review Tier 1 jobs first")
    print("   4. Check visa notes in Risks/Gaps column")
    print("   5. Check the 'Apply?' box for jobs you want")
    print("   6. Click the URL to apply")
    print("="*60)

if __name__ == "__main__":
    main()