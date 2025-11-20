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
        campaign_session = get_campaign_session()
        db_session = get_session()
        try:
            data = request.get_json()

            # Validation
            if not data.get('name'):
                return jsonify({'error': 'Le nom est requis'}), 400

            if not data.get('filters'):
                return jsonify({'error': 'Les filtres sont requis'}), 400

            filters = data['filters']

            # Si c'est un segment manuel, créer les sites pour les emails qui n'existent pas
            if 'manual_emails' in filters and filters['manual_emails']:
                manual_emails = filters['manual_emails']
                created_count = 0
                updated_count = 0

                for email in manual_emails:
                    # Vérifier si un site avec cet email existe déjà
                    existing_site = db_session.query(Site).filter(
                        Site.emails.like(f'%{email}%')
                    ).first()

                    if existing_site:
                        # L'email existe déjà, on ne fait rien
                        continue

                    # Extraire le domaine de l'email
                    domain = email.split('@')[1] if '@' in email else 'unknown.com'

                    # Vérifier si un site avec ce domaine existe déjà
                    existing_domain_site = db_session.query(Site).filter(
                        Site.domain == domain
                    ).first()

                    if existing_domain_site:
                        # Le domaine existe, ajouter l'email à la liste existante
                        if existing_domain_site.emails:
                            existing_emails = existing_domain_site.emails.split(';')
                            if email not in existing_emails:
                                existing_domain_site.emails += ';' + email
                                updated_count += 1
                        else:
                            existing_domain_site.emails = email
                            updated_count += 1
                    else:
                        # Créer un nouveau site avec cet email
                        new_site = Site(
                            domain=domain,
                            emails=email,
                            email_validation_score=100,  # Score max pour emails manuels
                            email_deliverable=True
                        )
                        db_session.add(new_site)
                        created_count += 1

                if created_count > 0 or updated_count > 0:
                    db_session.commit()
                    logger.info(f"Emails manuels: {created_count} site(s) créé(s), {updated_count} site(s) mis à jour")

            # Créer le segment
            segment = ContactSegment(
                name=data['name'],
                description=data.get('description'),
                filters=json.dumps(filters),
                is_active=True
            )

            campaign_session.add(segment)
            campaign_session.commit()

            # Calculer le nombre de contacts
            count = calculate_segment_count(segment.id)
            segment.estimated_count = count
            segment.last_count_update = datetime.utcnow()
            campaign_session.commit()

            logger.info(f"Nouveau segment créé: {segment.name} (ID: {segment.id}, {count} contacts)")

            return jsonify(segment.to_dict()), 201

        except Exception as e:
            campaign_session.rollback()
            db_session.rollback()
            logger.error(f"Erreur create_segment: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            campaign_session.close()
            db_session.close()


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

            filters = json.loads(segment.filters)
            results = []

            # Pour les segments manuels, afficher tous les emails individuels
            if 'manual_emails' in filters and filters['manual_emails']:
                manual_emails = filters['manual_emails']
                # Récupérer les sites qui contiennent ces emails
                query = build_segment_query(segment, db_session)
                contacts = query.limit(10).all()

                # Pour chaque site, extraire tous les emails qui correspondent à la liste manuelle
                for contact in contacts:
                    if contact.emails:
                        site_emails = contact.emails.split(';')
                        for email in site_emails:
                            email = email.strip()
                            # Vérifier si cet email est dans la liste manuelle
                            if email in manual_emails:
                                results.append({
                                    'id': contact.id,
                                    'domain': contact.domain,
                                    'emails': email,
                                    'email_validation_score': contact.email_validation_score or 0,
                                    'email_deliverable': contact.email_deliverable or False
                                })
            else:
                # Pour les segments automatiques, afficher les sites (comportement original)
                query = build_segment_query(segment, db_session)
                contacts = query.limit(10).all()

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


    # ============================================================================
    # API - HISTORIQUE
    # ============================================================================

    @app.route('/api/segments/<int:segment_id>/campaigns', methods=['GET'])
    def get_segment_campaigns(segment_id):
        """Obtenir l'historique des campagnes envoyées à ce segment"""
        campaign_session = get_campaign_session()
        try:
            segment = campaign_session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            # Récupérer toutes les campagnes utilisant ce segment
            from campaign_database import Campaign
            campaigns = campaign_session.query(Campaign).filter(
                Campaign.segment_id == segment_id
            ).order_by(Campaign.created_at.desc()).all()

            results = []
            for campaign in campaigns:
                results.append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status.value if campaign.status else None,
                    'subject': campaign.subject,
                    'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                    'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
                    'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None,
                    'total_recipients': campaign.total_recipients,
                    'emails_sent': campaign.emails_sent,
                    'emails_delivered': campaign.emails_delivered,
                    'emails_opened': campaign.emails_opened,
                    'emails_clicked': campaign.emails_clicked,
                    'open_rate': round((campaign.emails_opened / campaign.emails_sent * 100) if campaign.emails_sent > 0 else 0, 2),
                    'click_rate': round((campaign.emails_clicked / campaign.emails_sent * 100) if campaign.emails_sent > 0 else 0, 2),
                })

            return jsonify({
                'segment_id': segment_id,
                'segment_name': segment.name,
                'total_campaigns': len(results),
                'campaigns': results
            })

        except Exception as e:
            logger.error(f"Erreur get_segment_campaigns: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            campaign_session.close()


    @app.route('/api/segments/<int:segment_id>/emails/history', methods=['GET'])
    def get_segment_emails_history(segment_id):
        """Obtenir l'historique détaillé des emails envoyés pour ce segment"""
        campaign_session = get_campaign_session()
        try:
            segment = campaign_session.query(ContactSegment).get(segment_id)
            if not segment:
                return jsonify({'error': 'Segment non trouvé'}), 404

            # Récupérer tous les emails envoyés via les campagnes de ce segment
            from campaign_database import Campaign, CampaignEmail
            emails = campaign_session.query(CampaignEmail, Campaign).join(
                Campaign, CampaignEmail.campaign_id == Campaign.id
            ).filter(
                Campaign.segment_id == segment_id
            ).order_by(CampaignEmail.sent_at.desc()).limit(1000).all()

            results = []
            for email, campaign in emails:
                results.append({
                    'email_id': email.id,
                    'to_email': email.to_email,
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'campaign_subject': campaign.subject,
                    'status': email.status.value if email.status else None,
                    'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                    'delivered_at': email.delivered_at.isoformat() if email.delivered_at else None,
                    'opened_at': email.opened_at.isoformat() if email.opened_at else None,
                    'clicked_at': email.clicked_at.isoformat() if email.clicked_at else None,
                    'open_count': email.open_count,
                    'click_count': email.click_count,
                })

            return jsonify({
                'segment_id': segment_id,
                'segment_name': segment.name,
                'total_emails': len(results),
                'emails': results
            })

        except Exception as e:
            logger.error(f"Erreur get_segment_emails_history: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            campaign_session.close()


    @app.route('/api/emails/<email_address>/history', methods=['GET'])
    def get_email_history(email_address):
        """Obtenir tout l'historique d'envoi pour un email spécifique"""
        campaign_session = get_campaign_session()
        try:
            # Récupérer tous les emails envoyés à cette adresse
            from campaign_database import CampaignEmail, Campaign
            emails = campaign_session.query(CampaignEmail, Campaign).outerjoin(
                Campaign, CampaignEmail.campaign_id == Campaign.id
            ).filter(
                CampaignEmail.to_email == email_address
            ).order_by(CampaignEmail.sent_at.desc()).all()

            results = []
            for email, campaign in emails:
                result = {
                    'email_id': email.id,
                    'to_email': email.to_email,
                    'status': email.status.value if email.status else None,
                    'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                    'delivered_at': email.delivered_at.isoformat() if email.delivered_at else None,
                    'opened_at': email.opened_at.isoformat() if email.opened_at else None,
                    'clicked_at': email.clicked_at.isoformat() if email.clicked_at else None,
                    'open_count': email.open_count,
                    'click_count': email.click_count,
                }

                # Ajouter les infos de campagne si disponibles
                if campaign:
                    result.update({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'campaign_subject': campaign.subject,
                        'segment_id': campaign.segment_id,
                    })
                else:
                    # Email envoyé via un scénario
                    result.update({
                        'campaign_id': None,
                        'campaign_name': 'Scénario',
                        'campaign_subject': 'Email automatisé',
                        'segment_id': None,
                    })

                results.append(result)

            return jsonify({
                'email': email_address,
                'total_emails_received': len(results),
                'history': results
            })

        except Exception as e:
            logger.error(f"Erreur get_email_history: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            campaign_session.close()


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

    # Liste manuelle d'emails
    if 'manual_emails' in filters and filters['manual_emails']:
        from sqlalchemy import or_
        manual_emails = filters['manual_emails']
        if isinstance(manual_emails, list) and len(manual_emails) > 0:
            # Filtrer pour inclure uniquement les sites dont l'email correspond à la liste
            email_conditions = []
            for email in manual_emails:
                email_conditions.append(Site.emails.like(f'%{email}%'))
            query = query.filter(or_(*email_conditions))
            # Pour les segments manuels, on retourne directement sans appliquer d'autres filtres
            return query

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

        filters = json.loads(segment.filters)

        # Pour les segments manuels, compter les emails individuels
        if 'manual_emails' in filters and filters['manual_emails']:
            manual_emails = filters['manual_emails']
            return len(manual_emails)

        # Pour les autres segments, compter les sites
        query = build_segment_query(segment, db_session)
        count = query.count()

        return count

    except Exception as e:
        logger.error(f"Erreur calculate_segment_count: {e}")
        return 0
    finally:
        campaign_session.close()
        db_session.close()
