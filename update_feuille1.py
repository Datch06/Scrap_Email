#!/usr/bin/env python3
"""
Script pour mettre à jour SIRET/SIREN et dirigeants dans Feuille 1
Utilise toutes les améliorations : espaces, RCS, PDF, CGV/CGU
"""

import re
import ssl
import time
import json
import urllib.request
import gspread
import tempfile
import os
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Configuration
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 1'
REQUEST_TIMEOUT = 15
USE_PLAYWRIGHT_FALLBACK = True
RESULTS_FILE = 'feuille1_results.json'

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

# Pages légales à vérifier
LEGAL_PAGES = [
    '/mentions-legales', '/mentions-legales.html', '/mentions_legales',
    '/cgv', '/cgu', '/conditions-generales-vente', '/conditions-generales-utilisation',
    '/mentions', '/legal', '/legal-notice',
    '/a-propos', '/about', '/qui-sommes-nous', '/contact',
]

# Patterns améliorés
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*([\d\s\t]{14,20})', re.IGNORECASE)
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*([\d\s\t]{9,15})', re.IGNORECASE)
RCS_PATTERN = re.compile(r"\bsous le num[eé]ro\s+[A-Z]?\s*([\d\s\t]{9,20})", re.IGNORECASE)
ID_NUMBER_PATTERN = re.compile(r"\bnum[eé]ro\s+d['']identification\s*:?\s*([\d\s\t]{9,20})", re.IGNORECASE)

LEADER_PATTERNS = [
    re.compile(r'\bPrésident\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'\bDirecteur\s+[Gg]énéral\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'\bGérant\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
]

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)

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
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                return None
            data = resp.read()
            return data.decode('utf-8', errors='replace')
    except:
        return None

