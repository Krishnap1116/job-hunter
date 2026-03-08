# job_matcher_integrated.py - Job Matcher + Resume Tailor
# Works for ANY user — profile comes from their parsed resume stored in DB.
# Does NOT hardcode any role, skill, or experience assumptions.

import anthropic
import json
import re


class IntegratedMatcher:
    def __init__(self, anthropic_api_key, profile, filter_config):
        """
        Args:
            anthropic_api_key: Anthropic API key from user's settings
            profile: User profile dict from DB (name, experience_years,
                     core_skills, target_roles, etc.)
            filter_config: Claude filter settings from DB
        """
        self.api_key = anthropic_api_key
        self.profile = profile
        self.filter_config = filter_config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    # ─────────────────────────────────────────
    # Pre-filter (free, instant, no API call)
    # ─────────────────────────────────────────

    def pre_filter(self, jobs):
        """
        Fast rule-based filter before sending jobs to Claude.
        Eliminates obvious non-matches to save API costs.
        Returns: (filtered_jobs, rejection_reasons_dict)
        """
        filtered = []
        rejected_count = {}
        max_exp = self.filter_config.get('max_experience_required', 5)
        custom_reject_types = self.filter_config.get('custom_reject_employment', [])

        # Build seniority keywords from filter config
        seniority_keywords = self.filter_config.get(
            'reject_seniority_levels',
            ['senior', 'staff', 'principal', 'lead', 'manager',
             'director', 'vp', 'chief', 'head of']
        )

        # Build forbidden job types
        forbidden_types = ['intern', 'internship']
        if not self.filter_config.get('accept_part_time', False):
            forbidden_types.extend(['part-time', 'part time'])
        forbidden_types.extend(['freelance', '1099'])
        forbidden_types.extend([t.lower() for t in custom_reject_types])

        # Experience patterns — look for hard requirements in description
        exp_patterns = [
            r'(\d+)\+\s*years?\s+(?:of\s+)?(?:professional\s+)?experience\s+required',
            r'minimum\s+(?:of\s+)?(\d+)\s*years?',
            r'at\s+least\s+(\d+)\s*years?',
            r'requires?\s+(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s+required',
        ]

        for job in jobs:
            title = (job.get('title') or '').lower()
            description = (job.get('description') or '').lower()

            # ── Check 1: Seniority in title
            if any(kw in title for kw in seniority_keywords):
                rejected_count['Seniority level'] = rejected_count.get('Seniority level', 0) + 1
                continue

            # ── Check 2: Experience hard requirement in description
            rejected_exp = False
            for pattern in exp_patterns:
                matches = re.findall(pattern, description)
                for match in matches:
                    if int(match) >= max_exp:
                        key = f'{match}+ years required'
                        rejected_count[key] = rejected_count.get(key, 0) + 1
                        rejected_exp = True
                        break
                if rejected_exp:
                    break

            if rejected_exp:
                # Give benefit of doubt if job has flexible language
                if not self._is_flexible(description):
                    continue

            # ── Check 3: Forbidden job types in title or description
            if any(ft in title or ft in description[:500] for ft in forbidden_types):
                rejected_count['Job type'] = rejected_count.get('Job type', 0) + 1
                continue

            # ── Check 4: Auto-reject phrases from user config
            auto_reject = self.filter_config.get('auto_reject_phrases', [])
            phrase_rejected = False
            for phrase in auto_reject:
                if phrase.lower() in description:
                    rejected_count[f'Phrase: {phrase}'] = rejected_count.get(f'Phrase: {phrase}', 0) + 1
                    phrase_rejected = True
                    break
            if phrase_rejected:
                continue

            filtered.append(job)

        return filtered, rejected_count

    def _is_flexible(self, description):
        """
        Check if experience requirement has flexible language.
        e.g. 'Bachelor's + 4 years OR Master's + 2 years'
        """
        flexible_signals = [
            'preferred', 'desired', 'ideal', 'nice to have',
            'or equivalent', ' or master', ' or phd', 'bachelor.*or',
            'equivalent experience'
        ]
        return any(re.search(sig, description) for sig in flexible_signals)

    # ─────────────────────────────────────────
    # Claude Analysis
    # ─────────────────────────────────────────

    def analyze_job(self, job):
        """
        Send a single job to Claude Haiku for qualification analysis.
        Uses Haiku (not Sonnet) — fast and cheap, ideal for bulk analysis.
        Returns analysis dict or None on failure.
        """
        prompt = self._build_analysis_prompt(job)

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            text = self._clean_json(text)
            result = json.loads(text)

            # Sanitize None values that break downstream math
            result['experience_required_min'] = result.get('experience_required_min') or 0
            result['core_skills_match_percent'] = result.get('core_skills_match_percent') or 0
            result['role_match_percentage'] = result.get('role_match_percentage') or 0

            # Hard override: if Claude missed an experience disqualifier, catch it here
            max_exp = self.filter_config.get('max_experience_required', 5)
            exp_min = result.get('experience_required_min', 0)
            if (exp_min >= max_exp
                    and result.get('candidate_qualifies_experience')
                    and not self._is_flexible((job.get('description') or '').lower())):
                result['candidate_qualifies_experience'] = False
                result['overall_qualified'] = False

            # Calculate numeric match score
            result['match_score'] = self._calculate_score(result)

            return result

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON parse error for {job.get('company', '?')}: {str(e)[:60]}")
            return None
        except anthropic.APIStatusError as e:
            print(f"  ❌ Claude API error: {e.status_code} — {str(e)[:80]}")
            return None
        except Exception as e:
            print(f"  ❌ Analysis error for {job.get('company', '?')}: {str(e)[:80]}")
            return None

    def generate_tailored_bullets(self, job, analysis):
        """
        For Tier 2 jobs: generate tailored resume bullets using the JD's language.
        Strict guardrails — only rewrites existing experience, never fabricates.
        Returns list of bullet strings or empty list on failure.
        """
        prompt = self._build_tailoring_prompt(job, analysis)

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                temperature=0.2,  # Slight creativity for natural language
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()
            text = self._clean_json(text)
            result = json.loads(text)
            return result.get('tailored_bullets', [])

        except Exception as e:
            print(f"  ⚠️  Tailoring failed for {job.get('company', '?')}: {str(e)[:60]}")
            return []

    # ─────────────────────────────────────────
    # Prompts
    # ─────────────────────────────────────────

    def _build_analysis_prompt(self, job):
        """Build the qualification analysis prompt."""
        cfg = self.filter_config
        max_exp = cfg.get('max_experience_required', 5)

        # Build employment accept/reject lists from user config
        accept_types = ['Full-time']
        if cfg.get('accept_contract_to_hire'):
            accept_types.append('Contract-to-hire')
        if cfg.get('accept_contract_w2'):
            accept_types.append('W2 Contract')
        if cfg.get('accept_part_time'):
            accept_types.append('Part-time')
        for t in cfg.get('custom_accept_employment', []):
            accept_types.append(t)

        reject_types = ['1099', 'Freelance', 'Temporary', 'Seasonal']
        if cfg.get('reject_internships', True):
            reject_types.append('Internship')
        for t in cfg.get('custom_reject_employment', []):
            reject_types.append(t)

        visa_rule = ""
        if cfg.get('requires_visa_sponsorship'):
            visa_rule = "VISA: Auto-reject if job says 'no visa sponsorship', 'US citizen only', or 'security clearance required'."

        return f"""You are a job qualification analyzer. Analyze whether this candidate qualifies for this job.

CANDIDATE PROFILE:
- Name: {self.profile.get('name', 'Candidate')}
- Experience: {self.profile.get('experience_years', 'Unknown')} years ({self.profile.get('experience_level', 'unknown')} level)
- Core Skills: {', '.join((self.profile.get('core_skills') or [])[:20])}
- Target Roles: {', '.join(self.profile.get('target_roles') or [])}

JOB:
- Company: {job.get('company', 'Unknown')}
- Title: {job.get('title', 'Unknown')}
- Location: {job.get('location', 'Unknown')}
- Description:
{job.get('description', 'No description available')}

QUALIFICATION RULES:
1. EXPERIENCE: Reject if job REQUIRES {max_exp}+ years (hard requirement). Accept if it says "preferred" or "desired".
2. ROLE: Calculate what % of the job matches the candidate's target roles.
3. SKILLS: Calculate what % of required skills the candidate has.
4. EMPLOYMENT: Accept: {', '.join(accept_types)}. Reject: {', '.join(reject_types)}.
5. {visa_rule}
6. TIER 1 = Skill match >= {cfg.get('tier1_skill_threshold', 85)}% AND role match >= {cfg.get('min_target_role_percentage', 70)}%
7. TIER 2 = Skill match >= {cfg.get('tier2_skill_threshold', 65)}% AND role match >= {cfg.get('min_target_role_percentage', 70)}%

Return ONLY valid JSON, no explanation, no markdown:
{{
  "experience_required_min": <number or 0 if not specified>,
  "candidate_qualifies_experience": <true/false>,
  "experience_reasoning": "<one sentence>",

  "employment_type": "<detected type>",
  "candidate_qualifies_employment": <true/false>,

  "visa_friendly": <true/false>,
  "candidate_qualifies_visa": <true/false>,

  "role_match_percentage": <0-100>,
  "primary_role": "<what this job primarily is>",
  "relevant": <true/false>,

  "core_skills_match_percent": <0-100>,
  "matched_skills": ["<skill1>", "<skill2>"],
  "missing_skills": ["<skill1>", "<skill2>"],
  "ats_safe": <true/false>,

  "overall_qualified": <true/false>,
  "tier": <1 or 2 or null>,
  "final_reasoning": "<2 sentence summary of why qualified or not>"
}}"""

    def _build_tailoring_prompt(self, job, analysis):
        """
        Build resume tailoring prompt.
        STRICT: only reword existing experience using JD language.
        Never fabricate, never add skills the candidate doesn't have.
        """
        matched_skills = analysis.get('matched_skills', [])
        missing_skills = analysis.get('missing_skills', [])

        # Build work experience summary for context
        work_exp = self.profile.get('work_experience', [])
        exp_summary = ""
        if work_exp:
            exp_lines = []
            for exp in work_exp[:3]:
                exp_lines.append(
                    f"- {exp.get('role', '')} at {exp.get('company', '')} "
                    f"({exp.get('duration', '')}): used {', '.join(exp.get('key_skills', [])[:5])}"
                )
            exp_summary = "\n".join(exp_lines)
        else:
            exp_summary = f"Skills: {', '.join((self.profile.get('core_skills') or [])[:15])}"

        return f"""You are a resume tailoring assistant. Rewrite 3-4 resume bullet points for this candidate to better match this job.

STRICT RULES — YOU MUST FOLLOW THESE:
1. ONLY use experience the candidate actually has (listed below)
2. NEVER fabricate projects, tools, or skills they don't have
3. ONLY reword existing bullets to use the job's language and keywords
4. Keep bullets truthful, specific, and achievement-focused
5. Use strong action verbs
6. Include metrics where the candidate already has them

CANDIDATE'S ACTUAL EXPERIENCE:
{exp_summary}

Candidate's matched skills for this role: {', '.join(matched_skills[:10])}
Skills in JD that candidate is missing (DO NOT mention these): {', '.join(missing_skills[:5])}

TARGET JOB:
Company: {job.get('company')}
Title: {job.get('title')}
Key JD excerpt: {job.get('description', '')[:1500]}

Return ONLY valid JSON:
{{
  "tailored_bullets": [
    "• <bullet 1 using JD language>",
    "• <bullet 2 using JD language>",
    "• <bullet 3 using JD language>",
    "• <bullet 4 using JD language>"
  ],
  "keywords_used": ["<keyword1>", "<keyword2>"],
  "tailoring_note": "<one sentence: what was emphasized for this role>"
}}"""

    # ─────────────────────────────────────────
    # Scoring & Qualification
    # ─────────────────────────────────────────

    def _calculate_score(self, analysis):
        """
        Calculate match score 0-100.
        Weights: Skills 40% | Role 30% | Experience 20% | Visa+Employment 10%
        A job fails qualification checks will be capped regardless of score.
        """
        score = 0
        score += analysis.get('core_skills_match_percent', 0) * 0.40
        score += analysis.get('role_match_percentage', 0) * 0.30

        if analysis.get('candidate_qualifies_experience'):
            score += 20

        if analysis.get('candidate_qualifies_visa'):
            score += 5

        if analysis.get('candidate_qualifies_employment'):
            score += 5

        return int(score)

    def is_qualified(self, analysis):
        """
        Final qualification gate — ALL conditions must be true.
        A high match score alone is not enough.
        """
        if not analysis:
            return False

        return (
            analysis.get('candidate_qualifies_experience', False)
            and analysis.get('relevant', False)
            and analysis.get('ats_safe', False)
            and analysis.get('candidate_qualifies_visa', False)
            and analysis.get('candidate_qualifies_employment', False)
            and analysis.get('overall_qualified', False)
        )

    # ─────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────

    def _clean_json(self, text):
        """Strip markdown code fences and extract JSON object."""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        first = text.find('{')
        last = text.rfind('}')
        if first != -1 and last != -1:
            return text[first:last + 1]
        return text