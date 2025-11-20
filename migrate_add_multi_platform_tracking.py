#!/usr/bin/env python3
"""
Migration: Ajouter le tracking des sites présents sur plusieurs plateformes

Ce script:
1. Ajoute un champ 'also_on_linkavista' pour marquer les sites Ereferer aussi sur Linkavista
2. Ajoute un champ 'also_on_ereferer' pour marquer les sites Linkavista aussi sur Ereferer
3. Met à jour les sites en fonction de leur présence sur les deux plateformes

Usage:
    python3 migrate_add_multi_platform_tracking.py
"""

import sqlite3
import sys
from datetime import datetime

def add_multi_platform_fields():
    """Ajouter les champs de tracking multi-plateformes"""
    # Configurer un timeout plus long pour éviter les blocages
    conn = sqlite3.connect('scrap_email.db', timeout=30.0)
    cursor = conn.cursor()

    print("=" * 80)
    print("MIGRATION: Ajout du tracking multi-plateformes")
    print("=" * 80)
    print()

    try:
        # Vérifier les colonnes existantes
        cursor.execute("PRAGMA table_info(sites)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        # Ajouter also_on_linkavista si nécessaire
        if 'also_on_linkavista' not in existing_columns:
            print("📝 Ajout du champ 'also_on_linkavista'...")
            cursor.execute("ALTER TABLE sites ADD COLUMN also_on_linkavista BOOLEAN DEFAULT 0")
            print("✅ Champ 'also_on_linkavista' ajouté")
        else:
            print("ℹ️  Champ 'also_on_linkavista' existe déjà")

        # Ajouter also_on_ereferer si nécessaire
        if 'also_on_ereferer' not in existing_columns:
            print("📝 Ajout du champ 'also_on_ereferer'...")
            cursor.execute("ALTER TABLE sites ADD COLUMN also_on_ereferer BOOLEAN DEFAULT 0")
            print("✅ Champ 'also_on_ereferer' ajouté")
        else:
            print("ℹ️  Champ 'also_on_ereferer' existe déjà")

        conn.commit()

        print("\n" + "=" * 80)
        print("ÉTAPE 1: Champs créés avec succès")
        print("=" * 80)
        print()

        # Maintenant, identifier les sites présents sur les deux plateformes
        # Pour cela, nous devons scraper à nouveau Linkavista ou utiliser un fichier
        print("ℹ️  Pour marquer les sites présents sur les deux plateformes:")
        print("   1. Option 1: Exporter la liste des domaines Linkavista")
        print("   2. Option 2: Lancer scrape_async_linkavista.py en mode check-only")
        print()
        print("💡 Astuce: Les domaines qui existent déjà avec source_url='Ereferer'")
        print("   et qui sont trouvés sur Linkavista doivent être marqués")
        print()

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        conn.rollback()
        conn.close()
        return False

def mark_dual_platform_sites_from_file(linkavista_domains_file):
    """
    Marquer les sites présents sur les deux plateformes à partir d'un fichier

    Args:
        linkavista_domains_file: Fichier texte contenant un domaine par ligne
    """
    conn = sqlite3.connect('scrap_email.db', timeout=30.0)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("ÉTAPE 2: Marquage des sites multi-plateformes")
    print("=" * 80)
    print()

    try:
        # Lire les domaines Linkavista
        with open(linkavista_domains_file, 'r') as f:
            linkavista_domains = set(line.strip().lower() for line in f if line.strip())

        print(f"📂 {len(linkavista_domains):,} domaines chargés depuis {linkavista_domains_file}")

        # Compter les sites Ereferer qui sont aussi sur Linkavista
        marked_count = 0
        checked_count = 0

        cursor.execute("SELECT id, domain FROM sites WHERE source_url = 'Ereferer'")
        ereferer_sites = cursor.fetchall()

        print(f"🔍 Vérification de {len(ereferer_sites):,} sites Ereferer...")

        for site_id, domain in ereferer_sites:
            checked_count += 1
            if checked_count % 10000 == 0:
                print(f"   Progression: {checked_count:,}/{len(ereferer_sites):,}")

            if domain.lower() in linkavista_domains:
                cursor.execute(
                    "UPDATE sites SET also_on_linkavista = 1 WHERE id = ?",
                    (site_id,)
                )
                marked_count += 1

        # Marquer les sites Linkavista qui sont aussi sur Ereferer
        cursor.execute("""
            UPDATE sites
            SET also_on_ereferer = 1
            WHERE source_url LIKE '%linkavista%'
              AND domain IN (SELECT domain FROM sites WHERE source_url = 'Ereferer')
        """)
        linkavista_marked = cursor.rowcount

        conn.commit()

        print()
        print("=" * 80)
        print("✅ MIGRATION TERMINÉE")
        print("=" * 80)
        print(f"Sites Ereferer aussi sur Linkavista: {marked_count:,}")
        print(f"Sites Linkavista aussi sur Ereferer: {linkavista_marked:,}")
        print()

        conn.close()
        return True

    except FileNotFoundError:
        print(f"❌ Fichier non trouvé: {linkavista_domains_file}")
        print("💡 Créez d'abord ce fichier en exportant les domaines Linkavista")
        conn.close()
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    print()
    print("🚀 Migration: Tracking multi-plateformes")
    print()

    # Étape 1: Ajouter les champs
    if not add_multi_platform_fields():
        sys.exit(1)

    # Étape 2: Si un fichier de domaines est fourni, marquer les sites
    if len(sys.argv) > 1:
        linkavista_file = sys.argv[1]
        mark_dual_platform_sites_from_file(linkavista_file)
    else:
        print("ℹ️  Pour marquer les sites multi-plateformes, relancez avec:")
        print("   python3 migrate_add_multi_platform_tracking.py linkavista_domains.txt")
        print()
