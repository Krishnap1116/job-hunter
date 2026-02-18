# job-hunter
Automated job search system
# 🎯 AI Job Hunter - Self-Service Platform

A complete self-service job hunting platform powered by Claude AI.

## Features

- 📄 **Resume Parsing**: Upload your resume, AI extracts your profile
- 🔍 **Job Collection**: Scrapes multiple job boards automatically
- 🤖 **AI Matching**: Claude analyzes jobs and finds perfect matches
- 🎯 **Tiered Results**: Tier 1 (best matches) and Tier 2 (good backups)
- ⚙️ **Customizable**: Set your own filters and preferences
- 💾 **Local Storage**: All data stored in SQLite (no external dependencies)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the App
```bash
streamlit run app.py
```

### 3. Create Profile

1. Upload your resume (PDF)
2. AI will extract your skills and experience
3. Review and confirm your profile
4. Add your Anthropic API key in Settings

### 4. Find Jobs

1. Click "Collect Jobs" to scrape job boards
2. Click "Analyze Jobs" to match with AI
3. View your Tier 1 and Tier 2 matches!

## API Keys Needed

### Required:
- **Anthropic API Key**: Get from https://console.anthropic.com/

### Optional (for more job sources):
- **JSearch API**: Get from RapidAPI
- **Adzuna API**: Get from Adzuna

## Database

All data is stored in `job_hunter.db` (SQLite).

Tables:
- `profiles` - User profiles
- `filter_configs` - Filter settings
- `raw_jobs` - Scraped jobs
- `analyzed_jobs` - Matched jobs
- `api_keys` - API keys (encrypted in production)

## File Structure
```
job-hunter/
├── app.py                      # Main Streamlit app
├── database.py                 # Database manager
├── resume_parser.py            # Resume parsing with Claude
├── job_scraper_integrated.py   # Job scraper
├── job_matcher_integrated.py   # Job matcher with Claude
├── requirements.txt            # Python dependencies
├── job_hunter.db              # SQLite database (created on first run)
└── README.md                   # This file
```

## How It Works

1. **Upload Resume** → Claude extracts skills, experience, target roles
2. **Set Filters** → Configure max experience, skill thresholds, visa requirements
3. **Collect Jobs** → Scrapes RemoteOK, SimplifyJobs, JSearch, Adzuna
4. **Pre-Filter** → Quickly eliminates non-matches (seniority, experience)
5. **AI Analysis** → Claude deeply analyzes each job against your profile
6. **View Matches** → See Tier 1 (best) and Tier 2 (backup) matches

## Tips

- Start with 10-20 jobs when first testing
- Add optional API keys for more job sources
- Adjust filters if too many/few matches
- Jobs are deduplicated automatically

## Security Note

⚠️ API keys are stored in plain text in the SQLite database.

For production use, implement proper encryption!

## Support

Questions? Issues? Open a GitHub issue!