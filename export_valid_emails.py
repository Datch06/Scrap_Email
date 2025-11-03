#!/usr/bin/env python3
"""
Export des emails validés uniquement (status = 'valid' et deliverable = True)
"""

from database import get_session, Site
import csv
from datetime import datetime
import json

def export_valid_emails(output_file='valid_emails.csv', min_score=80):
    """
    Exporter les emails valides dans un fichier CSV

    Args:
        output_file: Nom du fichier de sortie
        min_score: Score minimum (0-100) pour considérer l'email comme valide
    """
    session = get_session()

    try:
        # Requête pour les emails valides
        query = session.query(Site).filter(
            Site.email_validated == True,
            Site.email_validation_status == 'valid',
            Site.email_deliverable == True,
            Site.email_validation_score >= min_score
        ).order_by(Site.email_validation_score.desc())

        sites = query.all()
        total = len(sites)

        if total == 0:
            print(f"❌ Aucun email valide trouvé (score >= {min_score})")
            return

        print(f"📊 {total} emails valides trouvés (score >= {min_score})")
        print(f"📝 Export vers {output_file}...")

        # Créer le CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # En-tête
            writer.writerow([
                'Email',
                'Domaine',
                'Score',
                'Validation Date',
                'SIRET',
                'Dirigeants',
                'Source URL'
            ])

            # Données
            for site in sites:
                # Nettoyer les emails (prendre le premier si plusieurs)
                emails_list = site.emails.replace(';', ',').split(',')
                primary_email = emails_list[0].strip() if emails_list else ''

                writer.writerow([
                    primary_email,
                    site.domain,
                    site.email_validation_score,
                    site.email_validation_date.strftime('%Y-%m-%d %H:%M:%S') if site.email_validation_date else '',
                    site.siret or '',
                    site.leaders or '',
                    site.source_url or ''
                ])

        print(f"✅ Export réussi : {output_file}")
        print(f"📈 Total emails exportés : {total}")

        # Stats par score
        scores = {}
        for site in sites:
            score_range = f"{(site.email_validation_score // 10) * 10}-{(site.email_validation_score // 10) * 10 + 9}"
            scores[score_range] = scores.get(score_range, 0) + 1

        print("\n📊 Répartition par score:")
        for score_range in sorted(scores.keys(), reverse=True):
            print(f"   {score_range}: {scores[score_range]} emails")

    finally:
        session.close()


def export_all_validation_results(output_file='all_validation_results.csv'):
    """Exporter tous les résultats de validation (valides, invalides, risqués)"""
    session = get_session()

    try:
        sites = session.query(Site).filter(
            Site.email_validated == True
        ).order_by(Site.email_validation_score.desc()).all()

        total = len(sites)
        print(f"📊 {total} emails validés trouvés")
        print(f"📝 Export vers {output_file}...")

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # En-tête
            writer.writerow([
                'Email',
                'Domaine',
                'Status',
                'Score',
                'Deliverable',
                'Details Syntaxe',
                'Details DNS',
                'Details SMTP',
                'Validation Date'
            ])

            # Données
            for site in sites:
                emails_list = site.emails.replace(';', ',').split(',')
                primary_email = emails_list[0].strip() if emails_list else ''

                # Parser les détails JSON
                details = json.loads(site.email_validation_details) if site.email_validation_details else {}

                writer.writerow([
                    primary_email,
                    site.domain,
                    site.email_validation_status or '',
                    site.email_validation_score,
                    'Oui' if site.email_deliverable else 'Non',
                    details.get('syntax', {}).get('message', ''),
                    details.get('dns', {}).get('message', ''),
                    details.get('smtp', {}).get('message', '') if details.get('smtp') else '',
                    site.email_validation_date.strftime('%Y-%m-%d %H:%M:%S') if site.email_validation_date else ''
                ])

        print(f"✅ Export réussi : {output_file}")

        # Stats par statut
        stats = {
            'valid': 0,
            'invalid': 0,
            'risky': 0,
            'unknown': 0
        }

        for site in sites:
            status = site.email_validation_status or 'unknown'
            stats[status] = stats.get(status, 0) + 1

        print("\n📊 Répartition par statut:")
        print(f"   ✅ Valides: {stats.get('valid', 0)}")
        print(f"   ❌ Invalides: {stats.get('invalid', 0)}")
        print(f"   ⚠️  Risqués: {stats.get('risky', 0)}")
        print(f"   ❓ Inconnus: {stats.get('unknown', 0)}")

    finally:
        session.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Exporter les emails validés')
    parser.add_argument('--output', '-o', default='valid_emails.csv', help='Fichier de sortie')
    parser.add_argument('--min-score', type=int, default=80, help='Score minimum (0-100)')
    parser.add_argument('--all', action='store_true', help='Exporter tous les résultats (pas seulement valides)')

    args = parser.parse_args()

    print("=" * 70)
    print("📧 EXPORT DES EMAILS VALIDÉS")
    print("=" * 70)
    print()

    if args.all:
        export_all_validation_results(args.output)
    else:
        export_valid_emails(args.output, args.min_score)

    print()
    print("=" * 70)
