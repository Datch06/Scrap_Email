#!/usr/bin/env python3
"""
Script pour ajouter SIRET/SIREN et dirigeants au Google Sheet existant
Utilise Playwright comme fallback pour les sites avec JavaScript

Usage:
    python3 update_sheet_with_leaders_playwright.py
"""

import re
import ssl
import time
import urllib.request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from html.parser import HTMLParser

# Configuration
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 1'
REQUEST_TIMEOUT = 15
PAUSE_SECONDS = 2.0
USE_PLAYWRIGHT_FALLBACK = True  # Activer Playwright comme fallback

# Patterns pour SIRET/SIREN
SIRET_PATTERN = re.compile(r'\b(\d{14})\b')
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*(\d{9})\b', re.IGNORECASE)
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*(\d{14})\b', re.IGNORECASE)
ID_NUMBER_PATTERN = re.compile(r'\bnum[eé]ro\s+d[\'\"]identification\s*:?\s*(\d[\d\s]{8,13})', re.IGNORECASE)

# Pages à vérifier pour mentions légales
LEGAL_PAGES = [
    '/mentions-legales',
    '/mentions-legales.html',
    '/mentions_legales',
    '/mentions',
    '/legal',
    '/legal-notice',
    '/a-propos',
    '/about',
    '/qui-sommes-nous',
    '/contact',
]

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

class TextExtractor(HTMLParser):
    """Extract all text from HTML"""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)

def build_opener():
    """Create URL opener with SSL context"""
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    except:
        ssl_context = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))

def fetch_page(url, opener):
    """Fetch a webpage"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                return None
            data = resp.read()
            return data.decode('utf-8', errors='replace')
    except Exception as e:
        return None

def fetch_page_with_playwright(url):
    """Fetch a webpage with Playwright (executes JavaScript)"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                text = page.inner_text('body')
                return text
            finally:
                browser.close()

    except ImportError:
        print("    ⚠ Playwright non installé (pip install playwright)")
        return None
    except Exception as e:
        return None

def extract_text_from_html(html):
    """Extract text from HTML"""
    if not html:
        return ""
    try:
        parser = TextExtractor()
        parser.feed(html)
        return parser.get_text()
    except:
        return ""

def search_siret_in_text(text):
    """Search for SIRET/SIREN in text with all patterns"""
    if not text:
        return None, None

    # Chercher SIRET avec le mot-clé (plus fiable)
    match = SIRET_WORD_PATTERN.search(text)
    if match:
        return match.group(1), 'SIRET'

    # Chercher SIREN avec le mot-clé
    match = SIREN_PATTERN.search(text)
    if match:
        return match.group(1), 'SIREN'

    # Chercher "numéro d'identification"
    match = ID_NUMBER_PATTERN.search(text)
    if match:
        id_number = match.group(1).replace(' ', '')
        if len(id_number) == 9:
            return id_number, 'SIREN'
        elif len(id_number) == 14:
            return id_number, 'SIRET'

    return None, None

def find_siret_siren(domain, opener):
    """Find SIRET or SIREN in legal pages"""
    print(f"  Recherche SIRET/SIREN pour {domain}...", end=' ', flush=True)

    # Essayer d'abord avec urllib (rapide)
    for page_path in LEGAL_PAGES:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if not html:
            continue

        text = extract_text_from_html(html)
        siret_siren, number_type = search_siret_in_text(text)

        if siret_siren:
            print(f"✓ {number_type}: {siret_siren}")
            return siret_siren, number_type

        time.sleep(0.3)

    # Si pas trouvé avec urllib, essayer avec Playwright (plus lent mais gère JavaScript)
    if USE_PLAYWRIGHT_FALLBACK:
        print("↻ Essai avec Playwright...", end=' ', flush=True)

        for page_path in LEGAL_PAGES[:5]:  # Seulement les 5 premières URLs
            url = f"https://{domain}{page_path}"
            text = fetch_page_with_playwright(url)

            if text:
                siret_siren, number_type = search_siret_in_text(text)

                if siret_siren:
                    print(f"✓ {number_type}: {siret_siren} (JS)")
                    return siret_siren, number_type

            time.sleep(0.5)

    # Si toujours pas trouvé, chercher des séquences de 14 chiffres (moins fiable)
    for page_path in LEGAL_PAGES[:3]:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if not html:
            continue

        text = extract_text_from_html(html)
        matches = SIRET_PATTERN.findall(text)

        if matches:
            siret = matches[0]
            print(f"? SIRET probable: {siret}")
            return siret, 'SIRET'

    print("✗ Non trouvé")
    return None, None

