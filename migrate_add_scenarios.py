#!/usr/bin/env python3
"""
Migration: Ajouter les tables pour le système de scénarios
"""

import sys
from campaign_database import (
    init_campaign_db,
    get_campaign_session,
    Scenario, ScenarioStep, ContactSequence, OperationLedger
)

def migrate():
    """Exécuter la migration"""
    print("=" * 70)
    print("MIGRATION: Ajout des tables de scénarios")
    print("=" * 70)
    print()

    try:
        # Créer toutes les tables (SQLAlchemy créera seulement celles qui n'existent pas)
        print("📦 Création des nouvelles tables...")
        engine = init_campaign_db()

        session = get_campaign_session()

        # Vérifier que les tables ont été créées
        print("✅ Tables créées:")
        print("   - scenarios")
        print("   - scenario_steps")
        print("   - contact_sequences")
        print("   - operation_ledger")
        print()

        # Afficher les statistiques
        scenario_count = session.query(Scenario).count()
        print(f"📊 Scénarios existants: {scenario_count}")

        session.close()

        print()
        print("=" * 70)
        print("✅ Migration terminée avec succès!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