def fetch_page_with_playwright(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            text = page.inner_text('body')
            browser.close()
            return text
    except:
        return None

def fetch_and_extract_pdf(url, opener):
    if not PDF_SUPPORT:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower():
                return None

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(resp.read())
                tmp_path = tmp.name

            reader = PdfReader(tmp_path)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + ' '

            os.unlink(tmp_path)
            return text
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

def search_siret_in_text(text, fuzzy=False):
    if not text:
        return None, None

    patterns = [
        (SIRET_WORD_PATTERN, 'SIRET'),
        (SIREN_PATTERN, 'SIREN'),
        (RCS_PATTERN, 'RCS'),
        (ID_NUMBER_PATTERN, 'ID'),
    ]

    for pattern, name in patterns:
        match = pattern.search(text)
        if match:
            siret = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
            if len(siret) == 14 and siret.isdigit():
                return siret, name
            elif len(siret) == 9 and siret.isdigit():
                return siret, name

    if fuzzy:
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
    print(f"  Recherche SIRET/SIREN pour {domain}...", end=' ', flush=True)

    # Phase 1: urllib
    for page_path in LEGAL_PAGES:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if html:
            text = extract_text_from_html(html)
            siret_siren, number_type = search_siret_in_text(text)

            if siret_siren:
                print(f"✓ {number_type}: {siret_siren}")
                return siret_siren, number_type

            time.sleep(0.3)

    # Phase 2: Playwright
    if USE_PLAYWRIGHT_FALLBACK:
        print("↻ Playwright...", end=' ', flush=True)
        for page_path in LEGAL_PAGES[:5]:
            url = f"https://{domain}{page_path}"
            text = fetch_page_with_playwright(url)

            if text:
                siret_siren, number_type = search_siret_in_text(text)
                if siret_siren:
                    print(f"✓ {number_type}: {siret_siren} (JS)")
                    return siret_siren, number_type

    # Phase 3: PDF
    if PDF_SUPPORT:
        print("📄 PDF...", end=' ', flush=True)
        for page_path in ['/mentions-legales', '/cgv', '/cgu', '/']:
            url = f"https://{domain}{page_path}"
            html = fetch_page(url, opener)

            if html:
                pdf_pattern = r'href=["\']([^"\']*\.pdf[^"\']*)["\']'
                pdf_matches = re.findall(pdf_pattern, html)

                for pdf_url in pdf_matches[:3]:
                    if not pdf_url.startswith('http'):
                        pdf_url = f'https://{domain}{pdf_url}'

                    pdf_text = fetch_and_extract_pdf(pdf_url, opener)
                    if pdf_text:
                        siret_siren, number_type = search_siret_in_text(pdf_text)
                        if siret_siren:
                            print(f"✓ {number_type}: {siret_siren} (PDF)")
                            return siret_siren, number_type

    # Phase 4: Fuzzy
    print("🔍 Fuzzy...", end=' ', flush=True)
    for page_path in LEGAL_PAGES[:3]:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if html:
            text = extract_text_from_html(html)
            siret_siren, number_type = search_siret_in_text(text, fuzzy=True)

            if siret_siren:
                print(f"✓ {number_type}: {siret_siren}")
                return siret_siren, number_type

    print("✗ Toujours pas trouvé")
    return None, None

def fetch_company_leaders(siret_siren, number_type, opener):
    print(f"    Recherche dirigeants...", end=' ', flush=True)

    if number_type and 'SIRET' in number_type:
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

        company_url = "https://www.societe.com" + match.group(1)
        time.sleep(1)

        company_html = fetch_page(company_url, opener)
        if not company_html:
            print("✗ Page entreprise non accessible")
            return []

        leaders = []
        for pattern in LEADER_PATTERNS:
            matches = pattern.findall(company_html)
            leaders.extend(matches)

        leaders = list(set(leaders))

        if leaders:
            print(f"✓ {len(leaders)} dirigeant(s)")
        else:
            print("✗ Aucun dirigeant trouvé")

        return leaders
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return []

def main():
    print("=" * 70)
    print("MISE À JOUR FEUILLE 1 - SIRET/SIREN ET DIRIGEANTS")
    print("=" * 70)

    # Connexion Google Sheets
    print("\n[1/5] Connexion à Google Sheets...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    spreadsheet = gc.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    # Récupérer les domaines
    print("[2/5] Récupération des domaines...")
    all_values = worksheet.get_all_values()

    # La structure: domaine (col 0), emails (col 1), date (col 2), ID (col 3), SIRET (col 4), label (col 5), Dirigeants (col 6)
    domains_to_process = []
    for i, row in enumerate(all_values[1:], start=2):  # Skip header
        if len(row) > 0 and row[0]:
            domain = row[0].strip()
            current_siret = row[4] if len(row) > 4 else ''

            # Traiter si NON TROUVÉ ou vide
            if not current_siret or current_siret == 'NON TROUVÉ':
                domains_to_process.append((i, domain))

    print(f"[INFO] {len(domains_to_process)} domaines à traiter")

    # Charger les résultats existants
    results = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"[INFO] {len(results)} résultats existants chargés")

    # Traiter les domaines
    print("\n[3/5] Traitement des domaines...")
    opener = build_opener()

    for idx, (row_num, domain) in enumerate(domains_to_process, 1):
        print(f"[{idx}/{len(domains_to_process)}] {domain}")

        # Skip si déjà traité
        if domain in results and results[domain].get('siret') != 'NON TROUVÉ':
            print("  ⏭  Déjà traité")
            continue

        # Chercher SIRET/SIREN
        siret_siren, number_type = find_siret_siren(domain, opener)

        # Chercher dirigeants si SIRET trouvé
        dirigeants = []
        if siret_siren:
            dirigeants = fetch_company_leaders(siret_siren, number_type, opener)

        # Enregistrer
        results[domain] = {
            'siret': siret_siren if siret_siren else 'NON TROUVÉ',
            'dirigeants': dirigeants,
            'row': row_num
        }

        # Sauvegarder régulièrement
        if idx % 10 == 0:
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(1)

    # Sauvegarder les résultats finaux
    print("\n[4/5] Sauvegarde des résultats...")
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Upload vers Google Sheets
    print("[5/5] Mise à jour du Google Sheet...")
    updates = []

    for domain, data in results.items():
        row_num = data.get('row')
        if not row_num:
            continue

        siret = data.get('siret', 'NON TROUVÉ')
        dirigeants = ', '.join(data.get('dirigeants', [])) if data.get('dirigeants') else ''

        # Colonne E (5) = SIRET, Colonne G (7) = Dirigeants
        updates.append({
            'range': f'E{row_num}:G{row_num}',
            'values': [[siret, '', dirigeants]]  # Colonne F vide (label)
        })

    # Batch update par chunks
    chunk_size = 100
    for i in range(0, len(updates), chunk_size):
        chunk = updates[i:i+chunk_size]
        worksheet.batch_update(chunk, value_input_option='USER_ENTERED')
        print(f"  Mis à jour {min(i+chunk_size, len(updates))}/{len(updates)} lignes")
        time.sleep(2)

    # Stats finales
    print("\n" + "=" * 70)
    print("TERMINÉ !")
    print("=" * 70)
    siret_found = sum(1 for d in results.values() if d.get('siret') and d['siret'] != 'NON TROUVÉ')
    dirigeants_found = sum(1 for d in results.values() if d.get('dirigeants'))
    print(f"Total domaines traités: {len(results)}")
    print(f"SIRET trouvés: {siret_found}")
    print(f"Dirigeants trouvés: {dirigeants_found}")
    print("=" * 70)

if __name__ == '__main__':
    main()
