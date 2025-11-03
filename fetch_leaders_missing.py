#!/usr/bin/env python3
"""
Script pour récupérer les dirigeants des sites qui ont SIRET mais pas de dirigeants
Tourne EN PARALLÈLE de l'import principal

Usage:
    python3 fetch_leaders_missing.py
"""

import sys
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

from db_helper import DBHelper
from database import Site

# ============================================================================
# CONFIGURATION
# ============================================================================

DELAY_BETWEEN_REQUESTS = 30  # 30 secondes entre requêtes (éviter rate limit)
STATS_INTERVAL = 10  # Stats tous les 10 sites
BATCH_SIZE = 100  # Traiter par batches

# ============================================================================
# PATTERNS POUR DIRIGEANTS
# ============================================================================

LEADER_PATTERNS = [
    re.compile(r'Président\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'Directeur\s+[Gg]énéral\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'Gérant\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
    re.compile(r'([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)\s*-?\s*Président', re.IGNORECASE),
    re.compile(r'([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)\s*-?\s*Directeur', re.IGNORECASE),
    re.compile(r'PDG\s*:?\s*([A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+(?:\s+[A-ZÉÈÊËÀÂÄÔÖÙÛÜÇ][a-zéèêëàâäôöùûüç]+)+)', re.IGNORECASE),
]

# ============================================================================
# FONCTIONS
# ============================================================================

def get_siren_from_siret(siret):
    """Extrait le SIREN (9 premiers chiffres) du SIRET"""
    if not siret:
        return None
    siret_clean = siret.replace(' ', '')
    if len(siret_clean) >= 9:
        return siret_clean[:9]
    elif len(siret_clean) == 9:
        return siret_clean
    return None


def fetch_leaders_playwright(siren, browser):
    """Récupère les dirigeants via Playwright"""
    try:
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Recherche sur societe.com
        url = f"https://www.societe.com/cgi-bin/search?champs={siren}"
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        text = page.inner_text('body')

        # Vérifier si rate limit
        if 'trop de requêtes' in text.lower() or 'too many requests' in text.lower():
            context.close()
            return None, 'RATE_LIMITED'

        # Chercher le lien de l'entreprise
        html = page.content()
        company_link_pattern = re.compile(r'href="(/societe/[^"]+\.html)"')
        match = company_link_pattern.search(html)

        if not match:
            context.close()
            return [], 'NOT_FOUND'

        company_url = "https://www.societe.com" + match.group(1)

        # Charger la page entreprise
        page.goto(company_url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        text = page.inner_text('body')

        # Vérifier rate limit
        if 'trop de requêtes' in text.lower() or 'too many requests' in text.lower():
            context.close()
            return None, 'RATE_LIMITED'

        # Chercher les dirigeants
        leaders = []
        for pattern in LEADER_PATTERNS:
            matches = pattern.findall(text)
            leaders.extend(matches)

        # Dédupliquer et nettoyer
        leaders = list(set(leaders))
        leaders = [l.strip() for l in leaders if len(l.strip()) > 3]

        context.close()

        return leaders, 'OK'

    except Exception as e:
        return None, f'ERROR: {str(e)}'


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("👔 RÉCUPÉRATION DIRIGEANTS - Sites avec SIRET sans dirigeants")
    print("=" * 80)
    print()
    print("⚡ Tourne EN PARALLÈLE de l'import principal")
    print("⏱️  30 secondes entre chaque requête (éviter rate limit)")
    print()

    # Récupérer les sites avec SIRET mais sans dirigeants
    with DBHelper() as db:
        sites_to_process = db.session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ',
            # Pas encore de dirigeants
            (Site.leaders.is_(None)) | (Site.leaders == '') | (Site.leaders == 'NON TROUVÉ')
        ).all()

        total = len(sites_to_process)
        print(f"📊 Sites à traiter: {total}")
        print()

        if total == 0:
            print("✅ Tous les sites avec SIRET ont déjà des dirigeants!")
            return

    # Lancer Playwright
    processed = 0
    found = 0
    not_found = 0
    rate_limited = 0
    errors = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        with DBHelper() as db:
            for i, site in enumerate(sites_to_process, 1):
                # Extraire SIREN
                siren = get_siren_from_siret(site.siret)
                if not siren:
                    print(f"  [{i}/{total}] {site.domain}: ⚠️  SIRET invalide")
                    continue

                print(f"  [{i}/{total}] {site.domain} (SIREN: {siren})... ", end='', flush=True)

                # Chercher dirigeants
                leaders, status = fetch_leaders_playwright(siren, browser)

                if status == 'RATE_LIMITED':
                    print("⏸️  RATE LIMIT - Attente 60s")
                    rate_limited += 1
                    time.sleep(60)
                    # Réessayer
                    leaders, status = fetch_leaders_playwright(siren, browser)

                if status == 'OK' and leaders:
                    leaders_str = '; '.join(leaders)
                    db.update_leaders(site.domain, leaders_str)
                    found += 1
                    print(f"✅ {len(leaders)} dirigeant(s): {leaders_str[:50]}...")
                elif status == 'NOT_FOUND' or (status == 'OK' and not leaders):
                    db.update_leaders(site.domain, 'NON TROUVÉ')
                    not_found += 1
                    print("❌ Non trouvé")
                else:
                    errors += 1
                    print(f"⚠️  {status}")

                processed += 1

                # Stats intermédiaires
                if processed % STATS_INTERVAL == 0:
                    stats = db.get_stats()
                    print(f"\n{'🔥'*40}")
                    print(f"📈 STATISTIQUES (Progression: {processed}/{total})")
                    print(f"{'🔥'*40}")
                    print(f"   Traités: {processed}")
                    print(f"   Trouvés: {found} ({found/processed*100:.1f}%)")
                    print(f"   Non trouvés: {not_found}")
                    print(f"   Erreurs: {errors}")
                    print(f"\n   BASE TOTALE:")
                    print(f"   Sites: {stats['total']}")
                    print(f"   Dirigeants: {stats['with_leaders']} ({stats['with_leaders']/stats['total']*100:.1f}%)")
                    print(f"{'🔥'*40}\n")

                # Pause entre requêtes
                if i < total:
                    time.sleep(DELAY_BETWEEN_REQUESTS)

        browser.close()

    # Stats finales
    print(f"\n{'='*80}")
    print(f"✅ TERMINÉ!")
    print(f"{'='*80}")
    print(f"   Sites traités: {processed}/{total}")
    print(f"   Dirigeants trouvés: {found} ({found/processed*100:.1f}%)")
    print(f"   Non trouvés: {not_found}")
    print(f"   Erreurs: {errors}")
    print(f"{'='*80}")
    print()
    print(f"🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur (Ctrl+C)")
        print("✅ Tous les dirigeants trouvés jusqu'ici sont en base!")
        sys.exit(0)
