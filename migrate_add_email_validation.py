#!/usr/bin/env python3
"""
Migration pour ajouter les champs de validation d'email à la base de données
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import text
from database import DATABASE_URL

def migrate():
    """Ajouter les colonnes de validation email"""
    engine = create_engine(DATABASE_URL)

    print("🔄 Migration: Ajout des champs de validation d'email...")

    # Colonnes à ajouter
    columns_to_add = [
        ("email_validated", "BOOLEAN DEFAULT 0"),
        ("email_validation_score", "INTEGER DEFAULT 0"),  # Score 0-100
        ("email_validation_status", "TEXT"),  # 'valid', 'invalid', 'risky', 'unknown'
        ("email_validation_details", "TEXT"),  # JSON avec détails (syntax, dns, smtp)
        ("email_validation_date", "DATETIME"),
        ("email_deliverable", "BOOLEAN DEFAULT 0"),  # Email peut recevoir des messages
    ]

    with engine.connect() as conn:
        for column_name, column_type in columns_to_add:
            try:
                # Vérifier si la colonne existe déjà
                result = conn.execute(text(f"PRAGMA table_info(sites)"))
                existing_columns = [row[1] for row in result]

                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE sites ADD COLUMN {column_name} {column_type}"))
                    conn.commit()
                    print(f"  ✓ Colonne '{column_name}' ajoutée")
                else:
                    print(f"  ⊘ Colonne '{column_name}' existe déjà")

            except Exception as e:
                print(f"  ✗ Erreur pour '{column_name}': {e}")

    print("✅ Migration terminée!")

if __name__ == '__main__':
    migrate()
