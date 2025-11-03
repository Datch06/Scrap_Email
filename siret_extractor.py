#!/usr/bin/env python3
"""
Module d'extraction de SIRET/SIREN depuis les sites web
Utilise plusieurs sources et stratégies
"""

import requests
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time


class SiretExtractor:
    """Extracteur de SIRET/SIREN avec multiples stratégies"""

    def __init__(self, use_playwright=False, timeout=10):
        self.use_playwright = use_playwright
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def extract_siret_from_text(self, text):
        """
        Extrait SIRET/SIREN depuis du texte brut

        Returns:
            tuple: (siret, type) où type est 'SIRET' ou 'SIREN'
        """
        # Patterns pour SIRET (14 chiffres) - patterns explicites d'abord
        siret_patterns = [
            # N° de Siret: "N° de Siret : 51046815000014"
            re.compile(r'(?:N°|n°|numéro|numero)\s+(?:de\s+)?(?:SIRET|Siret|siret)\s*[:\s]*(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b', re.IGNORECASE),
            # SIRET explicite: "SIRET: 123 456 789 00014"
            re.compile(r'(?:SIRET|Siret|siret)\s*[:\s]*(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b', re.IGNORECASE),
            # Pattern générique (14 chiffres)
            re.compile(r'\b(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b'),
        ]

        # Patterns pour SIREN (9 chiffres) - multiples variantes
        siren_patterns = [
            # SIREN explicite: "SIREN: 123 456 789"
            re.compile(r'(?:SIREN|siren|Siren)[:\s]*(\d{3}\s?\d{3}\s?\d{3})\b'),
            # RCS: "RCS Paris 123 456 789" ou "438 049 843 RCS"
            re.compile(r'(?:RCS|rcs)[:\s]*[A-Za-zÀ-ÿ\s]*(\d{3}\s?\d{3}\s?\d{3})\b'),
            re.compile(r'(\d{3}\s?\d{3}\s?\d{3})\s+(?:RCS|rcs)'),
            # Numéro d'identification: "numéro d'identification 123 456 789"
            re.compile(r'(?:numéro|numero|n°|N°)\s+(?:d\'identification|identification)[:\s]*(\d{3}\s?\d{3}\s?\d{3})\b', re.IGNORECASE),
            # Immatriculation: "Immatriculée au RCS 123 456 789"
            re.compile(r'(?:Immatricul|inscrit)[éeès]+\s+(?:au|sous\s+le)[:\s]*(?:RCS|rcs)[:\s]*[A-Za-zÀ-ÿ\s]*(\d{3}\s?\d{3}\s?\d{3})\b', re.IGNORECASE),
            # Registre du Commerce et des Sociétés: "immatriculée au Registre du Commerce et des Sociétés de Paris sous le numéro 123 456 789"
            re.compile(r'(?:Registre\s+du\s+Commerce\s+et\s+des\s+Sociétés|RCS)[^\.]{0,50}(?:sous\s+le\s+)?numéro\s+(\d{3}\s?\d{3}\s?\d{3})(?:\s?\d{5})?\b', re.IGNORECASE),
        ]

        # Chercher SIRET d'abord (14 chiffres) avec tous les patterns
        for pattern in siret_patterns:
            siret_matches = pattern.findall(text)
            if siret_matches:
                # Nettoyer et valider
                siret = siret_matches[0].replace(' ', '')
                if len(siret) == 14 and siret.isdigit():
                    return siret, 'SIRET'

        # Chercher SIREN (9 chiffres) avec tous les patterns
        for pattern in siren_patterns:
            siren_matches = pattern.findall(text)
            if siren_matches:
                siren = siren_matches[0].replace(' ', '')
                if len(siren) == 9 and siren.isdigit():
                    return siren, 'SIREN'

        return None, None

    def extract_from_domain(self, domain):
        """
        Extrait le SIRET depuis un domaine

        Stratégies:
        1. Pages mentions légales
        2. Pages CGV/conditions
        3. Page À propos
        4. Footer de la homepage
        5. Recherche pappers.fr (fallback)

        Returns:
            dict: {'siret': ..., 'siren': ..., 'type': ..., 'source': ...}
        """
        if not domain.startswith('http'):
            urls_to_try = [f'https://{domain}', f'http://{domain}']
        else:
            urls_to_try = [domain]

        # Pages à vérifier
        pages_to_check = [
            '',  # Homepage
            '/mentions-legales',
            '/mentions-legales.html',
            '/mentions-legales.php',
            '/page/mentions-legales',
            '/mentions',
            '/legal',
            '/cgv',
            '/conditions-generales',
            '/politique-de-confidentialite',
            '/politique-de-confidentialite/',
            '/confidentialite',
            '/privacy',
            '/a-propos',
            '/about',
            '/qui-sommes-nous',
            '/contact',
        ]

        for base_url in urls_to_try:
            for page in pages_to_check:
                try:
                    url = base_url + page
                    response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

                    if response.status_code == 200:
                        text = response.text
                        soup = BeautifulSoup(text, 'html.parser')

                        # Extraire le texte visible
                        visible_text = soup.get_text(separator=' ')

                        siret, siret_type = self.extract_siret_from_text(visible_text)

                        if siret:
                            result = {
                                'siret': siret if siret_type == 'SIRET' else None,
                                'siren': siret[:9] if siret_type == 'SIRET' else siret,
                                'type': siret_type,
                                'source': f'scraping:{page if page else "homepage"}'
                            }
                            return result

                except:
                    continue

        # Si aucun SIRET trouvé, essayer avec pappers.fr
        return self.search_pappers(domain)

    def search_pappers(self, domain):
        """
        Recherche le SIRET via pappers.fr en utilisant le nom de domaine

        Returns:
            dict ou None
        """
        try:
            # Extraire le nom de l'entreprise du domaine
            company_name = domain.replace('http://', '').replace('https://', '').split('/')[0]
            company_name = company_name.replace('www.', '').split('.')[0]

            url = f'https://www.pappers.fr/recherche?q={company_name}'

            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Chercher le SIREN dans les résultats
                siren_pattern = re.compile(r'SIREN\s*:\s*(\d{9})')
                match = siren_pattern.search(soup.get_text())

                if match:
                    siren = match.group(1)
                    return {
                        'siret': None,
                        'siren': siren,
                        'type': 'SIREN',
                        'source': 'pappers'
                    }

        except:
            pass

        return None

    def extract_with_playwright(self, domain):
        """
        Extrait le SIRET en utilisant Playwright (pour sites dynamiques)

        Returns:
            dict ou None
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()

            pages_to_check = [
                '',
                '/mentions-legales',
                '/legal',
                '/cgv',
            ]

            for page_path in pages_to_check:
                try:
                    url = f'https://{domain}{page_path}' if not domain.startswith('http') else f'{domain}{page_path}'
                    page.goto(url, wait_until='networkidle', timeout=20000)
                    page.wait_for_timeout(2000)

                    text = page.inner_text('body')

                    siret, siret_type = self.extract_siret_from_text(text)

                    if siret:
                        context.close()
                        browser.close()

                        return {
                            'siret': siret if siret_type == 'SIRET' else None,
                            'siren': siret[:9] if siret_type == 'SIRET' else siret,
                            'type': siret_type,
                            'source': f'playwright:{page_path if page_path else "homepage"}'
                        }

                except:
                    continue

            context.close()
            browser.close()

        return None


if __name__ == '__main__':
    # Tests
    extractor = SiretExtractor()

    test_domains = [
        'amazon.fr',
        'carrefour.fr',
        'fnac.com',
    ]

    for domain in test_domains:
        print(f"\nTest: {domain}")
        result = extractor.extract_from_domain(domain)
        if result:
            print(f"  SIREN: {result.get('siren')}")
            print(f"  SIRET: {result.get('siret')}")
            print(f"  Type: {result.get('type')}")
            print(f"  Source: {result.get('source')}")
        else:
            print("  ✗ Non trouvé")
