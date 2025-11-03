#!/usr/bin/env python3
"""
Script pour récupérer les dirigeants avec scraping lent (30s entre requêtes)
Pour éviter le rate limiting de societe.com
"""

import json
import time
import re
import gspread
from playwright.sync_api import sync_playwright

# Configuration
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
FEUILLE1_RESULTS = 'feuille1_results.json'
FEUILLE2_RESULTS = 'feuille2_results.json'
DIRIGEANTS_FILE = 'dirigeants_results.json'
DELAY_BETWEEN_REQUESTS = 30  # 30 secondes entre chaque requête

LEADER_PATTERNS = [
    re.compile(r'Président\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'Directeur\s+[Gg]énéral\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'Gérant\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)\s*-?\s*Président', re.IGNORECASE),
    re.compile(r'([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)\s*-?\s*Directeur', re.IGNORECASE),
]

def fetch_leaders_playwright(siren, browser):
    """Récupère les dirigeants avec Playwright"""
    try:
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
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
            return None, 'RATE_LIMITED'

        # Chercher le lien de l'entreprise
        html = page.content()
        company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
        match = company_link_pattern.search(html)

        if not match:
            context.close()
            return [], 'NOT_FOUND'

        company_url = "https://www.societe.com" + match.group(1)

        # Charger la page entreprise
        page.goto(company_url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        text = page.inner_text('body')

        # Vérifier rate limit sur page entreprise
        if 'trop de requêtes' in text.lower() or 'too many requests' in text.lower():
            context.close()
            return None, 'RATE_LIMITED'

        # Chercher les dirigeants
        leaders = []
        for pattern in LEADER_PATTERNS:
            matches = pattern.findall(text)
            leaders.extend(matches)

        leaders = list(set(leaders))
        context.close()

        return leaders, 'OK'

    except Exception as e:
        try:
            context.close()
        except:
            pass
        return [], f'ERROR: {e}'

def main():
    print("=" * 70)
    print("RÉCUPÉRATION LENTE DES DIRIGEANTS")
    print("=" * 70)

    # Charger les résultats existants
    print("\n[1/5] Chargement des résultats SIRET...")

    with open(FEUILLE1_RESULTS, 'r', encoding='utf-8') as f:
        feuille1 = json.load(f)

    with open(FEUILLE2_RESULTS, 'r', encoding='utf-8') as f:
        feuille2 = json.load(f)

    # Collecter tous les SIRET/SIREN à traiter
    to_process = []

    for domain, data in feuille1.items():
        siret = data.get('siret')
        if siret and siret != 'NON TROUVÉ':
            siren = siret[:9] if len(siret) == 14 else siret
            if not data.get('dirigeants'):
                to_process.append({
                    'domain': domain,
                    'siren': siren,
                    'sheet': 'feuille1',
                    'row': data.get('row')
                })

    for domain, data in feuille2.items():
        siret = data.get('siret')
        if siret and siret != 'NON TROUVÉ':
            siren = siret[:9] if len(siret) == 14 else siret
            if not data.get('dirigeants'):
                to_process.append({
                    'domain': domain,
                    'siren': siren,
                    'sheet': 'feuille2'
                })

    print(f"[INFO] {len(to_process)} entreprises à traiter")

    # Charger les résultats dirigeants existants
    dirigeants_results = {}
    try:
        with open(DIRIGEANTS_FILE, 'r', encoding='utf-8') as f:
            dirigeants_results = json.load(f)
        print(f"[INFO] {len(dirigeants_results)} dirigeants déjà récupérés")
    except:
        pass

    # Traiter avec Playwright
    print("\n[2/5] Récupération des dirigeants (30s entre chaque requête)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for idx, item in enumerate(to_process, 1):
            domain = item['domain']
            siren = item['siren']

            print(f"[{idx}/{len(to_process)}] {domain} (SIREN: {siren})", end=' ', flush=True)

            # Skip si déjà traité
            if siren in dirigeants_results and dirigeants_results[siren].get('status') == 'OK':
                leaders = dirigeants_results[siren].get('leaders', [])
                print(f"⏭  Déjà traité ({len(leaders)} dirigeant(s))")
                continue

            # Récupérer les dirigeants
            leaders, status = fetch_leaders_playwright(siren, browser)

            if status == 'RATE_LIMITED':
                print(f"⏸  Rate limit détecté - pause de 60s...")
                time.sleep(60)
                # Réessayer
                leaders, status = fetch_leaders_playwright(siren, browser)

            if status == 'OK':
                if leaders:
                    print(f"✓ {len(leaders)} dirigeant(s): {', '.join(leaders)}")
                else:
                    print("✗ Aucun dirigeant")
            else:
                print(f"✗ {status}")

            # Enregistrer
            dirigeants_results[siren] = {
                'leaders': leaders if leaders else [],
                'status': status,
                'domain': domain
            }

            # Mettre à jour les fichiers sources
            if item['sheet'] == 'feuille1' and leaders:
                feuille1[domain]['dirigeants'] = leaders
            elif item['sheet'] == 'feuille2' and leaders:
                feuille2[domain]['dirigeants'] = leaders

            # Sauvegarder régulièrement
            if idx % 5 == 0:
                with open(DIRIGEANTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(dirigeants_results, f, ensure_ascii=False, indent=2)
                with open(FEUILLE1_RESULTS, 'w', encoding='utf-8') as f:
                    json.dump(feuille1, f, ensure_ascii=False, indent=2)
                with open(FEUILLE2_RESULTS, 'w', encoding='utf-8') as f:
                    json.dump(feuille2, f, ensure_ascii=False, indent=2)

            # Pause pour éviter le rate limiting
            if idx < len(to_process):
                print(f"    ⏱  Pause de {DELAY_BETWEEN_REQUESTS}s...")
                time.sleep(DELAY_BETWEEN_REQUESTS)

        browser.close()

    # Sauvegarder les résultats finaux
    print("\n[3/5] Sauvegarde des résultats...")
    with open(DIRIGEANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(dirigeants_results, f, ensure_ascii=False, indent=2)
    with open(FEUILLE1_RESULTS, 'w', encoding='utf-8') as f:
        json.dump(feuille1, f, ensure_ascii=False, indent=2)
    with open(FEUILLE2_RESULTS, 'w', encoding='utf-8') as f:
        json.dump(feuille2, f, ensure_ascii=False, indent=2)

    # Mise à jour Google Sheets
    print("\n[4/5] Mise à jour des Google Sheets...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    spreadsheet = gc.open_by_key(SHEET_ID)

    # Feuille 1
    print("  Mise à jour Feuille 1...")
    worksheet1 = spreadsheet.worksheet('Feuille 1')
    updates1 = []
    for domain, data in feuille1.items():
        if data.get('row') and data.get('dirigeants'):
            dirigeants_str = ', '.join(data['dirigeants'])
            updates1.append({
                'range': f'G{data["row"]}',
                'values': [[dirigeants_str]]
            })

    if updates1:
        for i in range(0, len(updates1), 100):
            chunk = updates1[i:i+100]
            worksheet1.batch_update(chunk, value_input_option='USER_ENTERED')
            print(f"    Mis à jour {min(i+100, len(updates1))}/{len(updates1)} lignes")
            time.sleep(2)

    # Feuille 2
    print("  Mise à jour Feuille 2...")
    worksheet2 = spreadsheet.worksheet('Feuille 2')
    updates2 = []
    row = 2
    for domain, data in feuille2.items():
        if data.get('dirigeants'):
            dirigeants_str = ', '.join(data['dirigeants'])
            updates2.append({
                'range': f'C{row}',
                'values': [[dirigeants_str]]
            })
        row += 1

    if updates2:
        for i in range(0, len(updates2), 100):
            chunk = updates2[i:i+100]
            worksheet2.batch_update(chunk, value_input_option='USER_ENTERED')
            print(f"    Mis à jour {min(i+100, len(updates2))}/{len(updates2)} lignes")
            time.sleep(2)

    # Stats finales
    print("\n" + "=" * 70)
    print("TERMINÉ !")
    print("=" * 70)
    total_found = sum(1 for d in dirigeants_results.values() if d.get('leaders'))
    print(f"Total entreprises traitées: {len(dirigeants_results)}")
    print(f"Dirigeants trouvés: {total_found}")
    print("=" * 70)

if __name__ == '__main__':
    main()
