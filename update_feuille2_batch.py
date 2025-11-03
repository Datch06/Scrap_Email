#!/usr/bin/env python3
"""
Script pour ajouter SIRET/SIREN et dirigeants dans Feuille 2 avec Playwright fallback
Version BATCH: Enregistre d'abord dans un fichier JSON, puis upload en une fois

Usage:
    python3 update_feuille2_batch.py
"""

import re
import ssl
import time
import json
import urllib.request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

# Configuration
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 2'
REQUEST_TIMEOUT = 15
PAUSE_SECONDS = 2.0
USE_PLAYWRIGHT_FALLBACK = True
RESULTS_FILE = 'feuille2_results.json'  # Fichier pour stocker les résultats

# Patterns pour SIRET/SIREN (avec gestion des espaces)
SIRET_PATTERN = re.compile(r'\b(\d{14})\b')
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*([\d\s]{9,15})', re.IGNORECASE)
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*([\d\s]{14,20})', re.IGNORECASE)
ID_NUMBER_PATTERN = re.compile(r"\bnum[eé]ro\s+d['']identification\s*:?\s*(\d[\d\s]{8,20})", re.IGNORECASE)
RCS_PATTERN = re.compile(r"\bsous le num[eé]ro\s+[A-Z]?\s*([\d\s]{9,20})", re.IGNORECASE)

