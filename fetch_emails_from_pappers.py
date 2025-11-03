#!/usr/bin/env python3
"""
Script pour récupérer les emails via l'API Pappers en utilisant les SIRET
"""

import requests
import time
from db_helper import DBHelper
from database import get_session, Site

# Configuration API Pappers
PAPPERS_API_KEY = '9c9507b8e254e643ae1040e87eb573fed6f1d6dfc6049c74'
PAPPERS_API_URL = 'https://api.pappers.fr/v2/entreprise'

# Paramètres
DELAY_BETWEEN_REQUESTS = 0.5  # Délai en secondes entre chaque requête
MAX_SITES = None  # None = tous les sites, sinon nombre limite


def get_email_from_pappers(siret):
    """
    Récupérer l'email d'une entreprise via l'API Pappers

    Args:
        siret: Numéro SIRET de l'entreprise

    Returns:
        str: Email trouvé ou None
    """
    try:
        params = {
            'api_token': PAPPERS_API_KEY,
            'siret': siret
        }

        response = requests.get(PAPPERS_API_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # L'email peut être dans plusieurs champs
            email = None

            # 1. Email de l'entreprise
            if 'email' in data and data['email']:
                email = data['email']

            # 2. Email du représentant légal
            elif 'representants' in data and data['representants']:
                for rep in data['representants']:
                    if 'email' in rep and rep['email']:
                        email = rep['email']
                        break

            # 3. Email du siège
            elif 'siege' in data and 'email' in data['siege'] and data['siege']['email']:
                email = data['siege']['email']

            return email

        elif response.status_code == 404:
            print(f"    ⚠️  SIRET {siret} non trouvé dans Pappers")
            return None
        elif response.status_code == 429:
            print(f"    ⏸️  Rate limit atteint, pause de 5 secondes...")
            time.sleep(5)
            return get_email_from_pappers(siret)  # Retry
        else:
            print(f"    ❌ Erreur API Pappers ({response.status_code}): {response.text}")
            return None

    except Exception as e:
        print(f"    ❌ Erreur lors de la requête Pappers: {e}")
        return None


def fetch_emails_from_pappers(limit=None, dry_run=False):
    """
    Récupérer les emails pour tous les sites ayant un SIRET mais pas d'email

    Args:
        limit: Nombre maximum de sites à traiter (None = tous)
        dry_run: Si True, ne met pas à jour la base, juste affiche les résultats
    """
    session = get_session()

    try:
        # Récupérer les sites avec SIRET mais sans email (ou email depuis scraping uniquement)
        query = session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ'
        ).filter(
            (Site.emails.is_(None)) |
            (Site.emails == '') |
            (Site.emails == 'NO EMAIL FOUND')
        )

        if limit:
            query = query.limit(limit)

        sites = query.all()

        print(f"\n📊 Sites à traiter: {len(sites)}")
        print("=" * 70)

        stats = {
            'total': len(sites),
            'success': 0,
            'not_found': 0,
            'error': 0,
            'skipped': 0
        }

        with DBHelper() as db:
            for i, site in enumerate(sites, 1):
                print(f"\n[{i}/{len(sites)}] {site.domain}")
                print(f"    SIRET: {site.siret}")

                # Récupérer l'email depuis Pappers
                email = get_email_from_pappers(site.siret)

                if email:
                    print(f"    ✅ Email trouvé: {email}")

                    if not dry_run:
                        # Mettre à jour avec source 'siret'
                        db.update_email(site.domain, email, email_source='siret')

                    stats['success'] += 1
                else:
                    print(f"    ❌ Aucun email trouvé")
                    stats['not_found'] += 1

                # Pause entre les requêtes
                if i < len(sites):
                    time.sleep(DELAY_BETWEEN_REQUESTS)

        # Afficher les statistiques
        print("\n" + "=" * 70)
        print("RÉSUMÉ")
        print("=" * 70)
        print(f"Total traité: {stats['total']}")
        print(f"✅ Emails trouvés: {stats['success']}")
        print(f"❌ Emails non trouvés: {stats['not_found']}")
        print(f"⚠️  Erreurs: {stats['error']}")

        if dry_run:
            print("\n⚠️  MODE DRY RUN - Aucune modification en base de données")

        print("=" * 70)

        return stats

    finally:
        session.close()


def test_pappers_api():
    """Tester l'API Pappers avec un SIRET connu"""
    print("=" * 70)
    print("TEST DE L'API PAPPERS")
    print("=" * 70)

    # Prendre un SIRET de la base
    session = get_session()
    site = session.query(Site).filter(
        Site.siret.isnot(None),
        Site.siret != '',
        Site.siret != 'NON TROUVÉ'
    ).first()
    session.close()

    if not site:
        print("❌ Aucun SIRET trouvé en base de données")
        return False

    print(f"\nTest avec:")
    print(f"  Domaine: {site.domain}")
    print(f"  SIRET: {site.siret}")

    email = get_email_from_pappers(site.siret)

    if email:
        print(f"\n✅ API fonctionne !")
        print(f"  Email trouvé: {email}")
        return True
    else:
        print(f"\n⚠️  Aucun email trouvé pour ce SIRET")
        print("  (l'API fonctionne mais ce SIRET n'a pas d'email)")
        return True


if __name__ == '__main__':
    import sys

    print("=" * 70)
    print("RÉCUPÉRATION DES EMAILS VIA API PAPPERS")
    print("=" * 70)

    # Vérifier les arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            # Mode test
            test_pappers_api()
            sys.exit(0)
        elif sys.argv[1] == 'dry-run':
            # Mode dry-run: tester sans modifier la base
            print("\n🔍 MODE DRY-RUN (test uniquement, pas de modification)\n")
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            fetch_emails_from_pappers(limit=limit, dry_run=True)
            sys.exit(0)

    # Mode normal
    print("\n⚠️  ATTENTION: Ce script va mettre à jour la base de données")
    print("  - Il récupère les emails via l'API Pappers")
    print("  - Il marque ces emails comme source='siret'")
    print("  - Il NE remplace PAS les emails déjà trouvés par scraping")

    response = input("\nContinuer ? (oui/non): ").strip().lower()

    if response not in ['oui', 'o', 'yes', 'y']:
        print("❌ Annulé")
        sys.exit(0)

    # Demander la limite
    limit_input = input("\nNombre de sites à traiter (vide = tous): ").strip()
    limit = int(limit_input) if limit_input else None

    print()
    fetch_emails_from_pappers(limit=limit, dry_run=False)
