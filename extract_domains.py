#!/usr/bin/env python3
"""Extrait les domaines uniques depuis une liste de liens externes."""

import sys
from urllib.parse import urlparse
from pathlib import Path

# Domaines à exclure (sous-domaines du site crawlé, gros sites connus, réseaux sociaux)
EXCLUDED_PATTERNS = {
    # Gros sites connus
    'google.com', 'apple.com', 'microsoft.com', 'mozilla.org',
    'amazon.com', 'amazon.es', 'amazon.fr', 'amzn.to',
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'linkedin.com', 'pinterest.com', 'tiktok.com',
    # Services CDN/Analytics
    'uecdn.es', 'cloudflare.com', 'akamai.net',
    # Services génériques
    'support.', 'policies.', 'apps.', 'play.google.com',
    'ghostery.com', 'consenthub.utiq.com',
}

def extract_domain(url):
    """Extrait le domaine d'une URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Nettoyer les www
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.lower()
    except:
        return None

def get_root_domain(domain):
    """Extrait le domaine racine (ex: sub.example.com -> example.com)"""
    parts = domain.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return domain

def is_ip_address(domain):
    """Vérifie si c'est une adresse IP."""
    import re
    # Pattern pour IPv4
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    return bool(re.match(ipv4_pattern, domain))

def should_exclude(domain, main_domain_root):
    """Vérifie si un domaine doit être exclu."""
    if not domain:
        return True

    # Exclure les adresses IP
    if is_ip_address(domain):
        return True

    # Exclure les domaines invalides (pas de point)
    if '.' not in domain:
        return True

    # Exclure les sous-domaines du site principal
    domain_root = get_root_domain(domain)
    if domain_root == main_domain_root:
        return True

    # Exclure les patterns connus
    for pattern in EXCLUDED_PATTERNS:
        if pattern in domain or domain.endswith(pattern):
            return True

    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_domains.py <fichier_liens.txt> [domaine_principal]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Erreur: {input_file} n'existe pas")
        sys.exit(1)

    # Détecter le domaine principal depuis le nom du fichier
    main_domain = None
    if len(sys.argv) > 2:
        main_domain = sys.argv[2]
    else:
        # Essayer de détecter depuis le nom du fichier (ex: external_links_www.marca.com.txt)
        filename = input_file.stem  # external_links_www.marca.com
        if 'external_links_' in filename:
            main_domain = filename.replace('external_links_', '').replace('www_', 'www.')
            main_domain = main_domain.replace('_', '.')

    main_domain_root = get_root_domain(main_domain) if main_domain else None
    print(f"[INFO] Domaine principal détecté: {main_domain} (racine: {main_domain_root})", file=sys.stderr)

    domains = set()
    excluded_count = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url:
                domain = extract_domain(url)
                if domain:
                    if should_exclude(domain, main_domain_root):
                        excluded_count += 1
                    else:
                        domains.add(domain)

    # Trier et afficher
    for domain in sorted(domains):
        print(domain)

    print(f"\n--- {len(domains)} domaines uniques (suspects) ---", file=sys.stderr)
    print(f"--- {excluded_count} domaines exclus (sous-domaines/gros sites) ---", file=sys.stderr)

if __name__ == '__main__':
    main()
