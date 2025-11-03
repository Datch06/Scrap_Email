#!/usr/bin/env python3
"""
Validation complète des emails avec vérification SMTP
- Niveau 1: Validation syntaxique (format de l'email)
- Niveau 2: Vérification DNS (le domaine existe)
- Niveau 3: Vérification SMTP (la boîte email existe)
"""

import re
import dns.resolver
import smtplib
import socket
from datetime import datetime
from database import get_session, Site
import json
import time
from typing import Dict, Tuple
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EmailValidator:
    """Validateur d'emails avec vérification SMTP"""

    def __init__(self):
        self.dns_cache = {}  # Cache pour les enregistrements MX
        self.timeout = 10  # Timeout pour les connexions SMTP

    def validate_syntax(self, email: str) -> Tuple[bool, str]:
        """
        Niveau 1: Validation syntaxique de l'email
        Returns: (is_valid, message)
        """
        # Regex stricte pour email
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not email or not isinstance(email, str):
            return False, "Email vide ou invalide"

        email = email.strip().lower()

        if not re.match(pattern, email):
            return False, "Format d'email invalide"

        # Vérifications supplémentaires
        if '..' in email:
            return False, "Points consécutifs non autorisés"

        if email.startswith('.') or email.endswith('.'):
            return False, "Ne peut pas commencer/finir par un point"

        local, domain = email.split('@')

        if len(local) > 64:
            return False, "Partie locale trop longue (>64 caractères)"

        if len(domain) > 255:
            return False, "Domaine trop long (>255 caractères)"

        return True, "Syntaxe valide"

    def check_disposable_email(self, domain: str) -> bool:
        """Vérifier si c'est un email jetable/temporaire"""
        # Liste de domaines jetables courants
        disposable_domains = {
            'tempmail.com', 'guerrillamail.com', 'mailinator.com',
            '10minutemail.com', 'throwaway.email', 'temp-mail.org',
            'yopmail.com', 'maildrop.cc', 'sharklasers.com'
        }
        return domain.lower() in disposable_domains

    def get_mx_records(self, domain: str) -> Tuple[bool, list, str]:
        """
        Niveau 2: Vérification DNS - Récupérer les enregistrements MX
        Returns: (success, mx_records, message)
        """
        # Vérifier le cache
        if domain in self.dns_cache:
            return True, self.dns_cache[domain], "MX trouvé (cache)"

        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_list = [str(r.exchange).rstrip('.') for r in mx_records]

            if not mx_list:
                return False, [], "Aucun enregistrement MX trouvé"

            # Mettre en cache
            self.dns_cache[domain] = mx_list
            return True, mx_list, f"{len(mx_list)} serveur(s) MX trouvé(s)"

        except dns.resolver.NXDOMAIN:
            return False, [], "Domaine n'existe pas (NXDOMAIN)"
        except dns.resolver.NoAnswer:
            return False, [], "Pas de réponse DNS"
        except dns.resolver.Timeout:
            return False, [], "Timeout DNS"
        except Exception as e:
            return False, [], f"Erreur DNS: {str(e)}"

    def verify_smtp(self, email: str, mx_host: str) -> Tuple[bool, str]:
        """
        Niveau 3: Vérification SMTP - Vérifier si la boîte email existe
        Returns: (exists, message)
        """
        try:
            # Connexion au serveur SMTP
            server = smtplib.SMTP(timeout=self.timeout)
            server.set_debuglevel(0)

            # Connexion
            server.connect(mx_host)
            server.helo('admin.perfect-cocon-seo.fr')  # Identification
            server.mail('noreply@perfect-cocon-seo.fr')  # Expéditeur test

            # Vérification du destinataire
            code, message = server.rcpt(email)
            server.quit()

            # Codes de succès SMTP: 250 (OK), 251 (User not local, will forward)
            if code == 250:
                return True, "Boîte email existe (SMTP 250)"
            elif code == 251:
                return True, "Email accepté avec redirection (SMTP 251)"
            else:
                return False, f"Email rejeté (SMTP {code})"

        except smtplib.SMTPServerDisconnected:
            return False, "Serveur SMTP déconnecté"
        except smtplib.SMTPConnectError:
            return False, "Impossible de se connecter au serveur SMTP"
        except socket.timeout:
            return False, "Timeout SMTP"
        except socket.gaierror:
            return False, "Impossible de résoudre l'hôte MX"
        except Exception as e:
            # Certaines erreurs peuvent indiquer que l'email n'existe pas
            error_msg = str(e).lower()
            if 'user unknown' in error_msg or 'mailbox' in error_msg:
                return False, "Boîte email inexistante"
            return False, f"Erreur SMTP: {str(e)[:100]}"

    def validate_email(self, email: str) -> Dict:
        """
        Validation complète d'un email
        Returns: dict avec tous les détails de validation
        """
        result = {
            'email': email,
            'valid': False,
            'score': 0,
            'status': 'unknown',
            'deliverable': False,
            'details': {
                'syntax': {'valid': False, 'message': ''},
                'dns': {'valid': False, 'message': '', 'mx_records': []},
                'smtp': {'valid': False, 'message': ''},
                'disposable': False
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        # Nettoyer l'email
        email = email.strip().lower()
        result['email'] = email

        # 1. Validation syntaxique
        syntax_valid, syntax_msg = self.validate_syntax(email)
        result['details']['syntax'] = {'valid': syntax_valid, 'message': syntax_msg}

        if not syntax_valid:
            result['status'] = 'invalid'
            result['score'] = 0
            return result

        result['score'] += 30  # +30 points pour syntaxe valide

        # Extraire le domaine
        domain = email.split('@')[1]

        # Vérifier si c'est un email jetable
        is_disposable = self.check_disposable_email(domain)
        result['details']['disposable'] = is_disposable

        if is_disposable:
            result['status'] = 'risky'
            result['score'] = 20  # Score faible pour emails jetables
            return result

        # 2. Vérification DNS (MX records)
        dns_valid, mx_records, dns_msg = self.get_mx_records(domain)
        result['details']['dns'] = {
            'valid': dns_valid,
            'message': dns_msg,
            'mx_records': mx_records
        }

        if not dns_valid:
            result['status'] = 'invalid'
            result['score'] = 30  # Syntaxe OK mais domaine invalide
            return result

        result['score'] += 30  # +30 points pour DNS valide

        # 3. Vérification SMTP (si MX disponibles)
        if mx_records:
            # Essayer le premier serveur MX
            smtp_valid, smtp_msg = self.verify_smtp(email, mx_records[0])
            result['details']['smtp'] = {'valid': smtp_valid, 'message': smtp_msg}

            if smtp_valid:
                result['score'] += 40  # +40 points pour SMTP valide
                result['valid'] = True
                result['status'] = 'valid'
                result['deliverable'] = True
            else:
                result['status'] = 'risky'
                result['deliverable'] = False
        else:
            result['status'] = 'risky'

        return result


def validate_database_emails(batch_size: int = 100, limit: int = None, only_invalid: bool = False):
    """
    Valider tous les emails de la base de données

    Args:
        batch_size: Nombre d'emails à traiter par batch
        limit: Nombre maximum d'emails à valider (None = tous)
        only_invalid: Si True, ne valide que les emails non encore validés
    """
    session = get_session()
    validator = EmailValidator()

    try:
        # Requête pour récupérer les sites avec emails
        query = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        )

        if only_invalid:
            query = query.filter(
                (Site.email_validated.is_(None)) | (Site.email_validated == False)
            )

        total = query.count()
        logger.info(f"📊 {total} emails à valider")

        if limit:
            total = min(total, limit)
            logger.info(f"⚠️  Limite fixée à {limit} emails")

        stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'risky': 0,
            'errors': 0
        }

        # Traiter par batch
        offset = 0
        while offset < total:
            sites = query.limit(batch_size).offset(offset).all()

            if not sites:
                break

            for site in sites:
                try:
                    # Récupérer le premier email (si plusieurs)
                    emails_list = site.emails.replace(';', ',').split(',')
                    primary_email = emails_list[0].strip()

                    if not primary_email:
                        continue

                    logger.info(f"🔍 Validation: {primary_email} ({site.domain})")

                    # Valider l'email
                    validation_result = validator.validate_email(primary_email)

                    # Mettre à jour la base de données
                    site.email_validated = True
                    site.email_validation_score = validation_result['score']
                    site.email_validation_status = validation_result['status']
                    site.email_validation_details = json.dumps(validation_result['details'])
                    site.email_validation_date = datetime.utcnow()
                    site.email_deliverable = validation_result['deliverable']

                    # Stats
                    stats['total'] += 1
                    if validation_result['status'] == 'valid':
                        stats['valid'] += 1
                    elif validation_result['status'] == 'invalid':
                        stats['invalid'] += 1
                    elif validation_result['status'] == 'risky':
                        stats['risky'] += 1

                    # Afficher le résultat
                    status_emoji = {
                        'valid': '✅',
                        'invalid': '❌',
                        'risky': '⚠️',
                        'unknown': '❓'
                    }.get(validation_result['status'], '❓')

                    logger.info(
                        f"  {status_emoji} {validation_result['status'].upper()} "
                        f"(score: {validation_result['score']}/100) - "
                        f"{validation_result['details']['smtp']['message'] if validation_result['details']['smtp'] else 'N/A'}"
                    )

                    # Petite pause pour ne pas surcharger les serveurs SMTP
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"❌ Erreur pour {site.domain}: {e}")
                    stats['errors'] += 1
                    continue

            # Commit après chaque batch
            session.commit()
            logger.info(f"💾 Batch sauvegardé (offset: {offset})")

            offset += batch_size

            # Afficher les stats intermédiaires
            if stats['total'] > 0:
                logger.info(
                    f"📈 Progression: {stats['total']}/{total} | "
                    f"✅ {stats['valid']} | ❌ {stats['invalid']} | "
                    f"⚠️  {stats['risky']} | Erreurs: {stats['errors']}"
                )

        # Stats finales
        logger.info("\n" + "=" * 70)
        logger.info("📊 RAPPORT FINAL DE VALIDATION")
        logger.info("=" * 70)
        logger.info(f"Total traité: {stats['total']}")
        logger.info(f"✅ Valides: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")
        logger.info(f"❌ Invalides: {stats['invalid']} ({stats['invalid']/stats['total']*100:.1f}%)")
        logger.info(f"⚠️  Risqués: {stats['risky']} ({stats['risky']/stats['total']*100:.1f}%)")
        logger.info(f"Erreurs: {stats['errors']}")
        logger.info("=" * 70)

    finally:
        session.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Valider les emails de la base de données')
    parser.add_argument('--batch-size', type=int, default=100, help='Taille des batchs (défaut: 100)')
    parser.add_argument('--limit', type=int, default=None, help='Nombre max d\'emails à valider (défaut: tous)')
    parser.add_argument('--only-new', action='store_true', help='Valider uniquement les emails non encore validés')

    args = parser.parse_args()

    logger.info("🚀 Démarrage de la validation des emails...")
    validate_database_emails(
        batch_size=args.batch_size,
        limit=args.limit,
        only_invalid=args.only_new
    )
    logger.info("✅ Validation terminée!")
