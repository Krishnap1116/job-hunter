# test_matcher_comprehensive.py

from matcher import analyze_job
from config import get_resume_profile

print("="*80)
print("COMPREHENSIVE MATCHER (CLAUDE) TEST SUITE")
print("="*80)

# Load your ML engineer profile
resume_profile = get_resume_profile("ml_engineer")

test_cases = [
    # Experience tests
    {
        "name": "",
        "job": {
            "Job ID": "test001",
            "Company": "TestCo",
            "Title": "Machine Learning Engineer",
            "Description": """
            Required Qualifications:
            * atleast 7 years of experience developing machine learning models
            * atleast 5  years writing production-level code (Python, SQL)
            * Expert in deep learning frameworks
            """,
            "URL": "https://test.com/1"
        },
        "should_qualify": False,
        "fail_reason": "experience (5+ years)"
    },
    {
        "name": "3+ years REQUIRED - should REJECT",
        "job": {
            "Job ID": "test002",
            "Company": "TestCo",
            "Title": "ML Engineer",
            "Description": """
            Requirements:
            - Minimum 3 years of ML experience
            - Python, PyTorch, TensorFlow
            """,
            "URL": "https://test.com/2"
        },
        "should_qualify": False,
        "fail_reason": "experience (3+ years)"
    },
    {
        "name": "0-2 years - should QUALIFY",
        "job": {
            "Job ID": "test003",
            "Company": "TestCo",
            "Title": "Junior ML Engineer",
            "Description": """
            Requirements:
            - 0-2 years of experience
            - Python, PyTorch, ML fundamentals
            - Work on production ML systems
            """,
            "URL": "https://test.com/3"
        },
        "should_qualify": True,
        "fail_reason": None
    },
    {
        "name": "Account Executive (non-ML) - should REJECT",
        "job": {
            "Job ID": "test004",
            "Company": "Stripe",
            "Title": "Account Executive, Enterprise Sales",
            "Description": """
            Responsibilities:
            - Drive sales strategy
            - Build client relationships
            - Meet revenue targets
            No technical requirements
            """,
            "URL": "https://test.com/4"
        },
        "should_qualify": False,
        "fail_reason": "not ML role (role_match_percentage < 70%)"
    },
    {
        "name": "Product Manager - should REJECT",
        "job": {
            "Job ID": "test005",
            "Company": "Google",
            "Title": "Product Manager - AI",
            "Description": """
            - Define product roadmap
            - Work with ML engineers
            - Some technical knowledge helpful
            - 3+ years PM experience
            """,
            "URL": "https://test.com/5"
        },
        "should_qualify": False,
        "fail_reason": "not ML role + experience"
    },
    {
        "name": "Frontend with 'AI nice to have' - should REJECT",
        "job": {
            "Job ID": "test006",
            "Company": "Vercel",
            "Title": "Frontend Engineer",
            "Description": """
            - Build React applications
            - TypeScript, Next.js
            - Interest in AI is a plus
            - 2+ years frontend experience
            """,
            "URL": "https://test.com/6"
        },
        "should_qualify": False,
        "fail_reason": "not ML-focused (< 70%)"
    },
    {
        "name": "Perfect ML match - should QUALIFY",
        "job": {
            "Job ID": "test007",
            "Company": "Anthropic",
            "Title": "Research Engineer, Machine Learning",
            "Description": """
            Work on:
            - LLM training and fine-tuning
            - PyTorch, Python development
            - Production ML systems
            - RAG and agent systems
            Requirements:
            - 1-2 years ML experience or new grad with strong projects
            - Python, PyTorch, deep learning
            """,
            "URL": "https://test.com/7"
        },
        "should_qualify": True,
        "fail_reason": None
    },
    {
        "name": "Visa restriction (US citizen only) - should REJECT",
        "job": {
            "Job ID": "test008",
            "Company": "DefenseTech",
            "Title": "ML Engineer",
            "Description": """
            - Work on ML systems
            - Python, TensorFlow
            - 0-2 years experience
            - US citizenship required
            - Security clearance required
            """,
            "URL": "https://test.com/8"
        },
        "should_qualify": False,
        "fail_reason": "visa (US citizen only)"
    },
    {
        "name": "Data Scientist (forbidden) - should REJECT",
        "job": {
            "Job ID": "test009",
            "Company": "Meta",
            "Title": "Data Scientist II",
            "Description": """
            - Statistical analysis
            - A/B testing
            - SQL, Python, R
            - 2+ years analytics
            """,
            "URL": "https://test.com/9"
        },
        "should_qualify": False,
        "fail_reason": "forbidden role + experience"
    },
    {
        "name": "Low skill match (embedded systems) - should REJECT",
        "job": {
            "Job ID": "test010",
            "Company": "RoboCo",
            "Title": "Embedded ML Engineer",
            "Description": """
            - C++, CUDA programming
            - Hardware optimization
            - Embedded systems (STM32, ARM)
            - Real-time systems
            - 1-2 years experience
            """,
            "URL": "https://test.com/10"
        },
        "should_qualify": False,
        "fail_reason": "skill mismatch (< 65%)"
    }
]

print(f"\nTesting with profile: {resume_profile.get('name')}")
print(f"Core skills: {', '.join(resume_profile.get('core_skills', [])[:5])}...")
print(f"Experience: {resume_profile.get('experience_years')}")
print("\n" + "="*80)

passed = 0
failed = 0
failures = []

for i, test in enumerate(test_cases, 1):
    print(f"\n[{i}/10] Testing: {test['name']}")
    print(f"  Job: {test['job']['Title']} at {test['job']['Company']}")
    
    analysis = analyze_job(test["job"], resume_profile)
    
    if not analysis:
        print(f"  ❌ ERROR: Claude returned None")
        failed += 1
        failures.append({
            "test": test["name"],
            "error": "Claude returned None"
        })
        continue
    
    actually_qualified = analysis.get('overall_qualified', False)
    
    # Show what Claude decided
    print(f"  Claude says:")
    print(f"    - overall_qualified: {actually_qualified}")
    print(f"    - experience_qualifies: {analysis.get('candidate_qualifies_experience')}")
    print(f"    - relevant: {analysis.get('relevant')}")
    print(f"    - ats_safe: {analysis.get('ats_safe')}")
    print(f"    - visa_qualifies: {analysis.get('candidate_qualifies_visa')}")
    
    if actually_qualified == test["should_qualify"]:
        print(f"  ✅ CORRECT")
        passed += 1
    else:
        print(f"  ❌ WRONG!")
        print(f"    Expected: {test['should_qualify']}")
        print(f"    Got: {actually_qualified}")
        if not test["should_qualify"]:
            print(f"    Should reject because: {test['fail_reason']}")
        failed += 1
        failures.append({
            "test": test["name"],
            "expected": test["should_qualify"],
            "got": actually_qualified,
            "analysis": analysis
        })

print("\n" + "="*80)
print(f"RESULTS: {passed} passed, {failed} failed")
print("="*80)

if failures:
    print("\nFAILURES:")
    for fail in failures:
        print(f"\n❌ {fail['test']}")
        if "error" in fail:
            print(f"   Error: {fail['error']}")
        else:
            print(f"   Expected: {fail['expected']}")
            print(f"   Got: {fail['got']}")
            if 'analysis' in fail:
                print(f"   Reasoning: {fail['analysis'].get('final_reasoning', 'N/A')}")
else:
    print("\n🎉 ALL TESTS PASSED!")
    print("Claude is correctly rejecting/accepting jobs!")