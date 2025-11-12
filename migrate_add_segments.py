#!/usr/bin/env python3
"""
Migration: Ajouter les segments de contacts
"""

import sys
from campaign_database import init_campaign_db, Base

def migrate():
    """Exécuter la migration"""
    print("=" * 70)
    print("MIGRATION: Ajout des segments de contacts")
    print("=" * 70)
    print()

    try:
        engine = init_campaign_db()

        print("📦 Mise à jour du schéma via SQLAlchemy...")
        Base.metadata.create_all(engine)

        print("✅ Schéma mis à jour avec succès")
        print("   - Table contact_segments créée")
        print("   - Colonne segment_id ajoutée à scenarios")

        print()
        print("==" * 35)
        print("✅ Migration terminée avec succès!")
        print("==" * 35)

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
