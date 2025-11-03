#!/usr/bin/env python3
"""
Script pour importer les emails depuis la Feuille 3 (emails trouvés via SIRET/SIREN)
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from db_helper import DBHelper

# Configuration Google Sheets
SPREADSHEET_KEY = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 3'

def get_worksheet():
    """Connexion à la feuille Google Sheets"""
    print("Connexion à Google Sheets...")

    # Utiliser la nouvelle méthode gspread
    gc = gspread.service_account(filename='credentials.json')
    spreadsheet = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    print(f"✓ Connecté à '{WORKSHEET_NAME}'")
    return worksheet


def import_emails_from_sheet():
    """Importer les emails depuis la Feuille 3"""

    try:
        worksheet = get_worksheet()
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return 0

    # Récupérer toutes les données
    print("\nRécupération des données...")
    all_values = worksheet.get_all_values()

    if len(all_values) < 2:
        print("⚠ Feuille vide ou sans données")
        return 0

    # En-têtes (première ligne)
    headers = all_values[0]
    print(f"En-têtes: {headers}")

    # Trouver les index des colonnes
    try:
        domain_col = headers.index('Site') if 'Site' in headers else headers.index('Domain')
        email_col = headers.index('Emails')
    except ValueError as e:
        print(f"❌ Colonne manquante: {e}")
        print(f"Colonnes disponibles: {headers}")
        return 0

    # Colonnes optionnelles
    siret_col = headers.index('SIRET/SIREN') if 'SIRET/SIREN' in headers else None

    imported_count = 0
    updated_count = 0
    skipped_count = 0

    with DBHelper() as db:
        # Parcourir les lignes (en ignorant l'en-tête)
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) <= max(domain_col, email_col):
                continue

            domain = row[domain_col].strip() if domain_col < len(row) else ''
            email = row[email_col].strip() if email_col < len(row) else ''

            if not domain or not email or email == 'NO EMAIL FOUND':
                skipped_count += 1
                continue

            # Ajouter le site s'il n'existe pas
            site = db.add_site(domain, source_url='Feuille 3 - SIRET')

            # Vérifier si le site a déjà des emails
            if site.emails and site.emails != 'NO EMAIL FOUND':
                # Si la source actuelle est "scraping", on ne remplace pas
                if site.email_source == 'scraping':
                    print(f"  ⏭ {domain}: Email déjà trouvé par scraping, non remplacé")
                    skipped_count += 1
                    continue

            # Mettre à jour l'email avec la source "siret"
            db.update_email(domain, email, email_source='siret')

            # Mettre à jour le SIRET si disponible
            if siret_col is not None and siret_col < len(row):
                siret = row[siret_col].strip()
                if siret and siret != 'NON TROUVÉ':
                    db.update_siret(domain, siret, 'SIRET')

            # Mettre à jour le numéro de ligne dans la feuille
            db.session.query(db.Site).filter_by(domain=domain).update({
                'sheet_name': WORKSHEET_NAME,
                'sheet_row': i
            })
            db.session.commit()

            if site.emails and site.emails != email:
                print(f"  ✓ Mis à jour: {domain} (email source: SIRET)")
                updated_count += 1
            else:
                print(f"  ✓ Ajouté: {domain} (email source: SIRET)")
                imported_count += 1

    print(f"\n{'=' * 70}")
    print(f"RÉSUMÉ DE L'IMPORT")
    print(f"{'=' * 70}")
    print(f"  Nouveaux sites avec email: {imported_count}")
    print(f"  Sites mis à jour: {updated_count}")
    print(f"  Sites ignorés: {skipped_count}")
    print(f"  Total traité: {imported_count + updated_count + skipped_count}")
    print(f"{'=' * 70}")

    return imported_count + updated_count


if __name__ == '__main__':
    print("=" * 70)
    print("IMPORT DES EMAILS DEPUIS FEUILLE 3 (Source: SIRET/SIREN)")
    print("=" * 70)
    print()

    total = import_emails_from_sheet()

    print()
    print(f"✓ Import terminé: {total} sites importés/mis à jour")
