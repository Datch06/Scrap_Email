#!/usr/bin/env python3
"""
Application Flask pour l'interface de gestion du scraping
"""

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from flask_cors import CORS
from sqlalchemy import func, case
from database import init_db, get_session, Site, ScrapingJob, SiteStatus
from campaign_database import get_campaign_session, Unsubscribe
from datetime import datetime, timedelta
import json
import csv
import logging
from io import StringIO, BytesIO
from scenario_routes import register_scenario_routes

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialiser la base de données au démarrage
init_db()

# Enregistrer les routes des scénarios
register_scenario_routes(app)


# ============================================================================
# ROUTES - PAGES HTML
# ============================================================================

@app.route('/')
def index():
    """Page d'accueil avec dashboard"""
    return render_template('index.html')

@app.route('/sites')
def sites_page():
    """Page liste des sites"""
    return render_template('sites.html')

@app.route('/jobs')
def jobs_page():
    """Page des jobs de scraping"""
    return render_template('jobs.html')

@app.route('/validation')
def validation_page():
    """Page de validation des emails"""
    return render_template('validation.html')

@app.route('/campaigns')
def campaigns_page():
    """Page de gestion des campagnes"""
    return render_template('campaigns.html')


# ============================================================================
# API - STATISTIQUES
# ============================================================================

@app.route('/api/stats')
def get_stats():
    """Obtenir les statistiques globales"""
    session = get_session()

    try:
        # Total de sites
        total_sites = session.query(Site).count()

        # Sites par statut
        status_counts = {}
        for status in SiteStatus:
            count = session.query(Site).filter(Site.status == status).count()
            status_counts[status.value] = count

        # Sites avec emails
        sites_with_email = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Sites avec SIRET
        sites_with_siret = session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ'
        ).count()

        # Sites avec dirigeants
        sites_with_leaders = session.query(Site).filter(
            Site.leaders.isnot(None),
            Site.leaders != '',
            Site.leaders != 'NON TROUVÉ'
        ).count()

        # Sites complets (email + SIRET + dirigeants)
        sites_complete = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND',
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ',
            Site.leaders.isnot(None),
            Site.leaders != '',
            Site.leaders != 'NON TROUVÉ'
        ).count()

        # Sites avec erreurs
        sites_with_errors = session.query(Site).filter(Site.status == SiteStatus.ERROR).count()

        # Activité récente (dernières 24h)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_activity = session.query(Site).filter(Site.created_at >= yesterday).count()

        # Jobs en cours
        running_jobs = session.query(ScrapingJob).filter(ScrapingJob.status == 'running').count()

        # Emails par source
        emails_from_scraping = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND',
            Site.email_source == 'scraping'
        ).count()

        emails_from_siret = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND',
            Site.email_source == 'siret'
        ).count()

        # Stats de validation d'emails
        emails_validated = session.query(Site).filter(Site.email_validated == True).count()
        emails_valid = session.query(Site).filter(Site.email_validation_status == 'valid').count()
        emails_invalid = session.query(Site).filter(Site.email_validation_status == 'invalid').count()
        emails_risky = session.query(Site).filter(Site.email_validation_status == 'risky').count()

        # Stats CMS
        sites_with_cms = session.query(Site).filter(Site.cms.isnot(None)).count()
        cms_counts = {}
        cms_results = session.query(Site.cms, func.count(Site.id)).filter(Site.cms.isnot(None)).group_by(Site.cms).all()
        for cms, count in cms_results:
            cms_counts[cms] = count
        emails_deliverable = session.query(Site).filter(Site.email_deliverable == True).count()

        # Stats Blacklist
        sites_blacklisted = session.query(Site).filter(Site.blacklisted == True).count()

        return jsonify({
            'total_sites': total_sites,
            'status_counts': status_counts,
            'sites_with_email': sites_with_email,
            'emails_from_scraping': emails_from_scraping,
            'emails_from_siret': emails_from_siret,
            'sites_with_siret': sites_with_siret,
            'sites_with_leaders': sites_with_leaders,
            'sites_complete': sites_complete,
            'sites_with_errors': sites_with_errors,
            'recent_activity': recent_activity,
            'running_jobs': running_jobs,
            'email_rate': round((sites_with_email / total_sites * 100) if total_sites > 0 else 0, 1),
            'siret_rate': round((sites_with_siret / total_sites * 100) if total_sites > 0 else 0, 1),
            'leaders_rate': round((sites_with_leaders / total_sites * 100) if total_sites > 0 else 0, 1),
            'completion_rate': round((sites_complete / total_sites * 100) if total_sites > 0 else 0, 1),
            # Stats validation
            'emails_validated': emails_validated,
            'emails_valid': emails_valid,
            'emails_invalid': emails_invalid,
            'emails_risky': emails_risky,
            'emails_deliverable': emails_deliverable,
            'validation_rate': round((emails_validated / sites_with_email * 100) if sites_with_email > 0 else 0, 1),
            'deliverable_rate': round((emails_deliverable / emails_validated * 100) if emails_validated > 0 else 0, 1),
            # Stats CMS
            'sites_with_cms': sites_with_cms,
            'cms_counts': cms_counts,
            'cms_rate': round((sites_with_cms / total_sites * 100) if total_sites > 0 else 0, 1),
            # Stats Blacklist
            'sites_blacklisted': sites_blacklisted,
            'blacklist_rate': round((sites_blacklisted / total_sites * 100) if total_sites > 0 else 0, 1),
        })

    finally:
        session.close()


