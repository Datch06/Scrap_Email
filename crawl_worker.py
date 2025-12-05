#!/usr/bin/env python3
"""
Worker de crawl distribué pour serveurs distants

Ce script tourne sur les serveurs distants et:
1. Demande des tâches au serveur central via l'API
2. Crawle les sites vendeurs pour trouver les acheteurs
3. Cherche les emails des acheteurs
4. Envoie les résultats au serveur central
5. Envoie des heartbeats périodiques

Usage:
    python3 crawl_worker.py --api-url https://admin.perfect-cocon-seo.fr

    # Ou en arrière-plan:
    nohup python3 crawl_worker.py --api-url https://admin.perfect-cocon-seo.fr > crawl_worker.log 2>&1 &

Configuration via arguments ou variables d'environnement:
    --api-url       URL de l'API centrale (défaut: https://admin.perfect-cocon-seo.fr)
    --worker-id     ID unique du worker (défaut: worker_<hostname>)
    --batch-size    Nombre de sites par batch (défaut: 5)
    --concurrent    Requêtes simultanées (défaut: 20)
    --max-pages     Pages max par site (défaut: 5000)
"""

import asyncio
import aiohttp
import ssl
import socket
import time
import re
import argparse
import json
import os
import signal
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime
from collections import deque
from typing import Set, List, Dict, Optional, Tuple

# Configuration par défaut
DEFAULT_API_URL = "https://admin.perfect-cocon-seo.fr"
DEFAULT_BATCH_SIZE = 30
DEFAULT_CONCURRENT = 50
DEFAULT_MAX_PAGES = 5000
HEARTBEAT_INTERVAL = 30  # secondes
REQUEST_TIMEOUT = 15  # secondes
PAUSE_BETWEEN_SITES = 0.5  # secondes

# Patterns pour extraction
SOCIAL_DOMAINS = {
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'tiktok.com', 'pinterest.com', 'google.com',
    'apple.com', 'microsoft.com', 'amazon.com', 'amazon.fr'
}

EXCLUDED_PATTERNS = {
    'google.com', 'apple.com', 'microsoft.com', 'mozilla.org',
    'amazon.com', 'amazon.es', 'amazon.fr', 'amzn.to',
    'uecdn.es', 'cloudflare.com', 'akamai.net'
}

BLACKLISTED_DOMAINS = {
    'cnil.fr', 'gouv.fr', 'diplomatie.gouv.fr', 'education.gouv.fr',
    'economie.gouv.fr', 'interieur.gouv.fr', 'service-public.fr',
    'legifrance.gouv.fr', 'senat.fr', 'assemblee-nationale.fr'
}

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
IGNORE_EMAILS = {
    'example@example.com', 'email@example.com', 'contact@example.com',
    'test@test.com', 'noreply@example.com', 'vous@domaine.com',
}

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

# État global
running = True
current_task = None
pages_crawled = 0


def signal_handler(signum, frame):
    """Gestionnaire de signal pour arrêt propre"""
    global running
    print(f"\n⚠️  Signal {signum} reçu, arrêt en cours...")
    running = False


def extract_domain(url: str) -> Optional[str]:
    """Extraire le domaine d'une URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain = domain.replace('www.', '')
        return domain if domain else None
    except:
        return None


def is_blacklisted_domain(domain: str) -> bool:
    """Vérifier si un domaine est blacklisté"""
    if not domain:
        return True
    if domain in BLACKLISTED_DOMAINS:
        return True
    for blacklisted in BLACKLISTED_DOMAINS:
        if domain.endswith('.' + blacklisted):
            return True
    return False


def is_valid_fr_domain(domain: str) -> bool:
    """Vérifier si c'est un domaine .fr valide"""
    if not domain or not domain.endswith('.fr'):
        return False
    if is_blacklisted_domain(domain):
        return False
    for excluded in EXCLUDED_PATTERNS:
        if excluded in domain:
            return False
    for social in SOCIAL_DOMAINS:
        if social in domain:
            return False
    return True


def normalize_url(base: str, url: str) -> Optional[str]:
    """Normaliser une URL"""
    url = url.strip()
    if not url or url.startswith(('mailto:', 'javascript:', 'tel:', '#')):
        return None
    parsed = urlparse(url)
    if not parsed.scheme:
        url = urljoin(base, url)
        parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    return parsed.scheme + '://' + parsed.netloc + parsed.path


