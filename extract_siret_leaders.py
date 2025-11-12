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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


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
    # Session temporaire pour lire la liste des sites
    temp_session = get_session()

    # Construire la requête
    query = temp_session.query(Site.id, Site.domain, Site.siret_checked, Site.leaders_checked)

    if skip_existing_siret:
        query = query.filter(Site.siret_checked == False)

    total_sites = query.count()

    if max_sites:
        total_sites = min(total_sites, max_sites)

    # Récupérer la liste des sites (id, domain) pour éviter de garder la session ouverte
    sites_to_process = query.limit(total_sites).all()
    temp_session.close()

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

    siret_extractor = SiretExtractor()
    leaders_extractor = LeadersExtractor()

    processed = 0
    siret_found = 0
    leaders_found = 0
    errors = 0

    for site_id, site_domain, siret_checked, leaders_checked in sites_to_process:
        processed += 1
        progress = (processed / total_sites) * 100

        print(f"[{processed:5}/{total_sites}] ({progress:5.1f}%) {site_domain:<50}", end=" ", flush=True)

        # CRÉER UNE SESSION DÉDIÉE pour ce site (évite les locks)
        engine = create_engine(
            'sqlite:///scrap_email.db',
            connect_args={'timeout': 30, 'check_same_thread': False},
            poolclass=NullPool
        )
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Charger le site avec cette session dédiée
            site = session.query(Site).filter_by(id=site_id).first()

            if not site:
                print("❌ Site introuvable")
                continue

            # ÉTAPE 1 : Extraire SIRET si nécessaire
            if not site.siret_checked or not skip_existing_siret:
                result = siret_extractor.extract_from_domain(site_domain)

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

            # Commit avec retry
            for retry in range(3):
                try:
                    session.commit()
                    break
                except Exception as e:
                    if "locked" in str(e).lower() and retry < 2:
                        time.sleep(2)
                        session.rollback()
                    else:
                        raise

        except Exception as e:
            print(f"❌ Erreur: {str(e)[:30]}")
            try:
                session.rollback()
            except:
                pass
            errors += 1

        finally:
            # IMPORTANT : Fermer la session et disposer de l'engine
            session.close()
            engine.dispose()

        # Pause pour éviter rate limiting
        if processed % 10 == 0:
            time.sleep(delay * 2)
        else:
            time.sleep(delay)

        # Stats intermédiaires
        if processed % 100 == 0:
            print()
            print(f"📊 Stats: {siret_found} SIRET, {leaders_found} dirigeants, {errors} erreurs")
            print()

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
