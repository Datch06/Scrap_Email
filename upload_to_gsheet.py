#!/usr/bin/env python3
"""Upload domains to Google Sheets using gspread library.

Installation:
    pip install gspread oauth2client

Setup:
    1. Go to https://console.cloud.google.com/
    2. Create a new project or select existing one
    3. Enable Google Sheets API
    4. Create credentials (Service Account)
    5. Download JSON key file
    6. Share your Google Sheet with the service account email
    7. Save the JSON key as 'credentials.json' in this directory
"""

import sys
from pathlib import Path

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    print("Error: Required libraries not installed.")
    print("Please run: pip install gspread oauth2client")
    sys.exit(1)


def upload_domains_to_sheet(domains_file, sheet_url, credentials_file='credentials.json'):
    """Upload domains from file to Google Sheet."""

    # Check if credentials file exists
    if not Path(credentials_file).exists():
        print(f"Error: Credentials file '{credentials_file}' not found.")
        print("\nPlease follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project")
        print("3. Enable Google Sheets API")
        print("4. Create Service Account credentials")
        print("5. Download JSON key and save as 'credentials.json'")
        print("6. Share your Google Sheet with the service account email")
        return False

    # Read domains from file
    domains = []
    with open(domains_file, 'r', encoding='utf-8') as f:
        domains = [line.strip() for line in f if line.strip()]

    print(f"Found {len(domains)} domains to upload")

    # Setup credentials
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"Error authenticating: {e}")
        return False

    # Extract sheet ID from URL
    # URL format: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit...
    sheet_id = sheet_url.split('/d/')[1].split('/')[0]

    try:
        # Open the sheet
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.sheet1  # Use first worksheet

        # Clear existing data (optional - comment out if you want to append)
        # worksheet.clear()

        # Prepare data with header
        data = [['Domain']] + [[domain] for domain in domains]

        # Upload data
        worksheet.update('A1', data)

        print(f"✓ Successfully uploaded {len(domains)} domains to Google Sheet")
        print(f"  Sheet URL: {sheet_url}")
        return True

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Spreadsheet not found. Make sure:")
        print("1. The sheet URL is correct")
        print("2. You've shared the sheet with your service account email")
        return False
    except Exception as e:
        print(f"Error uploading data: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python upload_to_gsheet.py <domains_file.txt> [sheet_url]")
        print("\nExample:")
        print("  python upload_to_gsheet.py domains_fr_only.txt")
        sys.exit(1)

    domains_file = sys.argv[1]
    sheet_url = sys.argv[2] if len(sys.argv) > 2 else "https://docs.google.com/spreadsheets/d/19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I/edit?usp=sharing"

    if not Path(domains_file).exists():
        print(f"Error: File '{domains_file}' not found")
        sys.exit(1)

    upload_domains_to_sheet(domains_file, sheet_url)
