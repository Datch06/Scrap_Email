#!/usr/bin/env python3
"""Format emails CSV for Google Sheets with one row per domain."""

import sys
from pathlib import Path
from collections import defaultdict

def format_emails_for_gsheet(input_csv, output_csv):
    """Group emails by domain and format for Google Sheets."""

    # Read CSV and group emails by domain
    domain_emails = defaultdict(list)

    with open(input_csv, 'r', encoding='utf-8') as f:
        # Skip header
        next(f)

        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(',', 1)
            if len(parts) != 2:
                continue

            domain, email = parts

            # Skip "NO EMAIL FOUND"
            if email == 'NO EMAIL FOUND':
                domain_emails[domain] = []
            else:
                domain_emails[domain].append(email)

    # Write formatted CSV
    with open(output_csv, 'w', encoding='utf-8') as f:
        # Header
        f.write('Domain,Emails\n')

        # Write each domain with its emails
        for domain in sorted(domain_emails.keys()):
            emails = domain_emails[domain]

            if emails:
                # Join emails with semicolon
                emails_str = '; '.join(emails)
                f.write(f'{domain},"{emails_str}"\n')
            else:
                f.write(f'{domain},NO EMAIL FOUND\n')

    # Print summary
    domains_with_emails = sum(1 for emails in domain_emails.values() if emails)
    total_emails = sum(len(emails) for emails in domain_emails.values())

    print(f"[INFO] Formatted {len(domain_emails)} domains")
    print(f"[INFO] {domains_with_emails} domains have emails")
    print(f"[INFO] {total_emails} total emails")
    print(f"[INFO] Output saved to: {output_csv}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python format_for_gsheet.py <emails_found.csv> [output.csv]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('emails_formatted.csv')

    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)

    format_emails_for_gsheet(input_file, output_file)
