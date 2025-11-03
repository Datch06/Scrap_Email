#!/usr/bin/env python3
"""
Script de scraping pour LinkAvista MarketLink
Extrait les sites vendeurs de backlinks avec authentification
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from database import get_session, Site, SiteStatus
from datetime import datetime
from urllib.parse import urlparse

class LinkAvistaScraper:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.base_url = "https://linkavista.com"

    def login(self):
        """Se connecter à LinkAvista"""
        print(f"🔐 Connexion à LinkAvista avec {self.email}...")

        # Récupérer la page de login
        login_page = self.session.get(f"{self.base_url}/login")

        if login_page.status_code != 200:
            print(f"❌ Erreur d'accès à la page de login: {login_page.status_code}")
            return False

        # Parser pour trouver le token CSRF si nécessaire
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_token = None
        csrf_input = soup.find('input', {'name': '_token'}) or soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            csrf_token = csrf_input.get('value')

        # Préparer les données de login
        login_data = {
            'email': self.email,
            'password': self.password,
        }

        if csrf_token:
            login_data['_token'] = csrf_token

        # Tenter la connexion
        response = self.session.post(f"{self.base_url}/login", data=login_data, allow_redirects=True)

        # Vérifier si la connexion a réussi
        if 'logout' in response.text.lower() or 'dashboard' in response.url.lower():
            print("✅ Connexion réussie!")
            return True
        else:
            print(f"❌ Échec de connexion. URL: {response.url}")
            return False

    def extract_domain(self, url):
        """Extraire le domaine propre depuis une URL"""
        if not url:
            return None

        # Ajouter http:// si pas de protocole
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Nettoyer le domaine
            domain = domain.replace('www.', '').strip('/')
            return domain if domain else None
        except:
            return None

    def search_email_on_site(self, domain):
        """Chercher un email sur les pages du site"""
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

        pages_to_check = [
            f"http://{domain}",
            f"https://{domain}",
            f"http://{domain}/contact",
            f"https://{domain}/contact",
            f"http://{domain}/mentions-legales",
        ]

        for page_url in pages_to_check[:3]:  # Limiter à 3 pages pour être rapide
            try:
                response = self.session.get(page_url, timeout=5)
                if response.status_code == 200:
                    emails = email_pattern.findall(response.text)
                    if emails:
                        # Filtrer les emails génériques
                        valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com', 'domain.com'])]
                        if valid_emails:
                            return "; ".join(list(set(valid_emails))[:3])  # Max 3 emails
            except:
                continue

        return None

    def scrape_marketlink(self, max_pages=10):
        """Scraper les sites depuis MarketLink"""
        print("\n" + "="*80)
        print("🚀 SCRAPING LINKAVISTA MARKETLINK")
        print("="*80)

        if not self.login():
            print("❌ Impossible de se connecter. Arrêt du scraping.")
            return

        db_session = get_session()
        total_added = 0
        total_skipped = 0
        total_emails = 0

        for page in range(1, max_pages + 1):
            print(f"\n📄 Page {page}/{max_pages}")

            # URL de la page MarketLink
            marketlink_url = f"{self.base_url}/marketlink?page={page}"

            try:
                response = self.session.get(marketlink_url, timeout=15)

                if response.status_code != 200:
                    print(f"⚠️  Erreur {response.status_code} sur la page {page}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Trouver les sites (adapter selon la structure HTML réelle)
                # Rechercher les liens, tables ou divs contenant les sites
                sites_found = []

                # Méthode 1: Rechercher dans les liens
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)

                    # Si le lien contient un domaine externe
                    if 'http' in href and 'linkavista.com' not in href:
                        sites_found.append(href)
                    # Si le texte ressemble à un domaine
                    elif '.' in text and len(text) < 100:
                        sites_found.append(text)

                # Méthode 2: Rechercher dans les tables
                for table in soup.find_all('table'):
                    for row in table.find_all('tr'):
                        cells = row.find_all(['td', 'th'])
                        for cell in cells:
                            text = cell.get_text(strip=True)
                            if '.' in text and len(text) < 100 and ' ' not in text:
                                sites_found.append(text)

                if not sites_found:
                    print(f"⚠️  Aucun site trouvé sur la page {page}")
                    print("Structure HTML à analyser:")
                    print(response.text[:1000])
                    break

                print(f"🔍 {len(sites_found)} sites trouvés")

                # Traiter chaque site
                for idx, site_url in enumerate(sites_found, 1):
                    domain = self.extract_domain(site_url)

                    if not domain:
                        continue

                    # Vérifier si déjà en base
                    existing = db_session.query(Site).filter_by(domain=domain).first()
                    if existing:
                        total_skipped += 1
                        continue

                    print(f"  [{idx}/{len(sites_found)}] {domain} ", end='', flush=True)

                    # Chercher l'email
                    email = self.search_email_on_site(domain)

                    if email:
                        print(f"✉️  ✓ ", end='', flush=True)
                        total_emails += 1
                    else:
                        print(f"✉️  ✗ ", end='', flush=True)

                    # Créer l'entrée en base
                    site = Site(
                        domain=domain,
                        source_url=marketlink_url,
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

                    time.sleep(0.5)  # Pause entre chaque site

                time.sleep(2)  # Pause entre les pages

            except Exception as e:
                print(f"❌ Erreur sur la page {page}: {e}")
                continue

        db_session.close()

        print("\n" + "="*80)
        print("✅ SCRAPING TERMINÉ!")
        print("="*80)
        print(f"   Sites ajoutés: {total_added}")
        print(f"   Sites skippés: {total_skipped}")
        print(f"   Emails trouvés: {total_emails}")
        print("="*80)


if __name__ == "__main__":
    # Identifiants
    EMAIL = "datchdigital@gmail.com"
    PASSWORD = "B-BJoqV7"

    scraper = LinkAvistaScraper(EMAIL, PASSWORD)
    scraper.scrape_marketlink(max_pages=50)  # Scraper 50 pages
