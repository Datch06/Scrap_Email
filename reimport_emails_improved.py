#!/usr/bin/env python3
"""
Script amélioré pour ré-importer les emails depuis les CSV
- Concatène plusieurs emails par domaine
- Filtre les emails de tracking (sentry, etc.)
- Marque la source comme 'scraping'
"""

import csv
from collections import defaultdict
from db_helper import DBHelper

# Patterns d'emails à ignorer (tracking, sentry, etc.)
IGNORE_PATTERNS = [
    '@sentry.io',
    '@sentry.wixpress.com',
    '@sentry-next.wixpress.com',
    'noreply@',
    'no-reply@',
    'donotreply@',
    'bounce@',
    'postmaster@',
    'mailer-daemon@'
]

def should_ignore_email(email):
    """Vérifier si un email doit être ignoré"""
    if not email:
        return True

    email_lower = email.lower()

    # Ignorer les patterns connus
    for pattern in IGNORE_PATTERNS:
        if pattern.lower() in email_lower:
            return True

    return False


def import_emails_from_csv(csv_file, db):
    """
    Importer les emails depuis un CSV en concaténant les emails par domaine
    """
    print(f"\n📄 Import depuis {csv_file}...")

    # Grouper les emails par domaine
    emails_by_domain = defaultdict(list)

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').strip()
            email = row.get('email', '').strip()

            if not domain or not email or email == 'NO EMAIL FOUND':
                continue

            # Ignorer les emails de tracking
            if should_ignore_email(email):
                continue

            # Ajouter à la liste
            if email not in emails_by_domain[domain]:
                emails_by_domain[domain].append(email)

    print(f"  📊 Domaines uniques: {len(emails_by_domain)}")

    # Importer dans la base
    imported_count = 0
    updated_count = 0

    for domain, email_list in emails_by_domain.items():
        # Concaténer les emails avec des virgules
        emails_str = ', '.join(email_list)

        # Ajouter le site s'il n'existe pas
        site = db.add_site(domain)

        # Mettre à jour les emails avec source='scraping'
        db.update_email(domain, emails_str, email_source='scraping')

        if len(email_list) > 1:
            print(f"  ✓ {domain}: {len(email_list)} emails")
            updated_count += 1
        else:
            imported_count += 1

    total = imported_count + updated_count
    print(f"  ✓ {total} sites importés ({imported_count} avec 1 email, {updated_count} avec plusieurs)")

    return total


def main():
    print("=" * 70)
    print("RÉ-IMPORT AMÉLIORÉ DES EMAILS")
    print("=" * 70)
    print()
    print("Ce script va:")
    print("  1. Grouper les emails par domaine")
    print("  2. Filtrer les emails de tracking (sentry, etc.)")
    print("  3. Concaténer plusieurs emails avec des virgules")
    print("  4. Marquer tous les emails comme source='scraping'")
    print()

    response = input("Continuer ? (oui/non): ").strip().lower()
    if response not in ['oui', 'o', 'yes', 'y']:
        print("❌ Annulé")
        return

    total_imported = 0

    with DBHelper() as db:
        # Importer les CSV d'emails
        total_imported += import_emails_from_csv('emails_found.csv', db)
        total_imported += import_emails_from_csv('emails_formatted.csv', db)
        total_imported += import_emails_from_csv('emails_cleaned.csv', db)

        # Afficher les statistiques finales
        stats = db.get_stats()

        print("\n" + "=" * 70)
        print("RÉSUMÉ DE L'IMPORT")
        print("=" * 70)
        print(f"Total de domaines traités : {total_imported}")
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
        print("=" * 70)


if __name__ == '__main__':
    main()
