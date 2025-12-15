#!/usr/bin/env python3
"""
Daemon pour récupérer les réponses aux campagnes via IMAP
Vérifie périodiquement la boîte email et associe les réponses aux campagnes
"""

import imaplib
import email
from email.header import decode_header
import time
import re
import logging
from datetime import datetime
from typing import Optional, Tuple, List
import argparse

from campaign_database import (
    get_campaign_session, CampaignReply, CampaignEmail,
    ReplyStatus, ReplySentiment
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/www/Scrap_Email/email_reply_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EmailReplyChecker:
    """Vérificateur de réponses par IMAP"""

    def __init__(self, imap_server: str, imap_port: int, email_address: str, password: str):
        """
        Initialiser le vérificateur

        Args:
            imap_server: Serveur IMAP (ex: imap.gmail.com)
            imap_port: Port IMAP (993 pour SSL)
            email_address: Adresse email
            password: Mot de passe ou app password
        """
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.email_address = email_address
        self.password = password
        self.mail = None

    def connect(self) -> bool:
        """Connexion au serveur IMAP"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.email_address, self.password)
            logger.info(f"✅ Connecté à {self.imap_server} avec {self.email_address}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur de connexion IMAP: {e}")
            return False

    def disconnect(self):
        """Déconnexion du serveur IMAP"""
        try:
            if self.mail:
                self.mail.logout()
                logger.info("✅ Déconnecté du serveur IMAP")
        except:
            pass

    def decode_header_value(self, value: str) -> str:
        """Décoder un header d'email"""
        if not value:
            return ""

        decoded_parts = []
        for part, encoding in decode_header(value):
            if isinstance(part, bytes):
                # Gérer les encodings inconnus
                try:
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                except (LookupError, UnicodeDecodeError):
                    # Encoding inconnu, essayer utf-8 puis latin-1
                    try:
                        decoded_parts.append(part.decode('utf-8', errors='ignore'))
                    except:
                        decoded_parts.append(part.decode('latin-1', errors='ignore'))
            else:
                decoded_parts.append(str(part))
        return ' '.join(decoded_parts)

    def extract_email_address(self, email_field: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extraire nom et email d'un champ From/To

        Returns:
            (nom, email)
        """
        if not email_field:
            return None, None

        # Pattern pour extraire "Name <email@domain.com>" ou juste "email@domain.com"
        match = re.search(r'([^<]+)?<([^>]+)>', email_field)
        if match:
            name = match.group(1).strip() if match.group(1) else None
            email_addr = match.group(2).strip()
            return name, email_addr

        # Si pas de <>, c'est juste l'email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_field)
        if email_match:
            return None, email_match.group(0)

        return None, None

    def get_text_from_email(self, msg) -> Tuple[Optional[str], Optional[str]]:
        """
        Extraire le texte et HTML d'un email

        Returns:
            (text_body, html_body)
        """
        text_body = None
        html_body = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Ignorer les pièces jointes
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain" and not text_body:
                    try:
                        text_body = part.get_payload(decode=True).decode(errors='ignore')
                    except:
                        pass

                elif content_type == "text/html" and not html_body:
                    try:
                        html_body = part.get_payload(decode=True).decode(errors='ignore')
                    except:
                        pass
        else:
            # Non multipart
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    text_body = payload.decode(errors='ignore')
            except:
                pass

        return text_body, html_body

    def is_auto_reply(self, msg) -> bool:
        """Détecter si c'est une réponse automatique"""
        # Headers communs pour les auto-reply
        auto_reply_headers = [
            'X-Autoreply',
            'X-Autorespond',
            'Auto-Submitted',
            'X-Auto-Response-Suppress',
            'X-Autoresponder'
        ]

        for header in auto_reply_headers:
            if msg.get(header):
                return True

        # Vérifier le sujet
        subject = self.decode_header_value(msg.get('Subject', ''))
        auto_keywords = [
            'out of office', 'automatic reply', 'auto-reply', 'autoreply',
            'away', 'vacation', 'absence', 'hors du bureau', 'absent'
        ]

        subject_lower = subject.lower()
        for keyword in auto_keywords:
            if keyword in subject_lower:
                return True

        return False

    def analyze_sentiment(self, text: str) -> ReplySentiment:
        """
        Analyser le sentiment de base d'un texte

        Returns:
            ReplySentiment
        """
        if not text:
            return ReplySentiment.UNKNOWN

        text_lower = text.lower()

        # Mots positifs
        positive_keywords = [
            'intéressé', 'interested', 'oui', 'yes', 'accord', 'ok',
            'parfait', 'perfect', 'génial', 'great', 'merci', 'thank',
            'volontiers', 'excellent', 'appelez', 'call', 'discuter', 'discuss'
        ]

        # Mots négatifs
        negative_keywords = [
            'non', 'no', 'pas intéressé', 'not interested', 'refus',
            'arrêter', 'stop', 'désabonner', 'unsubscribe', 'spam',
            'enlever', 'remove', 'supprimer', 'delete'
        ]

        positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text_lower)

        if positive_count > negative_count and positive_count > 0:
            return ReplySentiment.POSITIVE
        elif negative_count > positive_count and negative_count > 0:
            return ReplySentiment.NEGATIVE
        elif '?' in text:
            return ReplySentiment.NEUTRAL  # Probablement une question

        return ReplySentiment.UNKNOWN

    def find_original_campaign_email(self, in_reply_to: str, references: str) -> Optional[int]:
        """
        Trouver l'email de campagne original via In-Reply-To ou References

        Returns:
            campaign_email_id ou None
        """
        if not in_reply_to and not references:
            return None

        session = get_campaign_session()

        try:
            # Chercher par In-Reply-To (le plus fiable)
            if in_reply_to:
                email_record = session.query(CampaignEmail).filter(
                    CampaignEmail.message_id == in_reply_to
                ).first()

                if email_record:
                    return email_record.id

            # Chercher dans References (peut contenir plusieurs message-ids)
            if references:
                message_ids = references.split()
                for msg_id in message_ids:
                    msg_id = msg_id.strip('<>')
                    email_record = session.query(CampaignEmail).filter(
                        CampaignEmail.message_id == msg_id
                    ).first()

                    if email_record:
                        return email_record.id

            return None

        finally:
            session.close()

    def check_new_replies(self) -> int:
        """
        Vérifier les nouveaux emails et les enregistrer

        Returns:
            Nombre de réponses trouvées
        """
        if not self.mail:
            if not self.connect():
                return 0

        try:
            # Sélectionner la boîte INBOX
            self.mail.select('INBOX')

            # Chercher TOUS les emails récents (pas seulement UNSEEN)
            # Car les emails peuvent être lus via webmail avant que le daemon les traite
            # Le daemon vérifie l'existence via message_id pour éviter les doublons
            from datetime import timedelta
            since_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
            status, messages = self.mail.search(None, 'SINCE', since_date)

            if status != 'OK':
                logger.warning("Pas de nouveaux emails")
                return 0

            email_ids = messages[0].split()

            if not email_ids:
                logger.info("📭 Aucun nouvel email")
                return 0

            logger.info(f"📬 {len(email_ids)} nouveaux emails trouvés")

            replies_saved = 0
            session = get_campaign_session()

            for email_id in email_ids:
                try:
                    # Récupérer l'email
                    status, msg_data = self.mail.fetch(email_id, '(RFC822)')

                    if status != 'OK':
                        continue

                    # Parser l'email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extraire les headers
                    message_id = msg.get('Message-ID', '').strip('<>')
                    in_reply_to = msg.get('In-Reply-To', '').strip('<>')
                    references = msg.get('References', '')
                    from_field = self.decode_header_value(msg.get('From', ''))
                    subject = self.decode_header_value(msg.get('Subject', ''))
                    date_str = msg.get('Date', '')

                    # Extraire email et nom de l'expéditeur
                    from_name, from_email = self.extract_email_address(from_field)

                    if not from_email:
                        logger.warning(f"Email sans expéditeur valide: {from_field}")
                        continue

                    # Vérifier si on a déjà cette réponse
                    existing = session.query(CampaignReply).filter(
                        CampaignReply.message_id == message_id
                    ).first()

                    if existing:
                        logger.debug(f"Réponse déjà enregistrée: {message_id}")
                        continue

                    # Trouver l'email de campagne original
                    campaign_email_id = self.find_original_campaign_email(in_reply_to, references)

                    campaign_id = None
                    if campaign_email_id:
                        campaign_email = session.query(CampaignEmail).get(campaign_email_id)
                        if campaign_email:
                            campaign_id = campaign_email.campaign_id

                    # Extraire le corps du message
                    text_body, html_body = self.get_text_from_email(msg)

                    # Détecter auto-reply
                    is_auto_reply = self.is_auto_reply(msg)

                    # Analyser le sentiment
                    sentiment = self.analyze_sentiment(text_body or '')

                    # Vérifier si ce message existe déjà (éviter les doublons)
                    existing = session.query(CampaignReply).filter(
                        CampaignReply.message_id == message_id
                    ).first()

                    if existing:
                        logger.debug(f"⏭️ Email déjà traité: {message_id[:50]}")
                        continue

                    # Créer l'enregistrement
                    reply = CampaignReply(
                        campaign_email_id=campaign_email_id,
                        campaign_id=campaign_id,
                        from_email=from_email,
                        from_name=from_name,
                        subject=subject,
                        body_text=text_body,
                        body_html=html_body,
                        message_id=message_id,
                        in_reply_to=in_reply_to,
                        references=references,
                        thread_id=in_reply_to or message_id,  # Utiliser in_reply_to comme thread_id
                        status=ReplyStatus.NEW,
                        sentiment=sentiment,
                        is_auto_reply=is_auto_reply
                    )

                    session.add(reply)
                    session.commit()

                    replies_saved += 1
                    logger.info(f"✅ Réponse enregistrée de {from_email}: {subject[:50]}")

                except Exception as e:
                    logger.error(f"❌ Erreur traitement email {email_id}: {e}", exc_info=True)
                    session.rollback()
                    continue

            session.close()

            return replies_saved

        except Exception as e:
            logger.error(f"❌ Erreur vérification emails: {e}", exc_info=True)
            return 0

    def run_continuous(self, interval_seconds: int = 300):
        """
        Exécuter en continu

        Args:
            interval_seconds: Intervalle entre vérifications (défaut: 5 minutes)
        """
        logger.info("=" * 80)
        logger.info("📧 DÉMARRAGE DU EMAIL REPLY DAEMON")
        logger.info("=" * 80)
        logger.info(f"Serveur IMAP: {self.imap_server}:{self.imap_port}")
        logger.info(f"Email: {self.email_address}")
        logger.info(f"Intervalle: {interval_seconds}s ({interval_seconds//60} minutes)")
        logger.info("=" * 80)

        while True:
            try:
                logger.info(f"\n🔍 Vérification des nouveaux emails...")

                new_replies = self.check_new_replies()

                if new_replies > 0:
                    logger.info(f"📬 {new_replies} nouvelle(s) réponse(s) enregistrée(s)")
                else:
                    logger.info("📭 Aucune nouvelle réponse")

                logger.info(f"⏸️  Prochaine vérification dans {interval_seconds//60} minutes...")
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("\n🛑 Arrêt du daemon demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur critique: {e}", exc_info=True)
                logger.info("⏸️  Attente de 1 minute avant réessai...")
                time.sleep(60)

        self.disconnect()
        logger.info("✅ Daemon arrêté proprement")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Email Reply Daemon - Récupération des réponses via IMAP')
    parser.add_argument('--imap-server', help='Serveur IMAP (ex: ssl0.ovh.net)')
    parser.add_argument('--imap-port', type=int, default=993, help='Port IMAP (défaut: 993)')
    parser.add_argument('--email', help='Adresse email')
    parser.add_argument('--password', help='Mot de passe')
    parser.add_argument('--interval', type=int, default=300, help='Intervalle en secondes (défaut: 300 = 5 min)')
    parser.add_argument('--test', action='store_true', help='Mode test: vérifier une fois puis quitter')
    parser.add_argument('--config', action='store_true', help='Utiliser imap_config.py')

    args = parser.parse_args()

    # Charger depuis le fichier de config si demandé ou si pas d'arguments
    imap_server = args.imap_server
    imap_port = args.imap_port
    email_address = args.email
    password = args.password
    interval = args.interval

    if args.config or not all([imap_server, email_address, password]):
        try:
            import imap_config
            imap_server = imap_server or imap_config.IMAP_SERVER
            imap_port = imap_port or imap_config.IMAP_PORT
            email_address = email_address or imap_config.IMAP_EMAIL
            password = password or imap_config.IMAP_PASSWORD
            interval = interval or getattr(imap_config, 'CHECK_INTERVAL', 300)
            logger.info("📁 Configuration chargée depuis imap_config.py")
        except ImportError:
            logger.error("❌ Fichier imap_config.py non trouvé. Créez-le ou passez les paramètres en ligne de commande.")
            logger.info("   Exemple: python3 email_reply_daemon.py --imap-server ssl0.ovh.net --email contact@example.com --password xxx")
            return

    if not all([imap_server, email_address, password]):
        logger.error("❌ Configuration incomplète. Serveur IMAP, email et mot de passe requis.")
        return

    checker = EmailReplyChecker(
        imap_server=imap_server,
        imap_port=imap_port,
        email_address=email_address,
        password=password
    )

    if args.test:
        logger.info("Mode test: vérification unique")
        if checker.connect():
            new_replies = checker.check_new_replies()
            logger.info(f"✅ Test terminé: {new_replies} réponse(s) trouvée(s)")
            checker.disconnect()
    else:
        checker.run_continuous(interval_seconds=interval)


if __name__ == '__main__':
    main()
