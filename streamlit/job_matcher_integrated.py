# job_matcher_integrated.py - Integrated Job Matcher

import anthropic
import json
import re

class IntegratedMatcher:
    def __init__(self, anthropic_api_key, profile, filter_config):
        self.api_key = anthropic_api_key
        self.profile = profile
        self.filter_config = filter_config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
    
    def pre_filter(self, jobs):
        """Quick pre-filter to eliminate obvious non-matches"""
        filtered_jobs = []
        rejected_count = {}
        
        max_exp = self.filter_config['max_experience_required']
        
        # ✅ Get custom reject employment types
        custom_reject_employment = self.filter_config.get('custom_reject_employment', [])
        
        for job in jobs:
            title = job.get('title', '').lower()
            description = job.get('description', '').lower()
            
            # Check seniority in title
            seniority_keywords = ['senior', 'staff', 'principal', 'lead', 'manager', 'director', 'vp', 'chief', 'head of']
            if any(keyword in title for keyword in seniority_keywords):
                rejected_count['Seniority in title'] = rejected_count.get('Seniority in title', 0) + 1
                continue
            
            # Check experience requirements
            exp_patterns = [
                r'(\d+)\+?\s*years?\s+required',
                r'minimum\s+of\s+(\d+)\s*years?',
                r'at least\s+(\d+)\s*years?',
                r'requires?\s+(\d+)\+?\s*years?'
            ]
            
            rejected_exp = False
            for pattern in exp_patterns:
                matches = re.findall(pattern, description)
                for match in matches:
                    years = int(match)
                    if years >= max_exp:
                        rejected_count[f'{years}+ years required'] = rejected_count.get(f'{years}+ years required', 0) + 1
                        rejected_exp = True
                        break
                if rejected_exp:
                    break
            
            if rejected_exp:
                continue
            
            # ✅ Check forbidden job types (including custom)
            forbidden_types = ['intern', 'internship', 'part-time', 'freelance', 'contractor']
            forbidden_types.extend(custom_reject_employment)  # Add custom types
            
            if any(ft in title or ft in description for ft in forbidden_types):
                rejected_count['Job type'] = rejected_count.get('Job type', 0) + 1
                continue
            
            # Passed pre-filter
            filtered_jobs.append(job)
        
        return filtered_jobs, rejected_count
    
    def analyze_job(self, job):
        """Analyze a single job with Claude"""
        prompt = self._build_prompt(job)
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            
            # Clean JSON
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace != -1 and last_brace != -1:
                text = text[first_brace:last_brace+1]
            
            result = json.loads(text)
            
            # Handle None values
            if result.get('experience_required_min') is None:
                result['experience_required_min'] = 0
            if result.get('core_skills_match_percent') is None:
                result['core_skills_match_percent'] = 0
            if result.get('role_match_percentage') is None:
                result['role_match_percentage'] = 0
            
            # ✅ FIX: Use correct config key
            max_exp = self.filter_config['max_experience_required']
            exp_min = result.get('experience_required_min', 0)
            
            if exp_min >= max_exp and result.get('candidate_qualifies_experience'):
                # Check if it's flexible
                desc = job.get('description', '').lower()
                is_flexible = self._has_flexible_requirements(desc)
                
                if not is_flexible:
                    result['candidate_qualifies_experience'] = False
                    result['overall_qualified'] = False
            
            # Calculate match score
            result['match_score'] = self._calculate_score(result)
            
            return result
            
        except Exception as e:
            print(f"❌ Analysis error: {str(e)[:80]}")
            return None
    
    def _build_prompt(self, job):
        """Build analysis prompt"""
        cfg = self.filter_config
        
        # ✅ FIX: Use correct config key
        max_exp = cfg['max_experience_required']
        
        exp_rules = f"""EXPERIENCE (STRICT):
    - Maximum acceptable: {max_exp - 1} years
    - Candidate has: {self.profile.get('experience_years', '0-2')}
    - REJECT if requires {max_exp}+ years (hard requirement)
    - ACCEPT if "preferred" or "desired" (not required)
    - ACCEPT if flexible (e.g., "Bachelor's+4 OR Master's+2")
    """
        
        role_rules = f"""ROLE RELEVANCE:
    - Target roles: {', '.join(self.profile.get('target_roles', []))}
    - Minimum match: {cfg['min_target_role_percentage']}%
    - Calculate: what % of job is target role work
    """
        # ✅ Build employment rules with custom types
        employment_accept = ["Full-time"]
        if cfg['accept_contract_to_hire']:
            employment_accept.append("Contract-to-hire")
        if cfg['accept_contract_w2']:
            employment_accept.append("W2 Contract")
        if cfg['accept_part_time']:
            employment_accept.append("Part-time")
        
        # Add custom accept types
        custom_accept = cfg.get('custom_accept_employment', [])
        employment_accept.extend(custom_accept)
        
        employment_reject = []
        if cfg['reject_internships']:
            employment_reject.append("Internship")
        
        # Add custom reject types
        custom_reject = cfg.get('custom_reject_employment', [])
        employment_reject.extend(custom_reject)
        employment_reject.extend(["1099", "Freelance", "Temporary"])
        
        employment_rules = f"""EMPLOYMENT TYPE:
    ACCEPT: {', '.join(employment_accept)}
    REJECT: {', '.join(employment_reject)}
    """
        skill_rules = f"""SKILLS:
    - Core skills: {', '.join(self.profile.get('core_skills', [])[:20])}
    - Minimum match: {cfg['min_skill_match_percent']}%
    - Tier 1: >= {cfg['tier1_skill_threshold']}%
    - Tier 2: >= {cfg['tier2_skill_threshold']}%
    """
        
        visa_rules = ""
        if cfg['requires_visa_sponsorship']:
            visa_rules = """VISA:
    - Auto-reject if: "no visa sponsorship", "US citizen only", "security clearance required"
    """
        
        prompt = f"""Analyze if candidate qualifies for this job.

    CANDIDATE:
    {self.profile.get('name', 'Candidate')}
    Experience: {self.profile.get('experience_years', '0-2')}
    Skills: {', '.join(self.profile.get('core_skills', [])[:15])}
    Target Roles: {', '.join(self.profile.get('target_roles', []))}

    JOB:
    Company: {job.get('company')}
    Title: {job.get('title')}
    Description: {job.get('description', '')[:3000]}

    RULES:
    {exp_rules}
    {role_rules}
    {skill_rules}
    {visa_rules}

    Return ONLY JSON:
    {{
    "experience_required_min": number,
    "candidate_qualifies_experience": boolean,
    "experience_reasoning": "why",
    
    "employment_type": "Full-time/Contract/etc",
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
    "final_reasoning": "brief summary"
    }}
    """
        
        return prompt
    
    def _has_flexible_requirements(self, description):
        """Check if job has flexible requirements"""
        desc = description.lower()
        
        # Multiple education paths
        has_multiple_paths = (
            ('bachelor' in desc or 'master' in desc or 'phd' in desc) and
            ' or ' in desc and
            ('+' in desc or 'with' in desc)
        )
        
        # Preferred language
        has_preferred = any(word in desc for word in [
            'preferred', 'desired', 'ideal', 'plus', 'nice to have'
        ])
        
        return has_multiple_paths or has_preferred
    
    def _calculate_score(self, analysis):
        """Calculate overall match score 0-100"""
        if not analysis:
            return 0
        
        score = 0
        
        # Skills (40%)
        score += analysis.get('core_skills_match_percent', 0) * 0.4
        
        # Role (30%)
        score += analysis.get('role_match_percentage', 0) * 0.3
        
        # Experience (20%)
        if analysis.get('candidate_qualifies_experience', False):
            score += 20
        
        # Visa (5%)
        if analysis.get('candidate_qualifies_visa', False):
            score += 5
        
        # Employment (5%)
        if analysis.get('candidate_qualifies_employment', False):
            score += 5
        
        return int(score)
    
    def is_qualified(self, analysis):
        """Check if candidate qualifies"""
        if not analysis:
            return False
        
        return (
            analysis.get('candidate_qualifies_experience', False) and
            analysis.get('relevant', False) and
            analysis.get('ats_safe', False) and
            analysis.get('candidate_qualifies_visa', False) and
            analysis.get('candidate_qualifies_employment', False) and
            analysis.get('overall_qualified', False)
        )