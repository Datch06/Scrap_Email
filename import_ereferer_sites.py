#!/usr/bin/env python3
"""
Import DIRECT des sites Ereferer dans la base avec recherche Email + SIRET

Ces sites sont les ACHETEURS de backlinks trouvés sur Ereferer.
On les importe directement et on recherche leurs infos.

Usage:
    python3 import_ereferer_sites.py
"""

import sys
import ssl
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime

from db_helper import DBHelper
from database import Site

# ============================================================================
# CONFIGURATION
# ============================================================================

SITE_URLS_FILE = 'site_urls.txt'
PAUSE_BETWEEN_SITES = 0.2  # Pause entre chaque site
PAUSE_BETWEEN_PAGES = 0.1
REQUEST_TIMEOUT = 10
STATS_INTERVAL = 50  # Stats tous les 50 sites

# ============================================================================
# PATTERNS
# ============================================================================

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
SIRET_PATTERN = re.compile(r'\b(\d{14})\b')
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*(\d{9})\b', re.IGNORECASE)
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*(\d{14})\b', re.IGNORECASE)

IGNORE_EMAILS = {
    'example@example.com', 'email@example.com', 'contact@example.com',
    'test@test.com', 'noreply@example.com', 'vous@domaine.com',
}

COMMON_CONTACT_PAGES = ['/', '/contact', '/contact-us', '/mentions-legales', '/qui-sommes-nous']
LEGAL_PAGES = [
    '/mentions-legales',
    '/mentions-legales.html',
    '/mentions_legales',
    '/mentions',
    '/legal',
    '/a-propos',
]

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

# ============================================================================
# CLASSES HELPER
# ============================================================================

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)

# ============================================================================
# FONCTIONS
# ============================================================================

def build_opener():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    except:
        ssl_context = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))


def fetch_page(url, opener):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode('utf-8', errors='ignore')
    except:
        return None


def extract_text_from_html(html):
    if not html:
        return ""
    try:
        parser = TextExtractor()
        parser.feed(html)
        return parser.get_text()
    except:
        return ""


def clean_domain(url):
    """Nettoie une URL pour extraire le domaine"""
    # Supprimer le protocole
    domain = url.replace('https://', '').replace('http://', '')
    # Supprimer www.
    domain = domain.replace('www.', '')
    # Prendre uniquement le domaine (avant le premier /)
    domain = domain.split('/')[0]
    # Supprimer les espaces
    domain = domain.strip()
    return domain if domain else None


def find_emails(domain, opener):
    """Trouve les emails d'un domaine"""
    emails = set()

    for page in COMMON_CONTACT_PAGES[:5]:
        url = f"https://{domain}{page}"
        html = fetch_page(url, opener)

        if html:
            matches = EMAIL_PATTERN.findall(html)
            for email in matches:
                email = email.lower().strip()
                if email not in IGNORE_EMAILS and not any(ext in email for ext in ['.png', '.jpg', '.gif', '.webp', '.svg']):
                    if 'example' not in email and 'test' not in email:
                        emails.add(email)

        time.sleep(PAUSE_BETWEEN_PAGES)

    return '; '.join(sorted(emails)) if emails else None


def find_siret_siren(domain, opener):
    """Trouve SIRET/SIREN dans les mentions légales"""

    for page in LEGAL_PAGES:
        url = f"https://{domain}{page}"
        html = fetch_page(url, opener)

        if html:
            text = extract_text_from_html(html)

            # Chercher SIRET explicite
            match = SIRET_WORD_PATTERN.search(text)
            if match:
                siret = match.group(1).replace(' ', '')
                if len(siret) == 14:
                    return siret, 'SIRET'

            # Chercher SIREN explicite
            match = SIREN_PATTERN.search(text)
            if match:
                siren = match.group(1).replace(' ', '')
                if len(siren) == 9:
                    return siren, 'SIREN'

            # Chercher pattern générique 14 chiffres
            matches = SIRET_PATTERN.findall(text)
            for siret in matches:
                if siret.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')):
                    return siret, 'SIRET'

        time.sleep(PAUSE_BETWEEN_PAGES)

    return None, None


