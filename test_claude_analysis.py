# test_claude_analysis.py

import os
from matcher import analyze_job
from config import get_resume_profile

# Make sure API key is set
if not os.getenv("ANTHROPIC_API_KEY"):
    print("❌ Set ANTHROPIC_API_KEY first:")
    print("   export ANTHROPIC_API_KEY='sk-ant-...'")
    exit(1)

profile = get_resume_profile("ml_engineer")

# Test 1: Oracle job (should reject)
oracle_job = {
    "Company": "Oracle",
    "Title": "Software Engineer - Frontend/UI",
    "Description": """Minimum of 7 years of software engineering experience, 
    with strong proficiency in modern UI frameworks (React, Knockout.js). 
    Nice to have: AI prompts and Vector Databases."""
}

# Test 2: Good ML job (should accept)
good_job = {
    "Company": "Anthropic",
    "Title": "ML Engineer",
    "Description": """0-2 years experience. Build LLM applications with PyTorch, 
    LangChain, RAG. New grads welcome. We sponsor H1B visas."""
}

print("=" * 70)
print("TESTING CLAUDE ANALYSIS (Costs $0.002)")
print("=" * 70)

print("\n1. Analyzing Oracle job...")
oracle_analysis = analyze_job(oracle_job, profile)

if oracle_analysis:
    print(f"   Overall Qualified: {oracle_analysis.get('overall_qualified')}")
    print(f"   Experience Qualifies: {oracle_analysis.get('candidate_qualifies_experience')}")
    print(f"   Role Match: {oracle_analysis.get('role_match_percentage')}%")
    print(f"   Reasoning: {oracle_analysis.get('final_reasoning', 'N/A')[:100]}...")
else:
    print("   ❌ Analysis failed")

print("\n2. Analyzing Anthropic job...")
good_analysis = analyze_job(good_job, profile)

if good_analysis:
    print(f"   Overall Qualified: {good_analysis.get('overall_qualified')}")
    print(f"   Experience Qualifies: {good_analysis.get('candidate_qualifies_experience')}")
    print(f"   Tier: {good_analysis.get('tier')}")
    print(f"   Skills Match: {good_analysis.get('core_skills_match_percent')}%")
    print(f"   Reasoning: {good_analysis.get('final_reasoning', 'N/A')[:100]}...")
else:
    print("   ❌ Analysis failed")

print("\n" + "=" * 70)
print("Expected Results:")
print("  Oracle: overall_qualified=False (7 years, frontend role)")
print("  Anthropic: overall_qualified=True (0-2 years, ML role)")
print("=" * 70)