#!/usr/bin/env python3
"""
Script de test pour debugger le crawling de backlinks
"""
import asyncio
import aiohttp
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
import ssl

# Configuration
TEST_URL = "https://arcep.fr"  # Site de test français
TIMEOUT = 10

class LinkExtractor(HTMLParser):
    """Parser HTML pour extraire les liens"""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


def extract_domain(url):
    """Extraire le domaine d'une URL"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    domain = domain.replace('www.', '')
    return domain if domain else None


def normalize_url(base, url):
    """Normaliser une URL"""
    url = url.strip()
    if not url or url.startswith(('mailto:', 'javascript:', 'tel:', '#')):
        return None

    parsed = urlparse(url)
    if not parsed.scheme:
        url = urljoin(base, url)
        parsed = urlparse(url)

    if parsed.scheme not in ('http', 'https'):
        return None

    return parsed.scheme + '://' + parsed.netloc + parsed.path


async def test_crawl(url):
    """Tester le crawl d'une URL"""
    print(f"\n🔍 Test de crawl sur: {url}")
    print("=" * 80)

    base_domain = extract_domain(url)
    print(f"✓ Domaine de base: {base_domain}")

    # Créer une session HTTP
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        try:
            # Fetch la page
            print(f"\n📥 Téléchargement de la page...")
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ssl=ssl_context,
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                if response.status != 200:
                    print(f"❌ Erreur HTTP {response.status}")
                    return

                html = await response.text()
                print(f"✓ Page téléchargée: {len(html)} caractères")

                # Parser les liens
                print(f"\n🔗 Extraction des liens...")
                parser = LinkExtractor()
                try:
                    parser.feed(html)
                    print(f"✓ {len(parser.links)} liens bruts trouvés")
                except Exception as e:
                    print(f"❌ Erreur parsing: {e}")
                    return

                # Analyser les liens
                print(f"\n📊 Analyse des liens:")
                internal_links = []
                external_links = []
                invalid_links = 0

                for i, link in enumerate(parser.links[:20]):  # Premiers 20 liens
                    normalized = normalize_url(url, link)
                    if not normalized:
                        invalid_links += 1
                        continue

                    link_domain = extract_domain(normalized)

                    if link_domain == base_domain:
                        internal_links.append(normalized)
                        if len(internal_links) <= 5:
                            print(f"  ✓ Lien INTERNE #{len(internal_links)}: {normalized}")
                    else:
                        external_links.append(link_domain)

                print(f"\n📈 Résumé:")
                print(f"  - Total liens bruts: {len(parser.links)}")
                print(f"  - Liens invalides/ignorés: {invalid_links}")
                print(f"  - Liens INTERNES trouvés: {len(internal_links)}")
                print(f"  - Liens externes: {len(external_links)}")

                if internal_links:
                    print(f"\n✅ SUCCESS: {len(internal_links)} liens internes seraient ajoutés à to_visit")
                    print(f"\nExemples de liens internes:")
                    for link in internal_links[:10]:
                        print(f"  - {link}")
                else:
                    print(f"\n❌ PROBLÈME: Aucun lien interne trouvé!")
                    print(f"\nDEBUG - Premiers liens bruts:")
                    for link in parser.links[:10]:
                        print(f"  - {repr(link)}")

        except Exception as e:
            print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    asyncio.run(test_crawl(TEST_URL))
