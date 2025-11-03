#!/usr/bin/env python3
"""Extract email addresses from a list of domains.

This script will:
1. Read a list of domains from a file
2. For each domain, fetch the homepage and common pages (contact, about, etc.)
3. Extract email addresses using regex
4. Save results to CSV
"""

import re
import sys
import time
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from html.parser import HTMLParser

# Common pages that often contain contact emails
COMMON_PAGES = [
    '/',
    '/contact',
    '/contact-us',
    '/contact.html',
    '/about',
    '/about-us',
    '/mentions-legales',
    '/legal',
    '/qui-sommes-nous',
    '/nous-contacter',
]

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

REQUEST_TIMEOUT = 10
PAUSE_BETWEEN_DOMAINS = 1.0
PAUSE_BETWEEN_PAGES = 0.5

# Regex pattern for email addresses
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Emails to ignore (common false positives)
IGNORE_EMAILS = {
    'example@example.com',
    'email@example.com',
    'contact@example.com',
    'info@example.com',
    'test@test.com',
    'noreply@example.com',
    'user@example.com',
}

def build_opener():
    """Create URL opener with SSL context."""
    try:
        ssl_context = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
    except Exception:
        ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    https_handler = urllib.request.HTTPSHandler(context=ssl_context)
    return urllib.request.build_opener(https_handler)

def fetch_page(url, opener):
    """Fetch a webpage and return its content."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                return None
            data = resp.read()
            try:
                return data.decode('utf-8', errors='replace')
            except Exception:
                return data.decode('latin-1', errors='replace')
    except Exception as e:
        return None

def extract_emails_from_text(text):
    """Extract email addresses from text using regex."""
    if not text:
        return set()

    emails = set()
    matches = EMAIL_PATTERN.findall(text)

    for email in matches:
        email = email.lower().strip()
        # Filter out common false positives
        if email in IGNORE_EMAILS:
            continue
        # Filter out image files and common extensions
        if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            continue
        # Filter out obviously fake emails
        if 'example' in email or 'test' in email or 'placeholder' in email:
            continue
        emails.add(email)

    return emails

def find_emails_for_domain(domain, opener, max_pages=5):
    """Find email addresses for a given domain."""
    print(f"[INFO] Scanning {domain}...", end=' ', flush=True)

    all_emails = set()
    pages_checked = 0

    for page_path in COMMON_PAGES[:max_pages]:
        if not domain.startswith('http'):
            url = f"https://{domain}{page_path}"
        else:
            url = f"{domain}{page_path}"

        html = fetch_page(url, opener)
        if html:
            emails = extract_emails_from_text(html)
            all_emails.update(emails)
            pages_checked += 1

        if PAUSE_BETWEEN_PAGES:
            time.sleep(PAUSE_BETWEEN_PAGES)

    print(f"found {len(all_emails)} email(s) in {pages_checked} page(s)")
    return all_emails

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_emails.py <domains_file.txt> [output.csv]")
        print("\nExample:")
        print("  python extract_emails.py domains_fr_only.txt emails_found.csv")
        sys.exit(1)

    domains_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('emails_found.csv')

    if not domains_file.exists():
        print(f"Error: File '{domains_file}' not found")
        sys.exit(1)

    # Read domains
    with open(domains_file, 'r', encoding='utf-8') as f:
        domains = [line.strip() for line in f if line.strip()]

    print(f"[INFO] Processing {len(domains)} domains...")
    print(f"[INFO] Output will be saved to: {output_file}")
    print()

    opener = build_opener()
    results = []

    for i, domain in enumerate(domains, 1):
        print(f"[{i}/{len(domains)}] ", end='')

        emails = find_emails_for_domain(domain, opener)

        if emails:
            for email in sorted(emails):
                results.append({
                    'domain': domain,
                    'email': email
                })
        else:
            results.append({
                'domain': domain,
                'email': 'NO EMAIL FOUND'
            })

        if PAUSE_BETWEEN_DOMAINS and i < len(domains):
            time.sleep(PAUSE_BETWEEN_DOMAINS)

    # Write results to CSV
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('domain,email\n')
        for result in results:
            f.write(f"{result['domain']},{result['email']}\n")

    # Print summary
    print()
    print("=" * 60)
    print(f"[DONE] Processed {len(domains)} domains")

    domains_with_emails = len(set(r['domain'] for r in results if r['email'] != 'NO EMAIL FOUND'))
    total_emails = len([r for r in results if r['email'] != 'NO EMAIL FOUND'])

    print(f"[DONE] Found emails for {domains_with_emails}/{len(domains)} domains")
    print(f"[DONE] Total emails found: {total_emails}")
    print(f"[DONE] Results saved to: {output_file}")
    print("=" * 60)

if __name__ == '__main__':
    main()
