#!/usr/bin/env python3
"""
Script pour supprimer les sites gouvernementaux et gros médias du Google Sheet
"""
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 2'
RESULTS_FILE = 'feuille2_results.json'

# Domaines à exclure
EXCLUDED_PATTERNS = [
    # Sites gouvernementaux
    '.gouv.fr',
    # Gros médias nationaux
    '20minutes.fr',
    'lefigaro.fr',
    'lequipe.fr',
    'ouest-france.fr',
    'franceinfo.fr',
    'francebleu.fr',
    'france3-regions.',
    'tf1info.fr',
    'europe1.fr',
    'rtl.fr',
    'rfi.fr',
    'cnews.fr',
    'linternaute.fr',
    'lemonde.fr',
    'liberation.fr',
    'lesechos.fr',
    'latribune.fr',
    'capital.fr',
    'marianne.net',
    'lexpress.fr',
    'challenges.fr',
    'lepoint.fr',
    'nouvelobs.com',
    'lavoixdunord.fr',
    'midilibre.fr',
    'ladepeche.fr',
    'lindependant.fr',
    'lunion.fr',
    'lyonne.fr',
    'lepopulaire.fr',
    'lamontagne.fr',
    'letelegramme.fr',
    'courrier-picard.fr',
    'nordlittoral.fr',
    'centrepresseaveyron.fr',
    'lardennais.fr',
    'nrpyrenees.fr',
    'petitbleu.fr',
    'monde-diplomatique.fr',
    # Gros médias - magazines people/féminins
    'closermag.fr',
    'voici.fr',
    'gala.fr',
    'moncarnet-gala.fr',
    'telestar.fr',
    'femmeactuelle.fr',
    'marieclaire.fr',
    'journaldesfemmes.fr',
    'madame.lefigaro.fr',
    'leparisien',
    # Gros sites généralistes
    'tripadvisor.',
    'pinterest.',
    'wikipedia.',
    'facebook.',
    'twitter.',
    'instagram.',
    'youtube.',
    'linkedin.',
    'google.',
    'apple.',
    'microsoft.',
    'amazon.',
]

def should_exclude(domain):
    """Vérifie si un domaine doit être exclu"""
    if not domain:
        return False

    domain_lower = domain.lower()

    for pattern in EXCLUDED_PATTERNS:
        if pattern in domain_lower:
            return True

    return False

def main():
    # Charger les résultats
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        results = json.load(f)

    print(f"[INFO] {len(results)} domaines dans le fichier JSON")

    # Filtrer les domaines
    domains_to_remove = []
    filtered_results = {}

    for domain, data in results.items():
        if should_exclude(domain):
            domains_to_remove.append(domain)
        else:
            filtered_results[domain] = data

    print(f"\n[INFO] {len(domains_to_remove)} domaines à supprimer:")
    for domain in sorted(domains_to_remove)[:20]:
        print(f"  - {domain}")
    if len(domains_to_remove) > 20:
        print(f"  ... et {len(domains_to_remove) - 20} autres")

    print(f"\n[INFO] {len(filtered_results)} domaines restants")

    # Sauvegarder les résultats filtrés
    backup_file = 'feuille2_results_backup.json'
    print(f"\n[INFO] Sauvegarde de l'original vers {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Sauvegarde des résultats filtrés dans {RESULTS_FILE}")
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(filtered_results, f, indent=2, ensure_ascii=False)

    # Connexion au Google Sheet
    print("\n[INFO] Connexion à Google Sheets...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(WORKSHEET_NAME)

    print("[INFO] Récupération des données...")
    all_values = worksheet.get_all_values()

    if not all_values:
        print("[ERROR] Sheet vide")
        return

    header = all_values[0]
    print(f"[INFO] Colonnes: {header}")

    # Identifier les lignes à supprimer
    rows_to_delete = []

    for idx, row in enumerate(all_values[1:], start=2):
        if not row:
            continue

        domain = row[0] if row else ''
        if domain and should_exclude(domain):
            rows_to_delete.append(idx)

    print(f"\n[INFO] {len(rows_to_delete)} lignes à supprimer du Google Sheet")

    if not rows_to_delete:
        print("[INFO] Aucune ligne à supprimer")
        return

    # Supprimer les lignes (en commençant par la fin pour ne pas décaler les indices)
    print("[INFO] Suppression des lignes...")
    for row_idx in sorted(rows_to_delete, reverse=True):
        worksheet.delete_rows(row_idx)
        print(f"  Supprimé ligne {row_idx}")

    print("\n" + "=" * 70)
    print(f"[DONE] {len(rows_to_delete)} lignes supprimées")
    print(f"Domaines restants: {len(filtered_results)}")
    print("=" * 70)

if __name__ == '__main__':
    main()
