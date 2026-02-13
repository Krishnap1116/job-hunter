# test_matcher.py

from matcher import build_dynamic_prompt
from config import get_resume_profile

# Get your profile
profile = get_resume_profile("ml_engineer")

# Test job (Oracle-like)
oracle_job = {
    "Company": "Oracle",
    "Title": "Software Engineer - Frontend/UI",
    "Description": """
Design, develop, troubleshoot, and debug complex software programs for web-based 
applications, tools, and services, with a strong emphasis on modern UI frameworks 
and frontend architecture. Build scalable, high-quality user interfaces using 
JavaScript, TypeScript, React.js, and Knockout.js.

Qualifications:
BS or MS degree in Computer Science or a related field, or equivalent practical experience.
Minimum of 7 years of software engineering experience, with strong proficiency in 
modern UI frameworks and web application development.

Nice to have: experience writing effective AI prompts and familiarity with Vector 
Databases for AI-driven or intelligent application features.
"""
}

# Good job (should pass)
good_job = {
    "Company": "Anthropic",
    "Title": "ML Engineer",
    "Description": """
We're looking for ML Engineers to build and deploy LLM-powered applications. 
You'll work with PyTorch, Transformers, and RAG systems to create production AI features.

Requirements:
- 0-2 years experience in ML/AI
- Strong Python skills
- Experience with PyTorch or TensorFlow
- Understanding of LLMs and transformer architectures

We sponsor H1B visas. New grads welcome!
"""
}

print("=" * 70)
print("TESTING MATCHER PROMPT GENERATION")
print("=" * 70)

print("\n1. ORACLE JOB (Should Reject):")
print("-" * 70)
prompt = build_dynamic_prompt(oracle_job, profile)
print(prompt[:500] + "...")

print("\n2. ANTHROPIC JOB (Should Accept):")
print("-" * 70)
prompt = build_dynamic_prompt(good_job, profile)
print(prompt[:500] + "...")

print("\n✅ Prompts generated successfully!")
print("Next: Test with actual Claude API")