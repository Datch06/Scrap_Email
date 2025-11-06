#!/usr/bin/env python3
"""
Module asynchrone avancé pour la recherche d'emails
Vérifie plus de pages et utilise des techniques sophistiquées
"""

import asyncio
import aiohttp
import re
from typing import Optional, List, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class AsyncEmailFinder:
    """Recherche avancée et asynchrone d'emails sur un site"""

    def __init__(self, session: aiohttp.ClientSession):
        """
        Initialiser le finder

        Args:
            session: Session aiohttp partagée
        """
        self.session = session

        # Patterns pour emails
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.mailto_pattern = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})')

        # Pattern pour emails obfusqués (ex: contact [at] domain [dot] com)
        self.obfuscated_pattern = re.compile(
            r'([A-Za-z0-9._%+-]+)\s*[\[\(]?\s*(?:at|@)\s*[\]\)]?\s*([A-Za-z0-9.-]+)\s*[\[\(]?\s*(?:dot|\.)\s*[\]\)]?\s*([A-Za-z]{2,})',
            re.IGNORECASE
        )

        # Emails à ignorer
        self.ignore_emails = {
            'example@example.com', 'email@example.com', 'contact@example.com',
            'test@test.com', 'noreply@example.com', 'vous@domaine.com',
            'your@email.com', 'name@domain.com', 'info@example.com',
            'admin@example.com', 'support@example.com', 'webmaster@example.com'
        }

        # Mots-clés à ignorer dans les emails
        self.ignore_keywords = [
            'example', 'test', 'domain', 'wix', 'placeholder',
            'yourname', 'youremail', 'sentry', 'gravatar',
            'wordpress', 'wp-content', 'dummy', 'fake'
        ]

    def is_valid_email(self, email: str) -> bool:
        """Vérifier si un email est valide et non spam"""
        email_lower = email.lower()

        # Vérifier si dans la liste d'ignorés
        if email_lower in self.ignore_emails:
            return False

        # Vérifier les mots-clés à ignorer
        if any(keyword in email_lower for keyword in self.ignore_keywords):
            return False

        # Vérifier le format basique
        if '@' not in email or '.' not in email.split('@')[1]:
            return False

        # Vérifier la longueur
        if len(email) < 6 or len(email) > 254:
            return False

        # Filtrer les faux positifs courants (JavaScript, CSS, etc.)
        # Emails qui contiennent des caractères suspects avant/après @
        local_part, domain_part = email.split('@', 1)

        # Local part ne doit pas contenir certains patterns
        invalid_patterns = [
            'window.', 'location.', '.location', '.click', '.host',
            'math.', 'document.', 'module.', 'ion.', 'navig@ion',
            '+window', 'authentic@ion', 'av@ars', 'm@h.', 'h.floor',
            'ific@ion', 'octoc@', 'moder@or', '.js', '.css', '.svg',
            '.png', '.jpg', '.gif', '.webp', 'st@us'
        ]

        if any(pattern in email_lower for pattern in invalid_patterns):
            return False

        # Les emails ne doivent pas avoir des extensions de fichiers
        if re.search(r'\.(js|css|svg|png|jpg|gif|webp|html|php|asp)$', email_lower):
            return False

        # Le domaine doit avoir au moins 2 caractères avant le TLD
        domain_parts = domain_part.split('.')
        if len(domain_parts) < 2 or len(domain_parts[0]) < 2:
            return False

        # La partie locale ne doit pas être trop courte
        if len(local_part) < 2:
            return False

        return True

    def extract_emails_from_html(self, html: str) -> Set[str]:
        """Extraire tous les emails d'un HTML"""
        emails = set()

        # Pattern standard
        standard_emails = self.email_pattern.findall(html)
        emails.update(standard_emails)

        # Pattern mailto:
        mailto_emails = self.mailto_pattern.findall(html)
        emails.update(mailto_emails)

        # Pattern obfusqué
        obfuscated_matches = self.obfuscated_pattern.findall(html)
        for match in obfuscated_matches:
            # Reconstituer l'email: user @ domain . tld
            email = f"{match[0].strip()}@{match[1].strip()}.{match[2].strip()}"
            emails.add(email)

        # Filtrer les emails valides
        valid_emails = {e for e in emails if self.is_valid_email(e)}

        return valid_emails

    def get_pages_to_check(self, domain: str) -> List[str]:
        """Retourner la liste des pages à vérifier pour un domaine"""
        pages = [
            # Pages principales
            f"https://{domain}",
            f"https://{domain}/",

            # Contact
            f"https://{domain}/contact",
            f"https://{domain}/contact-us",
            f"https://{domain}/contactez-nous",
            f"https://{domain}/nous-contacter",
            f"https://{domain}/contact.html",
            f"https://{domain}/contact.php",

            # Mentions légales
            f"https://{domain}/mentions-legales",
            f"https://{domain}/mentions-legales.html",
            f"https://{domain}/mentions_legales",
            f"https://{domain}/legal",
            f"https://{domain}/legal-notice",

            # À propos
            f"https://{domain}/a-propos",
            f"https://{domain}/about",
            f"https://{domain}/about-us",
            f"https://{domain}/qui-sommes-nous",
            f"https://{domain}/about.html",

            # Imprint (sites allemands/suisses)
            f"https://{domain}/imprint",
            f"https://{domain}/impressum",

            # Équipe
            f"https://{domain}/equipe",
            f"https://{domain}/team",
            f"https://{domain}/notre-equipe",

            # Services
            f"https://{domain}/services",
            f"https://{domain}/nos-services",
        ]

        # Version www
        pages_www = [p.replace(f"https://{domain}", f"https://www.{domain}") for p in pages]

        return pages + pages_www

    async def fetch_page(self, url: str, timeout: int = 5) -> Optional[str]:
        """Récupérer le contenu d'une page"""
        try:
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
                ssl=False
            ) as response:
                if response.status == 200:
                    return await response.text()
        except:
            pass

        return None

    async def search_emails_on_domain(self, domain: str, max_pages: int = 10) -> Optional[str]:
        """
        Chercher des emails sur un domaine de manière asynchrone

        Args:
            domain: Domaine à analyser
            max_pages: Nombre maximum de pages à vérifier

        Returns:
            String avec emails séparés par "; " ou None
        """
        all_emails = set()

        # Obtenir les pages à vérifier
        pages = self.get_pages_to_check(domain)[:max_pages]

        # Créer les tâches pour toutes les pages
        tasks = [self.fetch_page(page) for page in pages]

        # Exécuter toutes les requêtes en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Traiter les résultats
        for html in results:
            if isinstance(html, str) and html:
                emails = self.extract_emails_from_html(html)
                all_emails.update(emails)

                # Si on a trouvé au moins 1 email, on peut s'arrêter pour économiser du temps
                if len(all_emails) >= 3:
                    break

        # Retourner jusqu'à 3 emails uniques
        if all_emails:
            return "; ".join(sorted(all_emails)[:3])

        return None

    async def search_emails_batch(self, domains: List[str], max_pages: int = 10) -> dict:
        """
        Chercher des emails pour un lot de domaines

        Args:
            domains: Liste de domaines
            max_pages: Nombre maximum de pages par domaine

        Returns:
            Dict {domain: emails or None}
        """
        tasks = {domain: self.search_emails_on_domain(domain, max_pages) for domain in domains}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {domain: result if not isinstance(result, Exception) else None
                for domain, result in zip(tasks.keys(), results)}


# Fonction helper pour utilisation standalone
async def find_emails_async(domains: List[str], max_concurrent: int = 50, max_pages_per_domain: int = 10) -> dict:
    """
    Fonction helper pour rechercher des emails de manière asynchrone

    Args:
        domains: Liste de domaines
        max_concurrent: Nombre de requêtes simultanées
        max_pages_per_domain: Pages à vérifier par domaine

    Returns:
        Dict {domain: emails or None}
    """
    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        finder = AsyncEmailFinder(session)
        return await finder.search_emails_batch(domains, max_pages_per_domain)


# Test du module
if __name__ == "__main__":
    async def test():
        # Test avec quelques domaines
        test_domains = [
            "example.com",
            "github.com",
            "stackoverflow.com"
        ]

        print("🧪 Test du module AsyncEmailFinder")
        print("="*80)

        results = await find_emails_async(test_domains, max_pages_per_domain=5)

        for domain, emails in results.items():
            status = "✅" if emails else "❌"
            print(f"{status} {domain}: {emails or 'Aucun email trouvé'}")

    asyncio.run(test())
