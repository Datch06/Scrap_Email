#!/usr/bin/env python3
"""
Script pour extraire SIRET/SIREN et trouver les dirigeants via société.com

Usage:
    python3 find_company_leaders.py <domains_file.txt> [output.csv]

Le script va:
1. Lire la liste des domaines
2. Chercher SIRET/SIREN dans les mentions légales
3. Récupérer les dirigeants sur société.com
4. Sauvegarder dans un CSV
"""

import sys
import re
import ssl
import time
import urllib.request
import urllib.parse
from pathlib import Path
from html.parser import HTMLParser

# Configuration
REQUEST_TIMEOUT = 15
PAUSE_SECONDS = 2.0  # Respecter société.com

# Patterns pour SIRET/SIREN
SIRET_PATTERN = re.compile(r'\b(\d{14})\b')  # 14 chiffres
SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*(\d{9})\b', re.IGNORECASE)  # 9 chiffres
SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*(\d{14})\b', re.IGNORECASE)
# Pattern pour "numéro d'identification" ou variantes
ID_NUMBER_PATTERN = re.compile(r'\bnum[eé]ro\s+d['']identification\s*:?\s*(\d[\d\s]{8,13})', re.IGNORECASE)
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

def find_siret_siren(domain, opener):
    """Find SIRET or SIREN in legal pages"""
    print(f"  Recherche SIRET/SIREN pour {domain}...", end=' ', flush=True)

    for page_path in LEGAL_PAGES:
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if not html:
            continue

        text = extract_text_from_html(html)

        # Chercher SIRET avec le mot-clé (plus fiable)
        match = SIRET_WORD_PATTERN.search(text)
        if match:
            siret = match.group(1)
            print(f"✓ SIRET: {siret}")
            return siret, 'SIRET'

        # Chercher SIREN avec le mot-clé
        match = SIREN_PATTERN.search(text)
        if match:
            siren = match.group(1)
            print(f"✓ SIREN: {siren}")
            return siren, 'SIREN'

        # Chercher "numéro d'identification" (SIREN)
        match = ID_NUMBER_PATTERN.search(text)
        if match:
            id_number = match.group(1).replace(' ', '')
            if len(id_number) == 9:
                print(f"✓ SIREN (n° identification): {id_number}")
                return id_number, 'SIREN'
            elif len(id_number) == 14:
                print(f"✓ SIRET (n° identification): {id_number}")
                return id_number, 'SIRET'
        time.sleep(0.3)

    # Si pas trouvé avec mot-clé, chercher des séquences de 14 chiffres (moins fiable)
    for page_path in LEGAL_PAGES[:3]:  # Seulement les 3 premières pages
        url = f"https://{domain}{page_path}"
        html = fetch_page(url, opener)

        if not html:
            continue

        text = extract_text_from_html(html)
        matches = SIRET_PATTERN.findall(text)

        if matches:
            # Prendre le premier qui ressemble à un SIRET
            siret = matches[0]
            print(f"? SIRET probable: {siret}")
            return siret, 'SIRET'

    print("✗ Non trouvé")
    return None, None

def fetch_company_leaders(siret_siren, number_type, opener):
    """Fetch company leaders from société.com"""
    print(f"    Recherche dirigeants sur société.com...", end=' ', flush=True)

    # Construire l'URL société.com
    if number_type == 'SIRET':
        # Extraire le SIREN (9 premiers chiffres)
        siren = siret_siren[:9]
    else:
        siren = siret_siren

    url = f"https://www.societe.com/cgi-bin/search?champs={siren}"

    try:
        html = fetch_page(url, opener)
        if not html:
            print("✗ Erreur")
            return []

        # Chercher la page de l'entreprise
        # Pattern pour trouver le lien vers la fiche entreprise
        company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
        match = company_link_pattern.search(html)

        if not match:
            print("✗ Entreprise non trouvée")
            return []

        company_path = match.group(1)
        company_url = f"https://www.societe.com{company_path}"

        time.sleep(PAUSE_SECONDS)  # Respecter le site

        # Récupérer la page de l'entreprise
        html = fetch_page(company_url, opener)
        if not html:
            print("✗ Erreur page entreprise")
            return []

        # Extraire les dirigeants
        # Chercher les sections avec "Dirigeant", "Président", etc.
        leaders = []

        # Pattern pour dirigeants
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
                if len(name) > 5 and len(name) < 50:  # Filtrer les noms valides
                    leaders.append(name)

        # Dédupliquer
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
    if len(sys.argv) < 2:
        print("Usage: python3 find_company_leaders.py <domains_file.txt> [output.csv]")
        print("\nExemple:")
        print("  python3 find_company_leaders.py domains_fr_only.txt company_leaders.csv")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('company_leaders.csv')

    if not input_file.exists():
        print(f"[ERROR] Fichier {input_file} introuvable")
        sys.exit(1)

    # Lire les domaines
    with open(input_file, 'r', encoding='utf-8') as f:
        domains = [line.strip() for line in f if line.strip()]

    print(f"[INFO] Traitement de {len(domains)} domaines")
    print(f"[INFO] Output: {output_file}")
    print()

    opener = build_opener()
    results = []

    for i, domain in enumerate(domains, 1):
        print(f"[{i}/{len(domains)}] {domain}")

        # Trouver SIRET/SIREN
        siret_siren, number_type = find_siret_siren(domain, opener)

        if siret_siren:
            time.sleep(PAUSE_SECONDS)
            # Chercher les dirigeants
            leaders = fetch_company_leaders(siret_siren, number_type, opener)

            results.append({
                'domain': domain,
                'siret_siren': siret_siren,
                'type': number_type,
                'leaders': '; '.join(leaders) if leaders else 'NON TROUVÉ'
            })
        else:
            results.append({
                'domain': domain,
                'siret_siren': 'NON TROUVÉ',
                'type': '',
                'leaders': ''
            })

        time.sleep(1)  # Pause entre domaines

    # Sauvegarder les résultats
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('Domain,SIRET/SIREN,Type,Dirigeants\n')
        for result in results:
            f.write(f"{result['domain']},{result['siret_siren']},{result['type']},\"{result['leaders']}\"\n")

    # Statistiques
    found_siret = len([r for r in results if r['siret_siren'] != 'NON TROUVÉ'])
    found_leaders = len([r for r in results if r['leaders'] and r['leaders'] != 'NON TROUVÉ'])

    print()
    print("=" * 70)
    print(f"[DONE] Traité {len(domains)} domaines")
    print(f"[DONE] SIRET/SIREN trouvés: {found_siret}/{len(domains)}")
    print(f"[DONE] Dirigeants trouvés: {found_leaders}/{len(domains)}")
    print(f"[DONE] Résultats sauvegardés: {output_file}")
    print("=" * 70)

if __name__ == '__main__':
    main()
