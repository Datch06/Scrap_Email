#!/usr/bin/env python3
"""
Script de scraping INFINI pour trouver TOUS les sites acheteurs de backlinks

Ce script tourne en continu et:
1. Crawle tous les sites vendeurs de backlinks
2. Extrait tous les domaines .fr qui achètent des backlinks
3. Trouve leurs emails de contact
4. Stocke tout dans la base de données
5. Synchronise avec Google Sheets
6. Recommence indéfiniment jusqu'à épuisement de tous les sites

Usage:
    python3 scrape_backlinks_infinite.py

    # Ou en arrière-plan avec nohup:
    nohup python3 scrape_backlinks_infinite.py > scraping_infini.log 2>&1 &
"""

import sys
import ssl
import time
import urllib.request
import urllib.parse
import re
import random
from pathlib import Path
from html.parser import HTMLParser
from collections import deque
from datetime import datetime

# Import de nos modules
from db_helper import DBHelper

# Configuration
SITE_URLS_FILE = 'site_urls.txt'
EXPLORED_SITES_FILE = 'explored_seller_sites.txt'
PAUSE_BETWEEN_SITES = 0.1  # Secondes
PAUSE_BETWEEN_PAGES = 0.05
REQUEST_TIMEOUT = 10
MAX_PAGES_PER_SELLER_SITE = 500
MAX_DEPTH = 5
BATCH_SIZE = 100  # Traiter par batches pour sync régulière

# Patterns
SOCIAL_DOMAINS = {
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'tiktok.com', 'pinterest.com', 'google.com',
    'apple.com', 'microsoft.com', 'amazon.com', 'amazon.fr'
}

EXCLUDED_PATTERNS = {
    'google.com', 'apple.com', 'microsoft.com', 'mozilla.org',
    'amazon.com', 'amazon.es', 'amazon.fr', 'amzn.to',
    'uecdn.es', 'cloudflare.com', 'akamai.net',
}

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

IGNORE_EMAILS = {
    'example@example.com', 'email@example.com', 'contact@example.com',
    'test@test.com', 'noreply@example.com', 'vous@domaine.com',
}

COMMON_CONTACT_PAGES = ['/', '/contact', '/contact-us', '/mentions-legales', '/qui-sommes-nous']

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


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


def normalize_url(base, url):
    url = url.strip()
    if not url or url.startswith(('mailto:', 'javascript:', 'tel:', '#')):
        return None
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        url = urllib.parse.urljoin(base, url)
        parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    return parsed.scheme + '://' + parsed.netloc + parsed.path


def extract_domain(url):
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    domain = domain.replace('www.', '')
    return domain if domain else None


def is_valid_fr_domain(domain):
    if not domain or not domain.endswith('.fr'):
        return False
    for excluded in EXCLUDED_PATTERNS:
        if excluded in domain:
            return False
    for social in SOCIAL_DOMAINS:
        if social in domain:
            return False
    return True


def crawl_seller_site(start_url, opener, max_pages=MAX_PAGES_PER_SELLER_SITE):
    """Crawle un site vendeur pour extraire tous les domaines acheteurs"""
    print(f"  Crawling {start_url}...")

    visited = set()
    to_visit = deque([start_url])
    buyer_domains = set()
    base_domain = extract_domain(start_url)

    while to_visit and len(visited) < max_pages:
        url = to_visit.popleft()

        if url in visited:
            continue

        visited.add(url)
        html = fetch_page(url, opener)

        if not html:
            continue

        # Extraire les liens
        parser = LinkExtractor()
        try:
            parser.feed(html)
        except:
            pass

        for link in parser.links:
            normalized = normalize_url(url, link)
            if not normalized:
                continue

            link_domain = extract_domain(normalized)

            # Si c'est un lien interne, ajouter à la queue
            if link_domain == base_domain:
                if normalized not in visited and len(visited) < max_pages:
                    to_visit.append(normalized)
            # Si c'est un domaine .fr externe, c'est un acheteur potentiel
            elif is_valid_fr_domain(link_domain):
                buyer_domains.add(link_domain)

        time.sleep(PAUSE_BETWEEN_PAGES)

    print(f"    → {len(buyer_domains)} domaines acheteurs trouvés")
    return buyer_domains


def find_contact_email(domain, opener):
    """Trouve l'email de contact d'un domaine"""
    emails = set()

    for page in COMMON_CONTACT_PAGES[:5]:  # Limiter à 5 pages
        url = f"https://{domain}{page}"
        html = fetch_page(url, opener)

        if html:
            matches = EMAIL_PATTERN.findall(html)
            for email in matches:
                email = email.lower().strip()
                if email not in IGNORE_EMAILS and not any(ext in email for ext in ['.png', '.jpg', '.gif']):
                    emails.add(email)

        time.sleep(PAUSE_BETWEEN_PAGES)

    return '; '.join(sorted(emails)) if emails else None


