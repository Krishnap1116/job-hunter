import os

# Check if DATABASE_URL exists (means we're in Streamlit Cloud)
if os.getenv("DATABASE_URL"):
    print("🌐 Using PostgreSQL (Cloud)")
    from database_postgres import JobHunterDB
else:
    print("💻 Using SQLite (Local)")
    from database import JobHunterDB

# Export the class
__all__ = ['JobHunterDB']