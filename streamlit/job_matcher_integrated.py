# job_matcher_integrated.py - Job Matcher + Resume Tailor

import anthropic
import json
import re


class IntegratedMatcher:
    def __init__(self, anthropic_api_key, profile, filter_config):
        self.api_key     = anthropic_api_key
        self.profile     = profile
        self.filter_config = filter_config
        self.client      = anthropic.Anthropic(api_key=anthropic_api_key)

    # ─────────────────────────────────────────
    # Pre-filter
    # ─────────────────────────────────────────

    def pre_filter(self, jobs):
        """
        Fast rule-based filter. Key fixes vs previous version:
        - 'lead' seniority check is now title-boundary aware
          (rejects 'Lead Engineer' but not 'leading', 'leadership', 'team lead' in body)
        - Experience regex requires 'required'/'minimum' not just any number
        - Forbidden types only checked in title + first 300 chars (not full description)
        """
        filtered       = []
        rejected_count = {}
        max_exp        = self.filter_config.get('max_experience_required', 5)

        # Seniority keywords — matched as whole words in title only
        seniority_keywords = self.filter_config.get('reject_seniority_levels', [
            'senior', 'staff', 'principal', 'manager',
            'director', 'vp', 'vice president', 'chief', 'head of',
        ])
        # 'lead' needs special handling — match only as standalone word
        # to avoid rejecting "leadership", "leading", "team lead" in description
        reject_lead = 'lead' in [k.lower() for k in seniority_keywords]
        other_seniority = [k for k in seniority_keywords if k.lower() != 'lead']

        forbidden_types = ['intern', 'internship']
        if not self.filter_config.get('accept_part_time', False):
            forbidden_types.extend(['part-time', 'part time'])
        forbidden_types.extend(['freelance'])
        for t in self.filter_config.get('custom_reject_employment', []):
            forbidden_types.append(t.lower())

        # Experience patterns — only match HARD requirements
        exp_patterns = [
            r'minimum\s+(?:of\s+)?(\d+)\s*(?:\+\s*)?years?',
            r'at\s+least\s+(\d+)\s*years?',
            r'requires?\s+(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'(\d+)\+\s*years?\s+(?:of\s+)?experience\s+(?:is\s+)?required',
            r'(\d+)\+\s*years?\s+of\s+(?:relevant|professional|industry)',
        ]

        for job in jobs:
            title       = (job.get('title') or '').lower()
            description = (job.get('description') or '').lower()

            # ── Check 1: Seniority in title (whole word match)
            title_words = re.split(r'\W+', title)

            rejected_seniority = False
            for kw in other_seniority:
                kw_words = kw.lower().split()
                # Check if all words in the keyword appear consecutively in title_words
                for i in range(len(title_words) - len(kw_words) + 1):
                    if title_words[i:i+len(kw_words)] == kw_words:
                        rejected_seniority = True
                        break
                if rejected_seniority:
                    break

            # Special lead check: reject "Lead Engineer", "Lead Scientist" etc
            # but NOT "Tech Lead" at end (acceptable), not "leadership" in body
            if not rejected_seniority and reject_lead:
                # Only reject if 'lead' appears as FIRST word in title
                if title_words and title_words[0] == 'lead':
                    rejected_seniority = True
                # or as "lead" followed by a job-type noun
                elif re.search(r'\blead\s+(engineer|scientist|developer|analyst|architect|researcher)\b', title):
                    rejected_seniority = True

            if rejected_seniority:
                rejected_count['Seniority level'] = rejected_count.get('Seniority level', 0) + 1
                continue

            # ── Check 2: Hard experience requirement in description
            rejected_exp = False
            for pattern in exp_patterns:
                for match in re.findall(pattern, description):
                    years = int(match)
                    if years >= max_exp:
                        # Check for flexible overrides
                        if not self._is_flexible(description):
                            key = f'{years}+ years required'
                            rejected_count[key] = rejected_count.get(key, 0) + 1
                            rejected_exp = True
                        break
                if rejected_exp:
                    break

            if rejected_exp:
                continue

            # ── Check 3: Forbidden job types (title + first 300 chars only)
            search_zone = title + ' ' + description[:300]
            if any(ft in search_zone for ft in forbidden_types):
                rejected_count['Job type'] = rejected_count.get('Job type', 0) + 1
                continue

            # ── Check 4: Auto-reject phrases
            phrase_rejected = False
            for phrase in self.filter_config.get('auto_reject_phrases', []):
                if phrase.lower() in description:
                    rejected_count[f'Phrase: {phrase[:30]}'] = rejected_count.get(f'Phrase: {phrase[:30]}', 0) + 1
                    phrase_rejected = True
                    break
            if phrase_rejected:
                continue

            filtered.append(job)

        return filtered, rejected_count

    def _is_flexible(self, description):
        """Check if experience requirement has flexible language."""
        flexible = [
            'preferred', 'desired', 'ideal', 'nice to have',
            'or equivalent', ' or master', ' or phd', 'equivalent experience',
            'bachelor.*or', 'or relevant experience',
        ]
        return any(re.search(sig, description) for sig in flexible)

    # ─────────────────────────────────────────
    # Claude Analysis
    # ─────────────────────────────────────────

    def analyze_job(self, job):
        prompt = self._build_analysis_prompt(job)

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            text   = response.content[0].text.strip()
            text   = self._clean_json(text)
            result = json.loads(text)

            # Sanitize None → 0
            result['experience_required_min']    = result.get('experience_required_min') or 0
            result['core_skills_match_percent']  = result.get('core_skills_match_percent') or 0
            result['role_match_percentage']      = result.get('role_match_percentage') or 0

            # Hard override: catch experience disqualifiers Claude missed
            # Reject if job requires MORE years than user's max, regardless of what Claude said
            max_exp = self.filter_config.get('max_experience_required', 5)
            exp_min = result.get('experience_required_min', 0)
            if (exp_min > max_exp
                    and not self._is_flexible((job.get('description') or '').lower())):
                result['candidate_qualifies_experience'] = False
                result['overall_qualified'] = False
                print(f"  ⛔ Hard reject: {exp_min}+ yrs required, max is {max_exp}")

            result['match_score'] = self._calculate_score(result)
            return result

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON parse error {job.get('company','?')}: {str(e)[:60]}")
            return None
        except anthropic.APIStatusError as e:
            print(f"  ❌ Claude API error: {e.status_code}")
            return None
        except Exception as e:
            print(f"  ❌ Analysis error {job.get('company','?')}: {str(e)[:80]}")
            return None

    def generate_tailored_bullets(self, job, analysis):
        prompt = self._build_tailoring_prompt(job, analysis)

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            text   = response.content[0].text.strip()
            text   = self._clean_json(text)
            result = json.loads(text)
            return result.get('tailored_bullets', [])

        except Exception as e:
            print(f"  ⚠️  Tailoring failed {job.get('company','?')}: {str(e)[:60]}")
            return []

    # ─────────────────────────────────────────
    # Prompts
    # ─────────────────────────────────────────

    def _build_analysis_prompt(self, job):
        cfg     = self.filter_config
        max_exp = cfg.get('max_experience_required', 5)

        accept_types = ['Full-time']
        if cfg.get('accept_contract_to_hire'): accept_types.append('Contract-to-hire')
        if cfg.get('accept_contract_w2'):      accept_types.append('W2 Contract')
        if cfg.get('accept_part_time'):        accept_types.append('Part-time')
        for t in cfg.get('custom_accept_employment', []):
            accept_types.append(t)

        reject_types = ['1099', 'Freelance', 'Temporary', 'Seasonal']
        if cfg.get('reject_internships', True): reject_types.append('Internship')
        for t in cfg.get('custom_reject_employment', []):
            reject_types.append(t)

        visa_rule = ""
        if cfg.get('requires_visa_sponsorship'):
            visa_rule = "VISA: Reject if job says 'no sponsorship', 'US citizen only', or requires security clearance."

        return f"""You are a job qualification analyzer. Analyze whether this candidate qualifies for this job.

CANDIDATE:
- Experience: {self.profile.get('experience_years', '?')} years ({self.profile.get('experience_level', 'unknown')} level)
- Core Skills: {', '.join((self.profile.get('core_skills') or [])[:25])}
- Target Roles: {', '.join(self.profile.get('target_roles') or [])}

JOB:
- Company: {job.get('company', '?')}
- Title: {job.get('title', '?')}
- Description:
{job.get('description', 'No description')}

RULES:
1. EXPERIENCE: Reject ONLY if job REQUIRES (hard requirement) {max_exp}+ years. 'Preferred'/'desired' years = still qualified.
2. ROLE MATCH: % of job work that matches candidate's target roles.
3. SKILLS: % of job's REQUIRED skills the candidate has. Be generous — count adjacent/related skills.
4. EMPLOYMENT: Accept={', '.join(accept_types)}. Reject={', '.join(reject_types)}.
5. {visa_rule if visa_rule else 'VISA: Assume friendly unless explicitly stated otherwise.'}
6. TIER 1 = skill_match >= {cfg.get('tier1_skill_threshold', 80)}% AND role_match >= {cfg.get('min_target_role_percentage', 60)}%
7. TIER 2 = skill_match >= {cfg.get('tier2_skill_threshold', 60)}% AND role_match >= {cfg.get('min_target_role_percentage', 60)}%
8. Be GENEROUS on skill matching — if candidate has related/adjacent skills, count them as partial matches.
9. overall_qualified = true if experience + employment + role are all OK. Do NOT require perfect skill match.

Return ONLY valid JSON:
{{
  "experience_required_min": <number or 0>,
  "candidate_qualifies_experience": <true/false>,
  "experience_reasoning": "<one sentence>",

  "employment_type": "<detected>",
  "candidate_qualifies_employment": <true/false>,

  "visa_friendly": <true/false>,
  "candidate_qualifies_visa": <true/false>,

  "role_match_percentage": <0-100>,
  "primary_role": "<what this job is>",
  "relevant": <true/false>,

  "core_skills_match_percent": <0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],

  "overall_qualified": <true/false>,
  "tier": <1 or 2 or null>,
  "reasoning": "<2 sentences: why qualified or not, what's the best fit angle>"
}}"""

    def _build_tailoring_prompt(self, job, analysis):
        matched  = analysis.get('matched_skills', [])
        missing  = analysis.get('missing_skills', [])
        work_exp = self.profile.get('work_experience', [])

        if work_exp:
            exp_lines = []
            for e in work_exp[:3]:
                exp_lines.append(
                    f"- {e.get('role','')} at {e.get('company','')} "
                    f"({e.get('duration','')}): {', '.join(e.get('key_skills',[])[:5])}"
                )
            exp_summary = "\n".join(exp_lines)
        else:
            exp_summary = f"Skills: {', '.join((self.profile.get('core_skills') or [])[:15])}"

        return f"""Rewrite 3-4 resume bullet points for this candidate to better match the job description.

STRICT RULES:
1. ONLY use experience the candidate actually has
2. NEVER fabricate projects, tools, or skills they don't have
3. Reword existing experience using the job's language and keywords
4. Strong action verbs + metrics where candidate already has them

CANDIDATE EXPERIENCE:
{exp_summary}

Matched skills: {', '.join(matched[:10])}
Missing skills (DO NOT mention): {', '.join(missing[:5])}

JOB: {job.get('company')} — {job.get('title')}
JD excerpt: {job.get('description','')[:1500]}

Return ONLY valid JSON:
{{
  "tailored_bullets": [
    "• bullet 1",
    "• bullet 2",
    "• bullet 3",
    "• bullet 4"
  ]
}}"""

    # ─────────────────────────────────────────
    # Scoring & Qualification
    # ─────────────────────────────────────────

    def _calculate_score(self, analysis):
        """Skills 40% | Role 30% | Experience 20% | Visa+Employment 10%"""
        score  = analysis.get('core_skills_match_percent', 0) * 0.40
        score += analysis.get('role_match_percentage', 0)     * 0.30
        if analysis.get('candidate_qualifies_experience'):  score += 20
        if analysis.get('candidate_qualifies_visa'):        score += 5
        if analysis.get('candidate_qualifies_employment'):  score += 5
        return int(score)

    def is_qualified(self, analysis):
        """
        Qualification gate — key fix: removed 'ats_safe' requirement.
        ats_safe was an internal Claude field that it often returned False
        for no good reason, silently blocking qualified candidates.
        """
        if not analysis:
            return False

        return (
            analysis.get('overall_qualified', False)
            and analysis.get('candidate_qualifies_experience', False)
            and analysis.get('relevant', False)
            and analysis.get('candidate_qualifies_visa', False)
            and analysis.get('candidate_qualifies_employment', False)
            and analysis.get('tier') in (1, 2)
        )

    def _clean_json(self, text):
        text  = re.sub(r'```json\s*', '', text)
        text  = re.sub(r'```\s*',     '', text)
        first = text.find('{')
        last  = text.rfind('}')
        if first != -1 and last != -1:
            return text[first:last + 1]
        return text