def load_explored_sites():
    """Charge la liste des sites vendeurs déjà explorés"""
    if not Path(EXPLORED_SITES_FILE).exists():
        return set()
    with open(EXPLORED_SITES_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def save_explored_site(site):
    """Sauvegarde un site vendeur comme exploré"""
    with open(EXPLORED_SITES_FILE, 'a', encoding='utf-8') as f:
        f.write(site + '\n')


def load_seller_sites():
    """Charge tous les sites vendeurs"""
    if not Path(SITE_URLS_FILE).exists():
        print(f"❌ Fichier {SITE_URLS_FILE} introuvable!")
        return []

    with open(SITE_URLS_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and '.fr' in line]


def scrape_infinite():
    """Boucle de scraping infinie"""

    print("=" * 80)
    print("🚀 SCRAPING INFINI - TOUS LES ACHETEURS DE BACKLINKS")
    print("=" * 80)
    print()
    print("Configuration:")
    print(f"  - Pages par site vendeur: {MAX_PAGES_PER_SELLER_SITE}")
    print(f"  - Profondeur max: {MAX_DEPTH}")
    print(f"  - Pause entre sites: {PAUSE_BETWEEN_SITES}s")
    print(f"  - Batch size: {BATCH_SIZE}")
    print()

    opener = build_opener()
    cycle_count = 0
    total_domains_found = 0
    total_emails_found = 0

    while True:
        cycle_count += 1
        print(f"\n{'='*80}")
        print(f"CYCLE #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")

        # Charger les sites vendeurs
        all_seller_sites = load_seller_sites()
        explored_sites = load_explored_sites()

        # Sites non encore explorés
        unexplored = [s for s in all_seller_sites if s not in explored_sites]

        if not unexplored:
            print("✅ TOUS LES SITES VENDEURS ONT ÉTÉ EXPLORÉS!")
            print("🔄 Réinitialisation pour un nouveau cycle...")
            # Supprimer le fichier pour recommencer
            if Path(EXPLORED_SITES_FILE).exists():
                Path(EXPLORED_SITES_FILE).unlink()
            continue

        print(f"📊 Progression:")
        print(f"  - Total sites vendeurs: {len(all_seller_sites)}")
        print(f"  - Déjà explorés: {len(explored_sites)}")
        print(f"  - Restants: {len(unexplored)}")
        print()

        # Traiter chaque site vendeur
        with DBHelper() as db:
            for i, seller_site in enumerate(unexplored, 1):
                print(f"\n[{i}/{len(unexplored)}] Site vendeur: {seller_site}")

                try:
                    # Crawler le site vendeur
                    buyer_domains = crawl_seller_site(seller_site, opener)
                    total_domains_found += len(buyer_domains)

                    # Traiter chaque domaine acheteur
                    batch_emails = 0
                    for j, domain in enumerate(buyer_domains, 1):
                        # Vérifier si déjà en base
                        existing = db.session.query(db.Site).filter_by(domain=domain).first()
                        if existing:
                            continue

                        # Ajouter le site
                        db.add_site(domain, source_url=seller_site)

                        # Chercher l'email
                        print(f"    [{j}/{len(buyer_domains)}] {domain}... ", end='', flush=True)
                        email = find_contact_email(domain, opener)

                        if email:
                            db.update_email(domain, email, email_source='scraping')
                            print(f"✓ {email[:50]}")
                            total_emails_found += 1
                            batch_emails += 1
                        else:
                            db.update_email(domain, 'NO EMAIL FOUND', email_source='scraping')
                            print("✗ Pas d'email")

                        time.sleep(PAUSE_BETWEEN_SITES)

                    print(f"  ✅ {batch_emails} emails trouvés pour ce site vendeur")

                    # Marquer comme exploré
                    save_explored_site(seller_site)

                except Exception as e:
                    print(f"  ❌ Erreur: {e}")
                    continue

                # Statistiques intermédiaires
                stats = db.get_stats()
                print(f"\n  📈 Stats globales:")
                print(f"    - Total sites: {stats['total']}")
                print(f"    - Avec email: {stats['with_email']} ({stats['with_email']/stats['total']*100:.1f}%)")

        print(f"\n🎯 Cycle #{cycle_count} terminé!")
        print(f"  - Domaines trouvés ce cycle: {total_domains_found}")
        print(f"  - Emails trouvés ce cycle: {total_emails_found}")
        print()


if __name__ == '__main__':
    try:
        scrape_infinite()
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur (Ctrl+C)")
        print("Le scraping peut être repris à tout moment.")
        sys.exit(0)
