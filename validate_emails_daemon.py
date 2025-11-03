#!/usr/bin/env python3
"""
Daemon de validation automatique des emails
- Valide tous les emails existants au démarrage
- Surveille en continu les nouveaux emails
- Valide automatiquement dès qu'un nouvel email est trouvé
"""

import time
import signal
import sys
from datetime import datetime
from database import get_session, Site
from validate_emails import EmailValidator
import json
import logging

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

# Flag pour arrêter proprement le daemon
running = True

def signal_handler(sig, frame):
    """Gestion de l'arrêt propre du daemon"""
    global running
    logger.info("🛑 Arrêt du daemon demandé...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class EmailValidationDaemon:
    """Daemon de validation automatique des emails"""

    def __init__(self, batch_size=50, check_interval=60):
        """
        Args:
            batch_size: Nombre d'emails à valider par batch
            check_interval: Intervalle de vérification en secondes (défaut: 60s)
        """
        self.validator = EmailValidator()
        self.batch_size = batch_size
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

    def validate_email_entry(self, site, session):
        """Valider un email et mettre à jour la base"""
        try:
            # Récupérer le premier email
            emails_list = site.emails.replace(';', ',').split(',')
            primary_email = emails_list[0].strip()

            if not primary_email:
                return None

            logger.info(f"🔍 Validation: {primary_email} ({site.domain})")

            # Valider l'email
            validation_result = self.validator.validate_email(primary_email)

            # Mettre à jour la base de données
            site.email_validated = True
            site.email_validation_score = validation_result['score']
            site.email_validation_status = validation_result['status']
            site.email_validation_details = json.dumps(validation_result['details'])
            site.email_validation_date = datetime.utcnow()
            site.email_deliverable = validation_result['deliverable']

            # Stats
            self.stats['total_validated'] += 1
            if validation_result['status'] == 'valid':
                self.stats['valid'] += 1
            elif validation_result['status'] == 'invalid':
                self.stats['invalid'] += 1
            elif validation_result['status'] == 'risky':
                self.stats['risky'] += 1

            # Afficher le résultat
            status_emoji = {
                'valid': '✅',
                'invalid': '❌',
                'risky': '⚠️',
                'unknown': '❓'
            }.get(validation_result['status'], '❓')

            logger.info(
                f"  {status_emoji} {validation_result['status'].upper()} "
                f"(score: {validation_result['score']}/100)"
            )

            return validation_result

        except Exception as e:
            logger.error(f"❌ Erreur validation {site.domain}: {e}")
            self.stats['errors'] += 1
            return None

    def validate_batch(self, sites, session):
        """Valider un batch d'emails"""
        for site in sites:
            if not running:
                logger.info("⚠️  Arrêt demandé, interruption du batch...")
                break

            self.validate_email_entry(site, session)

            # Pause entre chaque validation
            time.sleep(0.5)

        # Commit après le batch
        session.commit()
        logger.info(f"💾 Batch de {len(sites)} emails sauvegardé")

    def validate_all_existing(self):
        """Phase 1: Valider tous les emails existants non validés"""
        session = get_session()

        try:
            # Compter les emails à valider
            total_to_validate = session.query(Site).filter(
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != 'NO EMAIL FOUND',
                (Site.email_validated.is_(None)) | (Site.email_validated == False)
            ).count()

            if total_to_validate == 0:
                logger.info("✅ Tous les emails existants sont déjà validés")
                return

            logger.info(f"🚀 Phase 1: Validation de {total_to_validate} emails existants...")

            offset = 0
            while offset < total_to_validate and running:
                # Récupérer un batch
                sites = session.query(Site).filter(
                    Site.emails.isnot(None),
                    Site.emails != '',
                    Site.emails != 'NO EMAIL FOUND',
                    (Site.email_validated.is_(None)) | (Site.email_validated == False)
                ).limit(self.batch_size).offset(offset).all()

                if not sites:
                    break

                logger.info(f"📦 Batch {offset//self.batch_size + 1} - Validation de {len(sites)} emails...")
                self.validate_batch(sites, session)

                offset += self.batch_size

                # Stats de progression
                progress = min(100, (offset / total_to_validate) * 100)
                logger.info(
                    f"📈 Progression: {progress:.1f}% | "
                    f"✅ {self.stats['valid']} | ❌ {self.stats['invalid']} | "
                    f"⚠️  {self.stats['risky']} | Erreurs: {self.stats['errors']}"
                )

            logger.info("✅ Phase 1 terminée - Tous les emails existants validés")

        finally:
            # Récupérer le dernier ID pour la surveillance
            last_site = session.query(Site).order_by(Site.id.desc()).first()
            if last_site:
                self.last_check_id = last_site.id
            session.close()

    def watch_for_new_emails(self):
        """Phase 2: Surveiller en continu les nouveaux emails"""
        logger.info(f"👀 Phase 2: Surveillance des nouveaux emails (vérification toutes les {self.check_interval}s)...")

        while running:
            session = get_session()

            try:
                # Chercher les nouveaux emails depuis le dernier check
                new_sites = session.query(Site).filter(
                    Site.id > self.last_check_id,
                    Site.emails.isnot(None),
                    Site.emails != '',
                    Site.emails != 'NO EMAIL FOUND',
                    (Site.email_validated.is_(None)) | (Site.email_validated == False)
                ).all()

                if new_sites:
                    logger.info(f"🆕 {len(new_sites)} nouveaux emails détectés !")
                    self.validate_batch(new_sites, session)

                    # Mettre à jour le dernier ID
                    self.last_check_id = max(site.id for site in new_sites)

                # Attendre avant la prochaine vérification
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                time.sleep(self.check_interval)
            finally:
                session.close()

    def print_final_stats(self):
        """Afficher les statistiques finales"""
        duration = (datetime.utcnow() - self.stats['start_time']).total_seconds()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)

        logger.info("\n" + "=" * 70)
        logger.info("📊 STATISTIQUES FINALES DU DAEMON")
        logger.info("=" * 70)
        logger.info(f"Durée d'exécution: {hours}h {minutes}m")
        logger.info(f"Total validé: {self.stats['total_validated']}")
        logger.info(f"✅ Valides: {self.stats['valid']}")
        logger.info(f"❌ Invalides: {self.stats['invalid']}")
        logger.info(f"⚠️  Risqués: {self.stats['risky']}")
        logger.info(f"Erreurs: {self.stats['errors']}")
        logger.info("=" * 70)

    def run(self):
        """Lancer le daemon"""
        logger.info("=" * 70)
        logger.info("🤖 DAEMON DE VALIDATION AUTOMATIQUE DES EMAILS")
        logger.info("=" * 70)
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Intervalle de surveillance: {self.check_interval}s")
        logger.info("Appuyez sur Ctrl+C pour arrêter")
        logger.info("=" * 70)
        logger.info("")

        try:
            # Phase 1: Valider tous les emails existants
            self.validate_all_existing()

            # Phase 2: Surveiller les nouveaux emails
            if running:
                self.watch_for_new_emails()

        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        finally:
            self.print_final_stats()
            logger.info("👋 Daemon arrêté")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Daemon de validation automatique des emails')
    parser.add_argument('--batch-size', type=int, default=50, help='Taille des batchs (défaut: 50)')
    parser.add_argument('--check-interval', type=int, default=60, help='Intervalle de vérification en secondes (défaut: 60)')

    args = parser.parse_args()

    # Lancer le daemon
    daemon = EmailValidationDaemon(
        batch_size=args.batch_size,
        check_interval=args.check_interval
    )
    daemon.run()
