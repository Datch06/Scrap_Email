#!/usr/bin/env python3
"""
Gestionnaire de campagnes d'emails
"""

import time
import re
from datetime import datetime
from typing import List, Dict, Optional
import logging
from campaign_database import (
    get_campaign_session,
    Campaign,
    CampaignEmail,
    EmailTemplate,
    Unsubscribe,
    CampaignStatus,
    EmailStatus
)
from database import get_session, Site
from ses_manager import SESManager
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CampaignManager:
    """Gestionnaire de campagnes d'emails"""

    def __init__(self):
        self.campaign_session = get_campaign_session()
        self.site_session = get_session()
        self.ses_manager = SESManager()

    def create_campaign(
        self,
        name: str,
        subject: str,
        html_body: str,
        description: str = None,
        text_body: str = None,
        min_validation_score: int = 80,
        only_deliverable: bool = True,
        max_emails_per_day: int = 200
    ) -> Campaign:
        """
        Créer une nouvelle campagne

        Args:
            name: Nom de la campagne
            subject: Sujet de l'email
            html_body: Corps HTML de l'email
            description: Description de la campagne
            text_body: Version texte de l'email
            min_validation_score: Score minimum de validation
            only_deliverable: Envoyer uniquement aux emails délivrables
            max_emails_per_day: Limite d'envoi quotidienne

        Returns:
            Campaign créée
        """
        campaign = Campaign(
            name=name,
            description=description,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=self.ses_manager.sender_email,
            from_name=self.ses_manager.sender_name,
            min_validation_score=min_validation_score,
            only_deliverable=only_deliverable,
            max_emails_per_day=max_emails_per_day,
            status=CampaignStatus.DRAFT
        )

        self.campaign_session.add(campaign)
        self.campaign_session.commit()

        logger.info(f"✅ Campagne créée: {name} (ID: {campaign.id})")
        return campaign

    def get_recipients(self, campaign: Campaign) -> List[Site]:
        """
        Récupérer les destinataires éligibles pour une campagne

        Args:
            campaign: Campagne

        Returns:
            Liste des sites éligibles
        """
        query = self.site_session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND',
            Site.email_validated == True,
            Site.email_validation_score >= campaign.min_validation_score,
            Site.is_active == True  # Exclure les sites désactivés
        )

        if campaign.only_deliverable:
            query = query.filter(Site.email_deliverable == True)

        # Récupérer les emails à exclure (déjà envoyés + désinscrits)
        sent_emails = self.campaign_session.query(CampaignEmail.to_email).filter(
            CampaignEmail.campaign_id == campaign.id
        ).all()
        sent_emails = [e[0] for e in sent_emails]

        # Récupérer les emails désinscrits
        unsubscribed = self.campaign_session.query(Unsubscribe.email).all()
        unsubscribed_emails = [e[0] for e in unsubscribed]

        # Combiner les exclusions
        excluded_emails = set(sent_emails + unsubscribed_emails)

        if excluded_emails:
            # Filtrer les sites dont l'email principal est exclu
            eligible_sites = []
            for site in query.all():
                primary_email = site.emails.split(',')[0].split(';')[0].strip()
                if primary_email not in excluded_emails:
                    eligible_sites.append(site)
            return eligible_sites

        return query.all()

    def prepare_campaign(self, campaign_id: int) -> Dict:
        """
        Préparer une campagne pour l'envoi

        Args:
            campaign_id: ID de la campagne

        Returns:
            Dict avec statistiques de préparation
        """
        campaign = self.campaign_session.query(Campaign).get(campaign_id)
        if not campaign:
            raise ValueError(f"Campagne {campaign_id} introuvable")

        # Récupérer les destinataires
        recipients = self.get_recipients(campaign)

        # Créer les entrées CampaignEmail
        for site in recipients:
            # Extraire le premier email
            primary_email = site.emails.split(',')[0].split(';')[0].strip()

            campaign_email = CampaignEmail(
                campaign_id=campaign.id,
                site_id=site.id,
                to_email=primary_email,
                to_domain=site.domain,
                status=EmailStatus.PENDING
            )
            self.campaign_session.add(campaign_email)

        # Mettre à jour la campagne
        campaign.total_recipients = len(recipients)
        campaign.status = CampaignStatus.SCHEDULED
        self.campaign_session.commit()

        logger.info(f"✅ Campagne {campaign.name} préparée: {len(recipients)} destinataires")

        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'total_recipients': len(recipients),
            'status': 'scheduled'
        }

    def add_unsubscribe_footer(self, html_body: str, email: str, campaign_id: int = None) -> str:
        """
        Ajouter un footer avec lien de désinscription au HTML

        Args:
            html_body: Contenu HTML
            email: Email du destinataire
            campaign_id: ID de la campagne (optionnel)

        Returns:
            HTML avec footer de désinscription
        """
        # Construire le lien de désinscription
        unsubscribe_url = f'https://admin.perfect-cocon-seo.fr/unsubscribe?email={email}'
        if campaign_id:
            unsubscribe_url += f'&campaign_id={campaign_id}'

        # Footer HTML
        footer_html = f'''
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 12px; color: #888;">
            <p>Vous recevez cet email car nous pensons que notre service pourrait vous intéresser.</p>
            <p>
                <a href="{unsubscribe_url}" style="color: #888; text-decoration: underline;">
                    Se désinscrire de nos communications
                </a>
            </p>
            <p style="margin-top: 10px;">
                Perfect Cocon SEO - Prospection de backlinks de qualité
            </p>
        </div>
        '''

        # Si l'email contient déjà une balise de fermeture </body>, insérer avant
        if '</body>' in html_body:
            html_body = html_body.replace('</body>', footer_html + '</body>')
        else:
            # Sinon, ajouter à la fin
            html_body += footer_html

        return html_body

    def personalize_email(self, html_body: str, site: Site, campaign_id: int = None) -> str:
        """
        Personnaliser un email avec les données du site

        Args:
            html_body: Template HTML
            site: Site destinataire
            campaign_id: ID de la campagne (optionnel, pour le lien de désinscription)

        Returns:
            HTML personnalisé
        """
        # Variables disponibles
        variables = {
            'domain': site.domain,
            'email': site.emails.split(',')[0].split(';')[0].strip() if site.emails else '',
            'siret': site.siret or '',
            'siren': site.siren or '',
            'leaders': site.leaders or '',
            'source_url': site.source_url or '',
        }

        # Remplacer les variables {{variable}}
        personalized = html_body
        for key, value in variables.items():
            personalized = personalized.replace(f'{{{{{key}}}}}', str(value))

        # Construire le lien de désinscription
        unsubscribe_link = f'https://admin.perfect-cocon-seo.fr/unsubscribe?email={variables["email"]}'
        if campaign_id:
            unsubscribe_link += f'&campaign_id={campaign_id}'

        # Si le template contient {{unsubscribe_link}}, le remplacer
        if '{{unsubscribe_link}}' in personalized:
            personalized = personalized.replace('{{unsubscribe_link}}', unsubscribe_link)
        else:
            # Sinon, ajouter automatiquement un footer de désinscription
            personalized = self.add_unsubscribe_footer(personalized, variables["email"], campaign_id)

        return personalized

    def send_campaign_email(self, campaign_email: CampaignEmail, campaign: Campaign) -> bool:
        """
        Envoyer un email de campagne

        Args:
            campaign_email: Email de campagne
            campaign: Campagne

        Returns:
            True si envoyé avec succès
        """
        try:
            # Récupérer le site
            site = self.site_session.query(Site).get(campaign_email.site_id)
            if not site:
                raise ValueError(f"Site {campaign_email.site_id} introuvable")

            # Personnaliser le contenu
            personalized_html = self.personalize_email(campaign.html_body, site, campaign.id)
            personalized_subject = self.personalize_email(campaign.subject, site, campaign.id)

            # Nettoyer le HTML du sujet (le sujet doit être en texte brut)
            personalized_subject = re.sub(r'<[^>]+>', '', personalized_subject)
            personalized_subject = personalized_subject.strip()

            # Envoyer via SES
            result = self.ses_manager.send_email(
                to_email=campaign_email.to_email,
                subject=personalized_subject,
                html_body=personalized_html,
                text_body=campaign.text_body,
                reply_to=campaign.reply_to
            )

            if result['success']:
                campaign_email.status = EmailStatus.SENT
                campaign_email.sent_at = datetime.utcnow()
                campaign_email.message_id = result.get('message_id')  # Enregistrer le message_id
                campaign.emails_sent += 1
            else:
                campaign_email.status = EmailStatus.FAILED
                campaign_email.error_message = result.get('error', 'Unknown error')
                campaign.emails_failed += 1

            self.campaign_session.commit()
            return result['success']

        except Exception as e:
            logger.error(f"❌ Erreur envoi à {campaign_email.to_email}: {e}")
            campaign_email.status = EmailStatus.FAILED
            campaign_email.error_message = str(e)
            campaign.emails_failed += 1
            self.campaign_session.commit()
            return False

    def run_campaign(self, campaign_id: int, limit: int = None) -> Dict:
        """
        Lancer l'envoi d'une campagne

        Args:
            campaign_id: ID de la campagne
            limit: Limite d'emails à envoyer (None = tous)

        Returns:
            Statistiques d'envoi
        """
        campaign = self.campaign_session.query(Campaign).get(campaign_id)
        if not campaign:
            raise ValueError(f"Campagne {campaign_id} introuvable")

        # Vérifier le statut
        if campaign.status not in [CampaignStatus.SCHEDULED, CampaignStatus.PAUSED]:
            raise ValueError(f"Campagne en statut {campaign.status.value}, impossible de lancer")

        # Mettre à jour le statut
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.utcnow()
        self.campaign_session.commit()

        # Récupérer les emails en attente
        query = self.campaign_session.query(CampaignEmail).filter(
            CampaignEmail.campaign_id == campaign.id,
            CampaignEmail.status == EmailStatus.PENDING
        )

        if limit:
            query = query.limit(limit)

        pending_emails = query.all()

        logger.info(f"🚀 Lancement campagne '{campaign.name}': {len(pending_emails)} emails à envoyer")

        stats = {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'sent': 0,
            'failed': 0,
            'start_time': datetime.utcnow()
        }

        for i, campaign_email in enumerate(pending_emails, 1):
            success = self.send_campaign_email(campaign_email, campaign)

            if success:
                stats['sent'] += 1
            else:
                stats['failed'] += 1

            # Afficher la progression
            if i % 10 == 0:
                logger.info(f"📈 Progression: {i}/{len(pending_emails)} ({i/len(pending_emails)*100:.1f}%)")

            # Pause entre emails
            if i < len(pending_emails):
                time.sleep(campaign.delay_between_emails)

        # Vérifier si la campagne est terminée
        remaining = self.campaign_session.query(CampaignEmail).filter(
            CampaignEmail.campaign_id == campaign.id,
            CampaignEmail.status == EmailStatus.PENDING
        ).count()

        if remaining == 0:
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.utcnow()
        else:
            campaign.status = CampaignStatus.PAUSED

        self.campaign_session.commit()

        stats['end_time'] = datetime.utcnow()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
        stats['remaining'] = remaining

        logger.info("\n" + "=" * 70)
        logger.info("📊 RAPPORT DE CAMPAGNE")
        logger.info("=" * 70)
        logger.info(f"Campagne: {campaign.name}")
        logger.info(f"✅ Envoyés: {stats['sent']}")
        logger.info(f"❌ Échoués: {stats['failed']}")
        logger.info(f"⏳ Restants: {stats['remaining']}")
        logger.info(f"⏱️  Durée: {int(stats['duration'])}s")
        logger.info("=" * 70)

        return stats

    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Récupérer les statistiques d'une campagne"""
        campaign = self.campaign_session.query(Campaign).get(campaign_id)
        if not campaign:
            raise ValueError(f"Campagne {campaign_id} introuvable")

        return campaign.to_dict()

    def list_campaigns(self) -> List[Dict]:
        """Lister toutes les campagnes"""
        campaigns = self.campaign_session.query(Campaign).order_by(
            Campaign.created_at.desc()
        ).all()
        return [c.to_dict() for c in campaigns]

    def send_test_email(self, campaign_id: int, test_emails: List[str], test_domain: str = "test.example.com") -> Dict:
        """
        Envoyer un email de test avec le contenu de la campagne

        Args:
            campaign_id: ID de la campagne
            test_emails: Liste des emails de test
            test_domain: Domaine fictif pour la personnalisation

        Returns:
            Dict avec résultats d'envoi
        """
        campaign = self.campaign_session.query(Campaign).get(campaign_id)
        if not campaign:
            raise ValueError(f"Campagne {campaign_id} introuvable")

        # Créer un site fictif pour la personnalisation
        test_site = Site(
            domain=test_domain,
            emails=test_emails[0],
            siret="12345678901234",
            siren="123456789",
            leaders="Jean Dupont, Marie Martin",
            source_url="https://example.com"
        )

        results = {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'sent': [],
            'failed': []
        }

        for email in test_emails:
            try:
                # Personnaliser le contenu avec le site de test
                personalized_html = self.personalize_email(campaign.html_body, test_site, campaign.id)
                personalized_subject = self.personalize_email(campaign.subject, test_site, campaign.id)

                # Nettoyer le HTML du sujet (le sujet doit être en texte brut)
                personalized_subject = re.sub(r'<[^>]+>', '', personalized_subject)
                personalized_subject = personalized_subject.strip()

                # Ajouter un préfixe [TEST] au sujet
                personalized_subject = f"[TEST] {personalized_subject}"

                # Envoyer l'email
                result = self.ses_manager.send_email(
                    to_email=email,
                    subject=personalized_subject,
                    html_body=personalized_html,
                    text_body=campaign.text_body,
                    reply_to=campaign.reply_to
                )

                if result['success']:
                    results['sent'].append(email)
                    logger.info(f"✅ Email de test envoyé à {email}")
                else:
                    results['failed'].append({'email': email, 'error': result.get('error', 'Échec envoi SES')})
                    logger.error(f"❌ Échec envoi test à {email}")

            except Exception as e:
                results['failed'].append({'email': email, 'error': str(e)})
                logger.error(f"❌ Erreur envoi test à {email}: {e}")

        results['total_sent'] = len(results['sent'])
        results['total_failed'] = len(results['failed'])

        logger.info(f"📊 Test campagne '{campaign.name}': {results['total_sent']} envoyés, {results['total_failed']} échoués")

        return results


if __name__ == '__main__':
    manager = CampaignManager()
    print("✅ Campaign Manager initialisé")
    print(f"📧 Expéditeur: {manager.ses_manager.sender_email}")
