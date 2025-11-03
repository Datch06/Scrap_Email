#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour scraper les liens externes du site fr.bijouxenvogue.com
Exclut les liens vers les réseaux sociaux
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict
from datetime import datetime

class BijouxEnVogueScraper:
    def __init__(self):
        self.base_url = "https://fr.bijouxenvogue.com"
        self.visited_urls = set()
        self.external_links = set()
        self.social_networks = {
            'facebook.com', 'fb.com', 'twitter.com', 'x.com', 'instagram.com',
            'linkedin.com', 'youtube.com', 'tiktok.com', 'pinterest.com',
            'snapchat.com', 'whatsapp.com', 'telegram.org', 'discord.com',
            'reddit.com', 'tumblr.com', 'flickr.com', 'vimeo.com',
            'dailymotion.com', 'twitch.tv', 'medium.com', 'github.com',
            'gitlab.com', 'bitbucket.org'
        }
        
    def is_social_network(self, url):
        """Vérifie si l'URL pointe vers un réseau social"""
        domain = urlparse(url).netloc.lower()
        for social in self.social_networks:
            if social in domain:
                return True
        return False
    
    def is_external_link(self, url, base_domain):
        """Vérifie si l'URL est externe au site"""
        parsed_url = urlparse(url)
        return parsed_url.netloc and parsed_url.netloc != base_domain
    
    def get_page_links(self, url):
        """Récupère tous les liens d'une page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # Récupérer tous les liens href
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                links.append(full_url)
            
            return links
            
        except Exception as e:
            print(f"Erreur lors de la récupération de {url}: {e}")
            return []
    
    def scrape_site(self, max_pages=None):
        """Scrape le site pour trouver tous les liens externes"""
        base_domain = urlparse(self.base_url).netloc
        urls_to_visit = [self.base_url]
        
        print(f"🔍 Début du scraping complet de {self.base_url}")
        if max_pages:
            print(f"📊 Limite de pages: {max_pages}")
        else:
            print("📊 Scraping complet - aucune limite de pages")
        print("-" * 50)
        
        page_count = 0
        
        while urls_to_visit:
            if max_pages and page_count >= max_pages:
                break
            current_url = urls_to_visit.pop(0)
            
            if current_url in self.visited_urls:
                continue
                
            self.visited_urls.add(current_url)
            page_count += 1
            
            print(f"📄 Page {page_count}: {current_url}")
            
            # Récupérer les liens de la page
            links = self.get_page_links(current_url)
            
            for link in links:
                # Nettoyer l'URL
                clean_link = link.split('#')[0].split('?')[0]
                
                # Vérifier si c'est un lien externe
                if self.is_external_link(clean_link, base_domain):
                    # Vérifier si ce n'est pas un réseau social
                    if not self.is_social_network(clean_link):
                        self.external_links.add(clean_link)
                        print(f"  🔗 Lien externe trouvé: {clean_link}")
                
                # Ajouter les liens internes à la liste de visite
                elif clean_link.startswith(self.base_url) and clean_link not in self.visited_urls and clean_link not in urls_to_visit:
                    # Filtrer les liens vers des fichiers (images, PDF, etc.)
                    if not any(clean_link.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.zip', '.rar']):
                        urls_to_visit.append(clean_link)
        
        print("-" * 50)
        print(f"✅ Scraping terminé!")
        print(f"📊 Pages visitées: {len(self.visited_urls)}")
        print(f"🔗 Liens externes trouvés: {len(self.external_links)}")
    
    def categorize_links(self):
        """Catégorise les liens par domaine"""
        categories = defaultdict(list)
        
        for link in self.external_links:
            domain = urlparse(link).netloc
            categories[domain].append(link)
        
        return categories
    
    def save_results(self, filename="liens_externes_bijouxenvogue.txt"):
        """Sauvegarde les résultats dans un fichier"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("LIENS EXTERNES DE FR.BIJOUXENVOGUE.COM\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"URL de base: {self.base_url}\n")
            f.write(f"Total de liens externes: {len(self.external_links)}\n\n")
            
            categories = self.categorize_links()
            
            for domain, links in sorted(categories.items()):
                f.write(f"\n🌐 DOMAINE: {domain}\n")
                f.write("-" * 30 + "\n")
                for link in sorted(links):
                    f.write(f"  • {link}\n")
        
        print(f"💾 Résultats sauvegardés dans: {filename}")
    
    def display_results(self):
        """Affiche les résultats de manière organisée"""
        print("\n" + "="*60)
        print("📋 RÉSULTATS DU SCRAPING")
        print("="*60)
        
        if not self.external_links:
            print("❌ Aucun lien externe trouvé")
            return
        
        categories = self.categorize_links()
        
        for domain, links in sorted(categories.items()):
            print(f"\n🌐 DOMAINE: {domain}")
            print("-" * 40)
            for link in sorted(links):
                print(f"  • {link}")
        
        print(f"\n📊 RÉSUMÉ:")
        print(f"  • Total des liens externes: {len(self.external_links)}")
        print(f"  • Nombre de domaines uniques: {len(categories)}")

def main():
    scraper = BijouxEnVogueScraper()
    
    # Lancer le scraping complet (sans limite de pages)
    scraper.scrape_site()
    
    # Afficher les résultats
    scraper.display_results()
    
    # Sauvegarder les résultats
    scraper.save_results()
    
    return scraper.external_links

if __name__ == "__main__":
    external_links = main()
