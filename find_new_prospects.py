#!/usr/bin/env python3
"""
Script pour trouver automatiquement de nouveaux prospects acheteurs de backlinks.

Usage:
    python3 find_new_prospects.py

Le script va:
1. Lire les sites vendeurs depuis site_urls.txt
2. Crawler ces sites pour trouver des liens externes
3. Extraire les domaines .fr
4. Chercher les emails de contact
5. Éviter les doublons avec les prospects déjà trouvés
6. Uploader 50 nouveaux prospects dans Google Sheets
"""

import sys
import ssl
import time
import urllib.request
import urllib.parse
import csv
import re
import random
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict, deque

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    print("[ERROR] Bibliothèques manquantes. Installez-les avec:")
    print("  pip install gspread oauth2client")
    sys.exit(1)

# Configuration
SITE_URLS_FILE = 'site_urls.txt'
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
EXPLORED_SITES_FILE = 'explored_seller_sites.txt'  # Fichier pour garder trace des sites explorés
MAX_NEW_PROSPECTS = None  # Illimité
MAX_PAGES_PER_SITE = 500  # Beaucoup plus de pages
MAX_DEPTH = 5  # Profondeur maximale
REQUEST_TIMEOUT = 10
PAUSE_SECONDS = 0.1  # Plus rapide
MAX_SELLER_SITES = None  # Tous les sites vendeurs

# Patterns d'exclusion
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

def normalize_url(base, url):
    url = url.strip()
    if not url or url.startswith(('mailto:', 'javascript:', 'tel:', '#')):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ('http', 'https'):
        return urllib.parse.urlunparse(parsed._replace(fragment=''))
    return urllib.parse.urljoin(base, url)

def get_domain(url):
    hostname = urllib.parse.urlparse(url).hostname or ''
    if hostname.startswith('www.'):
        hostname = hostname[4:]
    return hostname.lower()

def get_root_domain(domain):
    parts = domain.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else domain

def is_french_domain(domain):
    # Exclure les domaines .gouv.fr
    if domain.endswith('.gouv.fr'):
        return False
    return domain.endswith('.fr')

def should_exclude(domain, root_domain):
    if not domain or not is_french_domain(domain):
        return True
    if get_root_domain(domain) == get_root_domain(root_domain):
        return True
    for pattern in EXCLUDED_PATTERNS:
        if pattern in domain:
            return True
    for social in SOCIAL_DOMAINS:
        if domain == social or domain.endswith('.' + social):
            return True
    return False

def fetch_page(url, opener):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                return None
            return resp.read().decode('utf-8', errors='replace')
    except:
        return None

def extract_links(html, base_url):
    if not html:
        return set()
    try:
        extractor = LinkExtractor()
        extractor.feed(html)
        links = set()
        for link in extractor.links:
            normalized = normalize_url(base_url, link)
            if normalized:
                links.add(normalized)
        return links
    except:
        return set()

def crawl_site(start_url, opener, max_pages=MAX_PAGES_PER_SITE):
    """Crawl un site et retourne les domaines externes .fr"""
    root_domain = get_domain(start_url)
    print(f"  [CRAWL] {start_url}", flush=True)

    queue = deque([(start_url, 0)])
    visited = set()
    external_domains = set()

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > MAX_DEPTH:
            continue

        visited.add(url)
        html = fetch_page(url, opener)

        if not html:
            continue

        links = extract_links(html, url)

        for link in links:
            link_domain = get_domain(link)
            if not link_domain:
                continue

            if get_root_domain(link_domain) == get_root_domain(root_domain):
                if depth + 1 <= MAX_DEPTH and link not in visited:
                    queue.append((link, depth + 1))
            else:
                if not should_exclude(link_domain, root_domain):
                    external_domains.add(link_domain)

        time.sleep(PAUSE_SECONDS)

    print(f"    → {len(visited)} pages, {len(external_domains)} domaines .fr trouvés")
    return external_domains

def extract_emails_from_text(text):
    if not text:
        return set()
    emails = set()
    for match in EMAIL_PATTERN.findall(text):
        email = match.lower().strip()
        if email in IGNORE_EMAILS:
            continue
        # Exclure emails test/exemple
        if any(x in email for x in ['example', 'exemple', 'test@', 'placeholder', 'sentry', 'wixpress']):
            continue
        # Exclure emails .gouv.fr
        if email.endswith('.gouv.fr'):
            continue
        # Exclure fichiers images
        if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.avif')):
            continue
        emails.add(email)
    return emails

def find_contact_email(domain, opener):
    """Cherche l'email de contact d'un domaine"""
    emails = set()

    for path in COMMON_CONTACT_PAGES:
        url = f"https://{domain}{path}"
        html = fetch_page(url, opener)
        if html:
            found = extract_emails_from_text(html)
            emails.update(found)
            time.sleep(0.3)

    return list(emails)

