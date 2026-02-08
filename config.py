import os

# Resume Profile - CUSTOMIZE THIS WITH YOUR SKILLS
RESUME_PROFILE = {
    "core_skills": [
        "Python",
        "Machine Learning",
        "Deep Learning",
        "PyTorch",
        "TensorFlow",
        "NLP",
        "Computer Vision"
    ],
    "important_skills": [
        "AWS",
        "Docker",
        "Kubernetes",
        "FastAPI",
        "PostgreSQL",
        "Redis",
        "Git"
    ],
    "nice_skills": [
        "React",
        "TypeScript",
        "MLflow",
        "Airflow"
    ],
    "forbidden_keywords": [
        "data scientist",
        "business analyst",
        "support engineer",
        "technical writer",
        "project manager",
        "sales engineer"
    ]
}

SKILL_WEIGHTS = {
    "core": 3,
    "important": 2,
    "nice": 1
}

# API Keys from GitHub Secrets
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
# EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
# EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")