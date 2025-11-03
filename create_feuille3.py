#!/usr/bin/env python3
"""
Créer Feuille 3 avec uniquement les sites ayant SIRET + Dirigeants
"""

import json
import gspread
from time import sleep

# Configuration
CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
FEUILLE1_RESULTS = 'feuille1_results.json'
FEUILLE2_RESULTS = 'feuille2_results.json'

def main():
    print("=" * 70)
    print("CRÉATION FEUILLE 3 - SITES AVEC SIRET + DIRIGEANTS")
    print("=" * 70)

    # Charger les résultats
    print("\n[1/4] Chargement des données...")
    with open(FEUILLE1_RESULTS, 'r', encoding='utf-8') as f:
        feuille1 = json.load(f)

    with open(FEUILLE2_RESULTS, 'r', encoding='utf-8') as f:
        feuille2 = json.load(f)

    # Collecter les sites avec SIRET ET dirigeants
    print("[2/4] Collecte des sites avec SIRET + Dirigeants...")
    sites_complets = []

    for domain, data in feuille1.items():
        siret = data.get('siret')
        dirigeants = data.get('dirigeants', [])

        if siret and siret != 'NON TROUVÉ' and dirigeants:
            sites_complets.append({
                'domain': domain,
                'siret': siret,
                'dirigeants': ', '.join(dirigeants),
                'source': 'Feuille 1'
            })

    for domain, data in feuille2.items():
        siret = data.get('siret')
        dirigeants = data.get('dirigeants', [])

        if siret and siret != 'NON TROUVÉ' and dirigeants:
            sites_complets.append({
                'domain': domain,
                'siret': siret,
                'dirigeants': ', '.join(dirigeants),
                'source': 'Feuille 2'
            })

    print(f"[INFO] {len(sites_complets)} sites avec SIRET + Dirigeants trouvés")

    # Connexion Google Sheets
    print("\n[3/4] Connexion à Google Sheets...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    spreadsheet = gc.open_by_key(SHEET_ID)

    # Créer ou vider Feuille 3
    try:
        worksheet = spreadsheet.worksheet('Feuille 3')
        print("[INFO] Feuille 3 existe, vidage...")
        worksheet.clear()
    except:
        print("[INFO] Création de la Feuille 3...")
        worksheet = spreadsheet.add_worksheet(title='Feuille 3', rows=len(sites_complets)+1, cols=4)

    # Préparer les données
    print("[4/4] Remplissage de la Feuille 3...")

    # En-têtes
    headers = [['Domaine', 'SIRET/SIREN', 'Dirigeants', 'Source']]
    worksheet.update('A1:D1', headers, value_input_option='USER_ENTERED')

    # Formater les en-têtes
    worksheet.format('A1:D1', {
        'textFormat': {'bold': True},
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
    })

    # Données
    data_rows = []
    for site in sites_complets:
        data_rows.append([
            site['domain'],
            site['siret'],
            site['dirigeants'],
            site['source']
        ])

    # Upload par batch
    if data_rows:
        batch_size = 500
        for i in range(0, len(data_rows), batch_size):
            chunk = data_rows[i:i+batch_size]
            start_row = i + 2  # +2 car ligne 1 = header
            end_row = start_row + len(chunk) - 1

            worksheet.update(f'A{start_row}:D{end_row}', chunk, value_input_option='USER_ENTERED')
            print(f"  Lignes {start_row}-{end_row} ajoutées ({min(i+batch_size, len(data_rows))}/{len(data_rows)})")
            sleep(2)

    print("\n" + "=" * 70)
    print("TERMINÉ !")
    print("=" * 70)
    print(f"Feuille 3 créée avec {len(sites_complets)} sites")
    print(f"Lien: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={worksheet.id}")
    print("=" * 70)

if __name__ == '__main__':
    main()
