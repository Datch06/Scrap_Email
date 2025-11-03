#!/usr/bin/env python3
"""
Script pour importer les emails depuis la Feuille 1 (emails trouvés via scraping)
"""

import gspread
from db_helper import DBHelper

# Configuration Google Sheets
SPREADSHEET_KEY = '19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I'
WORKSHEET_NAME = 'Feuille 1'

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
    """Importer les emails depuis la Feuille 1"""

    try:
        worksheet = get_worksheet()
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return 0

    # Récupérer toutes les données
    print("\nRécupération des données...")
    all_values = worksheet.get_all_values()

    if len(all_values) < 1:
        print("⚠ Feuille vide ou sans données")
        return 0

    print(f"Total de lignes trouvées: {len(all_values)}")
    print(f"Exemple première ligne: {all_values[0][:3]}...")

    # Structure sans en-tête:
    # Colonne 0: Domain
    # Colonne 1: Emails
    # Colonne 2: Date
    # Colonne 3: SIRET/SIREN
    # Colonne 4: Type ou autre SIRET
    # Colonne 5+: Dirigeants (optionnel)

    domain_col = 0
    email_col = 1
    date_col = 2
    siret_col = 3
    siret2_col = 4
    leaders_col = 5  # Peut varier

    imported_count = 0
    updated_count = 0
    skipped_count = 0

    with DBHelper() as db:
        # Parcourir toutes les lignes (pas d'en-tête à ignorer)
        for i, row in enumerate(all_values, start=1):
            if len(row) <= max(domain_col, email_col):
                continue

            domain = row[domain_col].strip() if domain_col < len(row) else ''
            email = row[email_col].strip() if email_col < len(row) else ''

            if not domain:
                continue

            # Ajouter le site s'il n'existe pas
            site = db.add_site(domain, source_url='Feuille 1')

            # Mettre à jour l'email s'il est présent et non vide
            has_email = email and email != '' and email != 'NO EMAIL FOUND'

            if has_email:
                # Vérifier si le site a déjà des emails de meilleure qualité
                if site.emails and site.emails != 'NO EMAIL FOUND' and site.emails != email:
                    # Si les emails sont différents, on peut vouloir conserver l'ancien ou le combiner
                    print(f"  ℹ️  {domain}: Email existant différent")
                    print(f"      Ancien: {site.emails[:60]}...")
                    print(f"      Nouveau: {email[:60]}...")
                    updated_count += 1
                elif not site.emails or site.emails == 'NO EMAIL FOUND':
                    print(f"  ✓ {domain}: {email[:60]}{'...' if len(email) > 60 else ''}")
                    imported_count += 1
                else:
                    skipped_count += 1
                    continue

                # Mettre à jour l'email avec la source "scraping"
                db.update_email(domain, email, email_source='scraping')

            # Mettre à jour le SIRET si disponible
            if siret_col < len(row):
                siret = row[siret_col].strip()
                if siret and siret != '' and siret != 'NON TROUVÉ':
                    db.update_siret(domain, siret, 'SIRET')

            # Mettre à jour les dirigeants si disponibles
            if leaders_col < len(row):
                leaders = row[leaders_col].strip()
                if leaders and leaders != '' and leaders != 'NON TROUVÉ':
                    db.update_leaders(domain, leaders)

            # Mettre à jour le numéro de ligne dans la feuille
            from database import Site as SiteModel
            db.session.query(SiteModel).filter_by(domain=domain).update({
                'sheet_name': WORKSHEET_NAME,
                'sheet_row': i
            })
            db.session.commit()

    print(f"\n{'=' * 70}")
    print(f"RÉSUMÉ DE L'IMPORT")
    print(f"{'=' * 70}")
    print(f"  Nouveaux sites avec email: {imported_count}")
    print(f"  Sites mis à jour: {updated_count}")
    print(f"  Sites sans email (ignorés): {skipped_count}")
    print(f"  Total traité: {imported_count + updated_count + skipped_count}")
    print(f"{'=' * 70}")

    return imported_count + updated_count


if __name__ == '__main__':
    print("=" * 70)
    print("IMPORT DES EMAILS DEPUIS FEUILLE 1 (Source: Scraping)")
    print("=" * 70)
    print()

    total = import_emails_from_sheet()

    print()
    print(f"✓ Import terminé: {total} sites importés/mis à jour")
    print("\nVérifiez les statistiques sur: https://admin.perfect-cocon-seo.fr/api/stats")
