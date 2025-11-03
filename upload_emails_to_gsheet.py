#!/usr/bin/env python3
"""Upload formatted emails CSV to Google Sheets using gspread library."""

import sys
import csv
from pathlib import Path

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    print("Error: Required libraries not installed.")
    print("Please run: pip install gspread oauth2client")
    sys.exit(1)


def upload_emails_to_sheet(csv_file, sheet_url, credentials_file='credentials.json'):
    """Upload emails CSV to Google Sheet."""

    # Check if credentials file exists
    if not Path(credentials_file).exists():
        print(f"Error: Credentials file '{credentials_file}' not found.")
        print("\nPlease follow the setup instructions in GSHEET_SETUP.md")
        return False

    # Read CSV data
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            data.append(row)

    print(f"[INFO] Loaded {len(data)-1} rows from CSV (excluding header)")

    # Setup credentials
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return False

    # Extract sheet ID from URL
    sheet_id = sheet_url.split('/d/')[1].split('/')[0]

    try:
        # Open the sheet
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.sheet1

        # Clear existing data
        print("[INFO] Clearing existing data...")
        worksheet.clear()

        # Upload data
        print(f"[INFO] Uploading {len(data)} rows...")
        worksheet.update('A1', data)

        print(f"\n✓ Successfully uploaded {len(data)-1} domains with emails to Google Sheet")
        print(f"  Sheet URL: {sheet_url}")
        return True

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"[ERROR] Spreadsheet not found. Make sure:")
        print("1. The sheet URL is correct")
        print("2. You've shared the sheet with your service account email")
        return False
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python upload_emails_to_gsheet.py <emails_formatted.csv> [sheet_url]")
        print("\nExample:")
        print("  python upload_emails_to_gsheet.py emails_formatted.csv")
        sys.exit(1)

    csv_file = Path(sys.argv[1])
    sheet_url = sys.argv[2] if len(sys.argv) > 2 else "https://docs.google.com/spreadsheets/d/19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I/edit?usp=sharing"

    if not csv_file.exists():
        print(f"[ERROR] File '{csv_file}' not found")
        sys.exit(1)

    upload_emails_to_sheet(csv_file, sheet_url)
