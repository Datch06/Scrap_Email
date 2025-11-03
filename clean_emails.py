#!/usr/bin/env python3
"""Clean the emails CSV to remove invalid emails (images, etc.)"""

import re
import csv
from pathlib import Path

def is_valid_email(email):
    """Check if email is valid (not an image file, etc.)"""
    if email == 'NO EMAIL FOUND':
        return True

    # Remove obvious image files
    if email.endswith(('.avif', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')):
        return False

    # Check for basic email pattern
    if '@' not in email:
        return False

    # Remove example/fake emails
    fake_patterns = [
        'example.com',
        'exemple.org',
        'domain.com',
        'domaine.fr',
        'xxx.xx',
        'email.com',
        'sentry.io',
        'sentry.wixpress.com',
        'sentry-next.wixpress.com',
        'ingest.sentry.io',
    ]

    email_lower = email.lower()
    for pattern in fake_patterns:
        if pattern in email_lower:
            return False

    return True

def clean_csv(input_file, output_file):
    """Clean the emails CSV."""

    # Read input CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)

        cleaned_data = []
        stats = {'total': 0, 'removed': 0, 'kept': 0}

        for row in reader:
            if len(row) != 2:
                continue

            domain, emails_str = row

            if emails_str == 'NO EMAIL FOUND':
                cleaned_data.append([domain, 'NO EMAIL FOUND'])
                continue

            # Split emails
            emails = [e.strip() for e in emails_str.split(';')]
            stats['total'] += len(emails)

            # Filter valid emails
            valid_emails = [e for e in emails if is_valid_email(e)]
            stats['kept'] += len(valid_emails)
            stats['removed'] += len(emails) - len(valid_emails)

            if valid_emails:
                cleaned_emails = '; '.join(valid_emails)
                cleaned_data.append([domain, cleaned_emails])
            else:
                cleaned_data.append([domain, 'NO EMAIL FOUND'])

    # Write cleaned CSV
    with open(output_file, 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Domain', 'Emails'])
        writer.writerows(cleaned_data)

    print(f"[INFO] Cleaned {stats['total']} emails")
    print(f"[INFO] Kept {stats['kept']} valid emails")
    print(f"[INFO] Removed {stats['removed']} invalid emails (images, fake emails, etc.)")
    print(f"[INFO] Output saved to: {output_file}")

if __name__ == '__main__':
    input_file = Path('emails_formatted.csv')
    output_file = Path('emails_cleaned.csv')

    if not input_file.exists():
        print(f"Error: {input_file} not found")
        exit(1)

    clean_csv(input_file, output_file)
