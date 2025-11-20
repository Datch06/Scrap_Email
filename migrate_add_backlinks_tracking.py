#!/usr/bin/env python3
"""
Migration pour ajouter les champs de tracking du crawling de backlinks
"""

import sqlite3
from pathlib import Path

DB_PATH = '/var/www/Scrap_Email/scrap_email.db'

def migrate():
    """Ajouter les champs de tracking du crawling backlinks"""

    if not Path(DB_PATH).exists():
        print(f"❌ Base de données {DB_PATH} introuvable!")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Vérifier si les colonnes existent déjà
        cursor.execute("PRAGMA table_info(sites)")
        columns = [col[1] for col in cursor.fetchall()]

        added = []

        # Ajouter backlinks_crawled si elle n'existe pas
        if 'backlinks_crawled' not in columns:
            cursor.execute("""
                ALTER TABLE sites
                ADD COLUMN backlinks_crawled BOOLEAN DEFAULT 0
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_sites_backlinks_crawled ON sites (backlinks_crawled)")
            added.append('backlinks_crawled')
            print("✅ Colonne backlinks_crawled ajoutée")
        else:
            print("ℹ️  Colonne backlinks_crawled existe déjà")

        # Ajouter backlinks_crawled_at si elle n'existe pas
        if 'backlinks_crawled_at' not in columns:
            cursor.execute("""
                ALTER TABLE sites
                ADD COLUMN backlinks_crawled_at DATETIME
            """)
            added.append('backlinks_crawled_at')
            print("✅ Colonne backlinks_crawled_at ajoutée")
        else:
            print("ℹ️  Colonne backlinks_crawled_at existe déjà")

        # Commit
        conn.commit()

        if added:
            print(f"\n✅ Migration réussie! Colonnes ajoutées: {', '.join(added)}")
        else:
            print("\n✅ Base de données déjà à jour")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 70)
    print("🔧 MIGRATION BASE DE DONNÉES - TRACKING BACKLINKS")
    print("=" * 70)
    print("\nAjout des champs de tracking du crawling:")
    print("  - backlinks_crawled (BOOLEAN)")
    print("  - backlinks_crawled_at (DATETIME)")
    print()

    success = migrate()

    if success:
        print("\n" + "=" * 70)
        print("✅ MIGRATION TERMINÉE")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ MIGRATION ÉCHOUÉE")
        print("=" * 70)
