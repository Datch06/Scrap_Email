#!/usr/bin/env python3
"""
Extraire TOUS les domaines depuis LinkAvista (sans chercher les emails)

Ce script se connecte à LinkAvista et extrait tous les domaines disponibles
pour ensuite les comparer avec Ereferer et identifier les doublons.

Usage:
    python3 extract_all_linkavista_domains.py
"""

import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from typing import List, Set
import sys

class LinkAvistaDomainsExtractor:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.base_url = "https://linkavista.com"
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def login(self) -> bool:
        """Se connecter à LinkAvista"""
        print(f"🔐 Connexion à LinkAvista...")

        try:
            connector = aiohttp.TCPConnector(limit=50, ssl=False)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            )

            # Obtenir le CSRF token
            async with self.session.get(f"{self.base_url}/login") as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf_input = soup.find('input', {'name': '_token'})
                csrf_token = csrf_input.get('value') if csrf_input else None

            # Se connecter
            login_data = {
                'email': self.email,
                'password': self.password,
            }
            if csrf_token:
                login_data['_token'] = csrf_token

            async with self.session.post(
                f"{self.base_url}/login",
                data=login_data,
                allow_redirects=True
            ) as response:
                html = await response.text()

                if 'logout' in html.lower() and response.status == 200:
                    print("✅ Connexion réussie!\n")
                    return True
                else:
                    print(f"❌ Échec de connexion")
                    return False

        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False

    async def extract_domains_from_page(self, page_num: int, filter_type: str = "normal") -> List[str]:
        """Extraire tous les domaines d'une page"""
        try:
            # Construire l'URL selon le filtre
            if filter_type == "normal":
                url = f"{self.base_url}/marketlink" if page_num == 1 else f"{self.base_url}/marketlink/page/{page_num}"
            elif filter_type == "sensitive":
                if page_num == 1:
                    url = f"{self.base_url}/marketlink?show_sensitive_categories=on&sensitive_category_id=1"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}?show_sensitive_categories=on&sensitive_category_id=1"
            elif filter_type == "gnews":
                if page_num == 1:
                    url = f"{self.base_url}/marketlink?is_gnews=on"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}?is_gnews=on"
            else:
                return []

            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return []

                html = await response.text()

                # Extraire les URLs depuis le JSON embarqué dans la page
                urls = re.findall(r'"url":"([^"]+)"', html)
                urls = list(set(urls))  # Dédupliquer

                # Nettoyer les domaines
                domains = []
                for url in urls:
                    # Extraire le domaine de l'URL
                    domain = url.replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0].strip()
                    if domain and '.' in domain:
                        domains.append(domain.lower())

                return domains

        except asyncio.TimeoutError:
            return []
        except Exception as e:
            print(f"⚠️  Erreur page {page_num}: {e}")
            return []

    async def extract_all_domains(self) -> Set[str]:
        """Extraire TOUS les domaines de toutes les pages et tous les filtres"""
        all_domains = set()

        filters = [
            ("normal", "Normal"),
            ("sensitive", "Sensitive"),
            ("gnews", "Google News")
        ]

        print("=" * 80)
        print("📥 EXTRACTION DE TOUS LES DOMAINES LINKAVISTA")
        print("=" * 80)
        print()

        for filter_type, filter_name in filters:
            print(f"🔍 Filtre: {filter_name}")
            print("-" * 80)

            page_num = 1
            empty_pages = 0
            new_in_filter = 0

            while empty_pages < 3:  # Arrêter après 3 pages vides consécutives
                domains = await self.extract_domains_from_page(page_num, filter_type)

                if not domains:
                    empty_pages += 1
                else:
                    empty_pages = 0
                    before = len(all_domains)
                    all_domains.update(domains)
                    new_domains = len(all_domains) - before
                    new_in_filter += new_domains
                    print(f"📄 Page {page_num:4} → {len(domains)} sites (+{new_domains} nouveaux) | Total: {len(all_domains):,}")

                page_num += 1

                # Limite de sécurité
                if page_num > 100:
                    print("⚠️  Limite de 100 pages atteinte")
                    break

            print(f"✅ {filter_name}: +{new_in_filter:,} domaines supplémentaires (arrêt à la page {page_num})")
            print()

        return all_domains

    async def close(self):
        """Fermer la session"""
        if self.session:
            await self.session.close()

async def main():
    print()
    print("🚀 EXTRACTION DES DOMAINES LINKAVISTA")
    print()

    # Credentials Linkavista
    EMAIL = "datchdigital@gmail.com"
    PASSWORD = "B-BJoqV7"

    # Vérifier si les credentials sont fournis en argument
    if len(sys.argv) > 2:
        EMAIL = sys.argv[1]
        PASSWORD = sys.argv[2]

    extractor = LinkAvistaDomainsExtractor(EMAIL, PASSWORD)

    try:
        # Se connecter
        if not await extractor.login():
            print("❌ Impossible de se connecter à LinkAvista")
            return

        # Extraire tous les domaines
        all_domains = await extractor.extract_all_domains()

        print("=" * 80)
        print("✅ EXTRACTION TERMINÉE")
        print("=" * 80)
        print(f"🎯 Total: {len(all_domains):,} domaines uniques extraits")
        print()

        # Sauvegarder dans un fichier
        output_file = "linkavista_all_domains_complete.txt"
        with open(output_file, 'w') as f:
            for domain in sorted(all_domains):
                f.write(f"{domain}\n")

        print(f"📄 Domaines sauvegardés dans: {output_file}")
        print()

        # Maintenant comparer avec Ereferer
        print("=" * 80)
        print("🔍 COMPARAISON AVEC EREFERER")
        print("=" * 80)
        print()

        import sqlite3
        conn = sqlite3.connect('scrap_email.db')
        cursor = conn.cursor()

        # Récupérer les domaines Ereferer
        cursor.execute("SELECT domain FROM sites WHERE source_url = 'Ereferer'")
        ereferer_domains = {row[0].lower() for row in cursor.fetchall()}

        print(f"📊 Domaines Ereferer: {len(ereferer_domains):,}")
        print(f"📊 Domaines Linkavista: {len(all_domains):,}")
        print()

        # Intersection
        common = all_domains & ereferer_domains
        linkavista_only = all_domains - ereferer_domains
        ereferer_only = ereferer_domains - all_domains

        print("🎯 RÉSULTATS:")
        print(f"   Sites présents sur LES DEUX: {len(common):,}")
        print(f"   Sites uniquement Linkavista: {len(linkavista_only):,}")
        print(f"   Sites uniquement Ereferer: {len(ereferer_only):,}")
        print()

        # Sauvegarder les sites communs
        if common:
            common_file = "domains_on_both_platforms_complete.txt"
            with open(common_file, 'w') as f:
                for domain in sorted(common):
                    f.write(f"{domain}\n")

            print(f"📄 Sites communs sauvegardés dans: {common_file}")
            print()
            print("🔄 PROCHAINE ÉTAPE:")
            print(f"   python3 migrate_add_multi_platform_tracking.py {common_file}")

        conn.close()

    finally:
        await extractor.close()

if __name__ == "__main__":
    asyncio.run(main())
