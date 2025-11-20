#!/usr/bin/env python3
"""
Worker pour les campagnes continues
Vérifie périodiquement les campagnes continues actives et envoie des emails aux nouveaux contacts
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict
import os
import sys

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from campaign_database import (
    get_campaign_session, Campaign, CampaignStatus, CampaignEmail, EmailStatus
)
from campaign_manager import CampaignManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/www/Scrap_Email/continuous_campaign_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ContinuousCampaignWorker:
    """Worker pour gérer les campagnes continues"""

    def __init__(self):
        """Initialiser le worker"""
        self.campaign_manager = CampaignManager()
        self.campaign_session = get_campaign_session()
        logger.info("✅ Continuous Campaign Worker initialisé")

    def get_active_continuous_campaigns(self) -> List[Campaign]:
        """
        Récupérer toutes les campagnes continues actives

        Returns:
            Liste des campagnes continues en cours
        """
        campaigns = self.campaign_session.query(Campaign).filter(
            Campaign.is_continuous == True,
            Campaign.status.in_([CampaignStatus.RUNNING, CampaignStatus.SCHEDULED])
        ).all()

        return campaigns

    def get_new_recipients_for_campaign(self, campaign: Campaign) -> List:
        """
        Trouver les nouveaux contacts qui n'ont pas encore reçu l'email de cette campagne

        Args:
            campaign: La campagne continue

        Returns:
            Liste des nouveaux sites éligibles
        """
        # Récupérer tous les destinataires éligibles selon les critères de la campagne
        all_eligible = self.campaign_manager.get_recipients(campaign)

        # Récupérer les emails déjà envoyés pour cette campagne
        sent_emails = self.campaign_session.query(CampaignEmail.to_email).filter(
            CampaignEmail.campaign_id == campaign.id
        ).all()
        sent_emails_set = {email[0] for email in sent_emails}

        # Filtrer pour ne garder que les nouveaux
        new_recipients = []
        for site in all_eligible:
            primary_email = site.emails.split(',')[0].split(';')[0].strip()
            if primary_email not in sent_emails_set:
                new_recipients.append(site)

        return new_recipients

    def process_continuous_campaign(self, campaign: Campaign) -> Dict:
        """
        Traiter une campagne continue: trouver les nouveaux contacts et leur envoyer l'email

        Args:
            campaign: La campagne à traiter

        Returns:
            Résultat du traitement
        """
        logger.info(f"🔄 Traitement de la campagne continue '{campaign.name}' (ID: {campaign.id})")

        try:
            # Trouver les nouveaux destinataires
            new_recipients = self.get_new_recipients_for_campaign(campaign)

            if not new_recipients:
                logger.info(f"   ℹ️  Aucun nouveau contact pour la campagne '{campaign.name}'")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'new_recipients': 0,
                    'emails_sent': 0
                }

            logger.info(f"   📬 {len(new_recipients)} nouveaux contacts trouvés pour '{campaign.name}'")

            # Limiter le nombre d'envois par exécution pour ne pas surcharger
            max_per_run = 50
            recipients_to_process = new_recipients[:max_per_run]

            if len(new_recipients) > max_per_run:
                logger.info(f"   ⚠️  Limitation à {max_per_run} envois pour cette exécution")

            # Créer les entrées CampaignEmail pour les nouveaux destinataires
            emails_added = 0
            for site in recipients_to_process:
                primary_email = site.emails.split(',')[0].split(';')[0].strip()

                campaign_email = CampaignEmail(
                    campaign_id=campaign.id,
                    site_id=site.id,
                    to_email=primary_email,
                    to_domain=site.domain,
                    status=EmailStatus.PENDING
                )
                self.campaign_session.add(campaign_email)
                emails_added += 1

            self.campaign_session.commit()
            logger.info(f"   ✅ {emails_added} nouveaux destinataires ajoutés à la campagne")

            # Envoyer les emails (limité par le max_emails_per_day de la campagne)
            # Vérifier combien d'emails ont déjà été envoyés aujourd'hui
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            emails_sent_today = self.campaign_session.query(CampaignEmail).filter(
                CampaignEmail.campaign_id == campaign.id,
                CampaignEmail.sent_at >= today_start,
                CampaignEmail.status.in_([EmailStatus.SENT, EmailStatus.DELIVERED, EmailStatus.OPENED, EmailStatus.CLICKED])
            ).count()

            remaining_quota = campaign.max_emails_per_day - emails_sent_today

            if remaining_quota <= 0:
                logger.info(f"   ⚠️  Quota quotidien atteint pour '{campaign.name}' ({emails_sent_today}/{campaign.max_emails_per_day})")
                return {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'new_recipients': len(new_recipients),
                    'emails_sent': 0,
                    'quota_reached': True
                }

            # Envoyer jusqu'à la limite du quota
            emails_to_send = min(emails_added, remaining_quota)
            logger.info(f"   📤 Envoi de {emails_to_send} emails (quota restant: {remaining_quota})")

            # Mettre à jour le statut si nécessaire
            if campaign.status == CampaignStatus.SCHEDULED:
                campaign.status = CampaignStatus.RUNNING
                campaign.started_at = datetime.utcnow()
                self.campaign_session.commit()

            # Envoyer les emails via le campaign manager
            result = self.campaign_manager.send_campaign_emails(campaign.id, limit=emails_to_send)

            # Mettre à jour les statistiques de la campagne
            campaign.total_recipients = self.campaign_session.query(CampaignEmail).filter(
                CampaignEmail.campaign_id == campaign.id
            ).count()
            self.campaign_session.commit()

            logger.info(f"   ✅ Campagne '{campaign.name}': {result.get('sent', 0)} emails envoyés")

            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'new_recipients': len(new_recipients),
                'emails_sent': result.get('sent', 0),
                'quota_reached': False
            }

        except Exception as e:
            logger.error(f"   ❌ Erreur lors du traitement de la campagne '{campaign.name}': {str(e)}", exc_info=True)
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'error': str(e)
            }

    def run_once(self):
        """Exécuter une itération du worker"""
        logger.info("=" * 80)
        logger.info("🚀 Démarrage d'un cycle de traitement des campagnes continues")
        logger.info("=" * 80)

        try:
            # Récupérer toutes les campagnes continues actives
            campaigns = self.get_active_continuous_campaigns()

            if not campaigns:
                logger.info("ℹ️  Aucune campagne continue active")
                return

            logger.info(f"📋 {len(campaigns)} campagne(s) continue(s) active(s) trouvée(s)")

            # Traiter chaque campagne
            results = []
            for campaign in campaigns:
                result = self.process_continuous_campaign(campaign)
                results.append(result)

                # Pause entre les campagnes pour ne pas surcharger
                time.sleep(5)

            # Résumé
            logger.info("=" * 80)
            logger.info("📊 Résumé du cycle:")
            total_new = sum(r.get('new_recipients', 0) for r in results)
            total_sent = sum(r.get('emails_sent', 0) for r in results)
            logger.info(f"   - Nouveaux contacts détectés: {total_new}")
            logger.info(f"   - Emails envoyés: {total_sent}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Erreur lors du cycle de traitement: {str(e)}", exc_info=True)

    def run(self, interval_minutes: int = 30):
        """
        Exécuter le worker en continu

        Args:
            interval_minutes: Intervalle entre les exécutions (en minutes)
        """
        logger.info("=" * 80)
        logger.info("🎬 DÉMARRAGE DU CONTINUOUS CAMPAIGN WORKER")
        logger.info(f"⏱️  Intervalle: {interval_minutes} minutes")
        logger.info("=" * 80)

        while True:
            try:
                self.run_once()

                # Attendre avant la prochaine exécution
                logger.info(f"⏸️  Prochaine exécution dans {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("🛑 Arrêt du worker demandé par l'utilisateur")
                break
            except Exception as e:
                logger.error(f"❌ Erreur critique: {str(e)}", exc_info=True)
                logger.info("⏸️  Attente de 5 minutes avant de réessayer...")
                time.sleep(300)


def main():
    """Point d'entrée principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Worker pour les campagnes continues')
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Intervalle entre les exécutions (en minutes, défaut: 30)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Exécuter une seule fois puis quitter'
    )

    args = parser.parse_args()

    worker = ContinuousCampaignWorker()

    if args.once:
        logger.info("Mode: exécution unique")
        worker.run_once()
    else:
        logger.info("Mode: exécution continue")
        worker.run(interval_minutes=args.interval)


if __name__ == '__main__':
    main()
