import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from dotenv import load_dotenv
from config import GOOGLE_SHEETS_CREDENTIALS, SPREADSHEET_ID
# Load environment variables
load_dotenv('.env')

# Get credentials from environment
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")

def get_sheets_client():
    """Connect to Google Sheets"""
    if not GOOGLE_SHEETS_CREDENTIALS:
        raise Exception("GOOGLE_SHEETS_CREDENTIALS not found in environment")
    
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_sheet():
    """Get the job hunter spreadsheet"""
    if not SPREADSHEET_ID:
        raise Exception("SPREADSHEET_ID not found in environment")
    
    client = get_sheets_client()
    return client.open_by_key(SPREADSHEET_ID)