@app.route('/api/scraping-live')
def get_scraping_live():
    """Obtenir les statistiques du scraping de backlinks en temps réel"""
    session = get_session()

    try:
        # Stats globales LinkAvista
        total_sellers = session.query(Site).filter_by(is_linkavista_seller=True).count()
        total_buyers = session.query(Site).filter(Site.purchased_from.isnot(None)).count()
        buyers_with_email = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Activité récente (dernière heure)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_buyers = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.created_at >= one_hour_ago
        ).count()

        recent_emails = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND',
            Site.email_found_at >= one_hour_ago
        ).count()

        # Top 10 derniers sites vendeurs traités
        recent_sellers = session.query(Site).filter(
            Site.is_linkavista_seller == True
        ).order_by(Site.updated_at.desc()).limit(10).all()

        sellers_data = []
        for seller in recent_sellers:
            # Compter les acheteurs de ce vendeur
            buyers_count = session.query(Site).filter_by(purchased_from=seller.domain).count()
            sellers_data.append({
                'domain': seller.domain,
                'buyers_found': buyers_count,
                'updated_at': seller.updated_at.isoformat() if seller.updated_at else None
            })

        # Derniers acheteurs avec email trouvés
        latest_buyers = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != 'NO EMAIL FOUND'
        ).order_by(Site.email_found_at.desc()).limit(10).all()

        buyers_data = []
        for buyer in latest_buyers:
            buyers_data.append({
                'domain': buyer.domain,
                'email': buyer.emails[:60] + '...' if buyer.emails and len(buyer.emails) > 60 else buyer.emails,
                'purchased_from': buyer.purchased_from,
                'found_at': buyer.email_found_at.isoformat() if buyer.email_found_at else None
            })

        return jsonify({
            'summary': {
                'total_sellers': total_sellers,
                'total_buyers': total_buyers,
                'buyers_with_email': buyers_with_email,
                'conversion_rate': round((buyers_with_email / total_buyers * 100) if total_buyers > 0 else 0, 1)
            },
            'last_hour': {
                'new_buyers': recent_buyers,
                'new_emails': recent_emails
            },
            'recent_sellers': sellers_data,
            'latest_buyers': buyers_data
        })

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de scraping: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        session.close()