# ============================================================================
# IMPORT PRINCIPAL
# ============================================================================

def import_ereferer_sites():
    """
    Importe les sites Ereferer avec recherche Email + SIRET en temps réel
    """

    print("=" * 80)
    print("🚀 IMPORT SITES EREFERER + RECHERCHE EMAIL/SIRET")
    print("=" * 80)
    print()
    print("📂 Source: site_urls.txt (sites acheteurs de backlinks sur Ereferer)")
    print("⚡ Recherche simultanée: Email + SIRET/SIREN")
    print("💾 Upload instantané dans l'admin")
    print()

    # Charger les URLs
    if not Path(SITE_URLS_FILE).exists():
        print(f"❌ Fichier {SITE_URLS_FILE} introuvable!")
        return

    with open(SITE_URLS_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"📊 Total URLs à traiter: {len(urls)}")
    print()

    opener = build_opener()

    # Compteurs
    processed = 0
    added = 0
    skipped = 0
    emails_found = 0
    sirets_found = 0

    with DBHelper() as db:
        for i, url in enumerate(urls, 1):
            # Nettoyer le domaine
            domain = clean_domain(url)

            if not domain:
                continue

            # Vérifier si déjà en base
            existing = db.session.query(Site).filter_by(domain=domain).first()
            if existing:
                skipped += 1
                if i % 100 == 0:
                    print(f"  [{i}/{len(urls)}] {domain}: ⏭ Existe déjà (total skipped: {skipped})")
                continue

            # Ajouter le site
            db.add_site(domain, source_url='Ereferer')
            added += 1
            processed += 1

            print(f"  [{i}/{len(urls)}] {domain} ", end='', flush=True)

            # Rechercher EMAIL
            email = find_emails(domain, opener)
            if email:
                db.update_email(domain, email, email_source='scraping')
                emails_found += 1
                print(f"✉️ {email[:30]}... ", end='', flush=True)
            else:
                db.update_email(domain, 'NO EMAIL FOUND', email_source='scraping')
                print("✉️ ✗ ", end='', flush=True)

            # Rechercher SIRET/SIREN
            siret, siret_type = find_siret_siren(domain, opener)
            if siret:
                db.update_siret(domain, siret, siret_type)
                sirets_found += 1
                print(f"🏢 {siret_type}:{siret[:9]}... ", end='', flush=True)
            else:
                print("🏢 ✗ ", end='', flush=True)

            print("✅")

            # Commit pour visibilité immédiate
            db.session.commit()

            time.sleep(PAUSE_BETWEEN_SITES)

            # Stats intermédiaires
            if processed % STATS_INTERVAL == 0:
                stats = db.get_stats()
                print(f"\n{'🔥'*40}")
                print(f"📈 STATISTIQUES (Progression: {i}/{len(urls)})")
                print(f"{'🔥'*40}")
                print(f"   Traités: {processed} | Skipped: {skipped} | Ajoutés: {added}")
                print(f"   Emails: {emails_found} ({emails_found/processed*100:.1f}%)")
                print(f"   SIRET: {sirets_found} ({sirets_found/processed*100:.1f}%)")
                print(f"\n   BASE TOTALE:")
                print(f"   Sites: {stats['total']}")
                print(f"   Emails: {stats['with_email']} ({stats['with_email']/stats['total']*100:.1f}%)")
                print(f"   SIRET: {stats['with_siret']} ({stats['with_siret']/stats['total']*100:.1f}%)")
                print(f"{'🔥'*40}\n")

    # Stats finales
    print(f"\n{'='*80}")
    print(f"✅ IMPORT TERMINÉ!")
    print(f"{'='*80}")
    print(f"   URLs traitées: {len(urls)}")
    print(f"   Sites ajoutés: {added}")
    print(f"   Sites skippés (déjà en base): {skipped}")
    print(f"   Emails trouvés: {emails_found}")
    print(f"   SIRET trouvés: {sirets_found}")
    print(f"{'='*80}")
    print()
    print(f"🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")
    print()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        import_ereferer_sites()
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur (Ctrl+C)")
        print("✅ Tous les sites traités jusqu'ici sont en base!")
        sys.exit(0)
