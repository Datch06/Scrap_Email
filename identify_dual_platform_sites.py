#!/usr/bin/env python3
"""
Identifier les sites présents sur Ereferer ET Linkavista

Ce script analyse la base de données pour trouver quels domaines
sont présents sur les deux plateformes.

Usage:
    python3 identify_dual_platform_sites.py
"""

import sqlite3
from collections import defaultdict

def analyze_dual_platform_sites():
    """Analyser les sites présents sur plusieurs plateformes"""

    conn = sqlite3.connect('scrap_email.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("ANALYSE DES SITES MULTI-PLATEFORMES")
    print("=" * 80)
    print()

    # Récupérer tous les domaines avec leurs sources
    cursor.execute("""
        SELECT domain, source_url, id, emails, email_validated
        FROM sites
        WHERE source_url IN ('Ereferer', 'https://linkavista.com/marketlink')
           OR source_url LIKE '%linkavista%'
    """)

    # Grouper par domaine
    domains_info = defaultdict(list)
    for domain, source, site_id, emails, validated in cursor.fetchall():
        platform = 'Linkavista' if 'linkavista' in source.lower() else 'Ereferer'
        domains_info[domain].append({
            'platform': platform,
            'source': source,
            'id': site_id,
            'emails': emails,
            'validated': validated
        })

    # Identifier les sites sur les deux plateformes
    dual_platform = []
    ereferer_only = []
    linkavista_only = []

    for domain, infos in domains_info.items():
        platforms = set(info['platform'] for info in infos)

        if len(platforms) > 1:
            dual_platform.append((domain, infos))
        elif 'Ereferer' in platforms:
            ereferer_only.append(domain)
        elif 'Linkavista' in platforms:
            linkavista_only.append(domain)

    # Statistiques
    print("📊 STATISTIQUES")
    print("-" * 80)
    print(f"Sites uniquement sur Ereferer:     {len(ereferer_only):>10,}")
    print(f"Sites uniquement sur Linkavista:   {len(linkavista_only):>10,}")
    print(f"Sites sur LES DEUX plateformes:    {len(dual_platform):>10,}")
    print(f"Total unique de domaines:          {len(domains_info):>10,}")
    print()

    # Détails des sites sur les deux plateformes
    if dual_platform:
        print("=" * 80)
        print(f"⚠️  SITES PRÉSENTS SUR LES DEUX PLATEFORMES ({len(dual_platform):,})")
        print("=" * 80)
        print()
        print("Ces sites ont des entrées multiples en base de données!")
        print()

        # Afficher quelques exemples
        print("Exemples (10 premiers):")
        print("-" * 80)
        for domain, infos in dual_platform[:10]:
            print(f"\n🌐 {domain}")
            for info in infos:
                status = "✓ validé" if info['validated'] else "⏳ non validé"
                emails_info = info['emails'][:50] if info['emails'] else "Aucun"
                print(f"   • {info['platform']:12} | ID: {info['id']:7} | {status} | {emails_info}")

        if len(dual_platform) > 10:
            print(f"\n   ... et {len(dual_platform) - 10:,} autres sites")

        # Recommandations
        print()
        print("=" * 80)
        print("💡 RECOMMANDATIONS")
        print("=" * 80)
        print()
        print("Option 1: Garder les doublons et ajouter un flag 'also_on_linkavista'")
        print("   → Permet de tracker quelle plateforme a fourni chaque email")
        print()
        print("Option 2: Fusionner les entrées et garder la meilleure")
        print("   → Nettoie la base mais perd l'information de source")
        print()
        print("Option 3: Garder Ereferer comme source principale")
        print("   → Ajouter les sites Linkavista uniquement s'ils n'existent pas dans Ereferer")
        print()

    # Créer un fichier avec tous les domaines Linkavista pour la migration
    linkavista_domains_file = 'linkavista_all_domains.txt'
    with open(linkavista_domains_file, 'w') as f:
        # Tous les domaines trouvés dans Linkavista (même s'ils sont en doublon)
        all_linkavista = set()
        for domain, infos in domains_info.items():
            for info in infos:
                if info['platform'] == 'Linkavista':
                    all_linkavista.add(domain)

        for domain in sorted(all_linkavista):
            f.write(f"{domain}\n")

    print(f"📄 Fichier créé: {linkavista_domains_file}")
    print(f"   Contient {len(all_linkavista):,} domaines Linkavista")
    print()
    print("Utilisez ce fichier avec migrate_add_multi_platform_tracking.py pour marquer les sites")

    conn.close()

if __name__ == "__main__":
    analyze_dual_platform_sites()