@app.route('/api/scraping-state')
def get_scraping_state():
    """Obtenir l'état en temps réel des crawlers actifs (pages en cours de crawling)"""
    from pathlib import Path

    state_file = Path('/var/www/Scrap_Email/scraping_state.json')

    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            return jsonify(state)
        else:
            return jsonify({
                'sellers_in_progress': [],
                'last_update': None
            })

    except Exception as e:
        logger.error(f"Erreur lors de la lecture du state de scraping: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API - SITES
# ============================================================================

@app.route('/api/sites')
def get_sites():
    """Obtenir la liste des sites avec pagination et filtres"""
    session = get_session()

    try:
        # Paramètres de pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        # Filtres
        status_filter = request.args.get('status')
        search_query = request.args.get('search', '').strip()
        has_email = request.args.get('has_email')
        has_siret = request.args.get('has_siret')
        has_leaders = request.args.get('has_leaders')
        include_blacklisted = request.args.get('include_blacklisted', 'false').lower() == 'true'

        # Construire la requête
        query = session.query(Site)

        # Exclure les sites blacklistés par défaut
        if not include_blacklisted:
            query = query.filter(Site.blacklisted == False)

        # Filtre par statut
        if status_filter:
            query = query.filter(Site.status == SiteStatus(status_filter))

        # Recherche par domaine
        if search_query:
            query = query.filter(Site.domain.like(f'%{search_query}%'))

        # Filtre email
        if has_email == 'true':
            query = query.filter(
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != 'NO EMAIL FOUND'
            )
        elif has_email == 'false':
            query = query.filter(
                (Site.emails.is_(None)) | (Site.emails == '') | (Site.emails == 'NO EMAIL FOUND')
            )

        # Filtre SIRET
        if has_siret == 'true':
            query = query.filter(
                Site.siret.isnot(None),
                Site.siret != '',
                Site.siret != 'NON TROUVÉ'
            )
        elif has_siret == 'false':
            query = query.filter(
                (Site.siret.is_(None)) | (Site.siret == '') | (Site.siret == 'NON TROUVÉ')
            )

        # Filtre dirigeants
        if has_leaders == 'true':
            query = query.filter(
                Site.leaders.isnot(None),
                Site.leaders != '',
                Site.leaders != 'NON TROUVÉ'
            )
        elif has_leaders == 'false':
            query = query.filter(
                (Site.leaders.is_(None)) | (Site.leaders == '') | (Site.leaders == 'NON TROUVÉ')
            )

        # Total
        total = query.count()

        # Tri par date de mise à jour (plus récents en premier)
        query = query.order_by(Site.updated_at.desc())

        # Pagination
        offset = (page - 1) * per_page
        sites = query.limit(per_page).offset(offset).all()

        return jsonify({
            'sites': [site.to_dict() for site in sites],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>')
def get_site(site_id):
    """Obtenir les détails d'un site"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        return jsonify(site.to_dict())

    finally:
        session.close()


@app.route('/api/sites', methods=['POST'])
def create_site():
    """Créer un nouveau site"""
    session = get_session()

    try:
        data = request.json
        domain = data.get('domain', '').strip()

        if not domain:
            return jsonify({'error': 'Domain is required'}), 400

        # Vérifier si le site existe déjà
        existing = session.query(Site).filter(Site.domain == domain).first()
        if existing:
            return jsonify({'error': 'Site already exists', 'site': existing.to_dict()}), 409

        # Créer le site
        site = Site(
            domain=domain,
            source_url=data.get('source_url'),
            status=SiteStatus.DISCOVERED
        )
        session.add(site)
        session.commit()

        return jsonify(site.to_dict()), 201

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>', methods=['PUT'])
def update_site(site_id):
    """Mettre à jour un site"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        data = request.json

        # Mettre à jour les champs
        if 'emails' in data:
            site.emails = data['emails']
            site.email_source = data.get('email_source', 'scraping')
            site.email_checked = True
            if data['emails'] and data['emails'] != 'NO EMAIL FOUND':
                site.email_found_at = datetime.utcnow()

        if 'siret' in data:
            site.siret = data['siret']
            site.siret_type = data.get('siret_type')
            site.siret_checked = True
            if data['siret'] and data['siret'] != 'NON TROUVÉ':
                site.siret_found_at = datetime.utcnow()
                # Extraire le SIREN (9 premiers chiffres)
                if len(data['siret']) >= 9:
                    site.siren = data['siret'][:9]

        if 'leaders' in data:
            site.leaders = data['leaders']
            site.leaders_checked = True
            if data['leaders'] and data['leaders'] != 'NON TROUVÉ':
                site.leaders_found_at = datetime.utcnow()

        if 'status' in data:
            site.status = SiteStatus(data['status'])

        if 'last_error' in data:
            site.last_error = data['last_error']

        site.updated_at = datetime.utcnow()
        session.commit()

        return jsonify(site.to_dict())

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>', methods=['DELETE'])
def delete_site(site_id):
    """Supprimer un site"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        session.delete(site)
        session.commit()

        return jsonify({'success': True})

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>/toggle-active', methods=['POST'])
def toggle_site_active(site_id):
    """Activer ou désactiver un site"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        # Inverser le statut is_active
        site.is_active = not getattr(site, 'is_active', True)
        site.updated_at = datetime.utcnow()
        session.commit()

        return jsonify({
            'success': True,
            'is_active': site.is_active,
            'site': site.to_dict()
        })

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>/blacklist', methods=['POST'])
def blacklist_site(site_id):
    """Blacklister un site"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        data = request.json or {}
        reason = data.get('reason', '')

        site.blacklisted = True
        site.blacklist_reason = reason
        site.blacklisted_at = datetime.utcnow()
        session.commit()

        return jsonify({
            'success': True,
            'site': site.to_dict()
        })

    finally:
        session.close()


@app.route('/api/sites/<int:site_id>/unblacklist', methods=['POST'])
def unblacklist_site(site_id):
    """Retirer un site de la blacklist"""
    session = get_session()

    try:
        site = session.query(Site).filter(Site.id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        site.blacklisted = False
        site.blacklist_reason = None
        site.blacklisted_at = None
        session.commit()

        return jsonify({
            'success': True,
            'site': site.to_dict()
        })

    finally:
        session.close()


# ============================================================================
# API - JOBS
# ============================================================================

@app.route('/api/jobs')
def get_jobs():
    """Obtenir la liste des jobs"""
    session = get_session()

    try:
        jobs = session.query(ScrapingJob).order_by(ScrapingJob.created_at.desc()).limit(100).all()
        return jsonify([job.to_dict() for job in jobs])

    finally:
        session.close()


@app.route('/api/jobs', methods=['POST'])
def create_job():
    """Créer un nouveau job"""
    session = get_session()

    try:
        data = request.json
        job_type = data.get('job_type')

        if not job_type:
            return jsonify({'error': 'job_type is required'}), 400

        job = ScrapingJob(
            job_type=job_type,
            status='pending',
            config=json.dumps(data.get('config', {}))
        )
        session.add(job)
        session.commit()

        return jsonify(job.to_dict()), 201

    finally:
        session.close()


@app.route('/api/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    """Mettre à jour un job"""
    session = get_session()

    try:
        job = session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        data = request.json

        if 'status' in data:
            job.status = data['status']
            if data['status'] == 'running' and not job.start_time:
                job.start_time = datetime.utcnow()
            elif data['status'] in ['completed', 'failed'] and not job.end_time:
                job.end_time = datetime.utcnow()

        if 'processed_sites' in data:
            job.processed_sites = data['processed_sites']
        if 'success_count' in data:
            job.success_count = data['success_count']
        if 'error_count' in data:
            job.error_count = data['error_count']

        session.commit()
        return jsonify(job.to_dict())

    finally:
        session.close()


# ============================================================================
# API - EXPORT
# ============================================================================

@app.route('/api/export/csv')
def export_csv():
    """Exporter les sites en CSV"""
    session = get_session()

    try:
        sites = session.query(Site).all()

        # Créer le CSV
        output = StringIO()
        writer = csv.writer(output)

        # En-tête
        writer.writerow([
            'ID', 'Domaine', 'Statut', 'Emails', 'SIRET', 'SIREN',
            'Dirigeants', 'Source', 'Créé le', 'Mis à jour le'
        ])

        # Données
        for site in sites:
            writer.writerow([
                site.id,
                site.domain,
                site.status.value if site.status else '',
                site.emails or '',
                site.siret or '',
                site.siren or '',
                site.leaders or '',
                site.source_url or '',
                site.created_at.strftime('%Y-%m-%d %H:%M:%S') if site.created_at else '',
                site.updated_at.strftime('%Y-%m-%d %H:%M:%S') if site.updated_at else '',
            ])

        # Retourner le fichier
        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'sites_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

    finally:
        session.close()


# ============================================================================
# API - VALIDATION D'EMAILS
# ============================================================================

@app.route('/api/validation/start', methods=['POST'])
def start_email_validation():
    """Démarrer la validation des emails"""
    import subprocess
    import threading

    data = request.json or {}
    limit = data.get('limit', 100)
    only_new = data.get('only_new', True)

    # Commande à exécuter
    cmd = ['python3', 'validate_emails.py', '--batch-size', '50', '--limit', str(limit)]
    if only_new:
        cmd.append('--only-new')

    # Lancer en arrière-plan
    def run_validation():
        try:
            subprocess.run(cmd, cwd='/var/www/Scrap_Email')
        except Exception as e:
            print(f"Erreur validation: {e}")

    thread = threading.Thread(target=run_validation)
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Validation lancée pour {limit} emails',
        'params': {'limit': limit, 'only_new': only_new}
    })


@app.route('/api/validation/stats')
def get_validation_stats():
    """Statistiques détaillées de validation"""
    session = get_session()

    try:
        # Total avec emails
        total_with_email = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Stats validation
        total_validated = session.query(Site).filter(Site.email_validated == True).count()
        valid_count = session.query(Site).filter(Site.email_validation_status == 'valid').count()
        invalid_count = session.query(Site).filter(Site.email_validation_status == 'invalid').count()
        risky_count = session.query(Site).filter(Site.email_validation_status == 'risky').count()
        deliverable_count = session.query(Site).filter(Site.email_deliverable == True).count()

        # Score moyen
        avg_score_result = session.query(func.avg(Site.email_validation_score)).filter(
            Site.email_validated == True
        ).scalar()
        avg_score = round(avg_score_result, 1) if avg_score_result else 0

        return jsonify({
            'total_emails': total_with_email,
            'total_validated': total_validated,
            'pending_validation': total_with_email - total_validated,
            'valid': valid_count,
            'invalid': invalid_count,
            'risky': risky_count,
            'deliverable': deliverable_count,
            'avg_score': avg_score,
            'validation_rate': round((total_validated / total_with_email * 100) if total_with_email > 0 else 0, 1),
            'valid_rate': round((valid_count / total_validated * 100) if total_validated > 0 else 0, 1),
            'deliverable_rate': round((deliverable_count / total_validated * 100) if total_validated > 0 else 0, 1),
        })

    finally:
        session.close()


# ============================================================================
# API - CAMPAGNES D'EMAILS
# ============================================================================

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    """Lister toutes les campagnes"""
    from campaign_manager import CampaignManager
    try:
        manager = CampaignManager()
        campaigns = manager.list_campaigns()
        return jsonify(campaigns)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    """Créer une nouvelle campagne"""
    from campaign_manager import CampaignManager
    try:
        data = request.json
        manager = CampaignManager()

        campaign = manager.create_campaign(
            name=data.get('name'),
            subject=data.get('subject'),
            html_body=data.get('html_body'),
            description=data.get('description'),
            text_body=data.get('text_body'),
            min_validation_score=data.get('min_validation_score', 80),
            only_deliverable=data.get('only_deliverable', True),
            max_emails_per_day=data.get('max_emails_per_day', 200)
        )

        return jsonify(campaign.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/campaigns/<int:campaign_id>', methods=['GET'])
def get_campaign(campaign_id):
    """Obtenir les détails d'une campagne"""
    from campaign_manager import CampaignManager
    try:
        manager = CampaignManager()
        stats = manager.get_campaign_stats(campaign_id)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/campaigns/<int:campaign_id>/prepare', methods=['POST'])
def prepare_campaign(campaign_id):
    """Préparer une campagne"""
    from campaign_manager import CampaignManager
    try:
        manager = CampaignManager()
        result = manager.prepare_campaign(campaign_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/campaigns/<int:campaign_id>/send', methods=['POST'])
def send_campaign(campaign_id):
    """Envoyer une campagne"""
    import threading
    from campaign_manager import CampaignManager

    data = request.json or {}
    limit = data.get('limit', None)

    def run_campaign_async():
        try:
            manager = CampaignManager()
            manager.run_campaign(campaign_id, limit=limit)
        except Exception as e:
            logger.error(f"Erreur campagne: {e}")

    # Lancer en arrière-plan
    thread = threading.Thread(target=run_campaign_async)
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Campagne {campaign_id} lancée en arrière-plan',
        'limit': limit
    })


@app.route('/api/campaigns/<int:campaign_id>/test', methods=['POST'])
def send_test_campaign(campaign_id):
    """Envoyer des emails de test pour une campagne"""
    from campaign_manager import CampaignManager
    try:
        data = request.json or {}
        test_emails = data.get('test_emails', [])
        test_domain = data.get('test_domain', 'test.example.com')

        if not test_emails:
            return jsonify({'error': 'Aucune adresse email de test fournie'}), 400

        if not isinstance(test_emails, list):
            test_emails = [test_emails]

        manager = CampaignManager()
        results = manager.send_test_email(campaign_id, test_emails, test_domain)

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Lister les templates d'emails"""
    from campaign_database import get_campaign_session, EmailTemplate
    session = get_campaign_session()
    try:
        templates = session.query(EmailTemplate).filter(
            EmailTemplate.is_active == True
        ).all()
        return jsonify([t.to_dict() for t in templates])
    finally:
        session.close()


@app.route('/api/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """Obtenir un template"""
    from campaign_database import get_campaign_session, EmailTemplate
    session = get_campaign_session()
    try:
        template = session.query(EmailTemplate).get(template_id)
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        return jsonify(template.to_dict())
    finally:
        session.close()


@app.route('/api/templates', methods=['POST'])
def create_template():
    """Créer un nouveau template d'email"""
    from campaign_database import get_campaign_session, EmailTemplate
    import json as json_lib

    session = get_campaign_session()
    try:
        data = request.get_json()

        # Validation
        if not data.get('name'):
            return jsonify({'error': 'Le nom du template est requis'}), 400
        if not data.get('subject'):
            return jsonify({'error': 'Le sujet est requis'}), 400
        if not data.get('html_body'):
            return jsonify({'error': 'Le corps HTML est requis'}), 400

        # Créer le template
        template = EmailTemplate(
            name=data['name'],
            description=data.get('description'),
            category=data.get('category', 'prospection'),
            subject=data['subject'],
            html_body=data['html_body'],
            text_body=data.get('text_body'),
            available_variables=json_lib.dumps(data.get('available_variables', ['domain', 'email', 'siret', 'leaders', 'unsubscribe_link'])),
            is_active=True
        )

        session.add(template)
        session.commit()

        logger.info(f"Nouveau template créé: {template.name} (ID: {template.id})")

        return jsonify(template.to_dict()), 201

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur création template: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/templates/<int:template_id>/test', methods=['POST'])
def send_test_template(template_id):
    """Envoyer des emails de test pour un template"""
    from campaign_database import get_campaign_session, EmailTemplate
    from ses_manager import SESManager
    import re

    session = get_campaign_session()
    try:
        data = request.json or {}
        test_emails = data.get('test_emails', [])
        test_domain = data.get('test_domain', 'test.example.com')

        if not test_emails:
            return jsonify({'error': 'Aucune adresse email de test fournie'}), 400

        if not isinstance(test_emails, list):
            test_emails = [test_emails]

        # Récupérer le template
        template = session.query(EmailTemplate).get(template_id)
        if not template:
            return jsonify({'error': 'Template non trouvé'}), 404

        # Préparer les variables de test
        test_variables = {
            'domain': test_domain,
            'email': 'contact@' + test_domain,
            'siret': '12345678901234',
            'leaders': 'Jean Dupont (Gérant)',
            'unsubscribe_link': f'https://admin.perfect-cocon-seo.fr/unsubscribe?email=test@example.com&token=TEST'
        }

        # Remplacer les variables dans le sujet et le corps
        subject = template.subject
        html_body = template.html_body

        for var, value in test_variables.items():
            subject = subject.replace('{{' + var + '}}', value)
            html_body = html_body.replace('{{' + var + '}}', value)

        # Préfixer le sujet avec [TEST]
        subject = f"[TEST] {subject}"

        # Envoyer les emails
        ses_manager = SESManager()
        sent = []
        failed = []

        for email in test_emails:
            try:
                result = ses_manager.send_email(
                    to_email=email,
                    subject=subject,
                    html_body=html_body
                )
                if result:
                    sent.append(email)
                else:
                    failed.append({'email': email, 'error': 'Erreur d\'envoi'})
            except Exception as e:
                failed.append({'email': email, 'error': str(e)})

        return jsonify({
            'template_name': template.name,
            'total_sent': len(sent),
            'total_failed': len(failed),
            'sent': sent,
            'failed': failed
        })

    except Exception as e:
        logger.error(f"Erreur test template: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/campaigns/<int:campaign_id>/pause', methods=['POST'])
def pause_campaign(campaign_id):
    """Mettre en pause une campagne en cours d'exécution"""
    from campaign_database import get_campaign_session, Campaign, CampaignStatus

    session = get_campaign_session()
    try:
        campaign = session.query(Campaign).get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campagne non trouvée'}), 404

        # Vérifier que la campagne est en cours
        if campaign.status != CampaignStatus.RUNNING:
            return jsonify({'error': f'La campagne doit être en cours (status actuel: {campaign.status.value})'}), 400

        # Mettre en pause
        campaign.status = CampaignStatus.PAUSED
        session.commit()

        logger.info(f"⏸️  Campagne '{campaign.name}' (ID: {campaign_id}) mise en pause")

        return jsonify({
            'success': True,
            'campaign_id': campaign_id,
            'status': campaign.status.value,
            'message': f"Campagne '{campaign.name}' mise en pause"
        })

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur lors de la mise en pause de la campagne {campaign_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/campaigns/<int:campaign_id>/resume', methods=['POST'])
def resume_campaign(campaign_id):
    """Reprendre une campagne en pause"""
    from campaign_database import get_campaign_session, Campaign, CampaignStatus
    from campaign_manager import CampaignManager
    import threading

    session = get_campaign_session()
    try:
        campaign = session.query(Campaign).get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campagne non trouvée'}), 404

        # Vérifier que la campagne est en pause
        if campaign.status != CampaignStatus.PAUSED:
            return jsonify({'error': f'La campagne doit être en pause (status actuel: {campaign.status.value})'}), 400

        # Reprendre (remettre en RUNNING)
        campaign.status = CampaignStatus.RUNNING
        session.commit()

        logger.info(f"▶️  Campagne '{campaign.name}' (ID: {campaign_id}) reprise")

        # Relancer l'envoi dans un thread séparé
        campaign_manager = CampaignManager()
        thread = threading.Thread(
            target=campaign_manager.run_campaign,
            args=(campaign_id,),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'campaign_id': campaign_id,
            'status': campaign.status.value,
            'message': f"Campagne '{campaign.name}' reprise"
        })

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur lors de la reprise de la campagne {campaign_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ============================================================================
# ROUTES - UNSUBSCRIBE
# ============================================================================

@app.route('/unsubscribe')
def unsubscribe():
    """Page de désinscription des emails"""
    email = request.args.get('email', '').strip()
    reason = request.args.get('reason', '').strip()
    campaign_id = request.args.get('campaign_id', None)

    if not email:
        return render_template('unsubscribe.html',
                             error="Aucune adresse email fournie",
                             success=False)

    # Ajouter l'email à la liste des désinscriptions
    campaign_session = get_campaign_session()

    try:
        # Vérifier si déjà désinscrit
        existing = campaign_session.query(Unsubscribe).filter(
            Unsubscribe.email == email
        ).first()

        if existing:
            return render_template('unsubscribe.html',
                                 email=email,
                                 success=True,
                                 already_unsubscribed=True)

        # Ajouter à la liste
        unsubscribe_record = Unsubscribe(
            email=email,
            reason=reason if reason else None,
            campaign_id=int(campaign_id) if campaign_id else None,
            unsubscribed_at=datetime.utcnow()
        )

        campaign_session.add(unsubscribe_record)
        campaign_session.commit()

        return render_template('unsubscribe.html',
                             email=email,
                             success=True,
                             already_unsubscribed=False)

    except Exception as e:
        campaign_session.rollback()
        return render_template('unsubscribe.html',
                             error=f"Erreur lors de la désinscription: {str(e)}",
                             success=False)
    finally:
        campaign_session.close()


# ============================================================================
# ROUTES - AWS SES WEBHOOKS (SNS)
# ============================================================================

@app.route('/api/ses/webhook', methods=['POST'])
def ses_webhook():
    """
    Webhook pour recevoir les notifications AWS SES via SNS
    Gère: Bounces, Complaints, Deliveries, Opens, Clicks
    """
    import json
    from datetime import datetime

    try:
        # Récupérer le corps de la requête
        data = request.get_json(force=True)

        # Vérifier le type de message SNS
        message_type = request.headers.get('x-amz-sns-message-type')

        # Confirmation d'abonnement SNS
        if message_type == 'SubscriptionConfirmation':
            subscribe_url = data.get('SubscribeURL')
            logger.info(f"📨 SNS Subscription confirmation: {subscribe_url}")

            # Confirmer automatiquement l'abonnement
            try:
                import requests
                response = requests.get(subscribe_url, timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Abonnement SNS confirmé automatiquement")
                    return jsonify({'status': 'subscription_confirmed'}), 200
                else:
                    logger.error(f"❌ Erreur confirmation SNS: HTTP {response.status_code}")
                    return jsonify({'status': 'confirmation_failed', 'url': subscribe_url}), 500
            except Exception as e:
                logger.error(f"❌ Exception lors de la confirmation SNS: {e}")
                return jsonify({'status': 'confirmation_error', 'url': subscribe_url, 'error': str(e)}), 500

        # Notification SNS
        if message_type == 'Notification':
            # Parser le message
            message = json.loads(data.get('Message', '{}'))
            notification_type = message.get('notificationType')

            campaign_session = get_campaign_session()

            try:
                if notification_type == 'Bounce':
                    handle_bounce(message, campaign_session)
                elif notification_type == 'Complaint':
                    handle_complaint(message, campaign_session)
                elif notification_type == 'Delivery':
                    handle_delivery(message, campaign_session)
                elif notification_type == 'Open':
                    handle_open(message, campaign_session)
                elif notification_type == 'Click':
                    handle_click(message, campaign_session)

                campaign_session.commit()
                return jsonify({'status': 'success', 'type': notification_type}), 200

            except Exception as e:
                campaign_session.rollback()
                logger.error(f"❌ Erreur traitement webhook: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
            finally:
                campaign_session.close()

        return jsonify({'status': 'unknown_type'}), 200

    except Exception as e:
        logger.error(f"❌ Erreur webhook SES: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def handle_bounce(message, session):
    """Gérer un bounce"""
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    bounce = message.get('bounce', {})
    mail = message.get('mail', {})

    message_id = mail.get('messageId')
    bounce_type = bounce.get('bounceType', 'Unknown')  # Permanent ou Temporary
    recipients = bounce.get('bouncedRecipients', [])

    logger.info(f"📫 Bounce reçu - Type: {bounce_type}, Message ID: {message_id}")

    # Mettre à jour l'email dans la base
    campaign_email = session.query(CampaignEmail).filter(
        CampaignEmail.message_id == message_id
    ).first()

    if campaign_email:
        campaign_email.status = EmailStatus.BOUNCED
        campaign_email.bounced_at = datetime.utcnow()
        campaign_email.bounce_type = 'hard' if bounce_type == 'Permanent' else 'soft'
        campaign_email.error_message = bounce.get('bouncedRecipients', [{}])[0].get('diagnosticCode', '')

        # Incrémenter le compteur de la campagne
        campaign = session.query(Campaign).get(campaign_email.campaign_id)
        if campaign:
            campaign.emails_bounced += 1

        logger.info(f"  ✅ Email {campaign_email.to_email} marqué comme bounced")


def handle_complaint(message, session):
    """Gérer une plainte (spam)"""
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    complaint = message.get('complaint', {})
    mail = message.get('mail', {})

    message_id = mail.get('messageId')
    recipients = complaint.get('complainedRecipients', [])

    logger.info(f"⚠️ Plainte reçue - Message ID: {message_id}")

    # Mettre à jour l'email dans la base
    campaign_email = session.query(CampaignEmail).filter(
        CampaignEmail.message_id == message_id
    ).first()

    if campaign_email:
        campaign_email.status = EmailStatus.COMPLAINED

        # Incrémenter le compteur de la campagne
        campaign = session.query(Campaign).get(campaign_email.campaign_id)
        if campaign:
            campaign.emails_complained += 1

        # Ajouter automatiquement à la liste de désinscription
        from campaign_database import Unsubscribe
        existing = session.query(Unsubscribe).filter(
            Unsubscribe.email == campaign_email.to_email
        ).first()

        if not existing:
            unsubscribe = Unsubscribe(
                email=campaign_email.to_email,
                reason='Spam complaint',
                campaign_id=campaign_email.campaign_id,
                unsubscribed_at=datetime.utcnow()
            )
            session.add(unsubscribe)
            logger.info(f"  ✅ Email {campaign_email.to_email} ajouté à la liste de désinscription")


def handle_delivery(message, session):
    """Gérer une livraison réussie"""
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    delivery = message.get('delivery', {})
    mail = message.get('mail', {})

    message_id = mail.get('messageId')

    # Mettre à jour l'email dans la base
    campaign_email = session.query(CampaignEmail).filter(
        CampaignEmail.message_id == message_id
    ).first()

    if campaign_email and campaign_email.status == EmailStatus.SENT:
        campaign_email.status = EmailStatus.DELIVERED
        campaign_email.delivered_at = datetime.utcnow()

        # Incrémenter le compteur de la campagne
        campaign = session.query(Campaign).get(campaign_email.campaign_id)
        if campaign:
            campaign.emails_delivered += 1


def handle_open(message, session):
    """Gérer une ouverture d'email"""
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    open_data = message.get('open', {})
    mail = message.get('mail', {})

    message_id = mail.get('messageId')

    # Mettre à jour l'email dans la base
    campaign_email = session.query(CampaignEmail).filter(
        CampaignEmail.message_id == message_id
    ).first()

    if campaign_email:
        if campaign_email.status == EmailStatus.DELIVERED:
            campaign_email.status = EmailStatus.OPENED

        if not campaign_email.opened_at:
            campaign_email.opened_at = datetime.utcnow()

            # Incrémenter le compteur de la campagne (seulement la première ouverture)
            campaign = session.query(Campaign).get(campaign_email.campaign_id)
            if campaign:
                campaign.emails_opened += 1

        campaign_email.open_count += 1


def handle_click(message, session):
    """Gérer un clic sur un lien"""
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    click_data = message.get('click', {})
    mail = message.get('mail', {})

    message_id = mail.get('messageId')

    # Mettre à jour l'email dans la base
    campaign_email = session.query(CampaignEmail).filter(
        CampaignEmail.message_id == message_id
    ).first()

    if campaign_email:
        if campaign_email.status == EmailStatus.OPENED:
            campaign_email.status = EmailStatus.CLICKED

        if not campaign_email.clicked_at:
            campaign_email.clicked_at = datetime.utcnow()

            # Incrémenter le compteur de la campagne (seulement le premier clic)
            campaign = session.query(Campaign).get(campaign_email.campaign_id)
            if campaign:
                campaign.emails_clicked += 1

        campaign_email.click_count += 1


# ============================================================================
# LANCEMENT
# ============================================================================

if __name__ == '__main__':
    import os

    # Configuration
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))

    print("=" * 70)
    print("INTERFACE DE GESTION SCRAP EMAIL")
    print("=" * 70)
    print(f"\nMode: {'DEBUG' if debug_mode else 'PRODUCTION'}")
    print(f"Démarrage du serveur sur {host}:{port}...")

    if host == '0.0.0.0':
        print("Interface accessible sur : http://admin.perfect-cocon-seo.fr")
    else:
        print(f"Interface accessible sur : http://{host}:{port}")

    print("\nPages disponibles :")
    print("  - Dashboard : /")
    print("  - Sites : /sites")
    print("  - Jobs : /jobs")
    print("\nAppuyez sur Ctrl+C pour arrêter le serveur")
    print("=" * 70)

    app.run(debug=debug_mode, host=host, port=port)
