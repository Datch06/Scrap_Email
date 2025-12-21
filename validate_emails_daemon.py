#!/usr/bin/env python3
"""
Daemon de validation automatique des emails - VERSION ASYNC OPTIMISÉE
- Utilise asyncio pour 100+ validations simultanées
- Valide tous les emails existants au démarrage
- Surveille en continu les nouveaux emails
"""

import asyncio
import signal
import sys
import os
import fcntl
from datetime import datetime
from database import get_session, get_engine, Site, safe_commit
from validate_emails_async import AsyncEmailValidator
import json
import logging
from sqlalchemy.orm import sessionmaker

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_validation_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Lock file pour éviter les instances multiples
LOCK_FILE = '/var/www/Scrap_Email/validate_emails_daemon.lock'
lock_fp = None

def acquire_lock():
    """Acquérir le lock exclusif pour éviter les instances multiples"""
    global lock_fp
    try:
        lock_fp = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fp.write(str(os.getpid()))
        lock_fp.flush()
        return True
    except (IOError, OSError):
        logger.error("❌ Une autre instance du daemon est déjà en cours d'exécution")
        return False

def release_lock():
    """Libérer le lock"""
    global lock_fp
    if lock_fp:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()
        try:
            os.remove(LOCK_FILE)
        except:
            pass

# Flag pour arrêter proprement le daemon
running = True

