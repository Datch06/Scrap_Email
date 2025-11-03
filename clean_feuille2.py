#!/usr/bin/env python3
"""
Script pour nettoyer Feuille 2:
- Déplacer les sites avec emails vers Feuille 1 s'ils n'y sont pas déjà
- Supprimer les doublons
- Garder seulement les sites SANS email dans Feuille 2
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

CREDENTIALS_FILE = 'credentials.json'
SHEET_ID = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'

def clean_feuille2():
    print("[INFO] Connexion à Google Sheets...")
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)

    # Charger Feuille 1
    ws1 = sheet.sheet1
    feuille1_data = ws1.get_all_values()
    domaines_f1 = set()
    for row in feuille1_data[1:]:  # Skip header
        if row:
            domaines_f1.add(row[0].lower())

    print(f"[INFO] Feuille 1: {len(domaines_f1)} domaines")

    # Charger Feuille 2
    ws2 = sheet.worksheet('Feuille 2')
    feuille2_data = ws2.get_all_values()

    print(f"[INFO] Feuille 2: {len(feuille2_data)-1} lignes de données")

    # Analyser Feuille 2
    sites_avec_emails = []
    sites_sans_emails = []
    doublons = []

    for row in feuille2_data[1:]:  # Skip header
        if not row or len(row) < 2:
            continue

        domain = row[0]
        emails = row[1] if len(row) > 1 else ''
        date_collecte = row[2] if len(row) > 2 else ''

        # Vérifier si contient des emails (présence de @)
        if '@' in emails and emails != 'NO EMAIL FOUND':
            if domain.lower() in domaines_f1:
                doublons.append(domain)
            else:
                sites_avec_emails.append((domain, emails, date_collecte))
        else:
            sites_sans_emails.append((domain, 'NO EMAIL FOUND', date_collecte))

    print(f"\n[ANALYSE]")
    print(f"  - Sites avec emails (doublons de F1): {len(doublons)}")
    print(f"  - Sites avec emails (pas dans F1): {len(sites_avec_emails)}")
    print(f"  - Sites sans emails: {len(sites_sans_emails)}")

    # 1. Ajouter les sites avec emails à Feuille 1
    if sites_avec_emails:
        print(f"\n[ACTION] Ajout de {len(sites_avec_emails)} sites avec emails dans Feuille 1...")
        start_row = len(feuille1_data) + 1
        data_to_add = [[domain, emails, date_collecte] for domain, emails, date_collecte in sites_avec_emails]
        ws1.update(values=data_to_add, range_name=f'A{start_row}')
        print(f"  ✓ {len(sites_avec_emails)} sites ajoutés à Feuille 1")

    # 2. Réécrire Feuille 2 avec seulement les sites sans emails
    print(f"\n[ACTION] Nettoyage de Feuille 2 (garder seulement sites SANS emails)...")

    # Effacer tout sauf le header
    ws2.clear()

    # Réécrire le header + sites sans emails
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    new_data = [['Domain', 'Status', 'Date Collecte']]

    for domain, status, date_collecte in sites_sans_emails:
        new_data.append([domain, status, date_collecte if date_collecte else today])

    ws2.update(values=new_data, range_name='A1')
    print(f"  ✓ Feuille 2 nettoyée: {len(sites_sans_emails)} sites sans emails conservés")

    if doublons:
        print(f"  ✓ {len(doublons)} doublons supprimés")

    print(f"\n✅ TERMINÉ!")
    print(f"📊 Google Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print(f"\nRésumé:")
    print(f"  - Feuille 1: {len(domaines_f1) + len(sites_avec_emails)} domaines (avec emails)")
    print(f"  - Feuille 2: {len(sites_sans_emails)} domaines (sans emails)")

if __name__ == '__main__':
    clean_feuille2()
