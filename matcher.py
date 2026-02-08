# import anthropic
# import json
# import argparse
# import time
# from sheets_helper import get_sheet
# from email_helper import send_email
# from config import ANTHROPIC_API_KEY, RESUME_PROFILE

# def get_unanalyzed_jobs(limit=20):
#     """Get jobs with Status='Raw'"""
#     try:
#         sheet = get_sheet()
#         worksheet = sheet.worksheet("Raw Jobs")
        
#         all_data = worksheet.get_all_records()
#         raw_jobs = [job for job in all_data if job.get('Status') == 'Raw']
        
#         print(f"Found {len(raw_jobs)} unanalyzed jobs")
#         return raw_jobs[:limit]
        
#     except Exception as e:
#         print(f"Error getting jobs: {e}")
#         return []

# def analyze_job(job):
#     """Analyze single job with Claude"""
#     client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
#     prompt = f"""Analyze this job against my profile.

# MY PROFILE:
# Core Skills (must-have): {', '.join(RESUME_PROFILE['core_skills'])}
# Important: {', '.join(RESUME_PROFILE['important_skills'])}
# Nice-to-have: {', '.join(RESUME_PROFILE['nice_skills'])}

# Forbidden (auto-reject): {', '.join(RESUME_PROFILE['forbidden_keywords'])}

# JOB:
# Company: {job['Company']}
# Title: {job['Title']}
# Description: {job['Description'][:1500]}

# Return ONLY valid JSON (no markdown):
# {{
#   "relevant": true/false,
#   "ats_safe": true/false,
#   "match_score": 0-100,
#   "tier": 1 or 2 or null,
#   "why_strong": "Brief reason if tier 1",
#   "risks": "What I'd need to learn"
# }}

# Rules:
# - ats_safe=false if ANY core skill missing
# - Tier 1 ONLY for: ML systems, RAG, production AI, reliability-critical
# - match_score: core=3x weight, important=2x, nice=1x
# - If forbidden keyword → relevant=false
# """
    
#     try:
#         response = client.messages.create(
#             model="claude-3-5-haiku-20241022",
#             max_tokens=400,
#             messages=[{"role": "user", "content": prompt}]
#         )
        
#         text = response.content[0].text.strip()
        
#         # Remove markdown if present
#         if text.startswith("```"):
#             text = text.split("```")[1]
#             if text.startswith("json"):
#                 text = text[4:]
        
#         result = json.loads(text)
#         return result
        
#     except Exception as e:
#         print(f"Error analyzing {job['Company']}: {e}")
#         return None

# def save_analysis(job, analysis):
#     """Save to Analyzed Jobs sheet"""
#     try:
#         sheet = get_sheet()
        
#         # If not relevant or not ATS safe, mark as Rejected
#         if not analysis or not analysis.get('relevant') or not analysis.get('ats_safe'):
#             raw_sheet = sheet.worksheet("Raw Jobs")
#             cell = raw_sheet.find(job['Job ID'])
#             if cell:
#                 raw_sheet.update_cell(cell.row, 8, 'Rejected')
#             return False
        
#         # Save to Analyzed Jobs
#         analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
#         row = [
#             job['Job ID'],
#             job['Company'],
#             job['Title'],
#             job['URL'],
#             analysis.get('tier', ''),
#             analysis.get('match_score', 0),
#             analysis.get('why_strong', ''),
#             analysis.get('risks', ''),
#             '',  # Apply checkbox
#             ''   # Applied date
#         ]
        
#         analyzed_sheet.append_row(row)
        
#         # Update Raw Jobs status
#         raw_sheet = sheet.worksheet("Raw Jobs")
#         cell = raw_sheet.find(job['Job ID'])
#         if cell:
#             raw_sheet.update_cell(cell.row, 8, 'Analyzed')
        
#         return True
        
#     except Exception as e:
#         print(f"Error saving analysis: {e}")
#         return False

# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--limit', type=int, default=20)
#     args = parser.parse_args()
    
#     print(f"🤖 Analyzing up to {args.limit} jobs...")
    
#     jobs = get_unanalyzed_jobs(limit=args.limit)
    
#     if not jobs:
#         subject = "Job Hunter: No Jobs to Analyze"
#         message = """There are no unanalyzed jobs in your sheet.

# Either:
# 1. All jobs have been analyzed already
# 2. No new jobs were collected yet

# Run "Collect Jobs" first, then try again.

# Your Job Hunter Bot
# """
#         send_email(subject, message)
#         return
    
#     tier1_count = 0
#     tier2_count = 0
#     rejected_count = 0
#     tier1_jobs = []
    
#     for i, job in enumerate(jobs):
#         print(f"[{i+1}/{len(jobs)}] {job['Company']} - {job['Title']}")
        
#         analysis = analyze_job(job)
        
#         if analysis:
#             saved = save_analysis(job, analysis)
            
#             if saved:
#                 tier = analysis.get('tier')
#                 if tier == 1:
#                     tier1_count += 1
#                     tier1_jobs.append({
#                         'company': job['Company'],
#                         'title': job['Title'],
#                         'score': analysis.get('match_score', 0),
#                         'why': analysis.get('why_strong', '')
#                     })
#                 elif tier == 2:
#                     tier2_count += 1
#             else:
#                 rejected_count += 1
        
