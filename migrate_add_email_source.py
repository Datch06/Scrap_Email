#!/usr/bin/env python3
"""
Script de migration pour ajouter la colonne email_source
"""

import sqlite3
from pathlib import Path

DB_PATH = 'scrap_email.db'

def migrate():
    """Ajouter la colonne email_source si elle n'existe pas"""

    if not Path(DB_PATH).exists():
        print(f"❌ Base de données non trouvée: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Vérifier si la colonne existe déjà
    cursor.execute("PRAGMA table_info(sites)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'email_source' in columns:
        print("✓ La colonne 'email_source' existe déjà")
        conn.close()
        return True

    try:
        # Ajouter la colonne
        print("Ajout de la colonne 'email_source'...")
        cursor.execute("""
            ALTER TABLE sites
            ADD COLUMN email_source VARCHAR(20)
        """)
        conn.commit()
        print("✓ Colonne 'email_source' ajoutée avec succès")

        # Mettre à jour les valeurs par défaut
        # Les emails existants viennent probablement du scraping
        print("\nMise à jour des valeurs existantes...")
        cursor.execute("""
            UPDATE sites
            SET email_source = 'scraping'
            WHERE emails IS NOT NULL
            AND emails != ''
            AND emails != 'NO EMAIL FOUND'
        """)
        conn.commit()

        updated = cursor.rowcount
        print(f"✓ {updated} sites mis à jour avec email_source='scraping'")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 70)
    print("MIGRATION: Ajout de la colonne email_source")
    print("=" * 70)
    print()

    success = migrate()

    print()
    print("=" * 70)
    if success:
        print("✓ Migration terminée avec succès")
    else:
        print("❌ Migration échouée")
    print("=" * 70)
