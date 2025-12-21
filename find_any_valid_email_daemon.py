#!/usr/bin/env python3
"""
Daemon TURBO pour rechercher des emails valides en continu
Exécute find_any_valid_email.py en boucle avec traitement parallèle
"""

import asyncio
import signal
import sys
import time
from datetime import datetime
from database import get_session, Site
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/www/Scrap_Email/find_any_valid_email_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flag pour arrêter proprement le daemon
running = True

def signal_handler(sig, frame):
    """Gestion de l'arrêt propre du daemon"""
    global running
    logger.info("🛑 Arrêt du daemon demandé...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def count_sites_to_process():
    """Compter les sites sans email à traiter"""
    session = get_session()
    try:
        count = session.query(Site).filter(
            Site.is_active == True,
            Site.blacklisted == False,
            (
                (Site.emails == "NO EMAIL FOUND") |
                (Site.emails == None) |
                (Site.emails == "")
            ),
            # Exclure les sites déjà testés avec guessing
            ~Site.email_source.like('%any_valid%')
        ).count()
        return count
    finally:
        session.close()


async def run_email_finder(batch_size: int = 100, limit_per_run: int = 500,
                           max_concurrent: int = 50, parallel_sites: int = 20):
    """
    Exécuter le finder d'emails - VERSION TURBO

    Args:
        batch_size: Taille des lots
        limit_per_run: Nombre max de sites par exécution
        max_concurrent: Nombre max de requêtes HTTP simultanées
        parallel_sites: Nombre de sites traités en parallèle
    """
    from find_any_valid_email import AnyValidEmailFinder

    finder = AnyValidEmailFinder(max_concurrent=max_concurrent)

    await finder.process_all(
        limit=limit_per_run,
        batch_size=batch_size,
        parallel_sites=parallel_sites
    )


async def daemon_loop(check_interval: int = 60, batch_size: int = 100,
                      limit_per_run: int = 2000, max_concurrent: int = 100,
                      parallel_sites: int = 20):
    """
    Boucle principale du daemon - VERSION TURBO

    Args:
        check_interval: Intervalle entre les vérifications en secondes
        batch_size: Taille des lots
        limit_per_run: Nombre max de sites par exécution
        max_concurrent: Nombre max de requêtes HTTP simultanées
        parallel_sites: Nombre de sites traités en parallèle
    """
    global running

    logger.info("=" * 70)
    logger.info("🚀 DÉMARRAGE DU DAEMON - Find Any Valid Email - VERSION TURBO")
    logger.info("=" * 70)
    logger.info(f"   Intervalle de vérification: {check_interval}s ({check_interval/60:.1f} min)")
    logger.info(f"   Batch size: {batch_size}")
    logger.info(f"   Limite par exécution: {limit_per_run}")
    logger.info(f"   Concurrence HTTP: {max_concurrent}")
    logger.info(f"   Sites en parallèle: {parallel_sites}")
    logger.info("=" * 70)

    total_processed = 0
    start_time = datetime.now()

    while running:
        try:
            # Compter les sites à traiter
            sites_to_process = count_sites_to_process()

            if sites_to_process > 0:
                logger.info(f"\n📊 {sites_to_process} sites sans email à traiter")
                logger.info("🚀 Lancement du traitement TURBO...")

                run_start = time.time()
                await run_email_finder(
                    batch_size=batch_size,
                    limit_per_run=limit_per_run,
                    max_concurrent=max_concurrent,
                    parallel_sites=parallel_sites
                )
                run_duration = time.time() - run_start

                processed_this_run = min(sites_to_process, limit_per_run)
                total_processed += processed_this_run
                speed = processed_this_run / run_duration if run_duration > 0 else 0

                logger.info(f"✅ Traitement terminé en {run_duration:.1f}s ({speed:.1f} sites/s)")
                logger.info(f"📈 Total traités depuis le démarrage: {total_processed}")

            else:
                logger.info(f"✅ Aucun nouveau site à traiter")

            # Attendre avant la prochaine vérification
            if running:
                logger.info(f"💤 Pause de {check_interval}s...")

                # Attendre par petits intervalles pour pouvoir s'arrêter rapidement
                for _ in range(check_interval):
                    if not running:
                        break
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Erreur dans la boucle du daemon: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Attendre avant de réessayer
            if running:
                logger.info("⏳ Attente de 30s avant de réessayer...")
                await asyncio.sleep(30)

    # Statistiques finales
    total_duration = datetime.now() - start_time
    logger.info("\n" + "=" * 70)
    logger.info("🛑 ARRÊT DU DAEMON")
    logger.info("=" * 70)
    logger.info(f"   Durée totale: {total_duration}")
    logger.info(f"   Sites traités: {total_processed}")
    logger.info("=" * 70)


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Daemon TURBO de recherche d'emails valides en continu"
    )
    parser.add_argument('--check-interval', type=int, default=60,
                        help='Intervalle entre les vérifications en secondes (défaut: 60)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Taille des lots (défaut: 100)')
    parser.add_argument('--limit-per-run', type=int, default=2000,
                        help='Nombre max de sites par exécution (défaut: 2000)')
    parser.add_argument('--concurrent', type=int, default=100,
                        help='Nombre max de requêtes HTTP simultanées (défaut: 100)')
    parser.add_argument('--parallel-sites', type=int, default=20,
                        help='Nombre de sites traités en parallèle (défaut: 20)')

    args = parser.parse_args()

    asyncio.run(daemon_loop(
        check_interval=args.check_interval,
        batch_size=args.batch_size,
        limit_per_run=args.limit_per_run,
        max_concurrent=args.concurrent,
        parallel_sites=args.parallel_sites
    ))


if __name__ == "__main__":
    main()
