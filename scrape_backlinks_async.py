#!/usr/bin/env python3
"""
Scraper ASYNCHRONE pour trouver les acheteurs de backlinks

Ce script:
1. Charge tous les sites vendeurs de LinkAvista (79,430 sites)
2. Crawle chaque site vendeur de manière asynchrone
3. Extrait tous les domaines .fr externes (= acheteurs de backlinks)
4. Trouve leurs emails de contact
5. Stocke tout dans la base avec tracking de la provenance

Version asynchrone: 4-5x plus rapide que l'ancien système
"""

import asyncio
import aiohttp
import ssl
import time
import re
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from collections import deque
from db_helper import DBHelper
from database import Site
from email_finder_async import AsyncEmailFinder
import threading

# Timezone France (UTC+1)
FRANCE_TZ = timezone(timedelta(hours=1))

# Configuration
MAX_CONCURRENT = 20  # Requêtes simultanées pour crawler les sites vendeurs
MAX_PAGES_PER_SELLER = None  # Pas de limite - crawler toutes les pages
TIMEOUT = 10  # Secondes
BATCH_SIZE = 50  # Sauvegarder par lots
PAUSE_BETWEEN_SELLERS = 0.5  # Pause entre chaque site vendeur
MAX_CRAWL_DEPTH = None  # AUCUNE LIMITE - crawler jusqu'à épuisement des pages
MAX_SELLERS_PARALLEL = 10  # Nombre de sites vendeurs à traiter en parallèle (augmenté de 5 à 10)

# État du scraping
STATE_FILE = Path(__file__).parent / 'scraping_state.json'
state_lock = threading.Lock()

# Patterns
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

# Domaines à JAMAIS scraper (vendeurs ou acheteurs) - base hardcodée
BLACKLISTED_DOMAINS = {
    'cnil.fr',
    'gouv.fr',
    'diplomatie.gouv.fr',
    'education.gouv.fr',
    'economie.gouv.fr',
    'interieur.gouv.fr',
    'service-public.fr',
    'legifrance.gouv.fr',
    'senat.fr',
    'assemblee-nationale.fr'
}

def load_blacklist_file():
    """
    Charger les domaines du fichier blacklist.txt et les fusionner avec BLACKLISTED_DOMAINS
    Retourne l'ensemble complet des domaines à blacklister
    """
    blacklist_file = Path(__file__).parent / 'blacklist.txt'
    combined_blacklist = set(BLACKLISTED_DOMAINS)

    if blacklist_file.exists():
        try:
            with open(blacklist_file, 'r') as f:
                file_domains = {line.strip() for line in f if line.strip()}
                combined_blacklist.update(file_domains)
                if file_domains:
                    print(f"🚫 {len(file_domains)} domaines chargés depuis blacklist.txt")
        except Exception as e:
            print(f"⚠️  Erreur lors de la lecture de blacklist.txt: {e}")

    return combined_blacklist

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


class LinkExtractor(HTMLParser):
    """Parser HTML pour extraire les liens"""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


def extract_domain(url):
    """Extraire le domaine d'une URL"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    domain = domain.replace('www.', '')
    return domain if domain else None


def is_blacklisted_domain(domain):
    """Vérifier si un domaine est blacklisté"""
    if not domain:
        return True

    # Vérifier les domaines exacts
    if domain in BLACKLISTED_DOMAINS:
        return True

    # Vérifier si le domaine se termine par un domaine blacklisté (ex: *.gouv.fr)
    for blacklisted in BLACKLISTED_DOMAINS:
        if domain.endswith('.' + blacklisted) or domain == blacklisted:
            return True

    return False


def is_valid_fr_domain(domain):
    """Vérifier si c'est un domaine .fr valide"""
    if not domain or not domain.endswith('.fr'):
        return False

    # Vérifier si blacklisté
    if is_blacklisted_domain(domain):
        return False

    for excluded in EXCLUDED_PATTERNS:
        if excluded in domain:
            return False
    for social in SOCIAL_DOMAINS:
        if social in domain:
            return False
    return True


def normalize_url(base, url):
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


