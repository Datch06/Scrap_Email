#!/usr/bin/env python3
"""
Script pour réessayer les domaines qui ont "NON TROUVÉ" avec les patterns corrigés
"""
import re
import ssl
import time
import json
import urllib.request
import tempfile
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Configuration
REQUEST_TIMEOUT = 15
PAUSE_SECONDS = 2.0
USE_PLAYWRIGHT_FALLBACK = True
RESULTS_FILE = 'feuille2_results.json'

# Patterns corrigés pour SIRET/SIREN (avec gestion des espaces)
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

def fetch_and_extract_pdf(url, opener):
    """Télécharge et extrait le texte d'un PDF"""
    if not PDF_SUPPORT:
        return None

    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower():
                return None

            # Télécharger le PDF dans un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(resp.read())
                tmp_path = tmp.name

            # Extraire le texte
            reader = PdfReader(tmp_path)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + ' '

            # Nettoyer le fichier temporaire
            import os
            os.unlink(tmp_path)

            return text
    except Exception as e:
        return None

def search_siret_in_text(text, fuzzy=False):
    """Search for SIRET/SIREN in text"""
    match = SIRET_WORD_PATTERN.search(text)
    if match:
        siret = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
        if len(siret) == 14 and siret.isdigit():
            return siret, 'SIRET'

    match = SIREN_PATTERN.search(text)
    if match:
        siren = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
        if len(siren) == 9 and siren.isdigit():
            return siren, 'SIREN'

    match = ID_NUMBER_PATTERN.search(text)
    if match:
        id_number = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
        if len(id_number) == 9 and id_number.isdigit():
            return id_number, 'SIREN'
        elif len(id_number) == 14 and id_number.isdigit():
            return id_number, 'SIRET'

    match = RCS_PATTERN.search(text)
    if match:
        id_number = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
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

    # Phase 4: Chercher des liens PDF dans les pages HTML
    if PDF_SUPPORT:
        print("📄 Recherche PDF...", end=' ', flush=True)
        pdf_patterns = [r'href=["\']([^"\']*\.pdf[^"\']*)["\']', r'href=["\']([^"\']*(?:cgu|cgv|mentions)[^"\']*)["\']']

        for page_path in ['/mentions-legales', '/contact', '/']:
            url = f"https://{domain}{page_path}"
            html = fetch_page(url, opener)

            if html:
                for pattern in pdf_patterns:
                    pdf_links = re.findall(pattern, html, re.IGNORECASE)
                    for pdf_link in pdf_links[:3]:  # Max 3 PDF par page
                        # Construire l'URL complète du PDF
                        if pdf_link.startswith('http'):
                            pdf_url = pdf_link
                        elif pdf_link.startswith('/'):
                            pdf_url = f"https://{domain}{pdf_link}"
                        else:
                            pdf_url = f"https://{domain}/{pdf_link}"

                        # Extraire le texte du PDF
                        pdf_text = fetch_and_extract_pdf(pdf_url, opener)
                        if pdf_text:
                            siret_siren, number_type = search_siret_in_text(pdf_text)
                            if siret_siren:
                                print(f"✓ {number_type}: {siret_siren} (PDF)")
                                return siret_siren, number_type

    # Phase 5: Mode fuzzy - chercher n'importe quel numéro à 9 ou 14 chiffres
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

    print("✗ Toujours pas trouvé")
    return None, None

def fetch_company_leaders(siret_siren, number_type, opener):
    """Fetch company leaders from société.com"""
    print(f"    Recherche dirigeants...", end=' ', flush=True)

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

def main():
    # Charger les résultats existants
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # Filtrer les domaines "NON TROUVÉ"
    failed_domains = [(domain, info) for domain, info in results.items()
                      if info.get('siret') == 'NON TROUVÉ']

    print(f"[INFO] {len(failed_domains)} domaines avec 'NON TROUVÉ' à réessayer\n")

    if not failed_domains:
        print("[INFO] Aucun domaine à réessayer")
        return

    opener = build_opener()
    found_count = 0

    for idx, (domain, info) in enumerate(failed_domains, 1):
        print(f"[{idx}/{len(failed_domains)}] {domain}")

        # Chercher SIRET/SIREN avec les nouveaux patterns
        siret_siren, number_type = find_siret_siren(domain, opener)

        if siret_siren:
            found_count += 1
            results[domain]['siret'] = siret_siren
            time.sleep(PAUSE_SECONDS)

            # Chercher les dirigeants
            leaders = fetch_company_leaders(siret_siren, number_type, opener)
            results[domain]['dirigeants'] = '; '.join(leaders) if leaders else 'NON TROUVÉ'

            # Sauvegarder immédiatement
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

        time.sleep(1)

    print("\n" + "=" * 70)
    print(f"[DONE] Réessai terminé")
    print(f"Nouveaux SIRET trouvés: {found_count}/{len(failed_domains)}")
    print("=" * 70)

if __name__ == '__main__':
    main()
