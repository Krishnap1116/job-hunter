# test_prefilter_comprehensive.py

from pre_filter import should_analyze

print("="*80)
print("COMPREHENSIVE PRE-FILTER TEST SUITE")
print("="*80)

test_cases = [
    # Experience tests
    {
        "name": "5+ years explicit",
        "job": {
            "Title": "ML Engineer",
            "Description": "5+ years of experience required"
        },
        "expected": False,
        "reason": "5+ years required"
    },
    {
        "name": "2+ years explicit (at threshold)",
        "job": {
            "Title": "ML Engineer", 
            "Description": "2+ years of experience required"
        },
        "expected": False,
        "reason": "2+ years required"
    },
    {
        "name": "1-2 years (should pass)",
        "job": {
            "Title": "ML Engineer",
            "Description": "1-2 years of experience"
        },
        "expected": True,
        "reason": "Passed pre-filter"
    },
    {
        "name": "Minimum 3 years",
        "job": {
            "Title": "Software Engineer",
            "Description": "Minimum of 3 years experience in Python"
        },
        "expected": False,
        "reason": "3+ years required"
    },
    {
        "name": "At least 4 years",
        "job": {
            "Title": "Backend Engineer",
            "Description": "At least 4 years of software development"
        },
        "expected": False,
        "reason": "4+ years required"
    },
    
    # Seniority tests
    {
        "name": "Senior in title",
        "job": {
            "Title": "Senior Software Engineer",
            "Description": "Build scalable systems"
        },
        "expected": False,
        "reason": "Seniority: senior"
    },
    {
        "name": "Staff Engineer",
        "job": {
            "Title": "Staff Machine Learning Engineer",
            "Description": "Lead ML initiatives"
        },
        "expected": False,
        "reason": "Seniority: staff"
    },
    {
        "name": "Engineering Manager",
        "job": {
            "Title": "Engineering Manager - ML",
            "Description": "Manage team of engineers"
        },
        "expected": False,
        "reason": "Seniority: manager"
    },
    {
        "name": "Junior (should pass)",
        "job": {
            "Title": "Junior Software Engineer",
            "Description": "0-2 years experience"
        },
        "expected": True,
        "reason": "Passed pre-filter"
    },
    
    # Job type tests
    {
        "name": "Internship",
        "job": {
            "Title": "Software Engineering Internship",
            "Description": "Summer intern program"
        },
        "expected": False,
        "reason": "Job type: intern"
    },
    {
        "name": "Part-time",
        "job": {
            "Title": "Part-time ML Engineer",
            "Description": "20 hours per week"
        },
        "expected": False,
        "reason": "Job type: part-time"
    },
    {
        "name": "Contractor",
        "job": {
            "Title": "Contractor - Backend Engineer",
            "Description": "6 month contract"
        },
        "expected": False,
        "reason": "Job type: contractor"
    },
    
    # Forbidden titles tests
    {
        "name": "Business Analyst",
        "job": {
            "Title": "Business Analyst",
            "Description": "Analyze business requirements"
        },
        "expected": False,
        "reason": "Specific title: business analyst"
    },
    {
        "name": "Data Analyst",
        "job": {
            "Title": "Data Analyst - ML Team",
            "Description": "Analyze data trends"
        },
        "expected": False,
        "reason": "Specific title: data analyst"
    },
    {
        "name": "Solutions Engineer (forbidden)",
        "job": {
            "Title": "Solutions Engineer",
            "Description": "Customer-facing technical role"
        },
        "expected": False,
        "reason": "Specific title: solutions engineer"
    },
    {
        "name": "Product Manager",
        "job": {
            "Title": "Product Manager - AI",
            "Description": "Define product roadmap"
        },
        "expected": False,
        "reason": "Specific title: product manager"
    },
    
    # Edge cases
    {
        "name": "Research Scientist (should pass)",
        "job": {
            "Title": "Research Scientist - Machine Learning",
            "Description": "PhD preferred, 0-2 years industry"
        },
        "expected": True,
        "reason": "Passed pre-filter"
    },
    {
        "name": "Account Executive (non-tech)",
        "job": {
            "Title": "Account Executive",
            "Description": "Sales role"
        },
        "expected": True,  # No technical keyword check anymore
        "reason": "Passed pre-filter"
    },
    {
        "name": "Special characters in title",
        "job": {
            "Title": "[Expression of Interest] Research Engineer",
            "Description": "ML research position"
        },
        "expected": True,
        "reason": "Passed pre-filter"
    },
    {
        "name": "Range: 2-4 years",
        "job": {
            "Title": "ML Engineer",
            "Description": "2-4 years of experience required"
        },
        "expected": False,
        "reason": "2+ years required"
    },
    {
        "name": "Range: 3 to 5 years",
        "job": {
            "Title": "Software Engineer",
            "Description": "3 to 5 years experience"
        },
        "expected": False,
        "reason": "3+ years required"
    }
]

passed = 0
failed = 0
failures = []

for i, test in enumerate(test_cases, 1):
    should_pass, reason = should_analyze(test["job"])
    
    if should_pass == test["expected"]:
        status = "✅ PASS"
        passed += 1
    else:
        status = "❌ FAIL"
        failed += 1
        failures.append({
            "test": test["name"],
            "expected": test["expected"],
            "got": should_pass,
            "expected_reason": test["reason"],
            "got_reason": reason
        })
    
    print(f"{i:2}. {status} | {test['name']}")
    if should_pass != test["expected"]:
        print(f"    Expected: {test['expected']} ({test['reason']})")
        print(f"    Got:      {should_pass} ({reason})")

print("\n" + "="*80)
print(f"RESULTS: {passed} passed, {failed} failed")
print("="*80)

if failures:
    print("\nFAILURES:")
    for fail in failures:
        print(f"\n❌ {fail['test']}")
        print(f"   Expected: {fail['expected']} - {fail['expected_reason']}")
        print(f"   Got:      {fail['got']} - {fail['got_reason']}")
else:
    print("\n🎉 ALL TESTS PASSED!")