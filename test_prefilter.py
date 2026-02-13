# test_prefilter.py

from pre_filter import should_analyze

# Test jobs
test_jobs = [
    {
        "Title": "Software Engineer",
        "Description": "Minimum of 7 years of software engineering experience required.",
        "Company": "Oracle"
    },
    {
        "Title": "ML Engineer", 
        "Description": "0-2 years experience. We're looking for new grads with strong ML background.",
        "Company": "Anthropic"
    },
    {
        "Title": "Senior Software Engineer",
        "Description": "5+ years required",
        "Company": "BigCorp"
    },
    {
        "Title": "AI Engineer",
        "Description": "Entry level position. 1-2 years preferred but not required.",
        "Company": "Startup"
    },
    {
        "Title": "Data Scientist",
        "Description": "Looking for someone to analyze data.",
        "Company": "DataCo"
    }
]

print("=" * 70)
print("TESTING PRE-FILTER")
print("=" * 70)

for i, job in enumerate(test_jobs, 1):
    should_pass, reason = should_analyze(job)
    status = "✅ PASS" if should_pass else "❌ REJECT"
    
    print(f"\n{i}. {job['Company']} - {job['Title']}")
    print(f"   {status}: {reason}")

print("\n" + "=" * 70)