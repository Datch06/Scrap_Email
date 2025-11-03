#!/usr/bin/env python3
"""
Script COMPLET pour scraper LinkAvista MarketLink
Combine filtres et non-filtres pour maximiser les domaines
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from database import get_session, Site, SiteStatus
from datetime import datetime

class LinkAvistaCompleteScraper:
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

        login_page = self.session.get(f"{self.base_url}/login", timeout=10)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_input = soup.find('input', {'name': '_token'})
        csrf_token = csrf_input.get('value') if csrf_input else None

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

    def extract_urls_from_page(self, page_num, use_filters=False):
        """Extraire toutes les URLs d'une page"""
        try:
            if use_filters:
                # URL avec filtres (catégories sensibles incluses)
                if page_num == 1:
                    url = f"{self.base_url}/marketlink?category_id=&ttf=&domain=&keyword=&tf_min=0.00&tf_max=100.00&cf_min=0.00&cf_max=100.00&da_min=0.00&da_max=100.00&rd_min=&rd_max=&traffic_min=&traffic_max=&language=&show_sensitive_categories=on&sensitive_category_id=1"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}?category_id=&ttf=&domain=&keyword=&tf_min=0.00&tf_max=100.00&cf_min=0.00&cf_max=100.00&da_min=0.00&da_max=100.00&show_sensitive_categories=on&sensitive_category_id=1"
            else:
                # URL normale sans filtres
                if page_num == 1:
                    url = f"{self.base_url}/marketlink"
                else:
                    url = f"{self.base_url}/marketlink/page/{page_num}"

            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                return []

            # Extraire les URLs depuis le JSON
            urls = re.findall(r'"url":"([^"]+)"', response.text)
            urls = list(set(urls))  # Dédupliquer

            return urls

        except Exception as e:
            return []

    def search_email_on_site(self, domain):
        """Chercher un email sur le site"""
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
                        valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example', 'test', 'domain', 'wix', 'placeholder'])]
                        if valid_emails:
                            return "; ".join(list(set(valid_emails))[:3])
            except:
                continue

        return None

    def scrape_complete(self, max_pages=100):
        """Scraper complet : sans filtres + avec filtres"""
        print("\n" + "="*80)
        print("🚀 SCRAPING LINKAVISTA COMPLET - SANS FILTRES + AVEC FILTRES")
        print("="*80)

        if not self.login():
            return

        all_domains = set()

        # PHASE 1A: Extraction SANS filtres
        print("\n📥 PHASE 1A: Extraction SANS filtres")
        print("="*80)

        for page in range(1, max_pages + 1):
            print(f"📄 Page {page}/{max_pages} (sans filtres)... ", end='', flush=True)
            urls = self.extract_urls_from_page(page, use_filters=False)

            if not urls:
                print(f"⚠️  Arrêt à la page {page}")
                break

            new_urls = [u for u in urls if u not in all_domains]
            all_domains.update(urls)
            print(f"✅ {len(urls)} sites (+{len(new_urls)} nouveaux) | Total: {len(all_domains)}")

            time.sleep(1)

        print(f"\n✅ Sans filtres: {len(all_domains)} domaines uniques")

        # PHASE 1B: Extraction AVEC filtres
        print("\n📥 PHASE 1B: Extraction AVEC filtres")
        print("="*80)

        initial_count = len(all_domains)

        for page in range(1, max_pages + 1):
            print(f"📄 Page {page}/{max_pages} (avec filtres)... ", end='', flush=True)
            urls = self.extract_urls_from_page(page, use_filters=True)

            if not urls:
                print(f"⚠️  Arrêt à la page {page}")
                break

            new_urls = [u for u in urls if u not in all_domains]
            all_domains.update(urls)
            print(f"✅ {len(urls)} sites (+{len(new_urls)} nouveaux) | Total: {len(all_domains)}")

            time.sleep(1)

        filtered_added = len(all_domains) - initial_count
        print(f"\n✅ Avec filtres: +{filtered_added} domaines supplémentaires")
        print(f"🎯 TOTAL FINAL: {len(all_domains)} domaines uniques")

        # PHASE 2: Recherche d'emails et ajout en base
        print("\n📧 PHASE 2: Recherche d'emails et ajout en base")
        print("="*80)

        db_session = get_session()
        total_added = 0
        total_skipped = 0
        total_emails = 0

        for idx, domain in enumerate(sorted(all_domains), 1):
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
                email_source="linkavista_complete_scraping",
                status=SiteStatus.EMAIL_FOUND if email else SiteStatus.EMAIL_NOT_FOUND,
                created_at=datetime.utcnow()
            )

            db_session.add(site)
            db_session.commit()
            total_added += 1
            print("✅")

            # Pause
            if idx % 10 == 0:
                time.sleep(2)
            else:
                time.sleep(0.3)

        db_session.close()

        print("\n" + "="*80)
        print("✅ SCRAPING COMPLET TERMINÉ!")
        print("="*80)
        print(f"   Domaines uniques extraits: {len(all_domains)}")
        print(f"   Sites ajoutés en base: {total_added}")
        print(f"   Sites déjà existants: {total_skipped}")
        print(f"   Emails trouvés: {total_emails}")
        if total_added > 0:
            print(f"   Taux de découverte: {(total_emails/total_added*100):.1f}%")
        print("="*80)
        print("\n🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")


if __name__ == "__main__":
    EMAIL = "datchdigital@gmail.com"
    PASSWORD = "B-BJoqV7"

    scraper = LinkAvistaCompleteScraper(EMAIL, PASSWORD)
    scraper.scrape_complete(max_pages=100)
