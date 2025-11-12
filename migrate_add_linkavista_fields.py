#!/usr/bin/env python3
"""
Migration pour ajouter les champs is_linkavista_seller et purchased_from
"""

import sqlite3
from pathlib import Path

DB_PATH = 'scrap_email.db'

def migrate():
    """Ajouter les nouveaux champs à la table sites"""

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

        # Ajouter is_linkavista_seller si elle n'existe pas
        if 'is_linkavista_seller' not in columns:
            cursor.execute("""
                ALTER TABLE sites
                ADD COLUMN is_linkavista_seller BOOLEAN DEFAULT 0
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_sites_is_linkavista_seller ON sites (is_linkavista_seller)")
            added.append('is_linkavista_seller')
            print("✅ Colonne is_linkavista_seller ajoutée")
        else:
            print("ℹ️  Colonne is_linkavista_seller existe déjà")

        # Ajouter purchased_from si elle n'existe pas
        if 'purchased_from' not in columns:
            cursor.execute("""
                ALTER TABLE sites
                ADD COLUMN purchased_from VARCHAR(255)
            """)
            added.append('purchased_from')
            print("✅ Colonne purchased_from ajoutée")
        else:
            print("ℹ️  Colonne purchased_from existe déjà")

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
    print("🔧 MIGRATION BASE DE DONNÉES")
    print("=" * 70)
    print("\nAjout des champs LinkAvista:")
    print("  - is_linkavista_seller (BOOLEAN)")
    print("  - purchased_from (VARCHAR)")
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
