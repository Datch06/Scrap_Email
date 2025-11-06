#!/usr/bin/env python3
"""
Script de test pour le scraper asynchrone
Teste la recherche d'emails sur quelques sites de la base
"""

import asyncio
import aiohttp
from email_finder_async import AsyncEmailFinder
from database import get_session, Site
import sys


async def test_email_finder():
    """Tester le finder sur quelques sites de la base"""
    print("\n" + "="*80)
    print("🧪 TEST DU SCRAPER ASYNCHRONE")
    print("="*80)

    # Récupérer 5 sites de la base sans emails
    db_session = get_session()
    sites = db_session.query(Site).filter(
        Site.emails == "NO EMAIL FOUND",
        Site.is_active == True,
        Site.blacklisted == False
    ).limit(5).all()

    if not sites:
        print("❌ Aucun site sans email trouvé dans la base")
        return

    print(f"\n📊 Test sur {len(sites)} sites sans emails")
    print("-"*80)

    # Créer session
    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        finder = AsyncEmailFinder(session)

        results = []
        for i, site in enumerate(sites, 1):
            print(f"\n[{i}/{len(sites)}] 🔍 {site.domain}")

            emails = await finder.search_emails_on_domain(site.domain, max_pages=5)

            if emails:
                print(f"   ✅ Email trouvé: {emails}")
                results.append((site.domain, emails, True))
            else:
                print(f"   ❌ Aucun email trouvé")
                results.append((site.domain, None, False))

    db_session.close()

    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)

    found_count = sum(1 for _, _, found in results if found)
    success_rate = (found_count / len(results) * 100) if results else 0

    print(f"   Sites testés: {len(results)}")
    print(f"   Emails trouvés: {found_count}")
    print(f"   Taux de réussite: {success_rate:.1f}%")

    if found_count > 0:
        print("\n✅ Emails trouvés:")
        for domain, emails, found in results:
            if found:
                print(f"   • {domain}: {emails}")

    print("\n" + "="*80)
    print("✅ Test terminé !")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_email_finder())
