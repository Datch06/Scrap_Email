#!/usr/bin/env python3
"""
Version améliorée de extract_emails.py qui utilise la base de données

Usage:
    python3 extract_emails_db.py --limit 50
"""

import re
import sys
import time
import urllib.request
import ssl
import argparse
from db_helper import DBHelper

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

    return all_emails


def main():
    parser = argparse.ArgumentParser(description='Extract emails and store in database')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of sites to process (default: None = illimité)')
    parser.add_argument('--max-pages', type=int, default=10,
                        help='Maximum pages to check per site (default: 10)')
    args = parser.parse_args()

    print("=" * 70)
    print("EXTRACTION D'EMAILS AVEC BASE DE DONNÉES")
    print("=" * 70)

    with DBHelper() as db:
        # Créer un job pour tracer cette opération
        job = db.create_job('email', total_sites=args.limit)
        db.start_job(job.id)

        # Récupérer les sites sans email
        sites = db.get_sites_without_email(limit=args.limit)

        if not sites:
            print("\n✓ Aucun site à traiter (tous les sites ont déjà un email)")
            db.complete_job(job.id)
            return

        print(f"\n[INFO] {len(sites)} sites à traiter")
        print(f"[INFO] Recherche sur {args.max_pages} pages par site\n")

        opener = build_opener()
        processed = 0
        success = 0
        errors = 0

        for i, site in enumerate(sites, 1):
            domain = site.domain

            try:
                print(f"[{i}/{len(sites)}] {domain}...", end=' ', flush=True)

                emails = find_emails_for_domain(domain, opener, args.max_pages)

                if emails:
                    emails_str = '; '.join(sorted(emails))
                    db.update_email(domain, emails_str)
                    print(f"✓ {len(emails)} email(s) trouvé(s)")
                    success += 1
                else:
                    db.update_email(domain, 'NO EMAIL FOUND')
                    print("✗ Aucun email trouvé")

                processed += 1

            except Exception as e:
                print(f"✗ Erreur: {e}")
                db.set_error(domain, str(e))
                errors += 1
                processed += 1

            # Mettre à jour la progression du job
            db.update_job_progress(job.id, processed=processed, success=success, error=errors)

            # Pause entre domaines
            if i < len(sites) and PAUSE_BETWEEN_DOMAINS:
                time.sleep(PAUSE_BETWEEN_DOMAINS)

        # Terminer le job
        db.complete_job(job.id)

        # Statistiques finales
        print("\n" + "=" * 70)
        print("RÉSUMÉ")
        print("=" * 70)
        print(f"Sites traités : {processed}/{len(sites)}")
        print(f"Emails trouvés : {success}")
        print(f"Emails non trouvés : {processed - success - errors}")
        print(f"Erreurs : {errors}")

        # Statistiques globales
        stats = db.get_stats()
        print(f"\nStatistiques globales de la base :")
        print(f"  Total sites : {stats['total']}")
        print(f"  Sites avec email : {stats['with_email']} ({stats['with_email']/stats['total']*100:.1f}%)")
        print("=" * 70)
        print("\n✓ Traitement terminé !")
        print("Consultez les résultats sur : http://localhost:5000/sites")


if __name__ == '__main__':
    main()
