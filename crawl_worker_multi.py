#!/usr/bin/env python3 -u
"""
Worker de crawl distribué MULTI-SITES

Ce worker crawle PLUSIEURS sites en parallèle avec UN SEUL processus.
Beaucoup plus efficace que de lancer plusieurs workers.

Usage:
    python3 -u crawl_worker_multi.py --parallel-sites 4

    # Avec toutes les options:
    python3 -u crawl_worker_multi.py --api-url https://admin.perfect-cocon-seo.fr --parallel-sites 4 --concurrent 25
"""

# Force unbuffered output
import sys
sys.stdout = sys.stderr = open(sys.stdout.fileno(), 'w', buffering=1)

import asyncio
import aiohttp
import ssl
import socket
import time
import re
import argparse
import os
import signal
import sys
from urllib.parse import urlparse, urljoin
from datetime import datetime
from collections import deque
from typing import Set, List, Dict, Optional, Tuple

# Configuration par défaut
DEFAULT_API_URL = "https://admin.perfect-cocon-seo.fr"
DEFAULT_PARALLEL_SITES = 4  # Nombre de sites crawlés en parallèle
DEFAULT_CONCURRENT = 25  # Requêtes simultanées par site
DEFAULT_MAX_PAGES = 5000
HEARTBEAT_INTERVAL = 30
REQUEST_TIMEOUT = 10
PAUSE_BETWEEN_BATCHES = 2

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

# Extensions de fichiers non-HTML à ignorer
IGNORED_EXTENSIONS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp', '.tiff', '.avif',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    # Archives
    '.zip', '.rar', '.tar', '.gz', '.7z',
    # Media
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.wav', '.ogg', '.webm',
    # Code/Data
    '.css', '.js', '.json', '.xml', '.rss', '.atom', '.woff', '.woff2', '.ttf', '.eot',
    # Autres
    '.exe', '.dmg', '.apk', '.msi',
}

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

# État global
running = True
current_tasks = {}  # {site_id: {'domain': ..., 'pages': ..., 'recent_urls': [...]}}
MAX_RECENT_URLS = 5  # Nombre d'URLs récentes à garder par site


def signal_handler(signum, frame):
    global running
    print(f"\n⚠️  Signal {signum} reçu, arrêt en cours...")
    running = False


