#!/usr/bin/env python3
"""
Test Playwright pour extraire le SIRET de 20minutes.fr
"""

import re
from playwright.sync_api import sync_playwright

def extract_siret_with_playwright(url):
    """Extrait SIRET/SIREN avec Playwright (exécute JavaScript)"""

    with sync_playwright() as p:
        # Lancer le navigateur en mode headless
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Aller sur la page
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Attendre que le contenu soit chargé
            page.wait_for_timeout(2000)

            # Récupérer tout le texte de la page
            text = page.inner_text('body')

            print(f"Texte extrait ({len(text)} caractères)")

            # Patterns de recherche
            patterns = [
                (r'\bSIRET\s*:?\s*(\d[\d\s]{13,17})', 'SIRET'),
                (r'\bSIREN\s*:?\s*(\d[\d\s]{8,12})', 'SIREN'),
                (r'\bnum[eé]ro\s+d[\'\"]identification\s*:?\s*(\d[\d\s]{8,13})', 'SIREN/SIRET'),
                (r'identification\s*:?\s*(\d[\d\s]{8,13})', 'ID'),
            ]

            for pattern, label in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    number = match.group(1).replace(' ', '').replace('\n', '')
                    print(f'\n✓ Trouvé ({label}): {number}')
                    print(f'  Longueur: {len(number)} chiffres')

                    if len(number) == 9:
                        print(f'  Type: SIREN')
                        return number, 'SIREN'
                    elif len(number) == 14:
                        print(f'  Type: SIRET')
                        return number, 'SIRET'

            # Si rien trouvé, afficher un extrait contenant "identification"
            if 'identification' in text.lower():
                idx = text.lower().find('identification')
                print(f'\n⚠ "identification" trouvé mais pas extrait:')
                print(f'  {text[max(0, idx-50):idx+150]}')

            print('\n✗ Aucun SIRET/SIREN trouvé')
            return None, None

        finally:
            browser.close()

if __name__ == '__main__':
    url = 'https://www.20minutes.fr/mentions'
    print(f'Test de {url}\n')
    extract_siret_with_playwright(url)
