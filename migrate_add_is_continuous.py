#!/usr/bin/env python3
"""
Migration script to add is_continuous column to campaigns table
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'campaigns.db')

def migrate():
    """Add is_continuous column to campaigns table"""
    print(f"Migrating database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}")
        print("Creating new database with updated schema...")
        # Import and initialize the database with the new schema
        from campaign_database import init_campaign_db
        init_campaign_db()
        print("✓ New database created with is_continuous field")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(campaigns)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'is_continuous' in columns:
        print("✓ Column is_continuous already exists")
    else:
        print("Adding is_continuous column...")
        cursor.execute("""
            ALTER TABLE campaigns
            ADD COLUMN is_continuous BOOLEAN DEFAULT 0
        """)
        conn.commit()
        print("✓ Column is_continuous added successfully")

    conn.close()
    print("✓ Migration completed")

if __name__ == '__main__':
    migrate()
