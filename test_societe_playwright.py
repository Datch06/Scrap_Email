#!/usr/bin/env python3
"""
Test de récupération de dirigeants sur societe.com avec Playwright
"""
from playwright.sync_api import sync_playwright
import re

def test_societe_com(siren):
    """Test récupération dirigeants sur societe.com"""

    LEADER_PATTERNS = [
        re.compile(r'Président\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
        re.compile(r'Directeur\s+[Gg]énéral\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
        re.compile(r'Gérant\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
        re.compile(r'([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)\s*-?\s*Président', re.IGNORECASE),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()

        try:
            # Recherche sur societe.com
            url = f"https://www.societe.com/cgi-bin/search?champs={siren}"
            print(f"Test pour SIREN {siren}")
            print(f"URL: {url}\n")

            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)

            # Chercher le lien de l'entreprise
            html = page.content()
            company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
            match = company_link_pattern.search(html)

            if not match:
                print("✗ Lien entreprise non trouvé")
                # Afficher le contenu pour debug
                text = page.inner_text('body')
                if len(text) < 500:
                    print(f"Contenu court ({len(text)} chars): {text[:300]}")
                else:
                    print(f"Contenu OK ({len(text)} chars)")
                return []

            company_url = "https://www.societe.com" + match.group(1)
            print(f"✓ Page entreprise: {company_url}")

            # Charger la page entreprise
            page.goto(company_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)

            # Récupérer le texte visible
            text = page.inner_text('body')
            print(f"✓ Texte chargé: {len(text)} caractères\n")

            # Chercher les dirigeants
            leaders = []
            for pattern in LEADER_PATTERNS:
                matches = pattern.findall(text)
                leaders.extend(matches)

            leaders = list(set(leaders))

            if leaders:
                print(f"✓ {len(leaders)} dirigeant(s) trouvé(s):")
                for leader in leaders:
                    print(f"  - {leader}")
            else:
                print("✗ Aucun dirigeant trouvé")
                # Afficher les sections pertinentes
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if 'dirigeant' in line.lower() or 'président' in line.lower() or 'gérant' in line.lower():
                        print(f"  Ligne {i}: {line.strip()}")
                        if i+1 < len(lines):
                            print(f"  Ligne {i+1}: {lines[i+1].strip()}")

            return leaders

        except Exception as e:
            print(f"✗ Erreur: {e}")
            return []
        finally:
            browser.close()

# Tests
print("=" * 70)
print("TEST SOCIETE.COM AVEC PLAYWRIGHT")
print("=" * 70)

# Test 1: Amazon (grand groupe)
print("\n[Test 1] Amazon France Services")
test_societe_com("440272675")

# Test 2: Une PME (exemple de la Feuille 1)
print("\n" + "=" * 70)
print("\n[Test 2] PME exemple")
test_societe_com("790951577")  # tri-facile.fr

print("\n" + "=" * 70)