def extract_domain(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        return domain if domain else None
    except:
        return None


def is_blacklisted_domain(domain: str) -> bool:
    if not domain:
        return True
    if domain in BLACKLISTED_DOMAINS:
        return True
    for blacklisted in BLACKLISTED_DOMAINS:
        if domain.endswith('.' + blacklisted):
            return True
    return False


def is_valid_fr_domain(domain: str) -> bool:
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
    url = url.strip()
    if not url or url.startswith(('mailto:', 'javascript:', 'tel:', '#')):
        return None
    parsed = urlparse(url)
    if not parsed.scheme:
        url = urljoin(base, url)
        parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None

    # Ignorer les fichiers non-HTML (images, PDFs, etc.)
    path_lower = parsed.path.lower()
    for ext in IGNORED_EXTENSIONS:
        if path_lower.endswith(ext):
            return None

    # Ignorer aussi les URLs avec /wp-content/uploads/ (souvent des images)
    if '/wp-content/uploads/' in parsed.path:
        return None

    return parsed.scheme + '://' + parsed.netloc + parsed.path


class MultiSiteCrawlWorker:
    """Worker qui crawle plusieurs sites en parallèle"""

    def __init__(self, api_url: str, worker_id: str, parallel_sites: int,
                 concurrent: int, max_pages: int):
        self.api_url = api_url.rstrip('/')
        # Ajouter le PID pour avoir un ID unique par processus
        self.worker_id = f"{worker_id}-{os.getpid()}"
        self.parallel_sites = parallel_sites
        self.concurrent_per_site = concurrent
        self.max_pages = max_pages
        self.hostname = socket.gethostname()

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        self.stats = {
            'tasks_completed': 0,
            'buyers_found': 0,
            'emails_found': 0,
            'errors': 0,
            'pages_crawled': 0
        }

        print(f"🚀 Worker MULTI-SITES initialisé:")
        print(f"   - ID: {self.worker_id}")
        print(f"   - Hostname: {self.hostname}")
        print(f"   - API: {self.api_url}")
        print(f"   - Sites en parallèle: {self.parallel_sites}")
        print(f"   - Requêtes/site: {self.concurrent_per_site}")
        print(f"   - Max pages/site: {self.max_pages}")

    async def fetch_page(self, session: aiohttp.ClientSession, url: str,
                         semaphore: asyncio.Semaphore) -> Optional[str]:
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
        links = []
        try:
            href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
            links = href_pattern.findall(html)
        except:
            pass
        return links

    async def find_email(self, session: aiohttp.ClientSession, domain: str,
                         semaphore: asyncio.Semaphore) -> Optional[str]:
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

    async def crawl_single_site(self, session: aiohttp.ClientSession,
                                site_id: int, domain: str, url: str) -> Dict:
        """Crawler un seul site avec upload incrémental des acheteurs"""
        global current_tasks

        current_tasks[site_id] = {'domain': domain, 'pages': 0, 'recent_urls': []}

        semaphore = asyncio.Semaphore(self.concurrent_per_site)
        visited = set()
        to_visit = deque([url])
        buyer_domains = set()
        seller_domain = extract_domain(url)

        # Buffer pour upload incrémental (batch de 20 acheteurs)
        BATCH_SIZE = 20
        pending_buyers = []
        uploaded_domains = set()  # Éviter les doublons

        while to_visit and len(visited) < self.max_pages and running:
            # Prendre un batch d'URLs
            batch_urls = []
            while to_visit and len(batch_urls) < self.concurrent_per_site:
                next_url = to_visit.popleft()
                if next_url not in visited:
                    batch_urls.append(next_url)
                    visited.add(next_url)

            if not batch_urls:
                break

            # Crawler le batch
            tasks = [self.fetch_page(session, u, semaphore) for u in batch_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url_crawled, html in zip(batch_urls, results):
                current_tasks[site_id]['pages'] = len(visited)
                # Ajouter l'URL aux URLs récentes (garder seulement les dernières)
                recent = current_tasks[site_id]['recent_urls']
                recent.append(url_crawled)
                if len(recent) > MAX_RECENT_URLS:
                    current_tasks[site_id]['recent_urls'] = recent[-MAX_RECENT_URLS:]

                if isinstance(html, Exception) or not html:
                    continue

                links = await self.extract_links(html)

                for link in links:
                    normalized = normalize_url(url_crawled, link)
                    if not normalized:
                        continue

                    link_domain = extract_domain(normalized)

                    if link_domain == seller_domain:
                        if normalized not in visited:
                            to_visit.append(normalized)
                    elif is_valid_fr_domain(link_domain):
                        # Upload incrémental: ajouter au buffer si pas déjà uploadé
                        if link_domain not in buyer_domains and link_domain not in uploaded_domains:
                            buyer_domains.add(link_domain)
                            pending_buyers.append({'domain': link_domain, 'email': None})

                            # Si on atteint BATCH_SIZE, envoyer le batch
                            if len(pending_buyers) >= BATCH_SIZE:
                                await self.submit_buyers_batch(session, site_id, seller_domain, pending_buyers)
                                for b in pending_buyers:
                                    uploaded_domains.add(b['domain'])
                                self.stats['buyers_found'] += len(pending_buyers)
                                pending_buyers = []

        # Envoyer les acheteurs restants (sans email pour l'instant)
        if pending_buyers:
            await self.submit_buyers_batch(session, site_id, seller_domain, pending_buyers)
            for b in pending_buyers:
                uploaded_domains.add(b['domain'])
            self.stats['buyers_found'] += len(pending_buyers)
            pending_buyers = []

        # Chercher les emails des acheteurs et les uploader par batch
        email_semaphore = asyncio.Semaphore(10)  # Limiter les requêtes email
        buyers_with_email = []
        total_emails = 0

        for buyer_domain in buyer_domains:
            email = await self.find_email(session, buyer_domain, email_semaphore)
            if email:
                buyers_with_email.append({'domain': buyer_domain, 'email': email})
                total_emails += 1
                self.stats['emails_found'] += 1

                # Uploader les emails par batch de BATCH_SIZE
                if len(buyers_with_email) >= BATCH_SIZE:
                    await self.submit_buyers_batch(session, site_id, seller_domain, buyers_with_email)
                    buyers_with_email = []

        # Envoyer les derniers emails
        if buyers_with_email:
            await self.submit_buyers_batch(session, site_id, seller_domain, buyers_with_email)

        self.stats['pages_crawled'] += len(visited)

        # Retirer de current_tasks
        if site_id in current_tasks:
            del current_tasks[site_id]

        # Retourner un résumé (les données sont déjà uploadées)
        return {
            'site_id': site_id,
            'domain': domain,
            'buyers': [],  # Déjà uploadés de façon incrémentale
            'pages_crawled': len(visited),
            'total_buyers': len(buyer_domains),
            'total_emails': total_emails,
            'error': None
        }

    async def get_tasks(self, session: aiohttp.ClientSession, count: int) -> List[Dict]:
        """Demander des tâches (1 par site à crawler)"""
        try:
            url = f"{self.api_url}/api/crawl/task?worker_id={self.worker_id}&batch_size={count}"
            async with session.get(url, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('sites', [])
        except Exception as e:
            print(f"❌ Erreur get_tasks: {e}")
        return []

    async def submit_result(self, session: aiohttp.ClientSession, result: Dict) -> bool:
        try:
            url = f"{self.api_url}/api/crawl/result"
            result['worker_id'] = self.worker_id
            async with session.post(url, json=result, ssl=self.ssl_context) as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Erreur submit_result: {e}")

    async def submit_buyers_batch(self, session: aiohttp.ClientSession,
                                   site_id: int, seller_domain: str,
                                   buyers: List[Dict]) -> bool:
        """Envoyer un batch d'acheteurs à l'API (upload incrémental)"""
        if not buyers:
            return True
        try:
            url = f"{self.api_url}/api/crawl/buyers_batch"
            data = {
                'worker_id': self.worker_id,
                'site_id': site_id,
                'seller_domain': seller_domain,
                'buyers': buyers
            }
            async with session.post(url, json=data, ssl=self.ssl_context) as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Erreur submit_buyers_batch: {e}")
        return False

    async def send_heartbeat(self, session: aiohttp.ClientSession):
        global current_tasks
        try:
            url = f"{self.api_url}/api/crawl/heartbeat"

            # Construire la liste des tâches en cours
            tasks_info = [f"{t['domain']}({t['pages']}p)" for t in current_tasks.values()]
            current_task_str = " | ".join(tasks_info) if tasks_info else "idle"
            total_pages = sum(t['pages'] for t in current_tasks.values())

            # Construire la liste détaillée des sites avec URLs récentes
            sites_detail = []
            for site_id, task in current_tasks.items():
                sites_detail.append({
                    'domain': task['domain'],
                    'pages': task['pages'],
                    'recent_urls': task.get('recent_urls', [])[-MAX_RECENT_URLS:]
                })

            data = {
                'worker_id': self.worker_id,
                'hostname': self.hostname,
                'status': 'running',
                'current_task': current_task_str,
                'pages_crawled': total_pages,
                'sites_in_progress': sites_detail,  # Nouveau champ avec détail par site
                'stats': self.stats
            }
            async with session.post(url, json=data, ssl=self.ssl_context) as response:
                pass
        except:
            pass

    async def heartbeat_loop(self, session: aiohttp.ClientSession):
        while running:
            await self.send_heartbeat(session)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def run(self):
        global running, current_tasks

        print("\n" + "=" * 60)
        print(f"🚀 WORKER MULTI-SITES - {self.parallel_sites} sites en parallèle")
        print("=" * 60 + "\n")

        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=30,
            ttl_dns_cache=300,
            ssl=self.ssl_context
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            heartbeat_task = asyncio.create_task(self.heartbeat_loop(session))

            try:
                while running:
                    # Calculer combien de sites on peut lancer
                    active_count = len(current_tasks)
                    slots_available = self.parallel_sites - active_count

                    if slots_available > 0:
                        print(f"\n📋 Demande de {slots_available} tâche(s)...")
                        tasks = await self.get_tasks(session, slots_available)

                        if not tasks:
                            if active_count == 0:
                                print("😴 Aucune tâche, attente 60s...")
                                await asyncio.sleep(60)
                            continue

                        print(f"📦 {len(tasks)} tâche(s) reçue(s)")

                        # Lancer les crawls en parallèle
                        crawl_tasks = []
                        for task in tasks:
                            print(f"  ▶️  {task['domain']}")
                            crawl_task = asyncio.create_task(
                                self.crawl_single_site(
                                    session,
                                    task['id'],
                                    task['domain'],
                                    task['url']
                                )
                            )
                            crawl_tasks.append(crawl_task)

                        # Attendre qu'au moins un termine
                        if crawl_tasks:
                            done, pending = await asyncio.wait(
                                crawl_tasks,
                                return_when=asyncio.FIRST_COMPLETED,
                                timeout=10  # Check toutes les 10s
                            )

                            for completed_task in done:
                                try:
                                    result = await completed_task
                                    success = await self.submit_result(session, result)
                                    if success:
                                        self.stats['tasks_completed'] += 1
                                        print(f"  ✅ {result['domain']}: {len(result['buyers'])} acheteurs, {result['pages_crawled']} pages")
                                    else:
                                        print(f"  ⚠️  Échec envoi {result['domain']}")
                                except Exception as e:
                                    self.stats['errors'] += 1
                                    print(f"  ❌ Erreur: {e}")
                    else:
                        # Tous les slots sont occupés, attendre
                        await asyncio.sleep(5)

                    # Afficher les stats périodiquement
                    if self.stats['tasks_completed'] > 0 and self.stats['tasks_completed'] % 5 == 0:
                        print(f"\n📊 Stats: {self.stats['tasks_completed']} tâches, "
                              f"{self.stats['buyers_found']} acheteurs, "
                              f"{self.stats['emails_found']} emails, "
                              f"{self.stats['pages_crawled']} pages")

            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        print("\n✅ Worker arrêté proprement")


def main():
    parser = argparse.ArgumentParser(description='Worker de crawl MULTI-SITES')
    parser.add_argument('--api-url', default=os.environ.get('CRAWL_API_URL', DEFAULT_API_URL))
    parser.add_argument('--worker-id', default=os.environ.get('CRAWL_WORKER_ID'))
    parser.add_argument('--parallel-sites', type=int, default=DEFAULT_PARALLEL_SITES,
                        help=f'Nombre de sites en parallèle (défaut: {DEFAULT_PARALLEL_SITES})')
    parser.add_argument('--concurrent', type=int, default=DEFAULT_CONCURRENT,
                        help=f'Requêtes simultanées par site (défaut: {DEFAULT_CONCURRENT})')
    parser.add_argument('--max-pages', type=int, default=DEFAULT_MAX_PAGES)

    args = parser.parse_args()

    worker_id = args.worker_id or f"worker_{socket.gethostname()}"

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    worker = MultiSiteCrawlWorker(
        api_url=args.api_url,
        worker_id=worker_id,
        parallel_sites=args.parallel_sites,
        concurrent=args.concurrent,
        max_pages=args.max_pages
    )

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur")


if __name__ == '__main__':
    main()
