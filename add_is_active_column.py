#!/usr/bin/env python3
"""
Migration : Ajouter la colonne is_active à la table sites
"""

from database import get_session, Site
from sqlalchemy import text

def add_is_active_column():
    """Ajouter la colonne is_active si elle n'existe pas"""
    session = get_session()

    try:
        # Pour SQLite, vérifier si la colonne existe en interrogeant pragma
        result = session.execute(text("PRAGMA table_info(sites)"))
        columns = [row[1] for row in result.fetchall()]

        if 'is_active' in columns:
            print("✅ La colonne is_active existe déjà")
            return

        # Ajouter la colonne (SQLite n'accepte pas DEFAULT dans ALTER TABLE)
        print("📝 Ajout de la colonne is_active...")
        session.execute(text("ALTER TABLE sites ADD COLUMN is_active BOOLEAN"))
        session.commit()
        print("✅ Colonne is_active ajoutée")

        # Mettre à jour tous les sites existants à actifs (TRUE = 1 en SQLite)
        print("📝 Initialisation des valeurs...")
        session.execute(text("UPDATE sites SET is_active = 1 WHERE is_active IS NULL"))
        session.commit()
        print("✅ Tous les sites existants marqués comme actifs")

    except Exception as e:
        session.rollback()
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == '__main__':
    add_is_active_column()