def signal_handler(sig, frame):
    """Gestion de l'arrêt propre du daemon"""
    global running
    logger.info("🛑 Arrêt du daemon demandé...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class AsyncEmailValidationDaemon:
    """Daemon de validation automatique des emails - Version Async"""

    def __init__(self, batch_size=200, max_concurrent=100, check_interval=30):
        """
        Args:
            batch_size: Nombre d'emails à charger par batch (défaut: 200)
            max_concurrent: Nombre de validations simultanées (défaut: 100)
            check_interval: Intervalle de vérification en secondes (défaut: 30)
        """
        self.validator = AsyncEmailValidator(smtp_timeout=5.0, dns_timeout=3.0)
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.check_interval = check_interval
        self.last_check_id = 0
        self.stats = {
            'total_validated': 0,
            'valid': 0,
            'invalid': 0,
            'risky': 0,
            'errors': 0,
            'start_time': datetime.utcnow()
        }

    async def validate_batch(self, sites: list, db_session) -> int:
        """
        Valider un batch d'emails en parallèle

        Args:
            sites: Liste de tuples (site_id, email, domain)
            db_session: Session SQLAlchemy

        Returns:
            Nombre d'emails validés
        """
        if not sites:
            return 0

        # Préparer les emails à valider
        site_map = {site_id: (email, domain) for site_id, email, domain in sites}
        emails = [email for _, email, _ in sites]

        # Valider tous les emails en parallèle
        results = await self.validator.validate_emails_batch(emails, self.max_concurrent)

        # Mapper les résultats aux sites
        email_to_result = {r['email']: r for r in results}

        # Mettre à jour la base de données
        validated_count = 0
        for site_id, (email, domain) in site_map.items():
            result = email_to_result.get(email.lower())
            if not result:
                continue

            try:
                site = db_session.query(Site).filter_by(id=site_id).first()
                if site:
                    site.email_validated = True
                    site.email_validation_score = result['score']
                    site.email_validation_status = result['status']
                    site.email_validation_details = json.dumps(result['details'])
                    site.email_validation_date = datetime.utcnow()
                    site.email_deliverable = result['deliverable']

                    validated_count += 1
                    self.stats['total_validated'] += 1

                    if result['status'] == 'valid':
                        self.stats['valid'] += 1
                    elif result['status'] == 'invalid':
                        self.stats['invalid'] += 1
                    elif result['status'] == 'risky':
                        self.stats['risky'] += 1

            except Exception as e:
                logger.error(f"Erreur update site {site_id}: {e}")
                self.stats['errors'] += 1

        # Commit le batch
        try:
            safe_commit(db_session, max_retries=5)
        except Exception as e:
            logger.error(f"Erreur commit batch: {e}")
            db_session.rollback()

        return validated_count

    async def validate_all_existing(self):
        """Phase 1: Valider tous les emails existants non validés"""
        global running

        Session = sessionmaker(bind=get_engine())
        session = Session()

        try:
            # Compter les emails à valider
            initial_count = session.query(Site).filter(
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != 'NO EMAIL FOUND',
                (Site.email_validated.is_(None)) | (Site.email_validated == False)
            ).count()

            if initial_count == 0:
                logger.info("✅ Tous les emails existants sont déjà validés")
                return

            logger.info(f"🚀 Phase 1: Validation de {initial_count:,} emails...")
            logger.info(f"   Batch: {self.batch_size} | Concurrent: {self.max_concurrent}")

            batch_number = 0
            total_processed = 0
            start_time = datetime.utcnow()

            while running:
                # Récupérer un batch de sites
                sites_query = session.query(Site.id, Site.emails, Site.domain).filter(
                    Site.emails.isnot(None),
                    Site.emails != '',
                    Site.emails != 'NO EMAIL FOUND',
                    (Site.email_validated.is_(None)) | (Site.email_validated == False)
                ).limit(self.batch_size).all()

                if not sites_query:
                    break

                # Extraire le premier email de chaque site
                sites_data = []
                for site_id, emails_str, domain in sites_query:
                    emails_list = emails_str.replace(';', ',').split(',')
                    primary_email = emails_list[0].strip()
                    if primary_email:
                        sites_data.append((site_id, primary_email, domain))

                if not sites_data:
                    break

                batch_number += 1
                batch_start = datetime.utcnow()

                # Valider le batch
                validated = await self.validate_batch(sites_data, session)
                total_processed += validated

                batch_duration = (datetime.utcnow() - batch_start).total_seconds()
                speed = validated / batch_duration if batch_duration > 0 else 0

                # Stats de progression
                remaining = initial_count - total_processed
                progress = (total_processed / initial_count) * 100 if initial_count > 0 else 100

                # ETA
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if total_processed > 0:
                    eta_seconds = (remaining / total_processed) * elapsed
                    eta_hours = int(eta_seconds // 3600)
                    eta_mins = int((eta_seconds % 3600) // 60)
                    eta_str = f"{eta_hours}h{eta_mins:02d}m"
                else:
                    eta_str = "N/A"

                logger.info(
                    f"📦 Batch {batch_number}: {validated} validés en {batch_duration:.1f}s ({speed:.1f}/s) | "
                    f"Progress: {progress:.1f}% | "
                    f"✅{self.stats['valid']} ❌{self.stats['invalid']} ⚠️{self.stats['risky']} | "
                    f"ETA: {eta_str}"
                )

                # Rafraîchir la session périodiquement
                if batch_number % 10 == 0:
                    session.expire_all()

            logger.info(f"✅ Phase 1 terminée - {total_processed:,} emails validés")

        except Exception as e:
            logger.error(f"Erreur Phase 1: {e}", exc_info=True)
        finally:
            # Récupérer le dernier ID pour la surveillance
            last_site = session.query(Site).order_by(Site.id.desc()).first()
            if last_site:
                self.last_check_id = last_site.id
            session.close()

    async def watch_for_new_emails(self):
        """Phase 2: Surveiller en continu les nouveaux emails"""
        global running

        logger.info(f"👀 Phase 2: Surveillance des nouveaux emails (toutes les {self.check_interval}s)...")

        Session = sessionmaker(bind=get_engine())

        while running:
            session = Session()

            try:
                # Chercher les nouveaux emails
                new_sites_query = session.query(Site.id, Site.emails, Site.domain).filter(
                    Site.id > self.last_check_id,
                    Site.emails.isnot(None),
                    Site.emails != '',
                    Site.emails != 'NO EMAIL FOUND',
                    (Site.email_validated.is_(None)) | (Site.email_validated == False)
                ).all()

                if new_sites_query:
                    sites_data = []
                    for site_id, emails_str, domain in new_sites_query:
                        emails_list = emails_str.replace(';', ',').split(',')
                        primary_email = emails_list[0].strip()
                        if primary_email:
                            sites_data.append((site_id, primary_email, domain))

                    if sites_data:
                        logger.info(f"🆕 {len(sites_data)} nouveaux emails détectés!")
                        await self.validate_batch(sites_data, session)
                        self.last_check_id = max(s[0] for s in sites_data)

                # Attendre
                for _ in range(self.check_interval):
                    if not running:
                        break
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Erreur surveillance: {e}")
                await asyncio.sleep(self.check_interval)
            finally:
                session.close()

    def print_final_stats(self):
        """Afficher les statistiques finales"""
        duration = (datetime.utcnow() - self.stats['start_time']).total_seconds()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        speed = self.stats['total_validated'] / duration if duration > 0 else 0

        logger.info("\n" + "=" * 70)
        logger.info("📊 STATISTIQUES FINALES")
        logger.info("=" * 70)
        logger.info(f"Durée: {hours}h {minutes}m")
        logger.info(f"Total validé: {self.stats['total_validated']:,}")
        logger.info(f"Vitesse moyenne: {speed:.1f} emails/sec")
        logger.info(f"✅ Valides: {self.stats['valid']:,}")
        logger.info(f"❌ Invalides: {self.stats['invalid']:,}")
        logger.info(f"⚠️  Risqués: {self.stats['risky']:,}")
        logger.info(f"Erreurs: {self.stats['errors']:,}")
        logger.info("=" * 70)

    async def run(self):
        """Lancer le daemon"""
        logger.info("=" * 70)
        logger.info("🚀 DAEMON VALIDATION EMAILS - VERSION ASYNC")
        logger.info("=" * 70)
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Concurrent: {self.max_concurrent}")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info("=" * 70)

        try:
            # Phase 1
            await self.validate_all_existing()

            # Phase 2
            if running:
                await self.watch_for_new_emails()

        except Exception as e:
            logger.error(f"Erreur fatale: {e}", exc_info=True)
        finally:
            self.print_final_stats()
            logger.info("👋 Daemon arrêté")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Daemon validation emails (async)')
    parser.add_argument('--batch-size', type=int, default=200, help='Taille des batchs (défaut: 200)')
    parser.add_argument('--concurrent', type=int, default=100, help='Validations simultanées (défaut: 100)')
    parser.add_argument('--check-interval', type=int, default=30, help='Intervalle vérification (défaut: 30s)')

    args = parser.parse_args()

    if not acquire_lock():
        sys.exit(1)

    try:
        daemon = AsyncEmailValidationDaemon(
            batch_size=args.batch_size,
            max_concurrent=args.concurrent,
            check_interval=args.check_interval
        )
        asyncio.run(daemon.run())
    finally:
        release_lock()


if __name__ == '__main__':
    main()
