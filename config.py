
# config.py - Auto-loads parsed resume profiles

import os
import importlib.util
from pathlib import Path

# ==================== AUTO-LOAD RESUME PROFILES ====================

def load_resume_profiles():
    """
    Automatically load all parsed resume profiles from resume_profiles/ folder
    """
    profiles = {}
    
    # Default fallback profile (if no resumes parsed yet)
    profiles['default'] = {
        "name": "Default Profile",
        "description": "Default - parse your resume to create a custom profile",
        "experience_years": "0-2",
        "core_skills": ["Python", "JavaScript", "SQL"],
        "important_skills": ["Git", "AWS", "Docker"],
        "nice_skills": ["React", "Kubernetes"],
        "target_roles": ["Software Engineer"],
        "forbidden_keywords": ["data scientist", "business analyst"]
    }
    
    # Load all parsed profiles
    resume_profiles_dir = Path("resume_profiles")
    
    if resume_profiles_dir.exists():
        for profile_file in resume_profiles_dir.glob("*.py"):
            if profile_file.name == "__init__.py":
                continue
            
            try:
                profile_name = profile_file.stem  # filename without .py
                
                # Import the module
                spec = importlib.util.spec_from_file_location(profile_name, profile_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get the RESUME_PROFILE from the module
                if hasattr(module, 'RESUME_PROFILE'):
                    profiles[profile_name] = module.RESUME_PROFILE
                    print(f"✅ Loaded profile: {profile_name}")
                
            except Exception as e:
                print(f"⚠️  Failed to load {profile_file}: {e}")
    
    return profiles

# Load all profiles
RESUME_PROFILES = load_resume_profiles()

# Set default profile
DEFAULT_PROFILE = list(RESUME_PROFILES.keys())[0] if RESUME_PROFILES else "default"

def get_resume_profile(profile_name=None):
    """Get resume profile by name, or use default"""
    if profile_name and profile_name in RESUME_PROFILES:
        return RESUME_PROFILES[profile_name]
    return RESUME_PROFILES[DEFAULT_PROFILE]

def list_available_profiles():
    """List all available resume profiles"""
    print("\n📋 Available Resume Profiles:")
    print("=" * 70)
    for name, profile in RESUME_PROFILES.items():
        print(f"\n  {name}:")
        print(f"    Description: {profile.get('description', 'N/A')}")
        print(f"    Experience: {profile.get('experience_years', 'N/A')}")
        print(f"    Core Skills: {', '.join(profile.get('core_skills', [])[:5])}...")
        print(f"    Target Roles: {', '.join(profile.get('target_roles', []))}")
    print("=" * 70)

# ==================== API KEYS ====================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")
# # config.py - Multi-Resume Configuration

# import os

# # ==================== RESUME PROFILES ====================
# # Add as many resume profiles as you want
# # Users can select which one to use when running the matcher

# RESUME_PROFILES = {
#     # PROFILE 1: ML/AI Engineering Track
#     "ml_engineer": {
#         "name": "ML/AI Engineer",
#         "description": "Machine Learning & AI Engineering focus",
#         "experience_years": "0-2",
#         "core_skills": [
#             "Python",
#             "Machine Learning",
#             "Deep Learning",
#             "PyTorch",
#             "TensorFlow",
#             "NLP",
#             "Computer Vision"
#         ],
#         "important_skills": [
#             "AWS",
#             "Docker",
#             "Kubernetes",
#             "FastAPI",
#             "PostgreSQL",
#             "Redis",
#             "Git",
#             "Scikit-learn",
#             "Pandas",
#             "NumPy"
#         ],
#         "nice_skills": [
#             "React",
#             "TypeScript",
#             "MLflow",
#             "Airflow",
#             "Spark",
#             "Databricks",
#             "Snowflake"
#         ],
#         "target_roles": [
#             "Machine Learning Engineer",
#             "ML Engineer",
#             "AI Engineer",
#             "Research Engineer",
#             "Applied Scientist"
#         ],
#         "forbidden_keywords": [
#             "data scientist",
#             "data analyst",
#             "business analyst",
#             "support engineer",
#             "technical writer",
#             "project manager",
#             "sales engineer",
#             "customer success"
#         ]
#     },
    
#     # PROFILE 2: Full-Stack/Backend Track
#     "backend_engineer": {
#         "name": "Backend/Full-Stack Engineer",
#         "description": "Backend & Full-Stack Software Engineering",
#         "experience_years": "0-2",
#         "core_skills": [
#             "Python",
#             "JavaScript",
#             "TypeScript",
#             "Node.js",
#             "React",
#             "SQL",
#             "REST APIs",
#             "Git"
#         ],
#         "important_skills": [
#             "PostgreSQL",
#             "MongoDB",
#             "Redis",
#             "Docker",
#             "AWS",
#             "FastAPI",
#             "Express.js",
#             "GraphQL"
#         ],
#         "nice_skills": [
#             "Kubernetes",
#             "Terraform",
#             "Next.js",
#             "Vue.js",
#             "Microservices",
#             "RabbitMQ",
#             "Kafka"
#         ],
#         "target_roles": [
#             "Software Engineer",
#             "Backend Engineer",
#             "Full-Stack Engineer",
#             "Full Stack Developer",
#             "Web Developer"
#         ],
#         "forbidden_keywords": [
#             "data scientist",
#             "data analyst",
#             "business analyst",
#             "support engineer",
#             "technical writer",
#             "project manager",
#             "sales engineer",
#             "customer success",
#             "devops engineer"  # Remove if you want DevOps roles
#         ]
#     },
    
#     # PROFILE 3: Generic Software Engineer (Broadest)
#     "software_engineer": {
#         "name": "Software Engineer (General)",
#         "description": "General Software Engineering - broadest match",
#         "experience_years": "0-2",
#         "core_skills": [
#             "Python",
#             "JavaScript",
#             "Java",
#             "C++",
#             "Data Structures",
#             "Algorithms",
#             "Git",
#             "SQL"
#         ],
#         "important_skills": [
#             "AWS",
#             "Docker",
#             "REST APIs",
#             "PostgreSQL",
#             "MongoDB",
#             "React",
#             "Node.js"
#         ],
#         "nice_skills": [
#             "Kubernetes",
#             "TypeScript",
#             "GraphQL",
#             "Redis",
#             "Microservices",
#             "CI/CD"
#         ],
#         "target_roles": [
#             "Software Engineer",
#             "Software Developer",
#             "Engineer",
#             "Developer"
#         ],
#         "forbidden_keywords": [
#             "data scientist",
#             "business analyst",
#             "support engineer",
#             "technical writer",
#             "project manager",
#             "sales engineer"
#         ]
#     }
# }

# # ==================== DEFAULT PROFILE ====================
# # Set which profile to use by default
# DEFAULT_PROFILE = "ml_engineer"  # Change this to your main track

# # Helper function to get active profile
# def get_resume_profile(profile_name=None):
#     """Get resume profile by name, or use default"""
#     if profile_name and profile_name in RESUME_PROFILES:
#         return RESUME_PROFILES[profile_name]
#     return RESUME_PROFILES[DEFAULT_PROFILE]

# # ==================== API KEYS ====================
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
# SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
# ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
# ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")