def load_existing_prospects(sheet_id, credentials_file):
    """Charge les domaines déjà présents dans le Google Sheet"""
    try:
        scope = ['https://spreadsheets.google.com/feeds']
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)

        try:
            sheet = client.open_by_key(sheet_id)
            worksheet = sheet.sheet1
            records = worksheet.get_all_values()

            existing = set()
            for row in records[1:]:  # Skip header
                if row:
                    existing.add(row[0].lower())

            print(f"[INFO] {len(existing)} prospects déjà collectés")
            return existing, client, sheet
        except Exception as e:
            print(f"[WARN] Impossible de lire le sheet: {e}")
            print(f"[INFO] Le sheet sera initialisé avec un header")
            sheet = client.open_by_key(sheet_id)
            worksheet = sheet.sheet1
            try:
                worksheet.update('A1', [['Domain', 'Emails', 'Date Collecte']])
            except:
                pass
            return set(), client, sheet
    except Exception as e:
        print(f"[ERROR] Impossible de charger le Google Sheet: {e}")
        return set(), None, None

def upload_prospects(new_prospects, sheet, existing_count):
    """Upload les nouveaux prospects dans le Google Sheet (Feuille 1)"""
    try:
        worksheet = sheet.sheet1

        # Préparer les données
        import datetime
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        data = []
        for domain, emails in new_prospects:
            emails_str = '; '.join(emails) if emails else 'NO EMAIL FOUND'
            data.append([domain, emails_str, today])

        # Ajouter à la suite des données existantes
        start_row = existing_count + 2  # +1 pour header, +1 pour next row
        worksheet.update(f'A{start_row}', data)

        print(f"[SUCCESS] {len(data)} nouveaux prospects uploadés!")
        return True
    except Exception as e:
        print(f"[ERROR] Upload échoué: {e}")
        return False

def upload_prospects_no_email(domains_without_email, sheet):
    """Upload les domaines sans email dans Feuille 2"""
    try:
        # Vérifier si Feuille 2 existe, sinon la créer
        try:
            worksheet = sheet.worksheet('Feuille 2')
        except:
            worksheet = sheet.add_worksheet(title='Feuille 2', rows=1000, cols=3)
            worksheet.update('A1', [['Domain', 'Status', 'Date Collecte']])

        # Charger les domaines existants pour éviter les doublons
        existing_records = worksheet.get_all_values()
        existing_domains = set()
        for row in existing_records[1:]:  # Skip header
            if row:
                existing_domains.add(row[0].lower())

        # Préparer les données (seulement les nouveaux)
        import datetime
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        data = []
        for domain in domains_without_email:
            if domain.lower() not in existing_domains:
                data.append([domain, 'NO EMAIL FOUND', today])

        if data:
            # Ajouter à la suite des données existantes
            start_row = len(existing_records) + 1
            worksheet.update(f'A{start_row}', data)
            print(f"[SUCCESS] {len(data)} domaines sans email uploadés dans Feuille 2!")
        else:
            print(f"[INFO] Aucun nouveau domaine sans email à ajouter")

        return True
    except Exception as e:
        print(f"[ERROR] Upload Feuille 2 échoué: {e}")
        return False