LEGAL_PAGES = [
    '/mentions-legales',
    '/mentions-legales.html',
    '/mentions_legales',
    '/mentions',
    '/legal',
    '/legal-notice',
    '/cgv',
    '/cgu',
    '/conditions-generales-vente',
    '/conditions-generales-utilisation',
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
    """Fetch a webpage using Playwright (for JS-rendered content)"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            text = page.inner_text('body')
            browser.close()
            return text
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

def search_siret_in_text(text, fuzzy=False):
    """Search for SIRET/SIREN in text"""
    match = SIRET_WORD_PATTERN.search(text)
    if match:
        siret = match.group(1).replace(' ', '').replace('\xa0', '')
        if len(siret) == 14 and siret.isdigit():
            return siret, 'SIRET'

    match = SIREN_PATTERN.search(text)
    if match:
        siren = match.group(1).replace(' ', '').replace('\xa0', '')
        if len(siren) == 9 and siren.isdigit():
            return siren, 'SIREN'

    match = ID_NUMBER_PATTERN.search(text)
    if match:
        id_number = match.group(1).replace(' ', '').replace('\xa0', '')
        if len(id_number) == 9 and id_number.isdigit():
            return id_number, 'SIREN'
        elif len(id_number) == 14 and id_number.isdigit():
            return id_number, 'SIRET'

    match = RCS_PATTERN.search(text)
    if match:
        id_number = match.group(1).replace(' ', '').replace('\xa0', '')
        if len(id_number) == 9 and id_number.isdigit():
            return id_number, 'SIREN'
        elif len(id_number) == 14 and id_number.isdigit():
            return id_number, 'SIRET'

    # Mode fuzzy : chercher n'importe quel numéro à 9 ou 14 chiffres
    if fuzzy:
        # Chercher des séquences de chiffres avec espaces potentiels
        fuzzy_pattern = re.compile(r'\b([\d\s]{9,20})\b')
        matches = fuzzy_pattern.findall(text)

        for match in matches:
            cleaned = match.replace(' ', '').replace('\xa0', '')
            if len(cleaned) == 14 and cleaned.isdigit():
                return cleaned, 'SIRET_FUZZY'
            elif len(cleaned) == 9 and cleaned.isdigit():
                return cleaned, 'SIREN_FUZZY'

    return None, None

def find_siret_siren(domain, opener):
    """Find SIRET or SIREN in legal pages"""
    print(f"  Recherche SIRET/SIREN pour {domain}...", end=' ', flush=True)

    # Phase 1: urllib (rapide)
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

    # Phase 2: Playwright fallback
    if USE_PLAYWRIGHT_FALLBACK:
        print("↻ Essai avec Playwright...", end=' ', flush=True)
        for page_path in LEGAL_PAGES[:5]:
            url = f"https://{domain}{page_path}"
            text = fetch_page_with_playwright(url)

            if text:
                siret_siren, number_type = search_siret_in_text(text)
                if siret_siren:
                    print(f"✓ {number_type}: {siret_siren} (JS)")
                    return siret_siren, number_type

    # Phase 3: séquences de 14 chiffres
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

    # Phase 4: Mode fuzzy - chercher n'importe quel numéro à 9 ou 14 chiffres
    print("🔍 Mode fuzzy...", end=' ', flush=True)
    for page_path in LEGAL_PAGES[:3]:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if not html:
            continue

        text = extract_text_from_html(html)
        siret_siren, number_type = search_siret_in_text(text, fuzzy=True)

        if siret_siren:
            print(f"? {number_type}: {siret_siren}")
            return siret_siren, number_type

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

def load_existing_results():
    """Charger les résultats existants depuis le fichier JSON"""
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_results(results):
    """Sauvegarder les résultats dans le fichier JSON"""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

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
    # Charger les résultats existants
    results = load_existing_results()
    print(f"[INFO] {len(results)} résultats déjà enregistrés")

    # Connexion au sheet pour récupérer les domaines
    worksheet = connect_to_sheet()

    print("[INFO] Récupération des données de Feuille 2...")
    all_values = worksheet.get_all_values()

    if not all_values:
        print("[ERROR] Sheet vide")
        return

    header = all_values[0]
    print(f"[INFO] Colonnes actuelles: {header}")

    # Vérifier colonnes
    siret_col_idx = header.index('SIRET/SIREN') if 'SIRET/SIREN' in header else len(header)
    dirigeants_col_idx = header.index('Dirigeants') if 'Dirigeants' in header else len(header) + 1

    # Phase 1: COLLECTE DES DONNÉES
    print("\n" + "=" * 70)
    print("PHASE 1: COLLECTE DES DONNÉES")
    print("=" * 70 + "\n")

    opener = build_opener()
    total_rows = len(all_values) - 1
    print(f"[INFO] Traitement de {total_rows} domaines\n")

    for idx, row in enumerate(all_values[1:], start=2):
        if not row:
            continue

        domain = row[0] if row else ''
        if not domain:
            continue

        print(f"[{idx-1}/{total_rows}] {domain}")

        # Vérifier si déjà dans les résultats
        if domain in results:
            print(f"  ⏭ Déjà traité (SIRET: {results[domain]['siret']})")
            continue

        # Chercher SIRET/SIREN
        siret_siren, number_type = find_siret_siren(domain, opener)

        result = {
            'siret': '',
            'dirigeants': '',
            'row_index': idx
        }

        if siret_siren:
            result['siret'] = siret_siren
            time.sleep(PAUSE_SECONDS)

            # Chercher les dirigeants
            leaders = fetch_company_leaders(siret_siren, number_type, opener)
            result['dirigeants'] = '; '.join(leaders) if leaders else 'NON TROUVÉ'
        else:
            result['siret'] = 'NON TROUVÉ'

        # Sauvegarder immédiatement
        results[domain] = result
        save_results(results)

        time.sleep(1)

    print("\n" + "=" * 70)
    print("PHASE 1 TERMINÉE - Tous les résultats sont sauvegardés")
    print("=" * 70 + "\n")

    # Phase 2: UPLOAD VERS GOOGLE SHEETS
    print("\n" + "=" * 70)
    print("PHASE 2: UPLOAD VERS GOOGLE SHEETS")
    print("=" * 70 + "\n")

    # Reconnecter au sheet
    worksheet = connect_to_sheet()
    all_values = worksheet.get_all_values()
    header = all_values[0]

    # Vérifier/ajouter colonnes
    if 'SIRET/SIREN' not in header:
        header.append('SIRET/SIREN')
        siret_col_idx = len(header) - 1
    else:
        siret_col_idx = header.index('SIRET/SIREN')

    if 'Dirigeants' not in header:
        header.append('Dirigeants')
        dirigeants_col_idx = len(header) - 1
    else:
        dirigeants_col_idx = header.index('Dirigeants')

    # Mettre à jour l'en-tête
    worksheet.update(values=[header], range_name='1:1')
    print(f"[INFO] En-têtes mis à jour")

    # Préparer toutes les mises à jour
    updates = []
    for domain, result in results.items():
        row_idx = result['row_index']
        row = all_values[row_idx - 1] if row_idx - 1 < len(all_values) else []

        # Étendre la ligne si nécessaire
        while len(row) <= max(siret_col_idx, dirigeants_col_idx):
            row.append('')

        row[siret_col_idx] = result['siret']
        row[dirigeants_col_idx] = result['dirigeants']

        updates.append({
            'range': f'A{row_idx}:{chr(65 + len(row) - 1)}{row_idx}',
            'values': [row]
        })

    # Upload par batch de 100 lignes
    batch_size = 100
    total_updates = len(updates)

    for i in range(0, total_updates, batch_size):
        batch = updates[i:i + batch_size]
        print(f"[INFO] Upload batch {i//batch_size + 1}/{(total_updates + batch_size - 1)//batch_size} ({len(batch)} lignes)")

        for update in batch:
            worksheet.update(values=update['values'], range_name=update['range'])
            time.sleep(0.5)  # Petite pause entre chaque update

    print("\n" + "=" * 70)
    print("[DONE] Mise à jour de Feuille 2 terminée")
    print(f"Total: {len(results)} domaines traités")
    print("=" * 70)

if __name__ == '__main__':
    main()