def update_scraping_state(seller_domain, pages_crawled, current_url, buyers_found):
    """
    Mettre à jour l'état du scraping dans le fichier JSON
    Thread-safe grâce au lock
    """
    try:
        with state_lock:
            # Vérifier d'abord si le domaine est blacklisté
            blacklist_file = Path(__file__).parent / 'blacklist.txt'
            if blacklist_file.exists():
                with open(blacklist_file, 'r') as f:
                    blacklisted = {line.strip() for line in f if line.strip()}
                    if seller_domain in blacklisted:
                        # Domaine blacklisté, ne pas l'ajouter/mettre à jour dans le state
                        print(f"    🚫 {seller_domain} blacklisté, pas de mise à jour du state")
                        return

            # Lire l'état actuel
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
            else:
                state = {'sellers_in_progress': [], 'last_update': None}

            # Trouver ou créer l'entrée pour ce vendeur
            seller_entry = None
            for entry in state['sellers_in_progress']:
                if entry['domain'] == seller_domain:
                    seller_entry = entry
                    break

            if seller_entry is None:
                seller_entry = {'domain': seller_domain}
                state['sellers_in_progress'].append(seller_entry)

            # Mettre à jour les informations
            seller_entry['pages_crawled'] = pages_crawled
            seller_entry['current_url'] = current_url
            seller_entry['buyers_found'] = buyers_found
            seller_entry['last_update'] = datetime.now(FRANCE_TZ).isoformat()

            # Mettre à jour l'horodatage global
            state['last_update'] = datetime.now(FRANCE_TZ).isoformat()

            # Écrire le fichier
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
    except Exception as e:
        # Ne pas bloquer le scraping si l'écriture du state échoue
        print(f"    ⚠️  Erreur lors de la mise à jour du state: {e}")


def remove_seller_from_state(seller_domain):
    """
    Retirer un vendeur de l'état (quand le crawling est terminé)
    """
    try:
        with state_lock:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)

                # Retirer le vendeur de la liste
                state['sellers_in_progress'] = [
                    entry for entry in state['sellers_in_progress']
                    if entry['domain'] != seller_domain
                ]

                state['last_update'] = datetime.now(FRANCE_TZ).isoformat()

                with open(STATE_FILE, 'w') as f:
                    json.dump(state, f, indent=2)
    except Exception as e:
        print(f"    ⚠️  Erreur lors du retrait du state: {e}")


