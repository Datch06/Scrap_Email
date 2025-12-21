#!/usr/bin/env python3
"""
Validation asynchrone des emails avec vérification SMTP
Version TURBO - Optimisée pour 300+ validations/seconde
"""

import re
import asyncio
import aiodns
import aiosmtplib
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class AsyncEmailValidator:
    """Validateur d'emails asynchrone TURBO avec vérification SMTP"""

    def __init__(self, smtp_timeout: float = 3.0, dns_timeout: float = 2.0):
        self.dns_cache = {}  # Cache pour les enregistrements MX
        self.dns_negative_cache = {}  # Cache pour les domaines invalides
        self.smtp_timeout = smtp_timeout
        self.dns_timeout = dns_timeout
        self.resolver = None
        self._lock = asyncio.Lock()

        # TTL pour le cache négatif (évite de re-tester les domaines morts)
        self.negative_cache_ttl = timedelta(hours=24)

        # Domaines connus pour bloquer les vérifications SMTP (étendu)
        self.skip_smtp_domains = {
            # Google
            'gmail.com', 'googlemail.com', 'google.com',
            # Microsoft
            'hotmail.com', 'hotmail.fr', 'hotmail.co.uk', 'hotmail.de', 'hotmail.it', 'hotmail.es',
            'outlook.com', 'outlook.fr', 'outlook.de', 'outlook.co.uk',
            'live.com', 'live.fr', 'live.co.uk', 'live.de',
            'msn.com', 'msn.fr',
            # Yahoo
            'yahoo.com', 'yahoo.fr', 'yahoo.co.uk', 'yahoo.de', 'yahoo.it', 'yahoo.es',
            'ymail.com', 'rocketmail.com',
            # Apple
            'icloud.com', 'me.com', 'mac.com',
            # AOL/Verizon
            'aol.com', 'aol.fr', 'verizon.net',
            # Proton
            'protonmail.com', 'proton.me', 'pm.me',
            # France
            'orange.fr', 'wanadoo.fr', 'free.fr', 'sfr.fr', 'laposte.net',
            'bbox.fr', 'numericable.fr', 'neuf.fr', 'club-internet.fr',
            # Allemagne
            'gmx.de', 'gmx.net', 'gmx.com', 'web.de', 't-online.de',
            # Autres pays
            'libero.it', 'virgilio.it', 'alice.it',
            'mail.ru', 'yandex.ru', 'yandex.com',
            'qq.com', '163.com', '126.com',
            # Services pro qui bloquent
            'zoho.com', 'zohomail.com',
            'fastmail.com', 'fastmail.fm',
            'tutanota.com', 'tutamail.com',
            # Entreprises connues
            'amazon.com', 'amazon.fr', 'facebook.com', 'apple.com',
        }

        # Domaines jetables (étendu)
        self.disposable_domains = {
            'tempmail.com', 'guerrillamail.com', 'mailinator.com',
            '10minutemail.com', 'throwaway.email', 'temp-mail.org',
            'yopmail.com', 'maildrop.cc', 'sharklasers.com',
            'trashmail.com', 'fakeinbox.com', 'tempinbox.com',
            'getairmail.com', 'mohmal.com', 'dispostable.com',
            'mailnesia.com', 'spamgourmet.com', 'mintemail.com',
            'mytrashmail.com', 'mailexpire.com', 'temporarymail.net',
            'emailondeck.com', 'getnada.com', 'tempr.email',
            'discard.email', 'fakemailgenerator.com', 'throwawaymail.com',
        }

        # MX connus qui acceptent tout (catch-all confirmés)
        self.catch_all_mx = {
            'aspmx.l.google.com', 'alt1.aspmx.l.google.com',
            'mx.zoho.com', 'mx2.zoho.com',
        }

    async def _get_resolver(self):
        """Obtenir le resolver DNS avec serveurs rapides"""
        if self.resolver is None:
            async with self._lock:
                if self.resolver is None:
                    # Utiliser des DNS rapides (Cloudflare + Google)
                    self.resolver = aiodns.DNSResolver(
                        nameservers=['1.1.1.1', '8.8.8.8', '1.0.0.1', '8.8.4.4']
                    )
        return self.resolver

    def validate_syntax(self, email: str) -> Tuple[bool, str]:
        """Niveau 1: Validation syntaxique rapide"""
        if not email or not isinstance(email, str):
            return False, "Email vide"

        email = email.strip().lower()

        # Regex compilée serait plus rapide mais OK pour l'instant
        if '@' not in email:
            return False, "Pas de @"

        parts = email.split('@')
        if len(parts) != 2:
            return False, "Format invalide"

        local, domain = parts

        if not local or not domain:
            return False, "Partie vide"

        if len(local) > 64 or len(domain) > 255:
            return False, "Trop long"

        if '..' in email or email.startswith('.') or email.endswith('.'):
            return False, "Points invalides"

        if '.' not in domain:
            return False, "Domaine sans extension"

        # Pattern simplifié mais efficace
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, "Caractères invalides"

        return True, "OK"

    async def get_mx_records(self, domain: str) -> Tuple[bool, list, str]:
        """Niveau 2: Vérification DNS avec cache négatif"""
        # Cache positif
        if domain in self.dns_cache:
            return True, self.dns_cache[domain], "cache"

        # Cache négatif (évite de retester les domaines morts)
        if domain in self.dns_negative_cache:
            cache_time, reason = self.dns_negative_cache[domain]
            if datetime.utcnow() - cache_time < self.negative_cache_ttl:
                return False, [], f"neg_cache: {reason}"

        try:
            resolver = await self._get_resolver()
            mx_records = await asyncio.wait_for(
                resolver.query(domain, 'MX'),
                timeout=self.dns_timeout
            )
            mx_list = [str(r.host).rstrip('.') for r in mx_records]

            if not mx_list:
                self.dns_negative_cache[domain] = (datetime.utcnow(), "no_mx")
                return False, [], "Aucun MX"

            # Cache positif
            self.dns_cache[domain] = mx_list
            return True, mx_list, f"{len(mx_list)} MX"

        except asyncio.TimeoutError:
            # Ne pas cacher les timeouts (peut être temporaire)
            return False, [], "DNS timeout"
        except aiodns.error.DNSError as e:
            if e.args[0] == aiodns.error.ARES_ENOTFOUND:
                self.dns_negative_cache[domain] = (datetime.utcnow(), "nxdomain")
                return False, [], "Domaine inexistant"
            self.dns_negative_cache[domain] = (datetime.utcnow(), "dns_error")
            return False, [], "Erreur DNS"
        except Exception as e:
            return False, [], f"DNS: {str(e)[:30]}"

    async def verify_smtp(self, email: str, mx_host: str) -> Tuple[bool, str]:
        """Niveau 3: Vérification SMTP ultra-rapide"""
        try:
            smtp = aiosmtplib.SMTP(
                hostname=mx_host,
                port=25,
                timeout=self.smtp_timeout,
                start_tls=False,  # Plus rapide sans TLS pour vérification
            )

            await smtp.connect()

            # HELO rapide
            await smtp.helo('mail.perfect-cocon-seo.fr')

            # Essayer RCPT TO directement (plus fiable que VRFY)
            try:
                await smtp.mail('verify@perfect-cocon-seo.fr')
                code, _ = await smtp.rcpt(email)

                # Fermer proprement
                try:
                    await smtp.quit()
                except:
                    pass

                if code in (250, 251):
                    return True, f"OK ({code})"
                elif code in (450, 451, 452):
                    # Temporaire = probablement valide
                    return True, f"temp ({code})"
                else:
                    return False, f"rejeté ({code})"

            except aiosmtplib.SMTPRecipientsRefused:
                try:
                    await smtp.quit()
                except:
                    pass
                return False, "refusé"

        except aiosmtplib.SMTPConnectError:
            return False, "connexion impossible"
        except aiosmtplib.SMTPServerDisconnected:
            return False, "déconnecté"
        except asyncio.TimeoutError:
            return False, "timeout"
        except Exception as e:
            return False, f"err: {str(e)[:20]}"

    async def validate_email(self, email: str) -> Dict:
        """Validation complète ultra-optimisée"""
        result = {
            'email': email,
            'score': 0,
            'status': 'unknown',
            'details': {},
            'deliverable': False
        }

        email = email.strip().lower() if email else ''

        # Niveau 1: Syntaxe (très rapide)
        syntax_valid, syntax_msg = self.validate_syntax(email)
        if not syntax_valid:
            result['status'] = 'invalid'
            result['details']['syntax'] = syntax_msg
            return result

        result['score'] = 25
        domain = email.split('@')[1]

        # Email jetable
        if domain in self.disposable_domains:
            result['status'] = 'invalid'
            result['details']['disposable'] = True
            result['score'] = 10
            return result

        # Niveau 2: DNS/MX
        mx_valid, mx_list, mx_msg = await self.get_mx_records(domain)
        result['details']['mx'] = mx_msg

        if not mx_valid:
            result['status'] = 'invalid'
            result['score'] = 15
            return result

        result['score'] = 50

        # Skip SMTP pour les gros providers (réponse instantanée)
        if domain in self.skip_smtp_domains:
            result['status'] = 'valid'
            result['details']['smtp'] = 'skip_provider'
            result['score'] = 75
            result['deliverable'] = True
            return result

        # Niveau 3: SMTP
        if mx_list:
            smtp_valid, smtp_msg = await self.verify_smtp(email, mx_list[0])
            result['details']['smtp'] = smtp_msg

            if smtp_valid:
                result['status'] = 'valid'
                result['score'] = 100
                result['deliverable'] = True
            else:
                result['status'] = 'risky'
                result['score'] = 50
        else:
            result['status'] = 'risky'
            result['score'] = 50

        return result

    async def validate_emails_batch(self, emails: List[str], max_concurrent: int = 300) -> List[Dict]:
        """Valider un batch d'emails en parallèle (TURBO)"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_semaphore(email):
            async with semaphore:
                try:
                    return await self.validate_email(email)
                except Exception as e:
                    return {
                        'email': email,
                        'score': 0,
                        'status': 'error',
                        'details': {'error': str(e)[:50]},
                        'deliverable': False
                    }

        tasks = [validate_with_semaphore(email) for email in emails]
        return await asyncio.gather(*tasks)

    def clear_cache(self):
        """Vider les caches (utile si mémoire insuffisante)"""
        self.dns_cache.clear()
        self.dns_negative_cache.clear()

    def get_cache_stats(self) -> Dict:
        """Stats des caches"""
        return {
            'dns_cache_size': len(self.dns_cache),
            'negative_cache_size': len(self.dns_negative_cache),
        }


# Test standalone
if __name__ == '__main__':
    import sys

    async def main():
        validator = AsyncEmailValidator(smtp_timeout=3.0, dns_timeout=2.0)

        test_emails = [
            'contact@example.com',
            'test@gmail.com',
            'invalid-email',
            'user@nonexistent-domain-12345.com'
        ]

        if len(sys.argv) > 1:
            test_emails = sys.argv[1:]

        print("🚀 Test de validation TURBO...")
        start = datetime.now()

        results = await validator.validate_emails_batch(test_emails, max_concurrent=300)

        duration = (datetime.now() - start).total_seconds()

        for r in results:
            status_emoji = {'valid': '✅', 'invalid': '❌', 'risky': '⚠️'}.get(r['status'], '❓')
            print(f"{status_emoji} {r['email']}: {r['status']} (score: {r['score']})")

        print(f"\n⏱️ {len(test_emails)} emails en {duration:.2f}s ({len(test_emails)/duration:.1f}/s)")
        print(f"📊 Cache: {validator.get_cache_stats()}")

    asyncio.run(main())
