# resume_parser.py - Automatic Resume Skill Extraction

import anthropic
import os
import base64
import json
from pathlib import Path

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY not found!")
    print("\nSet it with: export ANTHROPIC_API_KEY='sk-ant-...'")
    exit(1)

def parse_resume_with_claude(resume_path):
    """Parse resume PDF and extract structured profile using Claude"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    print(f"📄 Reading resume: {resume_path}")
    
    # Read PDF as base64
    with open(resume_path, 'rb') as f:
        pdf_data = base64.standard_b64encode(f.read()).decode('utf-8')
    
    print("🤖 Analyzing resume with Claude...")
    
    prompt = """Analyze this resume and extract a structured profile for job matching.

Extract the following information:

1. EXPERIENCE LEVEL:
   - How many years of experience does this person have?
   - Are they: new grad (0 years), junior (0-2 years), mid-level (2-5 years), or senior (5+ years)?

2. TECHNICAL SKILLS:
   Categorize ALL technical skills mentioned into:
   - CORE SKILLS: Skills they have significant experience with (projects, work, multiple mentions)
   - IMPORTANT SKILLS: Skills they've used but less extensively
   - NICE-TO-HAVE SKILLS: Skills mentioned briefly or in coursework

3. TARGET ROLES:
   Based on their experience and projects, what job titles would they be a good fit for?
   Examples: "Software Engineer", "ML Engineer", "Backend Engineer", "Data Engineer"

4. EXPERIENCE SUMMARY:
   Briefly describe their background (e.g., "New grad with ML internship", "Junior engineer with 1 year backend experience")

Return ONLY valid JSON (no markdown, no explanation):
{
  "name": "Full Name",
  "experience_years": "0-2 / 2-5 / 5+",
  "experience_level": "new_grad / junior / mid / senior",
  "experience_summary": "Brief background description",
  
  "core_skills": ["skill1", "skill2", ...],
  "important_skills": ["skill1", "skill2", ...],
  "nice_skills": ["skill1", "skill2", ...],
  
  "target_roles": ["Job Title 1", "Job Title 2", ...],
  
  "education": {
    "degree": "BS/MS/PhD in X",
    "school": "University Name",
    "graduation": "Year or Expected Year"
  },
  
  "work_experience": [
    {
      "company": "Company Name",
      "role": "Job Title",
      "duration": "Dates",
      "key_skills": ["skill1", "skill2"]
    }
  ],
  
  "projects": [
    {
      "name": "Project Name",
      "description": "Brief description",
      "technologies": ["tech1", "tech2"]
    }
  ]
}

IMPORTANT:
- Be thorough - extract ALL technical skills mentioned
- Categorize skills accurately based on depth of experience shown
- For "core_skills", only include skills with concrete evidence (projects, work experience)
- Include programming languages, frameworks, tools, platforms, databases, etc.
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # ✅ UPDATED - Latest model
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )
        
        text = response.content[0].text.strip()
        
        # Clean JSON
        import re
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace+1]
        
        profile = json.loads(text)
        
        print(f"✅ Resume parsed successfully!")
        print(f"\nExtracted Profile:")
        print(f"  Name: {profile.get('name', 'N/A')}")
        print(f"  Experience: {profile.get('experience_summary', 'N/A')}")
        print(f"  Core Skills ({len(profile.get('core_skills', []))}): {', '.join(profile.get('core_skills', [])[:10])}...")
        print(f"  Target Roles: {', '.join(profile.get('target_roles', []))}")
        
        return profile
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw response: {text[:500]}")
        return None
        
    except Exception as e:
        print(f"❌ Error parsing resume: {e}")
        return None

def save_profile_to_config(profile, profile_name="my_resume"):
    """Save extracted profile to a Python config file"""
    config_code = f'''# Auto-generated resume profile
# Generated from: {profile.get('name', 'Unknown')}'s resume

RESUME_PROFILE = {{
    "name": "{profile_name}",
    "description": "{profile.get('experience_summary', 'Auto-extracted from resume')}",
    "experience_years": "{profile.get('experience_years', '0-2')}",
    "experience_level": "{profile.get('experience_level', 'junior')}",
    
    "core_skills": {json.dumps(profile.get('core_skills', []), indent=8)},
    
    "important_skills": {json.dumps(profile.get('important_skills', []), indent=8)},
    
    "nice_skills": {json.dumps(profile.get('nice_skills', []), indent=8)},
    
    "target_roles": {json.dumps(profile.get('target_roles', []), indent=8)},
    
    "forbidden_keywords": [
        "data scientist",
        "business analyst",
        "support engineer",
        "technical writer",
        "project manager",
        "sales engineer"
    ],
    
    # Original resume data for reference
    "education": {json.dumps(profile.get('education', {}), indent=8)},
    "work_experience": {json.dumps(profile.get('work_experience', []), indent=8)},
    "projects": {json.dumps(profile.get('projects', []), indent=8)}
}}
'''
    
    output_file = f"resume_profiles/{profile_name}.py"
    os.makedirs("resume_profiles", exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(config_code)
    
    print(f"\n✅ Profile saved to: {output_file}")
    return output_file

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse resume PDF and extract skills')
    parser.add_argument('resume_path', help='Path to resume PDF file')
    parser.add_argument('--name', default='my_resume', help='Profile name (default: my_resume)')
    parser.add_argument('--output', help='Output JSON file (optional)')
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.resume_path):
        print(f"❌ File not found: {args.resume_path}")
        return
    
    # Parse resume
    profile = parse_resume_with_claude(args.resume_path)
    
    if not profile:
        print("❌ Failed to parse resume")
        return
    
    # Save to config
    config_file = save_profile_to_config(profile, args.name)
    
    # Optionally save JSON
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(profile, f, indent=2)
        print(f"✅ JSON saved to: {args.output}")
    
    print("\n" + "=" * 70)
    print("🎉 RESUME PARSING COMPLETE!")
    print("=" * 70)
    print(f"\nTo use this profile:")
    print(f"1. Profile saved to: {config_file}")
    print(f"2. Run matcher with: python3 matcher.py --profile {args.name}")
    print("=" * 70)

if __name__ == "__main__":
    main()