class CrawlWorker:
    """Worker de crawl distribué"""

    def __init__(self, api_url: str, worker_id: str, batch_size: int,
                 concurrent: int, max_pages: int):
        self.api_url = api_url.rstrip('/')
        self.worker_id = worker_id
        self.batch_size = batch_size
        self.max_concurrent = concurrent
        self.max_pages = max_pages
        self.hostname = socket.gethostname()

        # SSL context permissif
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Statistiques
        self.stats = {
            'tasks_completed': 0,
            'buyers_found': 0,
            'emails_found': 0,
            'errors': 0,
            'pages_crawled': 0
        }

        print(f"🚀 Worker initialisé:")
        print(f"   - ID: {self.worker_id}")
        print(f"   - Hostname: {self.hostname}")
        print(f"   - API: {self.api_url}")
        print(f"   - Batch size: {self.batch_size}")
        print(f"   - Concurrent: {self.max_concurrent}")
        print(f"   - Max pages/site: {self.max_pages}")

    async def fetch_page(self, session: aiohttp.ClientSession, url: str,
                         semaphore: asyncio.Semaphore) -> Optional[str]:
        """Récupérer une page"""
        try:
            async with semaphore:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    ssl=self.ssl_context,
                    headers={'User-Agent': DEFAULT_USER_AGENT}
                ) as response:
                    if response.status == 200:
                        return await response.text()
        except:
            pass
        return None

    async def extract_links(self, html: str) -> List[str]:
        """Extraire les liens d'une page HTML"""
        links = []
        try:
            # Parser simple avec regex (évite dépendance lxml)
            href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
            links = href_pattern.findall(html)
        except:
            pass
        return links

    async def find_email(self, session: aiohttp.ClientSession, domain: str,
                         semaphore: asyncio.Semaphore) -> Optional[str]:
        """Chercher l'email de contact d'un domaine"""
        pages = ['/', '/contact', '/contact-us', '/mentions-legales', '/a-propos']
        emails = set()

        for page in pages[:5]:
            url = f"https://{domain}{page}"
            html = await self.fetch_page(session, url, semaphore)

            if html:
                matches = EMAIL_PATTERN.findall(html)
                for email in matches:
                    email = email.lower().strip()
                    if email not in IGNORE_EMAILS:
                        if not any(ext in email for ext in ['.png', '.jpg', '.gif', '.js', '.css']):
                            emails.add(email)

        return '; '.join(sorted(emails)) if emails else None

    async def crawl_seller(self, session: aiohttp.ClientSession,
                           site_id: int, domain: str, url: str) -> Dict:
        """
        Crawler un site vendeur pour trouver les acheteurs

        Returns:
            Dict avec buyers, pages_crawled, error
        """
        global current_task, pages_crawled

        current_task = domain
        pages_crawled = 0

        print(f"  🔍 Crawling {domain}...")

        semaphore = asyncio.Semaphore(self.max_concurrent)
        visited = set()
        to_visit = deque([url])
        buyer_domains = set()
        seller_domain = extract_domain(url)

        while to_visit and len(visited) < self.max_pages and running:
            batch_urls = []
            while to_visit and len(batch_urls) < self.max_concurrent:
                next_url = to_visit.popleft()
                if next_url not in visited:
                    batch_urls.append(next_url)
                    visited.add(next_url)

            if not batch_urls:
                break

            # Crawler le batch en parallèle
            tasks = [self.fetch_page(session, u, semaphore) for u in batch_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url_crawled, html in zip(batch_urls, results):
                pages_crawled += 1

                if isinstance(html, Exception) or not html:
                    continue

                # Extraire les liens
                links = await self.extract_links(html)

                for link in links:
                    normalized = normalize_url(url_crawled, link)
                    if not normalized:
                        continue

                    link_domain = extract_domain(normalized)

                    # Lien interne -> ajouter à la queue
                    if link_domain == seller_domain:
                        if normalized not in visited:
                            to_visit.append(normalized)

                    # Domaine .fr externe -> acheteur potentiel
                    elif is_valid_fr_domain(link_domain):
                        buyer_domains.add(link_domain)

            # Progress
            if len(visited) % 100 == 0:
                print(f"    📄 {len(visited)} pages, {len(buyer_domains)} acheteurs...")

        print(f"    ✓ {len(visited)} pages crawlées, {len(buyer_domains)} acheteurs")

        # Chercher les emails des acheteurs
        buyers = []
        for buyer_domain in buyer_domains:
            email = await self.find_email(session, buyer_domain, semaphore)
            buyers.append({
                'domain': buyer_domain,
                'email': email
            })
            if email:
                self.stats['emails_found'] += 1

        self.stats['pages_crawled'] += len(visited)
        self.stats['buyers_found'] += len(buyers)

        return {
            'site_id': site_id,
            'domain': domain,
            'buyers': buyers,
            'pages_crawled': len(visited),
            'error': None
        }

    async def get_tasks(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Demander des tâches au serveur central"""
        try:
            url = f"{self.api_url}/api/crawl/task?worker_id={self.worker_id}&batch_size={self.batch_size}"
            async with session.get(url, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('sites', [])
        except Exception as e:
            print(f"❌ Erreur get_tasks: {e}")
        return []

    async def submit_result(self, session: aiohttp.ClientSession, result: Dict) -> bool:
        """Envoyer les résultats au serveur central"""
        try:
            url = f"{self.api_url}/api/crawl/result"
            result['worker_id'] = self.worker_id

            async with session.post(url, json=result, ssl=self.ssl_context) as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Erreur submit_result: {e}")
        return False

    async def send_heartbeat(self, session: aiohttp.ClientSession):
        """Envoyer un heartbeat au serveur central"""
        global current_task, pages_crawled

        try:
            url = f"{self.api_url}/api/crawl/heartbeat"
            data = {
                'worker_id': self.worker_id,
                'hostname': self.hostname,
                'status': 'running',
                'current_task': current_task,
                'pages_crawled': pages_crawled,
                'stats': self.stats
            }

            async with session.post(url, json=data, ssl=self.ssl_context) as response:
                pass
        except:
            pass

    async def heartbeat_loop(self, session: aiohttp.ClientSession):
        """Boucle de heartbeat en arrière-plan"""
        while running:
            await self.send_heartbeat(session)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def run(self):
        """Boucle principale du worker"""
        global running, current_task

        print("\n" + "=" * 60)
        print("🚀 DÉMARRAGE DU WORKER DE CRAWL DISTRIBUÉ")
        print("=" * 60 + "\n")

        # Créer la session HTTP
        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=30,
            ttl_dns_cache=300,
            ssl=self.ssl_context
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Lancer le heartbeat en arrière-plan
            heartbeat_task = asyncio.create_task(self.heartbeat_loop(session))

            try:
                while running:
                    # Demander des tâches
                    print(f"\n📋 Demande de tâches ({self.batch_size} sites)...")
                    tasks = await self.get_tasks(session)

                    if not tasks:
                        print("😴 Aucune tâche disponible, attente 60s...")
                        await asyncio.sleep(60)
                        continue

                    print(f"📦 {len(tasks)} tâches reçues")

                    # Traiter chaque tâche
                    for i, task in enumerate(tasks, 1):
                        if not running:
                            break

                        print(f"\n[{i}/{len(tasks)}] Site: {task['domain']}")

                        try:
                            result = await self.crawl_seller(
                                session,
                                task['id'],
                                task['domain'],
                                task['url']
                            )

                            # Envoyer les résultats
                            success = await self.submit_result(session, result)
                            if success:
                                self.stats['tasks_completed'] += 1
                                print(f"    ✅ Résultats envoyés: {len(result['buyers'])} acheteurs")
                            else:
                                print(f"    ⚠️  Échec envoi résultats")

                        except Exception as e:
                            self.stats['errors'] += 1
                            print(f"    ❌ Erreur: {e}")

                            # Envoyer l'erreur au serveur
                            error_result = {
                                'site_id': task['id'],
                                'domain': task['domain'],
                                'buyers': [],
                                'pages_crawled': 0,
                                'error': str(e)
                            }
                            await self.submit_result(session, error_result)

                        # Pause entre les sites
                        await asyncio.sleep(PAUSE_BETWEEN_SITES)

                    # Stats
                    print(f"\n📊 Stats worker:")
                    print(f"   - Tâches complétées: {self.stats['tasks_completed']}")
                    print(f"   - Acheteurs trouvés: {self.stats['buyers_found']}")
                    print(f"   - Emails trouvés: {self.stats['emails_found']}")
                    print(f"   - Pages crawlées: {self.stats['pages_crawled']}")
                    print(f"   - Erreurs: {self.stats['errors']}")

            finally:
                # Arrêter le heartbeat
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        current_task = None
        print("\n✅ Worker arrêté proprement")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Worker de crawl distribué')
    parser.add_argument('--api-url', default=os.environ.get('CRAWL_API_URL', DEFAULT_API_URL),
                        help=f'URL de l\'API centrale (défaut: {DEFAULT_API_URL})')
    parser.add_argument('--worker-id', default=os.environ.get('CRAWL_WORKER_ID'),
                        help='ID unique du worker (défaut: worker_<hostname>)')
    parser.add_argument('--batch-size', type=int, default=int(os.environ.get('CRAWL_BATCH_SIZE', DEFAULT_BATCH_SIZE)),
                        help=f'Nombre de sites par batch (défaut: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--concurrent', type=int, default=int(os.environ.get('CRAWL_CONCURRENT', DEFAULT_CONCURRENT)),
                        help=f'Requêtes simultanées (défaut: {DEFAULT_CONCURRENT})')
    parser.add_argument('--max-pages', type=int, default=int(os.environ.get('CRAWL_MAX_PAGES', DEFAULT_MAX_PAGES)),
                        help=f'Pages max par site (défaut: {DEFAULT_MAX_PAGES})')

    args = parser.parse_args()

    # Générer le worker_id si non spécifié
    worker_id = args.worker_id or f"worker_{socket.gethostname()}"

    # Gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Créer et lancer le worker
    worker = CrawlWorker(
        api_url=args.api_url,
        worker_id=worker_id,
        batch_size=args.batch_size,
        concurrent=args.concurrent,
        max_pages=args.max_pages
    )

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur")


if __name__ == '__main__':
    main()
