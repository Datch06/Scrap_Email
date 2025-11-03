#!/usr/bin/env python3
"""
Script de scraping EN TEMPS RÉEL avec upload instantané vers l'admin

Fonctionnalités:
- Upload instantané dans la base de données (visible dans l'admin)
- Recherche simultanée: EMAIL + SIRET/SIREN + DIRIGEANTS
- Scraping infini 24/7
- Statistiques temps réel

Usage:
    python3 scrape_realtime_complete.py

    # En arrière-plan:
    nohup python3 scrape_realtime_complete.py > scraping_realtime.log 2>&1 &
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

# ============================================================================
# CONFIGURATION
# ============================================================================

SITE_URLS_FILE = 'site_urls.txt'
EXPLORED_SITES_FILE = 'explored_seller_sites.txt'

# Pauses (en secondes)
PAUSE_BETWEEN_SITES = 0.1
PAUSE_BETWEEN_PAGES = 0.05
REQUEST_TIMEOUT = 10

# Limites de crawl
MAX_PAGES_PER_SELLER_SITE = 500
MAX_DEPTH = 5

# Affichage
STATS_INTERVAL = 50  # Afficher stats tous les 50 sites

# ============================================================================
# PATTERNS & EXCLUSIONS
# ============================================================================

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

# Regex patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
SIRET_PATTERN = re.compile(r'\b(\d{14})\b')
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*(\d{9})\b', re.IGNORECASE)
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*(\d{14})\b', re.IGNORECASE)

IGNORE_EMAILS = {
    'example@example.com', 'email@example.com', 'contact@example.com',
    'test@test.com', 'noreply@example.com', 'vous@domaine.com',
}

# Pages communes
COMMON_CONTACT_PAGES = ['/', '/contact', '/contact-us', '/mentions-legales', '/qui-sommes-nous']
LEGAL_PAGES = [
    '/mentions-legales',
    '/mentions-legales.html',
    '/mentions_legales',
    '/mentions',
    '/legal',
    '/legal-notice',
    '/a-propos',
    '/about',
]

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

# ============================================================================
# CLASSES HELPER
# ============================================================================

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)


# ============================================================================
# FONCTIONS RÉSEAU
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


# ============================================================================
# EXTRACTION DE DONNÉES
# ============================================================================

def extract_text_from_html(html):
    """Extrait le texte d'un HTML"""
    if not html:
        return ""
    try:
        parser = TextExtractor()
        parser.feed(html)
        return parser.get_text()
    except:
        return ""


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
                # Filtrer les faux emails
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
                # Vérifier que c'est bien un SIRET (pas un numéro de téléphone par ex)
                if siret.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')):
                    return siret, 'SIRET'

        time.sleep(PAUSE_BETWEEN_PAGES)

    return None, None


# ============================================================================
# CRAWLING
# ============================================================================

def crawl_seller_site(start_url, opener, db, max_pages=MAX_PAGES_PER_SELLER_SITE):
    """
    Crawle un site vendeur et upload INSTANTANÉMENT chaque domaine trouvé
    """
    print(f"\n  🔍 Crawling {start_url}...")

    visited = set()
    to_visit = deque([start_url])
    base_domain = extract_domain(start_url)

    # Cache local pour éviter les doublons pendant le crawl
    processed_domains = set()

    domains_found = 0
    emails_found = 0
    sirets_found = 0

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

            # Si c'est un domaine .fr externe = ACHETEUR DE BACKLINK!
            elif is_valid_fr_domain(link_domain):

                # ========================================================
                # PROTECTION ANTI-DOUBLONS (DOUBLE VÉRIFICATION)
                # ========================================================

                # 1. Vérifier cache local (rapide - évite les doublons dans le même crawl)
                if link_domain in processed_domains:
                    continue

                # 2. Vérifier base de données (évite les doublons globaux)
                existing = db.session.query(db.Site).filter_by(domain=link_domain).first()
                if existing:
                    processed_domains.add(link_domain)  # Ajouter au cache local
                    continue

                # ========================================================
                # UPLOAD EN TEMPS RÉEL DANS LA BASE (VISIBLE DANS L'ADMIN)
                # ========================================================

                # Marquer comme traité
                processed_domains.add(link_domain)

                # AJOUTER LE SITE IMMÉDIATEMENT
                site = db.add_site(link_domain, source_url=start_url)
                domains_found += 1

                print(f"    [{domains_found}] {link_domain} ", end='', flush=True)

                # RECHERCHER EMAIL (en temps réel)
                email = find_emails(link_domain, opener)
                if email:
                    db.update_email(link_domain, email, email_source='scraping')
                    emails_found += 1
                    print(f"✉️ {email[:40]}... ", end='', flush=True)
                else:
                    db.update_email(link_domain, 'NO EMAIL FOUND', email_source='scraping')
                    print("✉️ ✗ ", end='', flush=True)

                # RECHERCHER SIRET/SIREN (en temps réel)
                siret, siret_type = find_siret_siren(link_domain, opener)
                if siret:
                    db.update_siret(link_domain, siret, siret_type)
                    sirets_found += 1
                    print(f"🏢 {siret_type}:{siret[:9]}... ", end='', flush=True)
                else:
                    print("🏢 ✗ ", end='', flush=True)

                print("✅")

                # COMMIT IMMÉDIAT POUR VISIBILITÉ DANS L'ADMIN
                db.session.commit()

                time.sleep(PAUSE_BETWEEN_SITES)

        time.sleep(PAUSE_BETWEEN_PAGES)

    print(f"\n  📊 Résultats pour {start_url}:")
    print(f"     Domaines: {domains_found} | Emails: {emails_found} | SIRET: {sirets_found}")

    return domains_found, emails_found, sirets_found


