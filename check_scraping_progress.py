#!/usr/bin/env python3
"""
Script de monitoring pour suivre la progression du scraping de backlinks
"""

from db_helper import DBHelper
from database import Site
from datetime import datetime, timedelta
import time

def check_progress():
    with DBHelper() as db:
        # Stats globales
        total_sellers = db.session.query(Site).filter_by(is_linkavista_seller=True).count()
        total_buyers = db.session.query(Site).filter(Site.purchased_from.isnot(None)).count()
        buyers_with_email = db.session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Activité récente (dernière heure)
        recent = datetime.utcnow() - timedelta(hours=1)
        recent_buyers = db.session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.created_at >= recent
        ).count()

        recent_emails = db.session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND',
            Site.email_found_at >= recent
        ).count()

        # Affichage
        print("=" * 80)
        print(f"📊 PROGRESSION DU SCRAPING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        print("📈 Stats globales:")
        print(f"  - Sites vendeurs traités: {total_sellers:,}")
        print(f"  - Acheteurs découverts: {total_buyers:,}")
        print(f"  - Acheteurs avec email: {buyers_with_email:,}")
        print(f"  - Taux de conversion email: {buyers_with_email/total_buyers*100:.1f}%" if total_buyers > 0 else "  - Taux: N/A")
        print()
        print("⏱️  Dernière heure:")
        print(f"  - Nouveaux acheteurs: {recent_buyers:,}")
        print(f"  - Emails trouvés: {recent_emails:,}")
        print()

        # Exemples récents
        latest_with_email = db.session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND'
        ).order_by(Site.email_found_at.desc()).limit(5).all()

        if latest_with_email:
            print("🎯 Derniers acheteurs avec email trouvés:")
            for site in latest_with_email:
                print(f"  ✅ {site.domain}")
                print(f"     Email: {site.emails[:60]}...")
                print(f"     Acheté de: {site.purchased_from}")
                print()

if __name__ == "__main__":
    check_progress()
