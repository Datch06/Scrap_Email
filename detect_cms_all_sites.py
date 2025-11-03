#!/usr/bin/env python3
"""
Script pour détecter le CMS de tous les sites existants dans la base de données
"""

import sys
from datetime import datetime
from database import get_session, Site
from cms_detector import CMSDetector
import time


def detect_cms_for_all_sites(batch_size=100, max_sites=None, skip_existing=True):
    """
    Détecte le CMS pour tous les sites de la base

    Args:
        batch_size: Nombre de sites à traiter par batch
        max_sites: Nombre maximum de sites à traiter (None = tous)
        skip_existing: Ignorer les sites avec CMS déjà détecté
    """
    session = get_session()
    detector = CMSDetector(timeout=8)

    # Compter les sites à traiter
    query = session.query(Site)

    if skip_existing:
        query = query.filter(Site.cms == None)

    total_sites = query.count()

    if max_sites:
        total_sites = min(total_sites, max_sites)

    print("="*80)
    print("🔍 DÉTECTION CMS POUR TOUS LES SITES")
    print("="*80)
    print(f"Sites à traiter: {total_sites:,}")
    print(f"Batch size: {batch_size}")
    print(f"Skip existing: {skip_existing}")
    print("="*80)
    print()

    processed = 0
    detected = 0
    failed = 0
    skipped = 0

    cms_stats = {}

    offset = 0

    while offset < total_sites:
        # Récupérer un batch de sites
        batch = query.limit(batch_size).offset(offset).all()

        if not batch:
            break

        for site in batch:
            processed += 1

            # Progress
            progress = (processed / total_sites) * 100
            print(f"[{processed:5}/{total_sites}] ({progress:5.1f}%) {site.domain:<50}", end=" ", flush=True)

            try:
                # Détecter le CMS
                result = detector.detect(site.domain)

                if result['cms']:
                    site.cms = result['cms']
                    site.cms_version = result['version']
                    site.cms_detected_at = datetime.utcnow()

                    session.commit()

                    # Statistiques
                    cms_name = result['cms']
                    cms_stats[cms_name] = cms_stats.get(cms_name, 0) + 1

                    detected += 1

                    # Affichage
                    version_str = f"v{result['version']}" if result['version'] else ""
                    print(f"✅ {result['cms']:<15} {version_str}")
                else:
                    skipped += 1
                    print("⚠️  Non détecté")

            except Exception as e:
                failed += 1
                print(f"❌ Erreur: {str(e)[:30]}")
                session.rollback()

            # Pause pour ne pas surcharger
            if processed % 10 == 0:
                time.sleep(1)
            else:
                time.sleep(0.2)

        offset += batch_size

        # Afficher stats intermédiaires tous les 100 sites
        if processed % 100 == 0:
            print()
            print(f"📊 Stats intermédiaires: {detected} CMS détectés, {skipped} non détectés, {failed} erreurs")
            print()

    session.close()

    # Résumé final
    print()
    print("="*80)
    print("✅ DÉTECTION TERMINÉE")
    print("="*80)
    print(f"Sites traités: {processed:,}")
    print(f"CMS détectés: {detected:,}")
    print(f"Non détectés: {skipped:,}")
    print(f"Erreurs: {failed:,}")
    print()

    if cms_stats:
        print("📊 Répartition par CMS:")
        print("-" * 40)
        for cms, count in sorted(cms_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / detected) * 100
            print(f"  {cms:<20} {count:6,} ({percentage:5.1f}%)")

    print("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Détecter le CMS de tous les sites')
    parser.add_argument('--batch-size', type=int, default=100, help='Taille des batchs')
    parser.add_argument('--max-sites', type=int, default=None, help='Nombre maximum de sites à traiter')
    parser.add_argument('--include-existing', action='store_true', help='Réanalyser les sites avec CMS déjà détecté')

    args = parser.parse_args()

    detect_cms_for_all_sites(
        batch_size=args.batch_size,
        max_sites=args.max_sites,
        skip_existing=not args.include_existing
    )