def fetch_company_leaders(siret_siren, number_type, opener):
    """Fetch company leaders from société.com"""
    print(f"    Recherche dirigeants sur société.com...", end=' ', flush=True)

    if number_type == 'SIRET':
        siren = siret_siren[:9]
    else:
        siren = siret_siren

    url = f"https://www.societe.com/cgi-bin/search?champs={siren}"

    try:
        html = fetch_page(url, opener)
        if not html:
            print("✗ Erreur")
            return []

        company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
        match = company_link_pattern.search(html)

        if not match:
            print("✗ Entreprise non trouvée")
            return []

        company_path = match.group(1)
        company_url = f"https://www.societe.com{company_path}"

        time.sleep(PAUSE_SECONDS)

        html = fetch_page(company_url, opener)
        if not html:
            print("✗ Erreur page entreprise")
            return []

        leaders = []
        leader_patterns = [
            r'(?:Président|Dirigeant|Gérant|Directeur général|DG|PDG)\s*:?\s*([A-ZÀ-Ü][a-zà-ü\-]+(?: [A-ZÀ-Ü][a-zà-ü\-]+)+)',
            r'<span[^>]*dirigeant[^>]*>([^<]+)</span>',
            r'class="[^"]*dirigeant[^"]*"[^>]*>([^<]+)<',
        ]

        text = extract_text_from_html(html)

        for pattern in leader_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.strip() if isinstance(match, str) else match[0].strip()
                if len(name) > 5 and len(name) < 50:
                    leaders.append(name)

        leaders = list(dict.fromkeys(leaders))

        if leaders:
            print(f"✓ {len(leaders)} dirigeant(s)")
        else:
            print("✗ Aucun dirigeant trouvé")

        return leaders

    except Exception as e:
        print(f"✗ Erreur: {e}")
        return []

def connect_to_sheet():
    """Connect to Google Sheet"""
    print("[INFO] Connexion à Google Sheets...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(WORKSHEET_NAME)
    return worksheet

def main():
    worksheet = connect_to_sheet()

    print("[INFO] Récupération des données du sheet...")
    all_values = worksheet.get_all_values()

    if not all_values:
        print("[ERROR] Sheet vide")
        return

    header = all_values[0]
    print(f"[INFO] Colonnes actuelles: {header}")

    siret_col_idx = None
    dirigeants_col_idx = None

    if 'SIRET/SIREN' in header:
        siret_col_idx = header.index('SIRET/SIREN')
        print(f"[INFO] Colonne SIRET/SIREN trouvée à l'index {siret_col_idx}")
    else:
        siret_col_idx = len(header)
        header.append('SIRET/SIREN')
        print(f"[INFO] Ajout de la colonne SIRET/SIREN à l'index {siret_col_idx}")

    if 'Dirigeants' in header:
        dirigeants_col_idx = header.index('Dirigeants')
        print(f"[INFO] Colonne Dirigeants trouvée à l'index {dirigeants_col_idx}")
    else:
        dirigeants_col_idx = len(header)
        header.append('Dirigeants')
        print(f"[INFO] Ajout de la colonne Dirigeants à l'index {dirigeants_col_idx}")

    worksheet.update(values=[header], range_name='1:1')

    opener = build_opener()

    total_rows = len(all_values) - 1
    print(f"\n[INFO] Traitement de {total_rows} domaines\n")

    for idx, row in enumerate(all_values[1:], start=2):
        if not row:
            continue

        domain = row[0] if row else ''
        if not domain:
            continue

        print(f"[{idx-1}/{total_rows}] {domain}")

        existing_siret = row[siret_col_idx] if len(row) > siret_col_idx else ''
        if existing_siret and existing_siret not in ['', 'NON TROUVÉ']:
            print(f"  ⏭ Déjà traité (SIRET: {existing_siret})")
            continue

        siret_siren, number_type = find_siret_siren(domain, opener)

        siret_value = ''
        dirigeants_value = ''

        if siret_siren:
            siret_value = siret_siren
            time.sleep(PAUSE_SECONDS)

            leaders = fetch_company_leaders(siret_siren, number_type, opener)
            dirigeants_value = '; '.join(leaders) if leaders else 'NON TROUVÉ'
        else:
            siret_value = 'NON TROUVÉ'

        while len(row) <= max(siret_col_idx, dirigeants_col_idx):
            row.append('')

        row[siret_col_idx] = siret_value
        row[dirigeants_col_idx] = dirigeants_value

        cell_range = f'A{idx}:{chr(65 + len(row) - 1)}{idx}'
        worksheet.update(values=[row], range_name=cell_range)

        time.sleep(1)

    print("\n" + "=" * 70)
    print("[DONE] Mise à jour terminée")
    print("=" * 70)

if __name__ == '__main__':
    main()
