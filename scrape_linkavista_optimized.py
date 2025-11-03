#!/usr/bin/env python3
"""
Script optimisé pour scraper LinkAvista MarketLink
Utilise l'API de pagination et extrait les données JSON
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import json
from database import get_session, Site, SiteStatus
from datetime import datetime
from urllib.parse import urlparse

class LinkAvistaScraperOptimized:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://linkavista.com"

    def login(self):
        """Se connecter à LinkAvista"""
        print(f"🔐 Connexion à LinkAvista...")

        # Récupérer la page de login et le CSRF token
        login_page = self.session.get(f"{self.base_url}/login", timeout=10)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_input = soup.find('input', {'name': '_token'})
        csrf_token = csrf_input.get('value') if csrf_input else None

        # Login
        login_data = {
            'email': self.email,
            'password': self.password,
        }
        if csrf_token:
            login_data['_token'] = csrf_token

        response = self.session.post(f"{self.base_url}/login", data=login_data, allow_redirects=True, timeout=15)

        if 'logout' in response.text.lower() and response.status_code == 200:
            print("✅ Connexion réussie!")
            return True
        else:
            print(f"❌ Échec de connexion")
            return False

    def extract_urls_from_page(self, page_num):
        """Extraire toutes les URLs d'une page"""
        try:
            if page_num == 1:
                url = f"{self.base_url}/marketlink"
            else:
                url = f"{self.base_url}/marketlink/page/{page_num}"

            print(f"📄 Chargement page {page_num}... ", end='', flush=True)
            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                print(f"❌ Erreur {response.status_code}")
                return []

            # Extraire les URLs depuis le JSON dans la page
            urls = re.findall(r'"url":"([^"]+)"', response.text)
            urls = list(set(urls))  # Dédupliquer

            print(f"✅ {len(urls)} sites trouvés")
            return urls

        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []

    def search_email_on_site(self, domain):
        """Chercher un email sur les pages du site"""
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

        pages_to_check = [
            f"https://{domain}",
            f"https://{domain}/contact",
            f"https://{domain}/mentions-legales",
        ]

        for page_url in pages_to_check:
            try:
                response = self.session.get(page_url, timeout=5)
                if response.status_code == 200:
                    emails = email_pattern.findall(response.text)
                    if emails:
                        # Filtrer les emails génériques
                        valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example', 'test', 'domain', 'wix', 'placeholder'])]
                        if valid_emails:
                            return "; ".join(list(set(valid_emails))[:3])  # Max 3 emails uniques
            except:
                continue

        return None

    def scrape_all_pages(self, max_pages=100):
        """Scraper toutes les pages de MarketLink"""
        print("\n" + "="*80)
        print("🚀 SCRAPING LINKAVISTA MARKETLINK - VERSION OPTIMISÉE")
        print("="*80)

        if not self.login():
            print("❌ Impossible de se connecter")
            return

        db_session = get_session()
        total_added = 0
        total_skipped = 0
        total_emails = 0
        all_domains = []

        # Phase 1: Extraire tous les domaines de toutes les pages
        print("\n📥 PHASE 1: Extraction de tous les domaines")
        print("="*80)

        for page in range(1, max_pages + 1):
            urls = self.extract_urls_from_page(page)

            if not urls:
                print(f"⚠️  Pas de sites sur la page {page}, arrêt.")
                break

            all_domains.extend(urls)
            time.sleep(1)  # Pause entre les pages

        # Dédupliquer
        all_domains = list(set(all_domains))
        print(f"\n✅ Total domaines uniques extraits: {len(all_domains)}")

        # Phase 2: Traiter chaque domaine
        print("\n📧 PHASE 2: Recherche d'emails et ajout en base")
        print("="*80)

        for idx, domain in enumerate(all_domains, 1):
            # Vérifier si déjà en base
            existing = db_session.query(Site).filter_by(domain=domain).first()
            if existing:
                total_skipped += 1
                continue

            print(f"[{idx}/{len(all_domains)}] {domain[:40]:40} ", end='', flush=True)

            # Chercher l'email
            email = self.search_email_on_site(domain)

            if email:
                print(f"✉️ ✓ ", end='', flush=True)
                total_emails += 1
            else:
                print(f"✉️ ✗ ", end='', flush=True)

            # Créer l'entrée en base
            site = Site(
                domain=domain,
                source_url="https://linkavista.com/marketlink",
                emails=email if email else "NO EMAIL FOUND",
                email_checked=True,
                email_found_at=datetime.utcnow() if email else None,
                email_source="linkavista_scraping",
                status=SiteStatus.EMAIL_FOUND if email else SiteStatus.EMAIL_NOT_FOUND,
                created_at=datetime.utcnow()
            )

            db_session.add(site)
            db_session.commit()
            total_added += 1
            print("✅")

            # Pause pour ne pas surcharger
            if idx % 10 == 0:
                time.sleep(2)
            else:
                time.sleep(0.3)

        db_session.close()

        print("\n" + "="*80)
        print("✅ SCRAPING TERMINÉ!")
        print("="*80)
        print(f"   Domaines extraits: {len(all_domains)}")
        print(f"   Sites ajoutés: {total_added}")
        print(f"   Sites skippés (déjà en base): {total_skipped}")
        print(f"   Emails trouvés: {total_emails}")
        print(f"   Taux de découverte: {(total_emails/total_added*100):.1f}%" if total_added > 0 else "")
        print("="*80)
        print("\n🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")


if __name__ == "__main__":
    EMAIL = "datchdigital@gmail.com"
    PASSWORD = "B-BJoqV7"

    scraper = LinkAvistaScraperOptimized(EMAIL, PASSWORD)
    scraper.scrape_all_pages(max_pages=100)  # Scraper jusqu'à 100 pages