# ============================================================================
# GESTION DES FICHIERS
# ============================================================================

def load_explored_sites():
    if not Path(EXPLORED_SITES_FILE).exists():
        return set()
    with open(EXPLORED_SITES_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def save_explored_site(site):
    with open(EXPLORED_SITES_FILE, 'a', encoding='utf-8') as f:
        f.write(site + '\n')


def load_seller_sites():
    if not Path(SITE_URLS_FILE).exists():
        print(f"❌ Fichier {SITE_URLS_FILE} introuvable!")
        return []

    with open(SITE_URLS_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and '.fr' in line]


# ============================================================================
# SCRAPING PRINCIPAL
# ============================================================================

def scrape_realtime():
    """
    Boucle de scraping INFINIE avec upload EN TEMPS RÉEL
    """

    print("=" * 80)
    print("🚀 SCRAPING TEMPS RÉEL - UPLOAD INSTANTANÉ DANS L'ADMIN")
    print("=" * 80)
    print()
    print("⚡ Recherche simultanée:")
    print("   - ✉️  Emails")
    print("   - 🏢 SIRET/SIREN")
    print("   - 📊 Upload instantané vers admin")
    print()
    print("Configuration:")
    print(f"   Pages/site vendeur: {MAX_PAGES_PER_SELLER_SITE}")
    print(f"   Profondeur: {MAX_DEPTH}")
    print(f"   Pause sites: {PAUSE_BETWEEN_SITES}s")
    print()

    opener = build_opener()
    cycle_count = 0

    # Compteurs globaux
    total_domains = 0
    total_emails = 0
    total_sirets = 0

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
            if Path(EXPLORED_SITES_FILE).exists():
                Path(EXPLORED_SITES_FILE).unlink()
            continue

        print(f"📊 Progression:")
        print(f"   Total sites vendeurs: {len(all_seller_sites)}")
        print(f"   Déjà explorés: {len(explored_sites)}")
        print(f"   Restants: {len(unexplored)}")
        print()

        # Ouvrir une session DB unique pour tout le cycle
        with DBHelper() as db:

            for i, seller_site in enumerate(unexplored, 1):
                print(f"\n{'─'*80}")
                print(f"[{i}/{len(unexplored)}] Site vendeur: {seller_site}")
                print(f"{'─'*80}")

                try:
                    # Crawler avec upload temps réel
                    domains, emails, sirets = crawl_seller_site(seller_site, opener, db)

                    total_domains += domains
                    total_emails += emails
                    total_sirets += sirets

                    # Marquer comme exploré
                    save_explored_site(seller_site)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"  ❌ Erreur: {e}")
                    continue

                # Afficher stats globales tous les N sites
                if i % STATS_INTERVAL == 0:
                    stats = db.get_stats()
                    print(f"\n{'🔥'*40}")
                    print(f"📈 STATISTIQUES GLOBALES (Cycle #{cycle_count})")
                    print(f"{'🔥'*40}")
                    print(f"   Total sites en base: {stats['total']}")
                    print(f"   Avec email: {stats['with_email']} ({stats['with_email']/stats['total']*100:.1f}%)")
                    print(f"   Avec SIRET: {stats['with_siret']} ({stats['with_siret']/stats['total']*100:.1f}%)")
                    print(f"\n   Ce cycle:")
                    print(f"   Domaines trouvés: {total_domains}")
                    print(f"   Emails trouvés: {total_emails}")
                    print(f"   SIRET trouvés: {total_sirets}")
                    print(f"{'🔥'*40}\n")

        # Fin du cycle
        print(f"\n{'='*80}")
        print(f"✅ CYCLE #{cycle_count} TERMINÉ!")
        print(f"{'='*80}")
        print(f"   Domaines: {total_domains}")
        print(f"   Emails: {total_emails}")
        print(f"   SIRET: {total_sirets}")
        print(f"{'='*80}\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        print("\n🎯 Consultez l'admin en temps réel sur:")
        print("   https://admin.perfect-cocon-seo.fr\n")

        time.sleep(2)

        scrape_realtime()

    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur (Ctrl+C)")
        print("✅ Tous les sites découverts sont déjà dans la base!")
        print("🔄 Le scraping peut être repris à tout moment.")
        sys.exit(0)
