#!/usr/bin/env python3
"""
Routes API pour la gestion des segments de contacts
"""

from flask import request, jsonify, render_template
from campaign_database import get_campaign_session, ContactSegment
from database import get_session, Site
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def register_segment_routes(app):
    """Enregistrer toutes les routes des segments"""

    # ============================================================================
    # PAGES
    # ============================================================================

    @app.route('/segments')
    def segments_page():
        """Page de gestion des segments"""
        return render_template('segments.html')


    # ============================================================================
    # API - SEGMENTS CRUD
    # ============================================================================

    @app.route('/api/segments', methods=['GET'])
    def get_segments():
        """Lister tous les segments"""
        session = get_campaign_session()
        try:
            segments = session.query(ContactSegment).filter_by(
                is_active=True
            ).order_by(ContactSegment.created_at.desc()).all()

            return jsonify([s.to_dict() for s in segments])
        except Exception as e:
            logger.error(f"Erreur get_segments: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments/<int:segment_id>', methods=['GET'])
    def get_segment(segment_id):
        """Obtenir les détails d'un segment"""
        session = get_campaign_session()
        try:
            segment = session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            return jsonify(segment.to_dict())
        except Exception as e:
            logger.error(f"Erreur get_segment: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments', methods=['POST'])
    def create_segment():
        """Créer un nouveau segment"""
        session = get_campaign_session()
        try:
            data = request.get_json()

            # Validation
            if not data.get('name'):
                return jsonify({'error': 'Le nom est requis'}), 400

            if not data.get('filters'):
                return jsonify({'error': 'Les filtres sont requis'}), 400

            # Créer le segment
            segment = ContactSegment(
                name=data['name'],
                description=data.get('description'),
                filters=json.dumps(data['filters']),
                is_active=True
            )

            session.add(segment)
            session.commit()

            # Calculer le nombre de contacts
            count = calculate_segment_count(segment.id)
            segment.estimated_count = count
            segment.last_count_update = datetime.utcnow()
            session.commit()

            logger.info(f"Nouveau segment créé: {segment.name} (ID: {segment.id}, {count} contacts)")

            return jsonify(segment.to_dict()), 201

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur create_segment: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments/<int:segment_id>', methods=['PUT'])
    def update_segment(segment_id):
        """Mettre à jour un segment"""
        session = get_campaign_session()
        try:
            segment = session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            data = request.get_json()

            # Mode rafraîchissement simple du compteur
            if data.get('_refresh_count'):
                count = calculate_segment_count(segment_id)
                segment.estimated_count = count
                segment.last_count_update = datetime.utcnow()
                session.commit()
                logger.info(f"Segment {segment_id} compteur rafraîchi: {count} contacts")
                return jsonify(segment.to_dict())

            # Mettre à jour les champs
            if 'name' in data:
                segment.name = data['name']
            if 'description' in data:
                segment.description = data['description']
            if 'filters' in data:
                segment.filters = json.dumps(data['filters'])
                # Recalculer le nombre de contacts
                count = calculate_segment_count(segment_id)
                segment.estimated_count = count
                segment.last_count_update = datetime.utcnow()

            session.commit()

            logger.info(f"Segment {segment_id} mis à jour")

            return jsonify(segment.to_dict())

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur update_segment: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments/<int:segment_id>', methods=['DELETE'])
    def delete_segment(segment_id):
        """Supprimer un segment (soft delete)"""
        session = get_campaign_session()
        try:
            segment = session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            # Soft delete
            segment.is_active = False
            session.commit()

            logger.info(f"Segment {segment_id} désactivé")

            return jsonify({'success': True, 'message': 'Segment désactivé'})

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur delete_segment: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments/refresh-stale', methods=['POST'])
    def refresh_stale_segments():
        """Rafraîchir les segments périmés (> 24h)"""
        session = get_campaign_session()
        try:
            # Segments actifs non mis à jour depuis 24h
            stale_threshold = datetime.utcnow() - timedelta(hours=24)

            segments = session.query(ContactSegment).filter(
                ContactSegment.is_active == True,
                (ContactSegment.last_count_update < stale_threshold) |
                (ContactSegment.last_count_update.is_(None))
            ).all()

            updated = []
            for segment in segments:
                count = calculate_segment_count(segment.id)
                segment.estimated_count = count
                segment.last_count_update = datetime.utcnow()
                updated.append({
                    'id': segment.id,
                    'name': segment.name,
                    'count': count
                })

            session.commit()
            logger.info(f"Rafraîchi {len(updated)} segments périmés")

            return jsonify({
                'success': True,
                'updated_count': len(updated),
                'segments': updated
            })

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur refresh_stale_segments: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/segments/<int:segment_id>/count', methods=['GET'])
    def get_segment_count(segment_id):
        """Calculer le nombre de contacts dans un segment"""
        try:
            count = calculate_segment_count(segment_id)
            return jsonify({'segment_id': segment_id, 'count': count})
        except Exception as e:
            logger.error(f"Erreur get_segment_count: {e}")
            return jsonify({'error': str(e)}), 500


    @app.route('/api/segments/<int:segment_id>/preview', methods=['GET'])
    def preview_segment_contacts(segment_id):
        """Prévisualiser les contacts d'un segment (10 premiers)"""
        campaign_session = get_campaign_session()
        db_session = get_session()
        try:
            segment = campaign_session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            # Construire la requête
            query = build_segment_query(segment, db_session)

            # Limiter à 10 pour prévisualisation
            contacts = query.limit(10).all()

            # Formater les résultats
            results = []
            for contact in contacts:
                results.append({
                    'id': contact.id,
                    'domain': contact.domain,
                    'emails': contact.emails.split(';')[0] if contact.emails else '',
                    'email_validation_score': contact.email_validation_score or 0,
                    'email_deliverable': contact.email_deliverable or False
                })

            return jsonify({
                'segment_id': segment_id,
                'preview': results,
                'total_in_preview': len(results)
            })

        except Exception as e:
            logger.error(f"Erreur preview_segment_contacts: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            campaign_session.close()
            db_session.close()


    logger.info("Routes des segments enregistrées")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def build_segment_query(segment, db_session):
    """Construire une requête SQLAlchemy basée sur les filtres du segment"""
    filters = json.loads(segment.filters)

    # Requête de base
    query = db_session.query(Site).filter(
        Site.emails.isnot(None),
        Site.emails != '',
        Site.emails != 'NO EMAIL FOUND'
    )

    # Score de validation
    if 'email_validation_score_min' in filters:
        query = query.filter(Site.email_validation_score >= filters['email_validation_score_min'])

    if 'email_validation_score_max' in filters:
        query = query.filter(Site.email_validation_score <= filters['email_validation_score_max'])

    # Délivrabilité
    if 'email_deliverable' in filters:
        query = query.filter(Site.email_deliverable == filters['email_deliverable'])

    # Domaines inclus (chercher dans les emails, pas dans le domaine du site)
    if 'domains_include' in filters and filters['domains_include']:
        domains = filters['domains_include']
        if isinstance(domains, list) and len(domains) > 0:
            # Au moins un domaine doit correspondre
            from sqlalchemy import or_
            domain_conditions = [Site.emails.like(f'%{domain}%') for domain in domains]
            query = query.filter(or_(*domain_conditions))

    # Domaines exclus (exclure si l'email contient un de ces domaines)
    if 'domains_exclude' in filters and filters['domains_exclude']:
        domains = filters['domains_exclude']
        if isinstance(domains, list) and len(domains) > 0:
            for domain in domains:
                query = query.filter(~Site.emails.like(f'%{domain}%'))

    # SIRET
    if 'has_siret' in filters:
        if filters['has_siret']:
            query = query.filter(Site.siret.isnot(None), Site.siret != '')
        else:
            query = query.filter(Site.siret.is_(None) | (Site.siret == ''))

    return query


def calculate_segment_count(segment_id):
    """Calculer le nombre de contacts dans un segment"""
    campaign_session = get_campaign_session()
    db_session = get_session()

    try:
        segment = campaign_session.query(ContactSegment).get(segment_id)
        if not segment:
            return 0

        query = build_segment_query(segment, db_session)
        count = query.count()

        return count

    except Exception as e:
        logger.error(f"Erreur calculate_segment_count: {e}")
        return 0
    finally:
        campaign_session.close()
        db_session.close()