#         # Rate limit: 2 seconds between requests
#         time.sleep(2)
    
#     # Send detailed email summary
#     subject = "Job Hunter: Analysis Complete!"
    
#     message = f"""Analysis Complete!

# SUMMARY:
# - Tier 1 (Strong Match): {tier1_count} jobs
# - Tier 2 (Safe Backup): {tier2_count} jobs
# - Rejected (Not a fit): {rejected_count} jobs

# """
    
#     if tier1_jobs:
#         message += "\nTOP TIER 1 MATCHES:\n"
#         message += "=" * 50 + "\n\n"
        
#         for job in sorted(tier1_jobs, key=lambda x: x['score'], reverse=True)[:3]:
#             message += f"{job['company']} - {job['title']}\n"
#             message += f"Score: {job['score']}/100\n"
#             message += f"Why: {job['why']}\n"
#             message += "-" * 50 + "\n\n"
    
#     message += """
# NEXT STEPS:
# 1. Open your Google Sheet
# 2. Go to "Analyzed Jobs" tab
# 3. Review Tier 1 jobs first
# 4. Check the "Apply?" box for jobs you want
# 5. Click the URL to apply

# Good luck!

# Your Job Hunter Bot
# """
    
#     send_email(subject, message)
#     print("✅ Done!")

# if __name__ == "__main__":
#     main()

import anthropic
import json
import argparse
import time
from sheets_helper import get_sheet
from config import ANTHROPIC_API_KEY, RESUME_PROFILE

def get_unanalyzed_jobs(limit=20):
    """Get jobs with Status='Raw'"""
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet("Raw Jobs")
        
        all_data = worksheet.get_all_records()
        raw_jobs = [job for job in all_data if job.get('Status') == 'Raw']
        
        print(f"Found {len(raw_jobs)} unanalyzed jobs")
        return raw_jobs[:limit]
        
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return []

def analyze_job(job):
    """Analyze single job with Claude - H1B aware"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""Analyze this job for an INTERNATIONAL STUDENT who will need H1B sponsorship in 2 years.

MY PROFILE:
Core Skills (must-have): {', '.join(RESUME_PROFILE['core_skills'])}
Important: {', '.join(RESUME_PROFILE['important_skills'])}
Nice-to-have: {', '.join(RESUME_PROFILE['nice_skills'])}

Forbidden (auto-reject): {', '.join(RESUME_PROFILE['forbidden_keywords'])}

VISA STATUS:
- Currently on F-1/OPT or will be
- Will need H1B sponsorship within 2 years
- Cannot accept roles requiring US citizenship or security clearance

JOB:
Company: {job['Company']}
Title: {job['Title']}
Description: {job['Description'][:2000]}

Return ONLY valid JSON (no markdown):
{{
  "relevant": true/false,
  "ats_safe": true/false,
  "visa_friendly": true/false,
  "visa_notes": "mentions sponsorship / neutral / requires citizenship",
  "match_score": 0-100,
  "tier": 1 or 2 or null,
  "why_strong": "Brief reason if tier 1",
  "risks": "What I'd need to learn OR visa concerns"
}}

Rules:
- visa_friendly=false if mentions: citizenship, clearance, "must be authorized", "no sponsorship"
- ats_safe=false if ANY core skill missing
- Tier 1 ONLY for: ML systems, RAG, production AI, reliability-critical
- match_score: core=3x weight, important=2x, nice=1x
- If forbidden keyword OR not visa_friendly → relevant=false
"""
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        # Remove markdown if present
        if text.startswith("```"):
            lines = text.split('\n')
            text = '\n'.join([l for l in lines if not l.strip().startswith('```')])
            if text.startswith("json"):
                text = text[4:].strip()
        
        # Try to parse
        result = json.loads(text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error for {job['Company']}: {e}")
        print(f"     Response was: {text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Error analyzing {job['Company']}: {e}")
        return None

def save_analysis(job, analysis):
    """Save to Analyzed Jobs sheet"""
    try:
        sheet = get_sheet()
        
        # Reject if not relevant, not ATS safe, OR not visa friendly
        if not analysis:
            return False
            
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
                reject_reason.append(f"visa issue: {analysis.get('visa_notes', 'unknown')}")
            
            print(f"  ❌ Rejected: {', '.join(reject_reason)}")
            return False
        
        # Save to Analyzed Jobs
        analyzed_sheet = sheet.worksheet("Analyzed Jobs")
        
        # Combine risks and visa notes
        risks_text = analysis.get('risks', '')
        visa_text = analysis.get('visa_notes', '')
        combined_risks = f"{risks_text}\nVisa: {visa_text}" if visa_text else risks_text
        
        row = [
            job['Job ID'],
            job['Company'],
            job['Title'],
            job['URL'],
            analysis.get('tier', ''),
            analysis.get('match_score', 0),
            analysis.get('why_strong', ''),
            combined_risks,
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