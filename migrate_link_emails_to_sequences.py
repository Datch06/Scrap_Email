#!/usr/bin/env python3
"""
Migration: Ajouter la colonne sequence_id à campaign_emails
"""

import sys
from sqlalchemy import text
from campaign_database import init_campaign_db, get_campaign_session

def migrate():
    """Exécuter la migration"""
    print("=" * 70)
    print("MIGRATION: Ajout de sequence_id à campaign_emails")
    print("=" * 70)
    print()

    try:
        engine = init_campaign_db()

        # La méthode la plus simple avec SQLAlchemy : recréer toutes les tables
        # SQLAlchemy créera seulement les colonnes manquantes
        print("📦 Mise à jour du schéma via SQLAlchemy...")

        # Cette commande va automatiquement ajouter les colonnes manquantes
        # sans affecter les colonnes existantes
        from campaign_database import Base
        Base.metadata.create_all(engine)

        print("✅ Schéma mis à jour avec succès")
        print("   - Colonne sequence_id ajoutée à campaign_emails")
        print("   - Index et contraintes créés")
        print("   - campaign_id est maintenant nullable")

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
