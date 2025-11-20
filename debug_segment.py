#!/usr/bin/env python3
"""
Script de debug pour vérifier les segments et les emails
"""

import sys
import json
from campaign_database import get_campaign_session, ContactSegment
from database import get_session, Site

def check_segment():
    campaign_session = get_campaign_session()
    db_session = get_session()

    try:
        # Récupérer le dernier segment créé
        segment = campaign_session.query(ContactSegment).filter(
            ContactSegment.name.like('%test%')
        ).order_by(ContactSegment.id.desc()).first()

        if not segment:
            print("Aucun segment de test trouvé")
            return

        print(f"\n{'='*70}")
        print(f"SEGMENT: {segment.name} (ID: {segment.id})")
        print(f"{'='*70}")
        print(f"Description: {segment.description}")
        print(f"Estimated count: {segment.estimated_count}")
        print(f"\nFiltres:")
        filters = json.loads(segment.filters)
        print(json.dumps(filters, indent=2))

        # Si c'est un segment manuel, vérifier les emails
        if 'manual_emails' in filters:
            manual_emails = filters['manual_emails']
            print(f"\n{'='*70}")
            print(f"EMAILS RECHERCHÉS: {len(manual_emails)}")
            print(f"{'='*70}")

            for email in manual_emails:
                print(f"\n🔍 Recherche de: {email}")

                # Chercher l'email dans la base
                sites = db_session.query(Site).filter(
                    Site.emails.like(f'%{email}%')
                ).all()

                if sites:
                    print(f"   ✅ Trouvé dans {len(sites)} site(s):")
                    for site in sites:
                        print(f"      - Domain: {site.domain}")
                        print(f"        Emails: {site.emails}")
                        print(f"        ID: {site.id}")
                else:
                    print(f"   ❌ PAS TROUVÉ dans la base")

                    # Vérifier si le domaine existe
                    domain = email.split('@')[1] if '@' in email else 'unknown'
                    domain_site = db_session.query(Site).filter(
                        Site.domain == domain
                    ).first()

                    if domain_site:
                        print(f"   ⚠️  Le domaine '{domain}' existe (Site ID: {domain_site.id})")
                        print(f"        Emails actuels: {domain_site.emails}")

        # Compter réellement les contacts trouvés
        print(f"\n{'='*70}")
        print("COMPTAGE RÉEL")
        print(f"{'='*70}")

        from sqlalchemy import or_
        query = db_session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        )

        if 'manual_emails' in filters:
            manual_emails = filters['manual_emails']
            email_conditions = []
            for email in manual_emails:
                email_conditions.append(Site.emails.like(f'%{email}%'))
            query = query.filter(or_(*email_conditions))

        count = query.count()
        print(f"Nombre de contacts trouvés: {count}")

        # Lister les sites trouvés
        sites = query.all()
        print(f"\nSites correspondants:")
        for site in sites:
            print(f"  - {site.domain}: {site.emails}")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        campaign_session.close()
        db_session.close()

if __name__ == '__main__':
    check_segment()
