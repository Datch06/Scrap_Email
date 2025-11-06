#!/usr/bin/env python3
"""
Re-scraper ASYNCHRONE pour les sites sans emails
Utilise le AsyncEmailFinder avancé pour retrouver des emails sur les sites où on n'en avait pas trouvé

Usage:
    python3 rescrape_no_emails_async.py [--limit 1000] [--concurrent 30]
"""

import asyncio
import aiohttp
import argparse
import time
from database import get_session, Site, SiteStatus
from datetime import datetime
from email_finder_async import AsyncEmailFinder
from typing import List


class AsyncEmailRescraper:
    """Re-scraper asynchrone pour les sites sans emails"""

    def __init__(self, max_concurrent: int = 30):
        """
        Initialiser le re-scraper

        Args:
            max_concurrent: Nombre de requêtes simultanées
        """
        self.max_concurrent = max_concurrent
        self.session = None
        self.finder = None

    async def init_session(self):
        """Initialiser la session aiohttp"""
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )

        self.finder = AsyncEmailFinder(self.session)

    async def close_session(self):
        """Fermer la session aiohttp"""
        if self.session:
            await self.session.close()

    async def rescrape_site(self, site: Site, stats: dict) -> None:
        """Re-scraper un site pour trouver des emails"""

        # Chercher des emails avec le finder avancé
        emails = await self.finder.search_emails_on_domain(site.domain, max_pages=10)

        if emails:
            # Email trouvé !
            site.emails = emails
            site.email_found_at = datetime.utcnow()
            site.email_source = "async_rescraping"
            site.status = SiteStatus.EMAIL_FOUND
            site.updated_at = datetime.utcnow()

            stats['emails_found'] += 1
            print(f"✅ {site.domain[:50]:50} → {emails[:60]}")
        else:
            # Toujours pas d'email
            site.updated_at = datetime.utcnow()
            stats['still_no_email'] += 1
            print(f"❌ {site.domain[:50]:50} → Toujours aucun email")

        site.retry_count += 1

    async def rescrape_batch(self, sites: List[Site], db_session, stats: dict) -> None:
        """Re-scraper un lot de sites"""

        tasks = []
        semaphore = asyncio.Semaphore(self.max_concurrent)

        for site in sites:
            async with semaphore:
                task = self.rescrape_site(site, stats)
                tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Commit tous les changements en une fois
        try:
            db_session.commit()
        except Exception as e:
            print(f"⚠️  Erreur commit: {e}")
            db_session.rollback()

    async def rescrape_all(self, limit: int = None, batch_size: int = 50):
        """
        Re-scraper tous les sites sans emails

        Args:
            limit: Nombre maximum de sites à re-scraper (None = tous)
            batch_size: Taille des lots pour le traitement
        """
        start_time = time.time()

        print("\n" + "="*80)
        print("🔄 RE-SCRAPING ASYNCHRONE DES SITES SANS EMAILS")
        print("="*80)
        print(f"   Concurrence: {self.max_concurrent} requêtes simultanées")
        print(f"   Batch size: {batch_size} sites par lot")
        if limit:
            print(f"   Limite: {limit:,} sites")
        print("="*80)

        # Initialiser la session
        await self.init_session()

        try:
            # Récupérer les sites sans emails
            db_session = get_session()

            # Sites avec "NO EMAIL FOUND" ou email_found = False et actifs
            query = db_session.query(Site).filter(
                Site.is_active == True,
                Site.blacklisted == False,
                (
                    (Site.emails == "NO EMAIL FOUND") |
                    (Site.emails == None) |
                    (Site.emails == "")
                )
            ).order_by(Site.created_at.desc())

            if limit:
                sites = query.limit(limit).all()
            else:
                sites = query.all()

            total_sites = len(sites)

            print(f"\n📊 Sites à re-scraper: {total_sites:,}")

            if total_sites == 0:
                print("✅ Aucun site à re-scraper !")
                return

            stats = {
                'emails_found': 0,
                'still_no_email': 0,
            }

            # Traiter par lots
            for i in range(0, total_sites, batch_size):
                batch = sites[i:i+batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_sites + batch_size - 1) // batch_size

                print(f"\n🔄 Lot {batch_num}/{total_batches} ({len(batch)} sites)")
                print("-"*80)

                batch_start = time.time()

                await self.rescrape_batch(batch, db_session, stats)

                batch_time = time.time() - batch_start
                speed = len(batch) / batch_time if batch_time > 0 else 0

                print(f"\n⏱️  Lot traité en {batch_time:.1f}s ({speed:.1f} sites/sec)")
                print(f"   Emails trouvés dans ce lot: {stats['emails_found']}")

                # Pause entre les lots
                if i + batch_size < total_sites:
                    await asyncio.sleep(1)

            db_session.close()

            # Résumé final
            total_time = time.time() - start_time
            success_rate = (stats['emails_found'] / total_sites * 100) if total_sites > 0 else 0

            print("\n" + "="*80)
            print("✅ RE-SCRAPING TERMINÉ!")
            print("="*80)
            print(f"   Temps total: {total_time:.1f}s ({total_time/60:.1f} minutes)")
            print(f"   Sites re-scrapés: {total_sites:,}")
            print(f"   Emails trouvés: {stats['emails_found']:,} ({success_rate:.1f}%)")
            print(f"   Toujours sans email: {stats['still_no_email']:,}")
            print(f"   Vitesse moyenne: {total_sites/total_time:.1f} sites/sec")
            print("="*80)
            print(f"\n💡 Gain estimé: {stats['emails_found']:,} nouveaux contacts !")
            print("🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")

        finally:
            await self.close_session()


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Re-scraper asynchrone pour sites sans emails")
    parser.add_argument('--limit', type=int, default=None, help='Nombre max de sites à traiter')
    parser.add_argument('--concurrent', type=int, default=30, help='Nombre de requêtes simultanées')
    parser.add_argument('--batch-size', type=int, default=50, help='Taille des lots')

    args = parser.parse_args()

    rescraper = AsyncEmailRescraper(max_concurrent=args.concurrent)

    await rescraper.rescrape_all(
        limit=args.limit,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    asyncio.run(main())