def main():
    print("=" * 70)
    print("RECHERCHE AUTOMATIQUE DE NOUVEAUX PROSPECTS")
    print("=" * 70)
    print()

    # Vérifier les fichiers
    if not Path(SITE_URLS_FILE).exists():
        print(f"[ERROR] {SITE_URLS_FILE} introuvable")
        sys.exit(1)

    if not Path(CREDENTIALS_FILE).exists():
        print(f"[ERROR] {CREDENTIALS_FILE} introuvable")
        print("Créez vos credentials Google Cloud (voir GSHEET_SETUP.md)")
        sys.exit(1)

    # Charger les prospects existants
    print("[1/5] Chargement des prospects existants...")
    existing_domains, client, sheet = load_existing_prospects(SHEET_ID, CREDENTIALS_FILE)

    if client is None:
        sys.exit(1)

    # Charger les sites déjà explorés
    explored_sites = set()
    if Path(EXPLORED_SITES_FILE).exists():
        with open(EXPLORED_SITES_FILE, 'r', encoding='utf-8') as f:
            explored_sites = set(line.strip() for line in f if line.strip())
        print(f"[INFO] {len(explored_sites)} sites vendeurs déjà explorés")

    # Lire les sites vendeurs
    print(f"\n[2/5] Lecture des sites vendeurs depuis {SITE_URLS_FILE}...")
    with open(SITE_URLS_FILE, 'r', encoding='utf-8') as f:
        all_seller_sites = [line.strip() for line in f if line.strip() and '.fr' in line]

    # Filtrer les sites non explorés
    unexplored_sites = [site for site in all_seller_sites if site not in explored_sites]

    if not unexplored_sites:
        print("[WARN] Tous les sites ont été explorés! Réinitialisation...")
        unexplored_sites = all_seller_sites
        explored_sites = set()

    # Sélectionner aléatoirement (tous si MAX_SELLER_SITES = None)
    if MAX_SELLER_SITES is None:
        num_to_select = len(unexplored_sites)
        seller_sites = unexplored_sites
    else:
        num_to_select = min(MAX_SELLER_SITES, len(unexplored_sites))
        seller_sites = random.sample(unexplored_sites, num_to_select)

    print(f"  → {len(all_seller_sites)} sites disponibles")
    print(f"  → {len(unexplored_sites)} sites non encore explorés")
    print(f"  → {num_to_select} sites sélectionnés aléatoirement")

    # Crawler les sites
    print(f"\n[3/5] Crawl des sites vendeurs...")
    opener = build_opener()
    all_buyer_domains = set()

    for i, site in enumerate(seller_sites, 1):
        print(f"\n[{i}/{len(seller_sites)}] Traitement de {site}")
        try:
            domains = crawl_site(site, opener, max_pages=MAX_PAGES_PER_SITE)
            all_buyer_domains.update(domains)
            print(f"  Total unique: {len(all_buyer_domains)} domaines")

            # Marquer ce site comme exploré
            explored_sites.add(site)
        except Exception as e:
            print(f"  [ERROR] {e}")

        # Continuer jusqu'à avoir traité tous les sites (pas de limite si MAX_NEW_PROSPECTS = None)
        if MAX_NEW_PROSPECTS is not None and len(all_buyer_domains) >= MAX_NEW_PROSPECTS * 10:
            break

    # Sauvegarder les sites explorés
    with open(EXPLORED_SITES_FILE, 'w', encoding='utf-8') as f:
        for site in sorted(explored_sites):
            f.write(site + '\n')
    print(f"\n[INFO] {len(explored_sites)} sites explorés sauvegardés dans {EXPLORED_SITES_FILE}")

    # Filtrer les nouveaux domaines
    new_domains = [d for d in all_buyer_domains if d not in existing_domains]
    print(f"\n[4/5] {len(new_domains)} nouveaux domaines trouvés (après dédoublonnage)")

    # Extraire les emails - continuer jusqu'à avoir tous les domaines avec emails
    if MAX_NEW_PROSPECTS is None:
        print(f"\n[5/5] Recherche d'emails pour TOUS les domaines (mode illimité)...")
    else:
        print(f"\n[5/5] Recherche de {MAX_NEW_PROSPECTS} domaines avec emails...")

    new_prospects = []
    domains_without_email = []
    domains_checked = 0

    for domain in new_domains:
        if MAX_NEW_PROSPECTS is not None and len(new_prospects) >= MAX_NEW_PROSPECTS:
            break

        domains_checked += 1
        if MAX_NEW_PROSPECTS is None:
            print(f"  [{len(new_prospects)}] {domain}...", end=' ', flush=True)
        else:
            print(f"  [{len(new_prospects)}/{MAX_NEW_PROSPECTS}] {domain}...", end=' ', flush=True)
        emails = find_contact_email(domain, opener)

        if emails:  # Seulement garder si des emails sont trouvés
            new_prospects.append((domain, emails))
            print(f"✓ {len(emails)} email(s)")
        else:
            domains_without_email.append(domain)
            print(f"✗ pas d'email")

    # Upload
    print()
    if new_prospects:
        print(f"[UPLOAD] Upload de {len(new_prospects)} prospects avec email...")
        upload_prospects(new_prospects, sheet, len(existing_domains))

    if domains_without_email:
        print(f"[UPLOAD] Upload de {len(domains_without_email)} domaines sans email dans Feuille 2...")
        upload_prospects_no_email(domains_without_email, sheet)

    # Afficher le lien
    if new_prospects or domains_without_email:
        print(f"\n✅ TERMINÉ!")
        print(f"📊 Google Sheet: https://docs.google.com/spreadsheets/d/{sheet.id}")
        print(f"📈 Total prospects avec email: {len(existing_domains) + len(new_prospects)}")
        print(f"🆕 Nouveaux prospects avec email: {len(new_prospects)}")
        print(f"📝 Domaines sans email (Feuille 2): {len(domains_without_email)}")
    else:
        print("[WARN] Aucun nouveau prospect trouvé")

    print()
    print("=" * 70)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[STOP] Arrêt par l'utilisateur")
        sys.exit(0)
