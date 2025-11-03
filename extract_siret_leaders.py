#!/usr/bin/env python3
"""
Script pour extraire SIRET et dirigeants pour tous les sites de la base
"""

import sys
from datetime import datetime
from database import get_session, Site
from siret_extractor import SiretExtractor
from leaders_extractor import LeadersExtractor
import time


def extract_siret_and_leaders(batch_size=50, max_sites=None, skip_existing_siret=True, skip_existing_leaders=True, delay=2):
    """
    Extrait SIRET et dirigeants pour tous les sites

    Args:
        batch_size: Nombre de sites à traiter par batch
        max_sites: Nombre maximum de sites à traiter (None = tous)
        skip_existing_siret: Ignorer les sites avec SIRET déjà trouvé
        skip_existing_leaders: Ignorer les sites avec dirigeants déjà trouvés
        delay: Délai en secondes entre chaque requête (éviter rate limit)
    """
    session = get_session()
    siret_extractor = SiretExtractor()
    leaders_extractor = LeadersExtractor()

    # Construire la requête
    query = session.query(Site)

    if skip_existing_siret:
        query = query.filter(Site.siret_checked == False)

    total_sites = query.count()

    if max_sites:
        total_sites = min(total_sites, max_sites)

    print("="*80)
    print("🔍 EXTRACTION SIRET ET DIRIGEANTS")
    print("="*80)
    print(f"Sites à traiter: {total_sites:,}")
    print(f"Batch size: {batch_size}")
    print(f"Delay: {delay}s")
    print(f"Skip existing SIRET: {skip_existing_siret}")
    print(f"Skip existing leaders: {skip_existing_leaders}")
    print("="*80)
    print()

    processed = 0
    siret_found = 0
    leaders_found = 0
    errors = 0

    offset = 0

    while offset < total_sites:
        # Récupérer un batch
        batch = query.limit(batch_size).offset(offset).all()

        if not batch:
            break

        for site in batch:
            processed += 1
            progress = (processed / total_sites) * 100

            print(f"[{processed:5}/{total_sites}] ({progress:5.1f}%) {site.domain:<50}", end=" ", flush=True)

            try:
                # ÉTAPE 1 : Extraire SIRET si nécessaire
                if not site.siret_checked or not skip_existing_siret:
                    result = siret_extractor.extract_from_domain(site.domain)

                    if result:
                        site.siret = result.get('siret')
                        site.siren = result.get('siren')
                        site.siret_type = result.get('type')
                        site.siret_found_at = datetime.utcnow()
                        siret_found += 1
                        print(f"✅ SIRET:{result.get('siret') or result.get('siren')[:14]}", end=" ")
                    else:
                        site.siret = 'NON TROUVÉ'
                        print("⚠️  Pas de SIRET", end=" ")

                    site.siret_checked = True

                # ÉTAPE 2: Extraire dirigeants si on a un SIREN
                if site.siren and site.siren != 'NON TROUVÉ':
                    if not site.leaders_checked or not skip_existing_leaders:
                        leaders_result = leaders_extractor.extract_from_siren(site.siren)

                        if leaders_result['status'] == 'rate_limited':
                            print("⏸  Rate limit - pause 60s...")
                            time.sleep(60)
                            # Réessayer
                            leaders_result = leaders_extractor.extract_from_siren(site.siren)

                        if leaders_result['leaders']:
                            site.leaders = '; '.join(leaders_result['leaders'])
                            site.leaders_found_at = datetime.utcnow()
                            leaders_found += 1
                            print(f"👤 {len(leaders_result['leaders'])} dir.")
                        else:
                            site.leaders = 'NON TROUVÉ'
                            print("👤 Pas de dir.")

                        site.leaders_checked = True
                else:
                    print()

                # Commit
                session.commit()

            except Exception as e:
                print(f"❌ Erreur: {str(e)[:30]}")
                session.rollback()
                errors += 1

            # Pause pour éviter rate limiting
            if processed % 10 == 0:
                time.sleep(delay * 2)
            else:
                time.sleep(delay)

        offset += batch_size

        # Stats intermédiaires
        if processed % 100 == 0:
            print()
            print(f"📊 Stats: {siret_found} SIRET, {leaders_found} dirigeants, {errors} erreurs")
            print()

    session.close()

    # Résumé final
    print()
    print("="*80)
    print("✅ EXTRACTION TERMINÉE")
    print("="*80)
    print(f"Sites traités: {processed:,}")
    print(f"SIRET trouvés: {siret_found:,}")
    print(f"Dirigeants trouvés: {leaders_found:,}")
    print(f"Erreurs: {errors:,}")
    print("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Extraire SIRET et dirigeants')
    parser.add_argument('--batch-size', type=int, default=50, help='Taille des batchs')
    parser.add_argument('--max-sites', type=int, default=None, help='Nombre maximum de sites')
    parser.add_argument('--include-existing-siret', action='store_true', help='Re-analyser les sites avec SIRET')
    parser.add_argument('--include-existing-leaders', action='store_true', help='Re-analyser les dirigeants')
    parser.add_argument('--delay', type=float, default=2.0, help='Délai entre requêtes (secondes)')

    args = parser.parse_args()

    extract_siret_and_leaders(
        batch_size=args.batch_size,
        max_sites=args.max_sites,
        skip_existing_siret=not args.include_existing_siret,
        skip_existing_leaders=not args.include_existing_leaders,
        delay=args.delay
    )
