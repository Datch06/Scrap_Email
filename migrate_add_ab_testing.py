#!/usr/bin/env python3
"""
Migration: Ajouter le support A/B testing
"""

import sys
from campaign_database import init_campaign_db, get_campaign_session

def migrate():
    """Exécuter la migration"""
    print("=" * 70)
    print("MIGRATION: Ajout du support A/B testing")
    print("=" * 70)
    print()

    try:
        engine = init_campaign_db()

        # SQLAlchemy créera automatiquement les nouvelles tables et colonnes
        print("📦 Mise à jour du schéma via SQLAlchemy...")

        from campaign_database import Base
        Base.metadata.create_all(engine)

        print("✅ Schéma mis à jour avec succès")
        print("   - Table step_template_variants créée")
        print("   - Colonne variant_id ajoutée à campaign_emails")

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
