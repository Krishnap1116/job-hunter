# test_prefilter.py

from pre_filter import should_analyze

# Test cases
test_jobs = [
    {
        "Title": "Software Engineer",
        "Description": "Minimum of 7 years of software engineering experience",
        "Company": "Oracle"
    },
    {
        "Title": "ML Engineer",
        "Description": "0-2 years experience required",
        "Company": "Startup"
    },
    {
        "Title": "Senior Software Engineer",
        "Description": "5+ years required",
        "Company": "BigCo"
    },
    {
        "Title": "Junior ML Engineer",
        "Description": "New grads welcome, 0-1 years",
        "Company": "GoodCo"
    }
]

for job in test_jobs:
    should_pass, reason = should_analyze(job)
    status = "✅ PASS" if should_pass else "❌ REJECT"
    print(f"{status} - {job['Company']}: {reason}")