import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from config import GOOGLE_SHEETS_CREDENTIALS, SPREADSHEET_ID

def get_sheets_client():
    """Connect to Google Sheets"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_sheet():
    """Get the job hunter spreadsheet"""
    client = get_sheets_client()
    return client.open_by_key(SPREADSHEET_ID)