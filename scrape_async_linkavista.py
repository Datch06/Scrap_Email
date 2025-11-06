#!/usr/bin/env python3
"""
Scraper ASYNCHRONE ultra-rapide pour LinkAvista MarketLink
Utilise asyncio + aiohttp pour scraper 2000+ sites/minute

Performance attendue: 4-5x plus rapide que le scraper synchrone
"""

import asyncio
import aiohttp
import time
import re
from bs4 import BeautifulSoup
from database import get_session, Site, SiteStatus
from datetime import datetime
from typing import List, Set, Optional
import sys
from email_finder_async import AsyncEmailFinder

class AsyncLinkAvistaScraper:
    def __init__(self, email: str, password: str, max_concurrent: int = 50):
        """
        Initialiser le scraper asynchrone

        Args:
            email: Email LinkAvista
            password: Mot de passe LinkAvista
            max_concurrent: Nombre de requêtes simultanées (défaut: 50)
        """
        self.email = email
        self.password = password
        self.max_concurrent = max_concurrent
        self.base_url = "https://linkavista.com"
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def login(self) -> bool:
        """Se connecter à LinkAvista de manière asynchrone"""
        print(f"🔐 Connexion à LinkAvista...")

        try:
            # Créer une session aiohttp avec cookie jar
            connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            )

            # Obtenir le CSRF token
            async with self.session.get(f"{self.base_url}/login") as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf_input = soup.find('input', {'name': '_token'})
                csrf_token = csrf_input.get('value') if csrf_input else None

            # Se connecter
            login_data = {
                'email': self.email,
                'password': self.password,
            }
            if csrf_token:
                login_data['_token'] = csrf_token

            async with self.session.post(
                f"{self.base_url}/login",
                data=login_data,
                allow_redirects=True
            ) as response:
                html = await response.text()

                if 'logout' in html.lower() and response.status == 200:
                    print("✅ Connexion réussie!")
                    return True
                else:
                    print(f"❌ Échec de connexion")
                    return False

        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False

    async def extract_urls_from_page(self, page_num: int, filter_type: str = "normal") -> List[str]:
        """Extraire toutes les URLs d'une page de manière asynchrone"""
        try:
            # Construire l'URL selon le filtre
            if filter_type == "normal":
                url = f"{self.base_url}/marketlink" if page_num == 1 else f"{self.base_url}/marketlink/page/{page_num}"
            elif filter_type == "sensitive":
                if page_num == 1:
                    url = f"{self.base_url}/marketlink?show_sensitive_categories=on&sensitive_category_id=1"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}?show_sensitive_categories=on&sensitive_category_id=1"
            elif filter_type == "gnews":
                if page_num == 1:
                    url = f"{self.base_url}/marketlink?is_gnews=on"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}?is_gnews=on"
            else:
                return []

            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return []

                html = await response.text()

                # Extraire les URLs
                urls = re.findall(r'"url":"([^"]+)"', html)
                urls = list(set(urls))  # Dédupliquer

                return urls

        except asyncio.TimeoutError:
            return []
        except Exception as e:
            return []

    async def search_email_on_site(self, domain: str) -> Optional[str]:
        """Chercher un email sur un site de manière asynchrone avec le finder avancé"""
        # Utiliser le AsyncEmailFinder pour une recherche plus complète
        finder = AsyncEmailFinder(self.session)
        return await finder.search_emails_on_domain(domain, max_pages=8)

    async def process_domain(self, domain: str, db_session, stats: dict) -> None:
        """Traiter un domaine: chercher email et ajouter en base"""

        # Exclure les domaines .gouv.fr
        if domain.endswith('.gouv.fr'):
            stats['skipped'] += 1
            return

        # Vérifier si déjà en base
        existing = db_session.query(Site).filter_by(domain=domain).first()
        if existing:
            stats['skipped'] += 1
            return

        # Chercher l'email
        email = await self.search_email_on_site(domain)

        if email:
            stats['emails_found'] += 1

        # Créer l'entrée en base
        site = Site(
            domain=domain,
            source_url="https://linkavista.com/marketlink",
            emails=email if email else "NO EMAIL FOUND",
            email_checked=True,
            email_found_at=datetime.utcnow() if email else None,
            email_source="linkavista_async_scraping",
            status=SiteStatus.EMAIL_FOUND if email else SiteStatus.EMAIL_NOT_FOUND,
            created_at=datetime.utcnow()
        )

        db_session.add(site)

        try:
            db_session.commit()
            stats['added'] += 1
        except Exception as e:
            # Rollback en cas d'erreur (doublon concurrent)
            db_session.rollback()
            stats['skipped'] += 1

    async def process_domains_batch(self, domains: List[str], db_session, stats: dict, semaphore: asyncio.Semaphore) -> None:
        """Traiter un lot de domaines avec limitation de concurrence"""
        tasks = []

        for domain in domains:
            async with semaphore:
                task = self.process_domain(domain, db_session, stats)
                tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def extract_all_domains(self, max_pages: int = 100) -> Set[str]:
        """Extraire tous les domaines avec tous les filtres de manière asynchrone"""
        print("\n📥 PHASE 1: Extraction ASYNCHRONE de tous les domaines")
        print("="*80)

        all_domains = set()

        # Configuration des filtres
        filters = [
            ("Normal", "normal", max_pages),
            ("Sensitive", "sensitive", max_pages),
            ("Google News", "gnews", 20),
        ]

        for filter_name, filter_type, max_p in filters:
            print(f"\n🔍 Filtre: {filter_name}")
            print("-"*80)

            initial_count = len(all_domains)

            # Créer les tâches pour toutes les pages du filtre
            tasks = []
            for page in range(1, max_p + 1):
                tasks.append(self.extract_urls_from_page(page, filter_type))

            # Exécuter toutes les pages en parallèle
            print(f"⚡ Extraction de {max_p} pages en parallèle...")
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Traiter les résultats
            for page_num, urls in enumerate(results, 1):
                if isinstance(urls, Exception) or not urls:
                    continue

                new_urls = [u for u in urls if u not in all_domains]
                all_domains.update(urls)
                print(f"📄 Page {page_num:3}/{max_p} → {len(urls):3} sites (+{len(new_urls):3} nouveaux) | Total: {len(all_domains):,}")

            filter_added = len(all_domains) - initial_count
            print(f"✅ {filter_name}: +{filter_added:,} domaines supplémentaires")

        print(f"\n🎯 TOTAL FINAL: {len(all_domains):,} domaines uniques extraits")
        return all_domains

    async def scrape_async(self, max_pages: int = 100, batch_size: int = 50):
        """
        Scraper asynchrone complet

        Args:
            max_pages: Nombre maximum de pages à scraper par filtre
            batch_size: Taille des lots pour le traitement parallèle
        """
        start_time = time.time()

        print("\n" + "="*80)
        print("🚀 SCRAPING LINKAVISTA ASYNCHRONE - ULTRA RAPIDE")
        print("="*80)
        print(f"   Concurrence: {self.max_concurrent} requêtes simultanées")
        print(f"   Batch size: {batch_size} domaines par lot")
        print("="*80)

        # Se connecter
        if not await self.login():
            return

        try:
            # PHASE 1: Extraire tous les domaines
            all_domains = await self.extract_all_domains(max_pages)

            extraction_time = time.time() - start_time
            print(f"\n⏱️  Temps d'extraction: {extraction_time:.1f}s ({len(all_domains)/extraction_time:.1f} domaines/sec)")

            # PHASE 2: Recherche d'emails et ajout en base
            print("\n📧 PHASE 2: Recherche d'emails ASYNCHRONE et ajout en base")
            print("="*80)

            db_session = get_session()
            stats = {
                'added': 0,
                'skipped': 0,
                'emails_found': 0,
            }

            # Créer un sémaphore pour limiter la concurrence
            semaphore = asyncio.Semaphore(self.max_concurrent)

            # Traiter les domaines par lots
            domains_list = sorted(all_domains)
            total_domains = len(domains_list)

            for i in range(0, total_domains, batch_size):
                batch = domains_list[i:i+batch_size]
                batch_start = time.time()

                print(f"\n🔄 Traitement du lot {i//batch_size + 1}/{(total_domains + batch_size - 1)//batch_size} ({len(batch)} domaines)...")

                # Traiter le lot en parallèle
                tasks = []
                for domain in batch:
                    async with semaphore:
                        task = self.process_domain(domain, db_session, stats)
                        tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

                batch_time = time.time() - batch_start
                speed = len(batch) / batch_time if batch_time > 0 else 0

                print(f"✅ Lot traité en {batch_time:.1f}s ({speed:.1f} sites/sec)")
                print(f"   Ajoutés: {stats['added']:,} | Ignorés: {stats['skipped']:,} | Emails: {stats['emails_found']:,}")

            db_session.close()

            # Résumé final
            total_time = time.time() - start_time

            print("\n" + "="*80)
            print("✅ SCRAPING ASYNCHRONE TERMINÉ!")
            print("="*80)
            print(f"   Temps total: {total_time:.1f}s ({total_time/60:.1f} minutes)")
            print(f"   Domaines extraits: {len(all_domains):,}")
            print(f"   Sites ajoutés: {stats['added']:,}")
            print(f"   Sites ignorés: {stats['skipped']:,}")
            print(f"   Emails trouvés: {stats['emails_found']:,}")
            if stats['added'] > 0:
                print(f"   Taux de découverte: {(stats['emails_found']/stats['added']*100):.1f}%")
            print(f"   Vitesse moyenne: {len(all_domains)/total_time:.1f} domaines/sec")
            print(f"   Gain de performance: ~4-5x plus rapide que le scraper synchrone")
            print("="*80)
            print("\n🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")

        finally:
            # Fermer la session aiohttp
            if self.session:
                await self.session.close()


async def main():
    """Point d'entrée principal"""
    EMAIL = "datchdigital@gmail.com"
    PASSWORD = "B-BJoqV7"
    MAX_CONCURRENT = 50  # Nombre de requêtes simultanées
    BATCH_SIZE = 100     # Taille des lots pour le traitement
    MAX_PAGES = 100      # Pages à scraper par filtre

    scraper = AsyncLinkAvistaScraper(
        email=EMAIL,
        password=PASSWORD,
        max_concurrent=MAX_CONCURRENT
    )

    await scraper.scrape_async(
        max_pages=MAX_PAGES,
        batch_size=BATCH_SIZE
    )


if __name__ == "__main__":
    # Configurer la politique d'event loop pour Windows (si nécessaire)
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Lancer le scraper asynchrone
    asyncio.run(main())
