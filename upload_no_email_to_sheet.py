#!/usr/bin/env python3
"""
Script pour uploader les domaines sans email dans Feuille 2
"""

import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'

def upload_domains_no_email(domains_file):
    """Upload les domaines sans email dans Feuille 2"""

    # Lire les domaines
    with open(domains_file, 'r', encoding='utf-8') as f:
        domains = [line.strip() for line in f if line.strip()]

    print(f"[INFO] {len(domains)} domaines sans email à uploader")

    # Connexion au sheet
    print("[INFO] Connexion à Google Sheets...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)

    # Vérifier si Feuille 2 existe
    try:
        worksheet = sheet.worksheet('Feuille 2')
        print("[INFO] Feuille 2 trouvée")
    except:
        print("[INFO] Création de Feuille 2...")
        worksheet = sheet.add_worksheet(title='Feuille 2', rows=1000, cols=3)
        worksheet.update(values=[['Domain', 'Status', 'Date Collecte']], range_name='A1')

    # Charger les domaines existants pour éviter les doublons
    existing_records = worksheet.get_all_values()
    existing_domains = set()
    for row in existing_records[1:]:  # Skip header
        if row:
            existing_domains.add(row[0].lower())

    print(f"[INFO] {len(existing_domains)} domaines déjà dans Feuille 2")

    # Préparer les données (seulement les nouveaux)
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')

    data = []
    for domain in domains:
        if domain.lower() not in existing_domains:
            data.append([domain, 'NO EMAIL FOUND', today])

    if data:
        # Ajouter à la suite des données existantes
        start_row = len(existing_records) + 1
        print(f"[INFO] Upload de {len(data)} nouveaux domaines à partir de la ligne {start_row}...")
        worksheet.update(values=data, range_name=f'A{start_row}')
        print(f"[SUCCESS] ✓ {len(data)} domaines sans email uploadés dans Feuille 2!")
    else:
        print(f"[INFO] Aucun nouveau domaine à ajouter (tous sont déjà présents)")

    print(f"\n📊 Google Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 upload_no_email_to_sheet.py <domains_file.txt>")
        sys.exit(1)

    domains_file = sys.argv[1]
    if not Path(domains_file).exists():
        print(f"[ERROR] Fichier {domains_file} introuvable")
        sys.exit(1)

    upload_domains_no_email(domains_file)
