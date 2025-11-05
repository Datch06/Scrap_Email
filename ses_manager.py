#!/usr/bin/env python3
"""
Amazon SES Manager - Gestion complète de l'envoi d'emails
"""

import boto3
from botocore.exceptions import ClientError
import logging
from datetime import datetime
import time
from typing import List, Dict, Optional
import json

# Configuration
try:
    from aws_config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_REGION,
        SES_SENDER_EMAIL,
        SES_SENDER_NAME,
        MAX_SEND_RATE,
        DELAY_BETWEEN_EMAILS,
        validate_config
    )
except ImportError:
    print("❌ Fichier aws_config.py non trouvé")
    print("   Créez-le d'abord avec vos credentials AWS")
    exit(1)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SESManager:
    """Gestionnaire Amazon SES pour l'envoi d'emails"""

    def __init__(self):
        """Initialiser le client SES"""
        if not validate_config():
            raise ValueError("Configuration AWS invalide")

        self.client = boto3.client(
            'ses',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.sender_email = SES_SENDER_EMAIL
        self.sender_name = SES_SENDER_NAME
        self.region = AWS_REGION

    def verify_email(self, email: str) -> bool:
        """
        Vérifier une adresse email dans SES

        Args:
            email: Adresse email à vérifier

        Returns:
            True si la demande de vérification a été envoyée
        """
        try:
            response = self.client.verify_email_identity(EmailAddress=email)
            logger.info(f"✅ Demande de vérification envoyée à {email}")
            logger.info(f"   Vérifiez votre boîte mail et cliquez sur le lien")
            return True
        except ClientError as e:
            logger.error(f"❌ Erreur vérification: {e}")
            return False

    def verify_domain(self, domain: str) -> Dict:
        """
        Vérifier un domaine dans SES

        Args:
            domain: Nom de domaine (ex: example.com)

        Returns:
            Dict avec les enregistrements DNS à configurer
        """
        try:
            response = self.client.verify_domain_identity(Domain=domain)
            verification_token = response['VerificationToken']

            logger.info(f"✅ Domaine {domain} en cours de vérification")
            logger.info(f"\n📋 Ajoutez cet enregistrement TXT à votre DNS:")
            logger.info(f"   Nom: _amazonses.{domain}")
            logger.info(f"   Type: TXT")
            logger.info(f"   Valeur: {verification_token}")

            return {
                'domain': domain,
                'verification_token': verification_token,
                'dns_record': f"_amazonses.{domain} TXT {verification_token}"
            }
        except ClientError as e:
            logger.error(f"❌ Erreur vérification domaine: {e}")
            return {}

    def check_verification_status(self, identity: str) -> str:
        """
        Vérifier le statut de vérification d'une identité

        Args:
            identity: Email ou domaine

        Returns:
            'Success', 'Pending', 'Failed', 'NotFound'
        """
        try:
            response = self.client.get_identity_verification_attributes(
                Identities=[identity]
            )

            if identity in response['VerificationAttributes']:
                status = response['VerificationAttributes'][identity]['VerificationStatus']
                return status
            else:
                return 'NotFound'
        except ClientError as e:
            logger.error(f"❌ Erreur vérification statut: {e}")
            return 'Error'

    def get_send_quota(self) -> Dict:
        """
        Récupérer les quotas d'envoi

        Returns:
            Dict avec Max24HourSend, MaxSendRate, SentLast24Hours
        """
        try:
            response = self.client.get_send_quota()

            quota = {
                'max_24h': int(response['Max24HourSend']),
                'max_rate': int(response['MaxSendRate']),
                'sent_24h': int(response['SentLast24Hours']),
                'remaining_24h': int(response['Max24HourSend'] - response['SentLast24Hours'])
            }

            logger.info(f"📊 Quotas SES:")
            logger.info(f"   Limite 24h: {quota['max_24h']}")
            logger.info(f"   Envoyés 24h: {quota['sent_24h']}")
            logger.info(f"   Restants: {quota['remaining_24h']}")
            logger.info(f"   Débit max: {quota['max_rate']}/s")

            return quota
        except ClientError as e:
            logger.error(f"❌ Erreur quota: {e}")
            return {}

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict:
        """
        Envoyer un email

        Args:
            to_email: Destinataire
            subject: Sujet
            html_body: Corps HTML
            text_body: Corps texte (optionnel)
            reply_to: Email de réponse (optionnel)

        Returns:
            Dict avec 'success' (bool) et 'message_id' (str) si succès
        """
        try:
            # Préparer le message
            message = {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                }
            }

            # Ajouter le corps texte si fourni
            if text_body:
                message['Body']['Text'] = {'Data': text_body, 'Charset': 'UTF-8'}

            # Préparer les paramètres d'envoi
            params = {
                'Source': f'"{self.sender_name}" <{self.sender_email}>',
                'Destination': {'ToAddresses': [to_email]},
                'Message': message
            }

            # Ajouter Reply-To si fourni
            if reply_to:
                params['ReplyToAddresses'] = [reply_to]

            # Envoyer
            response = self.client.send_email(**params)
            message_id = response['MessageId']

            logger.info(f"✅ Email envoyé à {to_email} (ID: {message_id})")
            return {'success': True, 'message_id': message_id}

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            if error_code == 'MessageRejected':
                logger.error(f"❌ Email rejeté pour {to_email}: {error_message}")
            elif error_code == 'MailFromDomainNotVerified':
                logger.error(f"❌ Domaine non vérifié: {self.sender_email}")
            else:
                logger.error(f"❌ Erreur envoi à {to_email}: {error_code} - {error_message}")

            return {'success': False, 'error': error_message}

    def send_bulk_emails(
        self,
        recipients: List[Dict],
        subject: str,
        html_template: str,
        delay: int = DELAY_BETWEEN_EMAILS
    ) -> Dict:
        """
        Envoyer des emails en masse avec personnalisation

        Args:
            recipients: Liste de dict avec 'email' et variables de personnalisation
            subject: Sujet de l'email
            html_template: Template HTML avec variables {{var}}
            delay: Délai entre chaque email en secondes

        Returns:
            Dict avec statistiques d'envoi
        """
        stats = {
            'total': len(recipients),
            'sent': 0,
            'failed': 0,
            'start_time': datetime.utcnow()
        }

        logger.info(f"🚀 Envoi de {stats['total']} emails...")

        for i, recipient in enumerate(recipients, 1):
            # Personnaliser le contenu
            email = recipient.get('email')
            html_body = html_template

            # Remplacer les variables
            for key, value in recipient.items():
                if key != 'email':
                    html_body = html_body.replace(f'{{{{{key}}}}}', str(value))

            # Envoyer
            success = self.send_email(
                to_email=email,
                subject=subject,
                html_body=html_body
            )

            if success:
                stats['sent'] += 1
            else:
                stats['failed'] += 1

            # Afficher progression
            if i % 10 == 0:
                logger.info(f"📈 Progression: {i}/{stats['total']} ({i/stats['total']*100:.1f}%)")

            # Pause entre emails
            if i < stats['total']:
                time.sleep(delay)

        # Stats finales
        stats['end_time'] = datetime.utcnow()
        duration = (stats['end_time'] - stats['start_time']).total_seconds()

        logger.info("\n" + "=" * 70)
        logger.info("📊 RAPPORT D'ENVOI")
        logger.info("=" * 70)
        logger.info(f"Total: {stats['total']}")
        logger.info(f"✅ Envoyés: {stats['sent']}")
        logger.info(f"❌ Échoués: {stats['failed']}")
        logger.info(f"⏱️  Durée: {int(duration)}s")
        logger.info(f"📈 Taux de succès: {stats['sent']/stats['total']*100:.1f}%")
        logger.info("=" * 70)

        return stats


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def setup_ses():
    """Assistant de configuration SES"""
    print("=" * 70)
    print("🔧 ASSISTANT DE CONFIGURATION AMAZON SES")
    print("=" * 70)
    print()

    manager = SESManager()

    # Vérifier les quotas
    print("1️⃣ Vérification des quotas...")
    quota = manager.get_send_quota()

    if quota['max_24h'] == 200:
        print("\n⚠️  SANDBOX MODE DÉTECTÉ")
        print("   Vous êtes limité à 200 emails/jour")
        print("   Pour augmenter, demandez la sortie du sandbox:")
        print("   https://console.aws.amazon.com/ses → Account Dashboard → Request production access")

    print("\n2️⃣ Vérification de l'expéditeur...")
    status = manager.check_verification_status(SES_SENDER_EMAIL)

    if status == 'Success':
        print(f"✅ Email {SES_SENDER_EMAIL} vérifié")
    elif status == 'Pending':
        print(f"⏳ Email {SES_SENDER_EMAIL} en attente de vérification")
        print("   Vérifiez votre boîte mail et cliquez sur le lien")
    elif status == 'NotFound':
        print(f"❌ Email {SES_SENDER_EMAIL} non vérifié")
        print(f"\n   Voulez-vous vérifier cet email maintenant? (o/n)")
        response = input("   > ")
        if response.lower() == 'o':
            manager.verify_email(SES_SENDER_EMAIL)

    print("\n✅ Configuration terminée!")
    print("\n📝 Prochaines étapes:")
    print("   1. Vérifiez votre email expéditeur (si pas encore fait)")
    print("   2. Demandez la sortie du sandbox (si nécessaire)")
    print("   3. Testez l'envoi avec test_ses.py")


if __name__ == '__main__':
    setup_ses()
