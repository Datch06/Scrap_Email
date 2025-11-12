#!/usr/bin/env python3
"""
Module d'extraction des dirigeants d'entreprise
Utilise societe.com, pappers.fr et autres sources
"""

import requests
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time


class LeadersExtractor:
    """Extracteur de dirigeants avec multiples sources"""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Patterns pour détecter les dirigeants (strictes pour éviter faux positifs)
        self.leader_patterns = [
            # Format "Fonction : Prénom NOM" ou "Fonction: Prénom NOM"
            re.compile(r'(?:Président|Directeur\s+général|Gérant(?:e)?)\s*:\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:[\s-][A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+){1,3})\b', re.IGNORECASE),

            # Format "Prénom NOM - Fonction" (nom avant fonction)
            re.compile(r'\b([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+\s+[A-Z]{2,}[A-Z]+)\s*[-–]\s*(?:Président|Directeur|Gérant|PDG|CEO)\b'),

            # Format très spécifique sur societe.com/pappers
            re.compile(r'\bDirigeant\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'),
        ]

    def clean_leader_name(self, name):
        """Nettoie et valide un nom de dirigeant"""
        if not name:
            return None

        # Nettoyer
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)

        # Vérifier que c'est bien un nom (pas une société)
        invalid_keywords = [
            'sas', 'sarl', 'sa ', 'eurl', 'sci', 'sasu',
            'société', 'company', 'limited', 'inc',
            'monsieur', 'madame', 'mme', 'mr', 'm.',
            'management', 'holding', 'group', 'consulting',
            'conseil', 'gestion', 'finance', 'invest',
            'capital', 'partners', 'associés', 'associé',
            'services', 'solutions', 'international',
            'ancien', 'ancienne', 'liquidateur', 'mandataire'
        ]

        name_lower = name.lower()
        for keyword in invalid_keywords:
            if keyword in name_lower:
                return None

        # Vérifier qu'il y a au moins 2 mots
        parts = name.split()
        if len(parts) < 2:
            return None

        # Rejeter si tous les mots sont en MAJUSCULES (souvent des sociétés)
        if all(part.isupper() for part in parts if len(part) > 1):
            return None

        # Vérifier que chaque partie commence par une majuscule
        if not all(part[0].isupper() for part in parts if part):
            return None

        # Vérifier qu'il n'y a pas de mots suspects typiques des sociétés
        suspicious_patterns = [
            r'\b[A-Z]{3,}\b',  # Acronymes de 3+ lettres (ex: TWS, AME, SARL)
            r'\b\d+\b',         # Numéros
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, name):
                # Exception: les particules comme "De", "Le", "La" sont OK
                if not re.match(r'^(De|Le|La|Du|Des)\b', name, re.IGNORECASE):
                    return None

        # Rejeter les noms avec moins de 4 caractères au total
        if len(name.replace(' ', '')) < 4:
            return None

        # Rejeter si contient des mots de liaison/verbes
        stop_words = ['le', 'la', 'de', 'du', 'des', 'voir', 'depuis', 'pour',
                      'avec', 'sans', 'dans', 'sur', 'par', 'en', 'au', 'aux',
                      'été', 'accède', 'désignée', 'afficher', 'fiche']

        words_lower = [w.lower() for w in parts]
        for word in words_lower:
            if word in stop_words and word not in ['de', 'le', 'la', 'du']:
                return None

        # Vérifier format typique : Prénom Nom ou Nom Prénom
        # Au moins un mot doit avoir plus de 2 lettres
        if not any(len(part) > 2 for part in parts):
            return None

        return name

    def extract_from_siren(self, siren):
        """
        Extrait les dirigeants depuis un SIREN

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            dict: {'leaders': [...], 'source': ..., 'status': ...}
        """
        # Essayer societe.com d'abord
        result = self.extract_from_societe_com(siren)
        if result and result['leaders']:
            return result

        # Fallback sur pappers.fr
        return self.extract_from_pappers(siren)

    def extract_from_societe_com(self, siren):
        """
        Extrait depuis societe.com avec Playwright (évite Cloudflare)

        Returns:
            dict: {'leaders': [...], 'source': 'societe.com', 'status': ...}
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()

                # Recherche sur societe.com
                url = f"https://www.societe.com/cgi-bin/search?champs={siren}"
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)

                text = page.inner_text('body')

                # Vérifier si rate limit
                if 'trop de requêtes' in text.lower() or 'too many requests' in text.lower():
                    context.close()
                    browser.close()
                    return {'leaders': [], 'source': 'societe.com', 'status': 'rate_limited'}

                # Chercher le lien de l'entreprise
                html = page.content()
                company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
                match = company_link_pattern.search(html)

                if not match:
                    context.close()
                    browser.close()
                    return {'leaders': [], 'source': 'societe.com', 'status': 'not_found'}

                company_url = "https://www.societe.com" + match.group(1)

                # Charger la page entreprise
                page.goto(company_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)

                text = page.inner_text('body')

                # Vérifier rate limit sur page entreprise
                if 'trop de requêtes' in text.lower() or 'too many requests' in text.lower():
                    context.close()
                    browser.close()
                    return {'leaders': [], 'source': 'societe.com', 'status': 'rate_limited'}

                # Chercher les dirigeants
                leaders = []
                for pattern in self.leader_patterns:
                    matches = pattern.findall(text)
                    for match in matches:
                        cleaned = self.clean_leader_name(match)
                        if cleaned and cleaned not in leaders:
                            leaders.append(cleaned)

                context.close()
                browser.close()

                return {
                    'leaders': leaders,
                    'source': 'societe.com',
                    'status': 'success' if leaders else 'no_leaders'
                }

        except Exception as e:
            return {'leaders': [], 'source': 'societe.com', 'status': f'error: {str(e)}'}

    def extract_from_pappers(self, siren):
        """
        Extrait depuis pappers.fr

        Returns:
            dict: {'leaders': [...], 'source': 'pappers', 'status': ...}
        """
        try:
            url = f'https://www.pappers.fr/entreprise/{siren}'

            # Utiliser Playwright pour éviter Cloudflare
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = context.new_page()

                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(3000)

                text = page.inner_text('body')

                # Vérifier Cloudflare
                if 'just a moment' in text.lower() or 'cloudflare' in text.lower():
                    context.close()
                    browser.close()
                    return {'leaders': [], 'source': 'pappers', 'status': 'cloudflare_blocked'}

                # Chercher les dirigeants
                leaders = []

                # Section dirigeants sur pappers
                if 'dirigeant' in text.lower():
                    lines = text.split('\n')
                    in_leaders_section = False

                    for i, line in enumerate(lines):
                        if 'dirigeant' in line.lower() and not in_leaders_section:
                            in_leaders_section = True
                            # Lire les 10 prochaines lignes
                            for j in range(i+1, min(i+11, len(lines))):
                                for pattern in self.leader_patterns:
                                    matches = pattern.findall(lines[j])
                                    for match in matches:
                                        cleaned = self.clean_leader_name(match)
                                        if cleaned and cleaned not in leaders:
                                            leaders.append(cleaned)

                                # Vérifier si on sort de la section
                                if any(x in lines[j].lower() for x in ['capital', 'chiffre', 'effectif', 'adresse']):
                                    break

                context.close()
                browser.close()

                return {
                    'leaders': leaders,
                    'source': 'pappers',
                    'status': 'success' if leaders else 'no_leaders'
                }

        except Exception as e:
            return {'leaders': [], 'source': 'pappers', 'status': f'error: {str(e)}'}


if __name__ == '__main__':
    # Tests
    extractor = LeadersExtractor()

    test_sirens = [
        '440272675',  # Amazon France
        '542065479',  # Carrefour
    ]

    for siren in test_sirens:
        print(f"\nTest SIREN: {siren}")
        result = extractor.extract_from_siren(siren)
        print(f"  Status: {result['status']}")
        print(f"  Source: {result['source']}")
        if result['leaders']:
            print(f"  Dirigeants ({len(result['leaders'])}):")
            for leader in result['leaders']:
                print(f"    - {leader}")
        else:
            print("  ✗ Aucun dirigeant trouvé")
