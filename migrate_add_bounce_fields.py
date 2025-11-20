#!/usr/bin/env python3
"""
Migration script to add bounce_reason field to campaign_emails table
and create email_blacklist table
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'campaigns.db')

def migrate():
    """Add bounce_reason column and create email_blacklist table"""
    print(f"Migrating database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}")
        print("Creating new database with updated schema...")
        # Import and initialize the database with the new schema
        from campaign_database import init_campaign_db
        init_campaign_db()
        print("✓ New database created with bounce fields and blacklist table")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if bounce_reason column already exists in campaign_emails
    cursor.execute("PRAGMA table_info(campaign_emails)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'bounce_reason' in columns:
        print("✓ Column bounce_reason already exists in campaign_emails")
    else:
        print("Adding bounce_reason column to campaign_emails...")
        cursor.execute("""
            ALTER TABLE campaign_emails
            ADD COLUMN bounce_reason TEXT
        """)
        conn.commit()
        print("✓ Column bounce_reason added successfully to campaign_emails")

    # Check if email_blacklist table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='email_blacklist'
    """)

    if cursor.fetchone():
        print("✓ Table email_blacklist already exists")
    else:
        print("Creating email_blacklist table...")
        cursor.execute("""
            CREATE TABLE email_blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL UNIQUE,
                bounce_type VARCHAR(50) NOT NULL,
                bounce_reason TEXT,
                first_bounced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_bounced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                bounce_count INTEGER DEFAULT 1,
                campaign_id INTEGER
            )
        """)

        # Create index on email for faster lookups
        cursor.execute("""
            CREATE INDEX idx_email_blacklist_email ON email_blacklist(email)
        """)

        conn.commit()
        print("✓ Table email_blacklist created successfully")

    # Populate blacklist from existing bounced emails
    print("Populating email_blacklist from existing bounced emails...")
    cursor.execute("""
        INSERT OR IGNORE INTO email_blacklist
            (email, bounce_type, bounce_reason, first_bounced_at, last_bounced_at, campaign_id)
        SELECT
            to_email,
            COALESCE(bounce_type, 'hard') as bounce_type,
            error_message as bounce_reason,
            bounced_at,
            bounced_at,
            campaign_id
        FROM campaign_emails
        WHERE status = 'bounced' AND bounced_at IS NOT NULL
    """)

    rows_added = cursor.rowcount
    conn.commit()
    print(f"✓ Added {rows_added} bounced emails to blacklist")

    conn.close()
    print("✓ Migration completed")

if __name__ == '__main__':
    migrate()
