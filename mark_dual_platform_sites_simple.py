#!/usr/bin/env python3
"""
Marquer les sites présents sur Linkavista ET Ereferer

Ce script lit le fichier des domaines communs et met à jour
le champ 'is_linkavista_seller' pour les sites Ereferer qui sont
aussi sur Linkavista.

Usage:
    python3 mark_dual_platform_sites_simple.py domains_on_both_platforms_complete.txt
"""

import sqlite3
import sys
import time

def mark_sites(domains_file):
    """Marquer les sites présents sur les deux plateformes"""

    print("=" * 80)
    print("MARQUAGE DES SITES MULTI-PLATEFORMES")
    print("=" * 80)
    print()

    # Charger les domaines
    try:
        with open(domains_file, 'r') as f:
            domains_to_mark = set(line.strip().lower() for line in f if line.strip())
        print(f"📂 {len(domains_to_mark):,} domaines chargés depuis {domains_file}")
    except FileNotFoundError:
        print(f"❌ Fichier non trouvé: {domains_file}")
        return False

    # Connexion avec retry
    max_retries = 5
    retry_delay = 2
    conn = None

    for attempt in range(max_retries):
        try:
            print(f"\n🔄 Tentative de connexion ({attempt + 1}/{max_retries})...")
            conn = sqlite3.connect('scrap_email.db', timeout=60.0)
            print("✅ Connexion établie")
            break
        except sqlite3.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"⏳ Base verrouillée, attente de {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"❌ Impossible de se connecter après {max_retries} tentatives")
                return False

    cursor = conn.cursor()

    try:
        print()
        print("=" * 80)
        print("ANALYSE DE LA SITUATION")
        print("=" * 80)
        print()

        # Compter les sites Ereferer
        cursor.execute("SELECT COUNT(*) FROM sites WHERE source_url = 'Ereferer'")
        ereferer_total = cursor.fetchone()[0]
        print(f"📊 Sites Ereferer en base: {ereferer_total:,}")

        # Compter combien sont déjà marqués vendeurs
        cursor.execute("""
            SELECT COUNT(*) FROM sites
            WHERE source_url = 'Ereferer' AND is_linkavista_seller = 1
        """)
        already_marked = cursor.fetchone()[0]
        print(f"✓  Déjà marqués comme vendeurs: {already_marked:,}")

        # Compter combien parmi les domaines à marquer sont dans Ereferer
        print(f"\n🔍 Recherche des correspondances...")

        marked_count = 0
        not_found = 0
        batch_size = 1000
        domains_list = list(domains_to_mark)

        print(f"📝 Traitement par lots de {batch_size}...")

        for i in range(0, len(domains_list), batch_size):
            batch = domains_list[i:i + batch_size]

            # Trouver les IDs des sites Ereferer correspondants
            placeholders = ','.join('?' * len(batch))
            cursor.execute(f"""
                SELECT id, domain FROM sites
                WHERE source_url = 'Ereferer'
                  AND domain IN ({placeholders})
                  AND (is_linkavista_seller IS NULL OR is_linkavista_seller = 0)
            """, batch)

            sites_to_update = cursor.fetchall()

            if sites_to_update:
                # Mettre à jour par lot
                ids_to_update = [site[0] for site in sites_to_update]
                placeholders_ids = ','.join('?' * len(ids_to_update))

                cursor.execute(f"""
                    UPDATE sites
                    SET is_linkavista_seller = 1
                    WHERE id IN ({placeholders_ids})
                """, ids_to_update)

                marked_count += len(sites_to_update)
                conn.commit()

                if (i + batch_size) % 5000 == 0:
                    print(f"   Progression: {i + batch_size:,}/{len(domains_list):,} | Marqués: {marked_count:,}")

        not_found = len(domains_to_mark) - marked_count

        print()
        print("=" * 80)
        print("✅ MARQUAGE TERMINÉ")
        print("=" * 80)
        print()
        print(f"Sites Ereferer marqués comme aussi sur Linkavista: {marked_count:,}")
        print(f"Domaines non trouvés dans Ereferer: {not_found:,}")
        print()

        # Vérification finale
        cursor.execute("""
            SELECT COUNT(*) FROM sites
            WHERE source_url = 'Ereferer' AND is_linkavista_seller = 1
        """)
        final_marked = cursor.fetchone()[0]
        new_marked = final_marked - already_marked

        print("📊 RÉSULTAT FINAL:")
        print(f"   Total sites Ereferer marqués vendeurs: {final_marked:,}")
        print(f"   Nouveaux marqués lors de cette opération: {new_marked:,}")
        print()

        # Statistiques globales
        cursor.execute("SELECT COUNT(*) FROM sites WHERE is_linkavista_seller = 1")
        total_vendors = cursor.fetchone()[0]

        print("🎯 STATISTIQUES GLOBALES:")
        print(f"   Total sites vendeurs de liens: {total_vendors:,}")
        print()

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mark_dual_platform_sites_simple.py <fichier_domaines>")
        print()
        print("Exemple:")
        print("  python3 mark_dual_platform_sites_simple.py domains_on_both_platforms_complete.txt")
        sys.exit(1)

    domains_file = sys.argv[1]
    success = mark_sites(domains_file)
    sys.exit(0 if success else 1)
