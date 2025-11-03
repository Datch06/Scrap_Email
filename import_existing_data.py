#!/usr/bin/env python3
"""
Script pour importer les données existantes dans la base de données
"""

import json
import csv
from pathlib import Path
from db_helper import DBHelper


def import_from_csv(csv_file, db):
    """Importer des sites depuis un fichier CSV"""
    print(f"\n📄 Import depuis {csv_file}...")

    if not Path(csv_file).exists():
        print(f"  ⚠ Fichier non trouvé: {csv_file}")
        return 0

    count = 0
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain') or row.get('Domain')
            if not domain:
                continue

            # Ajouter le site
            site = db.add_site(domain)

            # Ajouter email si présent
            email = row.get('email') or row.get('Emails')
            if email and email != 'NO EMAIL FOUND':
                db.update_email(domain, email)

            # Ajouter SIRET si présent
            siret = row.get('SIRET/SIREN') or row.get('siret_siren')
            if siret and siret != 'NON TROUVÉ':
                siret_type = row.get('Type') or row.get('type') or 'SIRET'
                db.update_siret(domain, siret, siret_type)

            # Ajouter dirigeants si présent
            leaders = row.get('Dirigeants') or row.get('leaders')
            if leaders and leaders != 'NON TROUVÉ':
                db.update_leaders(domain, leaders)

            count += 1

    print(f"  ✓ {count} sites importés")
    return count


def import_from_json(json_file, db):
    """Importer des sites depuis un fichier JSON"""
    print(f"\n📄 Import depuis {json_file}...")

    if not Path(json_file).exists():
        print(f"  ⚠ Fichier non trouvé: {json_file}")
        return 0

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for domain, info in data.items():
        # Ajouter le site
        site = db.add_site(domain)

        # Ajouter SIRET si présent
        siret = info.get('siret')
        if siret and siret != 'NON TROUVÉ':
            db.update_siret(domain, siret, 'SIRET')

        # Ajouter dirigeants si présent
        leaders = info.get('dirigeants')
        if leaders:
            if isinstance(leaders, list):
                db.update_leaders(domain, leaders)
            elif leaders != 'NON TROUVÉ':
                db.update_leaders(domain, leaders)

        count += 1

    print(f"  ✓ {count} sites importés")
    return count


def import_from_txt(txt_file, db, source_url=None):
    """Importer une liste de domaines depuis un fichier texte"""
    print(f"\n📄 Import depuis {txt_file}...")

    if not Path(txt_file).exists():
        print(f"  ⚠ Fichier non trouvé: {txt_file}")
        return 0

    count = 0
    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            domain = line.strip()
            if domain and not domain.startswith('#'):
                db.add_site(domain, source_url)
                count += 1

    print(f"  ✓ {count} domaines importés")
    return count


def main():
    print("=" * 70)
    print("IMPORT DES DONNÉES EXISTANTES")
    print("=" * 70)

    total_imported = 0

    with DBHelper() as db:
        # Importer les CSV d'emails
        total_imported += import_from_csv('emails_found.csv', db)
        total_imported += import_from_csv('emails_formatted.csv', db)
        total_imported += import_from_csv('emails_cleaned.csv', db)

        # Importer les résultats JSON
        total_imported += import_from_json('feuille1_results.json', db)
        total_imported += import_from_json('feuille2_results.json', db)
        total_imported += import_from_json('dirigeants_results.json', db)

        # Importer les listes de domaines
        total_imported += import_from_txt('domains_fr_only.txt', db, 'ladepeche.fr')
        total_imported += import_from_txt('domains_ladepeche_cleaned.txt', db, 'ladepeche.fr')
        total_imported += import_from_txt('domains_marca_filtered.txt', db, 'marca.com')

        # Afficher les statistiques finales
        stats = db.get_stats()

        print("\n" + "=" * 70)
        print("RÉSUMÉ DE L'IMPORT")
        print("=" * 70)
        print(f"Total de sites importés : {total_imported}")
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
        print("\nVous pouvez maintenant lancer l'interface :")
        print("  python3 app.py")
        print("=" * 70)


if __name__ == '__main__':
    main()