class BacklinksCrawler:
    """Crawler asynchrone pour extraire les acheteurs de backlinks"""

    def __init__(self, max_concurrent=MAX_CONCURRENT):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # SSL context permissif
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Statistiques
        self.stats = {
            'sellers_processed': 0,
            'buyers_found': 0,
            'emails_found': 0,
            'errors': 0
        }

    async def fetch_page(self, session, url):
        """Récupérer une page de manière asynchrone"""
        try:
            async with self.semaphore:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                    ssl=self.ssl_context,
                    headers={'User-Agent': DEFAULT_USER_AGENT}
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return html
        except Exception:
            pass
        return None

    async def crawl_seller_site(self, session, seller_url, seller_domain):
        """
        Crawle un site vendeur pour extraire tous les domaines acheteurs
        SANS LIMITE - crawle toutes les pages du site

        Args:
            session: Session aiohttp
            seller_url: URL du site vendeur
            seller_domain: Domaine du site vendeur

        Returns:
            set: Ensemble des domaines acheteurs trouvés
        """
        print(f"  🔍 Crawling {seller_domain} (AUCUNE LIMITE - toutes les pages)...")

        visited = set()
        to_visit = deque([seller_url])
        buyer_domains = set()

        while to_visit:
            # Vérifier si le domaine a été blacklisté (annulé via dashboard)
            # Optimisation: vérifier toutes les 10 pages seulement
            if len(visited) % 10 == 0:
                blacklist_file = Path(__file__).parent / 'blacklist.txt'
                if blacklist_file.exists():
                    with open(blacklist_file, 'r') as f:
                        blacklisted = {line.strip() for line in f if line.strip()}
                        if seller_domain in blacklisted:
                            print(f"    🚫 {seller_domain} blacklisté, arrêt immédiat du crawl")
                            remove_seller_from_state(seller_domain)
                            return buyer_domains

            url = to_visit.popleft()

            if url in visited:
                continue

            visited.add(url)

            # Mettre à jour l'état en temps réel
            update_scraping_state(seller_domain, len(visited), url, len(buyer_domains))

            html = await self.fetch_page(session, url)

            if not html:
                continue

            # Extraire les liens
            parser = LinkExtractor()
            try:
                parser.feed(html)
            except:
                pass

            # Compter les liens trouvés
            links_found = len(parser.links)
            internal_links_added = 0

            for link in parser.links:
                normalized = normalize_url(url, link)
                if not normalized:
                    continue

                link_domain = extract_domain(normalized)

                # Si c'est un lien interne, ajouter à la queue
                if link_domain == seller_domain:
                    if normalized not in visited:
                        to_visit.append(normalized)
                        internal_links_added += 1

                # Si c'est un domaine .fr externe, c'est un acheteur potentiel
                elif is_valid_fr_domain(link_domain):
                    buyer_domains.add(link_domain)

            # Afficher la progression tous les 50 pages
            if len(visited) % 50 == 0:
                print(f"    📄 {len(visited)} pages crawlées, {len(buyer_domains)} acheteurs trouvés...")

        print(f"    ✓ {len(visited)} pages crawlées, {len(buyer_domains)} acheteurs trouvés sur {seller_domain}")

        # Retirer ce vendeur de l'état une fois terminé
        remove_seller_from_state(seller_domain)

        return buyer_domains

    async def process_seller(self, session, db, seller_site, blacklist=None):
        """
        Traite un site vendeur:
        1. Crawle le site vendeur
        2. Extrait les domaines acheteurs
        3. Cherche leurs emails
        4. Stocke dans la base

        Args:
            blacklist: Set de domaines à exclure (depuis blacklist.txt + hardcodés)
        """
        if blacklist is None:
            blacklist = set()

        # Utiliser source_url seulement si c'est une vraie URL (commence par http)
        if seller_site.source_url and seller_site.source_url.startswith('http'):
            seller_url = seller_site.source_url
        else:
            seller_url = f"https://{seller_site.domain}"

        seller_domain = extract_domain(seller_url)

        # Skip si le domaine est invalide
        if not seller_domain:
            print(f"  ⚠️  Domaine invalide ignoré: {seller_site.domain} (url={seller_url})")
            return

        # Skip si le domaine est blacklisté (gouv.fr, cnil.fr, ou annulé via dashboard)
        if is_blacklisted_domain(seller_domain) or seller_domain in blacklist:
            print(f"  🚫 Domaine blacklisté ignoré: {seller_domain}")
            # Marquer comme crawlé pour ne plus le retraiter
            db.session.query(Site).filter_by(id=seller_site.id).update({
                'backlinks_crawled': True,
                'backlinks_crawled_at': datetime.utcnow()
            })
            db.session.commit()
            return

        try:
            # Marquer le site comme vendeur LinkAvista
            db.session.query(Site).filter_by(id=seller_site.id).update({
                'is_linkavista_seller': True
            })

            # Crawler le site vendeur pour trouver les acheteurs
            buyer_domains = await self.crawl_seller_site(session, seller_url, seller_domain)
            self.stats['buyers_found'] += len(buyer_domains)

            # Traiter chaque acheteur
            new_buyers = []
            for buyer_domain in buyer_domains:
                # Vérifier si déjà en base
                existing = db.session.query(Site).filter_by(domain=buyer_domain).first()
                if existing:
                    # Mettre à jour purchased_from si pas déjà défini
                    if not existing.purchased_from:
                        db.session.query(Site).filter_by(id=existing.id).update({
                            'purchased_from': seller_domain
                        })
                    continue

                # Ajouter le nouveau site acheteur
                new_site = db.add_site(
                    buyer_domain,
                    source_url=seller_url,
                    purchased_from=seller_domain
                )
                new_buyers.append(buyer_domain)

            # Chercher les emails pour les nouveaux acheteurs
            if new_buyers:
                print(f"    📧 Recherche d'emails pour {len(new_buyers)} nouveaux acheteurs...")

                # Créer un email finder avec la session
                email_finder = AsyncEmailFinder(session)

                emails_found = 0
                for buyer_domain in new_buyers:
                    email = await email_finder.search_emails_on_domain(buyer_domain, max_pages=8)

                    if email:
                        db.update_email(buyer_domain, email, email_source='backlinks_async')
                        emails_found += 1
                        self.stats['emails_found'] += 1
                        print(f"      ✓ {buyer_domain}: {email[:50]}")
                    else:
                        db.update_email(buyer_domain, 'NO EMAIL FOUND', email_source='backlinks_async')
                        print(f"      ✗ {buyer_domain}: Pas d'email")

                print(f"    ✅ {emails_found}/{len(new_buyers)} emails trouvés")

            # Marquer le site vendeur comme crawlé
            db.session.query(Site).filter_by(id=seller_site.id).update({
                'backlinks_crawled': True,
                'backlinks_crawled_at': datetime.utcnow()
            })
            db.session.commit()

            self.stats['sellers_processed'] += 1

            # Retirer de l'état (déjà fait dans crawl_seller_site)
            # remove_seller_from_state(seller_domain)

        except Exception as e:
            print(f"    ❌ Erreur: {e}")
            self.stats['errors'] += 1

            # Même en cas d'erreur, marquer comme crawlé pour ne pas le retraiter
            try:
                db.session.query(Site).filter_by(id=seller_site.id).update({
                    'backlinks_crawled': True,
                    'backlinks_crawled_at': datetime.utcnow()
                })

                # Retirer de l'état en cas d'erreur
                remove_seller_from_state(seller_domain)
                db.session.commit()
            except:
                pass

    async def run(self, limit=None):
        """
        Lance le scraping de tous les sites vendeurs LinkAvista

        Args:
            limit: Nombre max de sites vendeurs à traiter (None = tous)
        """
        print("=" * 80)
        print("🚀 SCRAPING ASYNCHRONE DES ACHETEURS DE BACKLINKS")
        print("=" * 80)
        print()
        print("Configuration:")
        print(f"  - Concurrence: {self.max_concurrent} requêtes simultanées")
        print(f"  - Vendeurs en parallèle: {MAX_SELLERS_PARALLEL}")
        print(f"  - Pages max par vendeur: AUCUNE LIMITE")
        print(f"  - Timeout: {TIMEOUT}s")
        print(f"  - Batch size: {BATCH_SIZE}")
        print()
        print("🚀 MODE ULTRA-RAPIDE ACTIVÉ:")
        print(f"   - {MAX_SELLERS_PARALLEL} sites vendeurs crawlés en parallèle")
        print("   - AUCUNE limite de pages par site")
        print("   - Extraction exhaustive de tous les acheteurs de backlinks")
        print()

        start_time = time.time()

        # Charger la blacklist depuis le fichier
        blacklist = load_blacklist_file()

        with DBHelper() as db:
            # Charger UNIQUEMENT les sites vendeurs NON crawlés et non blacklistés
            query = db.session.query(Site).filter(
                Site.is_linkavista_seller == True,  # Seulement les vendeurs
                Site.blacklisted == False,
                Site.backlinks_crawled == False,  # Uniquement les sites pas encore crawlés
                ~Site.domain.in_(blacklist)  # Exclure les domaines du fichier blacklist.txt
            )

            if limit:
                query = query.limit(limit)

            seller_sites = query.all()
            total_sellers = len(seller_sites)

            print(f"📊 Sites vendeurs à traiter: {total_sellers}")
            print()

            # Créer une session aiohttp
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent,
                ssl=self.ssl_context
            )

            async with aiohttp.ClientSession(connector=connector) as session:
                # NOUVELLE LOGIQUE: Queue dynamique globale pour ne jamais attendre
                # On lance MAX_SELLERS_PARALLEL vendeurs, et dès qu'un termine, on lance le suivant
                # PLUS DE BATCHES - on traite TOUS les vendeurs en continu
                print(f"\n🔄 Traitement avec queue dynamique globale ({MAX_SELLERS_PARALLEL} vendeurs max en parallèle)")
                print(f"   Dès qu'un vendeur se termine, le suivant démarre immédiatement")
                print("-" * 80)

                # Créer une queue avec TOUS les vendeurs
                seller_queue = list(seller_sites)
                running_tasks = {}  # {task: seller_domain}
                processed_domains = set()  # Domaines déjà traités pour éviter les doublons

                # Lancer les premiers vendeurs
                while len(running_tasks) < MAX_SELLERS_PARALLEL and seller_queue:
                    seller_site = seller_queue.pop(0)
                    if seller_site.domain not in processed_domains:
                        print(f"  ▶️  {seller_site.domain}")
                        task = asyncio.create_task(self.process_seller(session, db, seller_site, blacklist))
                        running_tasks[task] = seller_site.domain
                        processed_domains.add(seller_site.domain)

                # Tant qu'il y a des tâches en cours
                while running_tasks:
                    # Attendre qu'au moins une tâche se termine
                    done, pending = await asyncio.wait(
                        running_tasks.keys(),
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Nettoyer les tâches terminées
                    for task in done:
                        seller_domain = running_tasks.pop(task)
                        try:
                            await task  # Récupérer le résultat ou l'exception
                            print(f"  ✓ {seller_domain} terminé")
                        except Exception as e:
                            print(f"  ✗ {seller_domain} erreur: {e}")

                    # Lancer de nouveaux vendeurs pour remplir les slots libres
                    while len(running_tasks) < MAX_SELLERS_PARALLEL:
                        # Si la queue locale est vide, recharger depuis la DB (pour les sites annulés)
                        if not seller_queue:
                            new_sites = db.session.query(Site).filter(
                                Site.is_linkavista_seller == True,
                                Site.blacklisted == False,
                                Site.backlinks_crawled == False,
                                ~Site.domain.in_(processed_domains),  # Exclure les déjà traités
                                ~Site.domain.in_(blacklist)  # Exclure les domaines du fichier blacklist.txt
                            ).limit(10).all()  # Charger 10 nouveaux sites max

                            if new_sites:
                                seller_queue.extend(new_sites)
                                print(f"  🔄 {len(new_sites)} nouveaux sites chargés depuis la DB")
                            else:
                                break  # Plus de sites disponibles

                        if seller_queue:
                            seller_site = seller_queue.pop(0)
                            if seller_site.domain not in processed_domains:
                                print(f"  ▶️  {seller_site.domain} (slot libéré)")
                                task = asyncio.create_task(self.process_seller(session, db, seller_site, blacklist))
                                running_tasks[task] = seller_site.domain
                                processed_domains.add(seller_site.domain)
                        else:
                            break  # Plus de sites à traiter

                    await asyncio.sleep(PAUSE_BETWEEN_SELLERS)

            # Commit final après tous les vendeurs
            db.session.commit()

            # Stats finales
            elapsed = time.time() - start_time
            speed = self.stats['sellers_processed'] / elapsed if elapsed > 0 else 0

            print()
            print("=" * 80)
            print(f"📈 Stats finales:")
            print(f"  - Vendeurs traités: {self.stats['sellers_processed']}/{total_sellers}")
            print(f"  - Acheteurs trouvés: {self.stats['buyers_found']}")
            print(f"  - Emails trouvés: {self.stats['emails_found']}")
            print(f"  - Erreurs: {self.stats['errors']}")
            print(f"  - Vitesse: {speed:.2f} vendeurs/sec")
            print(f"  - Temps écoulé: {elapsed/60:.1f} min")
            print("=" * 80)
            print()

        # Stats finales
        elapsed = time.time() - start_time

        print()
        print("=" * 80)
        print("✅ SCRAPING TERMINÉ")
        print("=" * 80)
        print()
        print("📊 Résultats finaux:")
        print(f"  - Vendeurs traités: {self.stats['sellers_processed']}")
        print(f"  - Acheteurs trouvés: {self.stats['buyers_found']}")
        print(f"  - Emails trouvés: {self.stats['emails_found']}")
        print(f"  - Erreurs: {self.stats['errors']}")
        print()
        print(f"⏱️  Temps total: {elapsed/60:.1f} minutes")
        print(f"🚀 Vitesse moyenne: {self.stats['sellers_processed']/elapsed:.2f} vendeurs/sec")
        print()


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='Scraper asynchrone pour trouver les acheteurs de backlinks'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Nombre max de sites vendeurs à traiter (défaut: tous)'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=MAX_CONCURRENT,
        help=f'Nombre de requêtes simultanées (défaut: {MAX_CONCURRENT})'
    )

    args = parser.parse_args()

    crawler = BacklinksCrawler(max_concurrent=args.concurrent)
    await crawler.run(limit=args.limit)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêté par l'utilisateur (Ctrl+C)")
        print("Le scraping peut être repris à tout moment.")
