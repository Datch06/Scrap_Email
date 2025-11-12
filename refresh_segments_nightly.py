#!/usr/bin/env python3
"""
Script de mise à jour nocturne des segments de contacts
À exécuter via cron chaque nuit pour recalculer le nombre de contacts
"""

import sys
import logging
from datetime import datetime
from campaign_database import get_campaign_session, ContactSegment
from database import get_session, Site
import json

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_segment_query(segment, db_session):
    """Construire une requête SQLAlchemy basée sur les filtres d'un segment"""
    filters = json.loads(segment.filters)

    # Base: contacts avec email
    query = db_session.query(Site).filter(
        Site.emails.isnot(None),
        Site.emails != '',
        Site.emails != 'NO EMAIL FOUND'
    )

    # Filtre: score minimum
    if 'email_validation_score_min' in filters:
        query = query.filter(Site.email_validation_score >= filters['email_validation_score_min'])

    # Filtre: score maximum
    if 'email_validation_score_max' in filters:
        query = query.filter(Site.email_validation_score <= filters['email_validation_score_max'])

    # Filtre: deliverability
    if 'email_deliverable' in filters:
        if filters['email_deliverable']:
            query = query.filter(Site.email_deliverable == True)
        else:
            query = query.filter(Site.email_deliverable == False)

    # Filtre: SIRET
    if 'has_siret' in filters:
        if filters['has_siret']:
            query = query.filter(
                Site.siret.isnot(None),
                Site.siret != '',
                Site.siret != 'NON TROUVÉ'
            )
        else:
            query = query.filter(
                (Site.siret.is_(None)) |
                (Site.siret == '') |
                (Site.siret == 'NON TROUVÉ')
            )

    # Filtre: domaines à inclure
    if 'domains_include' in filters and filters['domains_include']:
        domains = filters['domains_include']
        if isinstance(domains, list) and len(domains) > 0:
            conditions = []
            for domain in domains:
                conditions.append(Site.emails.like(f'%{domain}%'))
            query = query.filter(db_session.query(Site).filter(*conditions).exists())

    # Filtre: domaines à exclure
    if 'domains_exclude' in filters and filters['domains_exclude']:
        domains = filters['domains_exclude']
        if isinstance(domains, list):
            for domain in domains:
                query = query.filter(~Site.emails.like(f'%{domain}%'))

    return query


def calculate_segment_count(segment_id, campaign_session, db_session):
    """Calculer le nombre de contacts dans un segment"""
    segment = campaign_session.query(ContactSegment).get(segment_id)
    if not segment:
        return 0

    query = build_segment_query(segment, db_session)
    return query.count()


def refresh_all_segments():
    """Rafraîchir tous les segments actifs"""
    logger.info("=" * 70)
    logger.info("MISE À JOUR NOCTURNE DES SEGMENTS")
    logger.info("=" * 70)
    logger.info("")

    campaign_session = get_campaign_session()
    db_session = get_session()

    try:
        # Récupérer tous les segments actifs
        segments = campaign_session.query(ContactSegment).filter_by(
            is_active=True
        ).all()

        logger.info(f"📊 {len(segments)} segment(s) actif(s) trouvé(s)")
        logger.info("")

        updated_count = 0
        total_contacts = 0

        for segment in segments:
            try:
                logger.info(f"🔄 Traitement: {segment.name} (ID: {segment.id})")

                old_count = segment.estimated_count or 0
                new_count = calculate_segment_count(segment.id, campaign_session, db_session)

                segment.estimated_count = new_count
                segment.last_count_update = datetime.utcnow()
                campaign_session.commit()

                diff = new_count - old_count
                diff_str = f"+{diff}" if diff > 0 else str(diff)

                logger.info(f"   ✅ Mis à jour: {old_count} → {new_count} contacts ({diff_str})")

                updated_count += 1
                total_contacts += new_count

            except Exception as e:
                logger.error(f"   ❌ Erreur pour segment {segment.id}: {e}")
                campaign_session.rollback()
                continue

        logger.info("")
        logger.info("=" * 70)
        logger.info(f"✅ TERMINÉ: {updated_count}/{len(segments)} segment(s) mis à jour")
        logger.info(f"📊 Total de contacts: {total_contacts}")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"❌ Erreur globale: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        campaign_session.close()
        db_session.close()


if __name__ == '__main__':
    success = refresh_all_segments()
    sys.exit(0 if success else 1)
