#!/usr/bin/env python3
"""
Script pour blacklister les domaines invalides (numéros SIREN/nombres)
"""

import sys
sys.path.insert(0, '/var/www/Scrap_Email')

from database import get_session, Site
from datetime import datetime

def cleanup_numeric_domains():
    """Blackliste tous les domaines qui sont uniquement des chiffres"""
    session = get_session()

    try:
        # Compter d'abord
        all_sites = session.query(Site).all()
        numeric_sites = []

        print("Recherche des domaines numériques...")
        for site in all_sites:
            if site.domain and site.domain.isdigit():
                numeric_sites.append(site)

        print(f"\nTrouvé {len(numeric_sites)} domaines numériques sur {len(all_sites)} sites")

        if not numeric_sites:
            print("✓ Aucun domaine numérique à nettoyer")
            return

        # Afficher quelques exemples
        print(f"\nExemples:")
        for site in numeric_sites[:10]:
            print(f"  ID {site.id}: {site.domain}")

        # Demander confirmation
        response = input(f"\nVoulez-vous blacklister ces {len(numeric_sites)} domaines? (oui/non): ")

        if response.lower() != 'oui':
            print("Opération annulée")
            return

        # Blacklister
        count = 0
        for site in numeric_sites:
            if not site.blacklisted:
                site.blacklisted = True
                site.blacklist_reason = "Domaine invalide (numéro SIREN/numérique)"
                site.blacklisted_at = datetime.utcnow()
                count += 1

        session.commit()

        print(f"\n✓ {count} domaines blacklistés")
        print(f"  {len(numeric_sites) - count} étaient déjà blacklistés")

    except Exception as e:
        session.rollback()
        print(f"✗ Erreur: {e}")
        raise

    finally:
        session.close()


if __name__ == '__main__':
    cleanup_numeric_domains()
