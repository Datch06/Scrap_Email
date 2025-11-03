#!/usr/bin/env python3
"""
Script pour importer les emails depuis emails_cleaned.csv
Ce fichier contient déjà les emails filtrés et formatés
"""

import csv
from db_helper import DBHelper

def main():
    print("=" * 70)
    print("IMPORT DES EMAILS DEPUIS emails_cleaned.csv")
    print("=" * 70)
    print()

    csv_file = 'emails_cleaned.csv'
    imported_count = 0
    updated_count = 0
    skipped_count = 0

    with DBHelper() as db:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                domain = row.get('Domain', '').strip()
                emails = row.get('Emails', '').strip()

                if not domain:
                    continue

                # Ignorer si pas d'email trouvé
                if not emails or emails == 'NO EMAIL FOUND':
                    skipped_count += 1
                    continue

                # Ajouter le site s'il n'existe pas
                site = db.add_site(domain)

                # Vérifier si le site a déjà des emails
                if site.emails and site.emails != 'NO EMAIL FOUND' and site.emails != emails:
                    print(f"  ℹ️  {domain}: Email existant remplacé")
                    print(f"      Ancien: {site.emails[:80]}...")
                    print(f"      Nouveau: {emails[:80]}...")
                    updated_count += 1
                elif not site.emails or site.emails == 'NO EMAIL FOUND':
                    print(f"  ✓ {domain}: {emails[:80]}{'...' if len(emails) > 80 else ''}")
                    imported_count += 1
                else:
                    # Emails identiques
                    skipped_count += 1
                    continue

                # Mettre à jour les emails avec source='scraping'
                db.update_email(domain, emails, email_source='scraping')

        # Afficher les statistiques finales
        stats = db.get_stats()

        print("\n" + "=" * 70)
        print("RÉSUMÉ DE L'IMPORT")
        print("=" * 70)
        print(f"Nouveaux emails importés : {imported_count}")
        print(f"Emails mis à jour : {updated_count}")
        print(f"Domaines sans email (ignorés) : {skipped_count}")
        print(f"\nStatistiques de la base de données :")
        print(f"  📊 Total sites : {stats['total']}")
        print(f"  ✉️  Avec email : {stats['with_email']}")
        print(f"  🏢 Avec SIRET : {stats['with_siret']}")
        print(f"  👔 Avec dirigeants : {stats['with_leaders']}")

        if stats['total'] > 0:
            print(f"\nTaux de complétion :")
            print(f"  Email : {stats['with_email'] / stats['total'] * 100:.1f}%")
            print(f"  SIRET : {stats['with_siret'] / stats['total'] * 100:.1f}%")
            print(f"  Dirigeants : {stats['with_leaders'] / stats['total'] * 100:.1f}%")

        print("=" * 70)
        print("✓ Import terminé !")
        print("\nVous pouvez vérifier sur: https://admin.perfect-cocon-seo.fr")
        print("=" * 70)


if __name__ == '__main__':
    main()
