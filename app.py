#!/usr/bin/env python3
"""
Application Flask pour l'interface de gestion du scraping
"""

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from flask_cors import CORS
from sqlalchemy import func, case
from database import init_db, get_session, Site, ScrapingJob, SiteStatus, safe_commit
from campaign_database import get_campaign_session, Unsubscribe
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
import logging
import threading
from io import StringIO, BytesIO
from scenario_routes import register_scenario_routes
from segment_routes import register_segment_routes
from distributed_crawl_api import crawl_api

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache pour les stats (évite les requêtes SQL lourdes à chaque refresh)
STATS_CACHE_FILE = Path('/var/www/Scrap_Email/stats_cache.json')
DAILY_STATS_CACHE_FILE = Path('/var/www/Scrap_Email/daily_stats_cache.json')
STATS_CACHE_MAX_AGE = 300  # 5 minutes
DAILY_STATS_CACHE_MAX_AGE = 600  # 10 minutes (données journalières, moins urgentes)
stats_update_lock = threading.Lock()
daily_stats_update_lock = threading.Lock()

app = Flask(__name__)
CORS(app)

# Initialiser la base de données au démarrage
init_db()

# Enregistrer les routes des scénarios
register_scenario_routes(app)

# Enregistrer les routes des segments
register_segment_routes(app)

# Enregistrer les routes de crawl distribué
app.register_blueprint(crawl_api)


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

def load_stats_cache():
    """Charger les stats depuis le cache si disponible et récent"""
    if STATS_CACHE_FILE.exists():
        try:
            with open(STATS_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cached_at = datetime.fromisoformat(cache.get('cached_at', '2000-01-01'))
            if (datetime.utcnow() - cached_at).total_seconds() < STATS_CACHE_MAX_AGE:
                return cache.get('data')
        except Exception as e:
            logger.warning(f"Erreur lecture cache stats: {e}")
    return None


def save_stats_cache(data):
    """Sauvegarder les stats dans le cache"""
    try:
        cache = {
            'cached_at': datetime.utcnow().isoformat(),
            'data': data
        }
        with open(STATS_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"Erreur écriture cache stats: {e}")


def compute_stats_background():
    """Calculer les stats en arrière-plan et mettre à jour le cache"""
    if not stats_update_lock.acquire(blocking=False):
        return  # Un autre thread calcule déjà
    try:
        logger.info("🔄 Calcul des stats en arrière-plan...")
        data = compute_stats_data()
        save_stats_cache(data)
        logger.info("✅ Stats mises à jour dans le cache")
    finally:
        stats_update_lock.release()


def compute_stats_data():
    """Calculer les stats depuis la DB (fonction lourde)"""
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
            Site.leaders != '[]',
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

        # Stats CMS (exclure NONE et vide)
        sites_with_cms = session.query(Site).filter(
            Site.cms.isnot(None),
            Site.cms != '',
            Site.cms != 'NONE'
        ).count()
        cms_counts = {}
        cms_results = session.query(Site.cms, func.count(Site.id)).filter(Site.cms.isnot(None)).group_by(Site.cms).all()
        for cms, count in cms_results:
            cms_counts[cms] = count
        emails_deliverable = session.query(Site).filter(Site.email_deliverable == True).count()

        # Stats Blacklist
        sites_blacklisted = session.query(Site).filter(Site.blacklisted == True).count()

        # Stats Sites Vendeurs (LinkAvista)
        total_sellers = session.query(Site).filter_by(is_linkavista_seller=True).count()
        total_buyers = session.query(Site).filter(Site.purchased_from.isnot(None)).count()

        # Stats Campagnes - Désinscrits
        campaign_session = get_campaign_session()
        total_unsubscribed = 0
        try:
            total_unsubscribed = campaign_session.query(Unsubscribe).count()
        except Exception as e:
            logger.error(f"Erreur récupération désinscrits: {e}")
        finally:
            campaign_session.close()

        # Stats Scraping Backlinks
        backlinks_scraped = session.query(Site).filter(Site.backlinks_crawled == True).count()
        backlinks_not_scraped = session.query(Site).filter(
            (Site.backlinks_crawled == False) | (Site.backlinks_crawled.is_(None))
        ).count()
        # Sites vendeurs scrappés
        sellers_scraped = session.query(Site).filter(
            Site.is_linkavista_seller == True,
            Site.backlinks_crawled == True
        ).count()
        sellers_not_scraped = session.query(Site).filter(
            Site.is_linkavista_seller == True,
            (Site.backlinks_crawled == False) | (Site.backlinks_crawled.is_(None))
        ).count()

        # Stats Contacts extraits
        sites_with_contacts = session.query(Site).filter(
            Site.contact_firstname.isnot(None),
            Site.contact_lastname.isnot(None)
        ).count()

        return {
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
            'emails_validated': emails_validated,
            'emails_valid': emails_valid,
            'emails_invalid': emails_invalid,
            'emails_risky': emails_risky,
            'emails_deliverable': emails_deliverable,
            'validation_rate': round((emails_validated / sites_with_email * 100) if sites_with_email > 0 else 0, 1),
            'deliverable_rate': round((emails_deliverable / emails_validated * 100) if emails_validated > 0 else 0, 1),
            'sites_with_cms': sites_with_cms,
            'cms_counts': cms_counts,
            'cms_rate': round((sites_with_cms / total_sites * 100) if total_sites > 0 else 0, 1),
            'sites_blacklisted': sites_blacklisted,
            'blacklist_rate': round((sites_blacklisted / total_sites * 100) if total_sites > 0 else 0, 1),
            'total_sellers': total_sellers,
            'total_buyers': total_buyers,
            'total_unsubscribed': total_unsubscribed,
            'backlinks_scraped': backlinks_scraped,
            'backlinks_not_scraped': backlinks_not_scraped,
            'backlinks_total': backlinks_scraped + backlinks_not_scraped,
            'backlinks_progress': round((backlinks_scraped / (backlinks_scraped + backlinks_not_scraped) * 100) if (backlinks_scraped + backlinks_not_scraped) > 0 else 0, 1),
            'sellers_scraped': sellers_scraped,
            'sellers_not_scraped': sellers_not_scraped,
            'sellers_scraping_progress': round((sellers_scraped / total_sellers * 100) if total_sellers > 0 else 0, 1),
            'sites_with_contacts': sites_with_contacts,
            'contacts_rate': round((sites_with_contacts / sites_with_email * 100) if sites_with_email > 0 else 0, 1),
        }
    finally:
        session.close()


@app.route('/api/stats')
def get_stats():
    """Obtenir les statistiques globales (avec cache)"""
    # Essayer de charger depuis le cache
    cached_data = load_stats_cache()
    if cached_data:
        return jsonify(cached_data)

    # Pas de cache valide - lancer le calcul en arrière-plan
    threading.Thread(target=compute_stats_background, daemon=True).start()

    # Retourner le cache périmé s'il existe, sinon des valeurs par défaut
    if STATS_CACHE_FILE.exists():
        try:
            with open(STATS_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            return jsonify(cache.get('data', {}))
        except:
            pass

    # Retourner des valeurs par défaut pendant le premier calcul
    return jsonify({
        'total_sites': 0,
        'status_counts': {},
        'sites_with_email': 0,
        'sites_with_siret': 0,
        'sites_with_leaders': 0,
        'sites_complete': 0,
        'email_rate': 0,
        'siret_rate': 0,
        'leaders_rate': 0,
        'completion_rate': 0,
        'loading': True,
        'message': 'Calcul des stats en cours...'
    })


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

        # Top 10 derniers sites vendeurs RÉELLEMENT CRAWLÉS (pas juste mis à jour)
        recent_sellers = session.query(Site).filter(
            Site.is_linkavista_seller == True,
            Site.backlinks_crawled == True,
            Site.backlinks_crawled_at.isnot(None)
        ).order_by(Site.backlinks_crawled_at.desc()).limit(10).all()

        sellers_data = []
        for seller in recent_sellers:
            # Compter les acheteurs de ce vendeur
            buyers_count = session.query(Site).filter_by(purchased_from=seller.domain).count()
            sellers_data.append({
                'domain': seller.domain,
                'buyers_found': buyers_count,
                'updated_at': seller.backlinks_crawled_at.isoformat() if seller.backlinks_crawled_at else None
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
    from datetime import datetime, timedelta

    workers_file = Path('/var/www/Scrap_Email/crawl_workers.json')
    WORKER_TIMEOUT = 300  # 5 minutes

    try:
        sites = []
        if workers_file.exists():
            with open(workers_file, 'r') as f:
                workers_data = json.load(f)

            # Parcourir tous les workers actifs et collecter leurs sites en cours
            for worker_id, worker in workers_data.get('workers', {}).items():
                # Vérifier si le worker est encore actif
                last_heartbeat = worker.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        last_beat = datetime.fromisoformat(last_heartbeat)
                        if (datetime.utcnow() - last_beat).total_seconds() > WORKER_TIMEOUT:
                            continue  # Worker mort, ignorer
                    except:
                        continue

                # Ajouter les sites en cours de ce worker
                for site in worker.get('sites_in_progress', []):
                    sites.append({
                        'domain': site.get('domain', '?'),
                        'pages_crawled': site.get('pages', 0),
                        'recent_urls': site.get('recent_urls', []),
                        'worker_id': worker_id
                    })

        return jsonify({
            'sites': sites,
            'count': len(sites),
            'last_update': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Erreur lors de la lecture du state de scraping: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cancel-crawl', methods=['POST'])
def cancel_crawl():
    """
    Annuler le crawl d'un site en cours, le blacklister et démarrer un nouveau site

    Stratégie rapide:
    1. Retirer immédiatement du JSON (rapide, pas de lock)
    2. Mettre à jour la DB en arrière-plan avec thread
    """
    from pathlib import Path
    import threading

    data = request.get_json()
    domain = data.get('domain')

    if not domain:
        return jsonify({'error': 'Domaine manquant'}), 400

    # 1. PRIORITÉ: Retirer immédiatement du fichier JSON (pas de lock DB)
    state_file = Path('/var/www/Scrap_Email/scraping_state.json')

    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)

            # Filtrer le site annulé
            original_count = len(state.get('sellers_in_progress', []))
            state['sellers_in_progress'] = [
                s for s in state.get('sellers_in_progress', [])
                if s.get('domain') != domain
            ]
            new_count = len(state['sellers_in_progress'])
            state['last_update'] = datetime.utcnow().isoformat()

            # Sauvegarder immédiatement
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)

            if original_count == new_count:
                return jsonify({'error': f'Site {domain} non trouvé dans les crawlers actifs'}), 404

            logger.info(f"✓ Site {domain} retiré du scraping_state.json immédiatement")

    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du JSON: {e}")
        return jsonify({'error': f'Impossible de modifier le fichier d\'état: {str(e)}'}), 500

    # 1.5. Ajouter au fichier blacklist.txt (PERSISTANT, pas de lock DB)
    blacklist_file = Path('/var/www/Scrap_Email/blacklist.txt')
    try:
        # Lire la blacklist existante
        existing_domains = set()
        if blacklist_file.exists():
            with open(blacklist_file, 'r') as f:
                existing_domains = set(line.strip() for line in f if line.strip())

        # Ajouter le nouveau domaine si pas déjà présent
        if domain not in existing_domains:
            with open(blacklist_file, 'a') as f:
                f.write(f"{domain}\n")
            logger.info(f"🚫 Site {domain} ajouté à blacklist.txt (persistant)")
        else:
            logger.info(f"✓ Site {domain} déjà dans blacklist.txt")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de blacklist.txt: {e}")
        # Ne pas bloquer le processus pour cette erreur

    # 2. Mise à jour DB en arrière-plan (thread séparé pour ne pas bloquer)
    def update_db_async():
        """Mettre à jour la DB de manière asynchrone"""
        import time
        import random

        max_retries = 10
        for attempt in range(max_retries):
            session = get_session()
            try:
                site = session.query(Site).filter_by(domain=domain).first()
                if site:
                    site.blacklisted = True
                    site.backlinks_crawled = True
                    site.backlinks_crawled_at = datetime.utcnow()
                    site.updated_at = datetime.utcnow()
                    safe_commit(session)
                    logger.info(f"🚫 Site {domain} blacklisté dans la DB (async)")
                session.close()
                break  # Succès
            except Exception as e:
                session.rollback()
                session.close()
                if 'database is locked' in str(e) and attempt < max_retries - 1:
                    time.sleep(random.uniform(0.5, 2.0))  # Attente plus longue en arrière-plan
                    continue
                else:
                    logger.error(f"Erreur DB async pour {domain}: {e}")
                    break

    # Lancer la mise à jour DB dans un thread séparé
    db_thread = threading.Thread(target=update_db_async, daemon=True)
    db_thread.start()

    # 3. Trouver le prochain site (lecture rapide, pas de lock)
    try:
        # Lire la blacklist à jour (y compris le domaine qu'on vient d'ajouter)
        blacklist_file = Path('/var/www/Scrap_Email/blacklist.txt')
        current_blacklist = set()
        if blacklist_file.exists():
            with open(blacklist_file, 'r') as f:
                current_blacklist = {line.strip() for line in f if line.strip()}

        session = get_session()
        next_site = session.query(Site).filter(
            Site.is_linkavista_seller == True,
            Site.backlinks_crawled == False,
            Site.blacklisted == False,
            ~Site.domain.in_(current_blacklist)  # Exclure les domaines du fichier blacklist
        ).first()
        next_domain = next_site.domain if next_site else None
        session.close()
    except:
        next_domain = "Un nouveau site sera chargé automatiquement"

    return jsonify({
        'success': True,
        'message': f'Site {domain} retiré du crawl immédiatement. Blacklistage DB en cours...',
        'blacklisted_domain': domain,
        'new_site': next_domain
    })


@app.route('/api/process-alerts')
def get_process_alerts():
    """Obtenir les alertes des processus en arrière-plan"""
    from pathlib import Path

    alert_file = Path('/var/www/Scrap_Email/process_alerts.json')

    try:
        if alert_file.exists():
            with open(alert_file, 'r') as f:
                alerts = json.load(f)
            return jsonify(alerts)
        else:
            return jsonify({
                "siret_extractor": {
                    "status": "unknown",
                    "message": "Fichier d'alertes non trouvé",
                    "timestamp": datetime.utcnow().isoformat(),
                    "last_check": datetime.utcnow().isoformat()
                }
            })
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors de la lecture des alertes: {e}")
        # Réparer le fichier corrompu
        try:
            with open(alert_file, 'w') as f:
                json.dump({}, f)
            logger.info("Fichier process_alerts.json réparé")
        except:
            pass
        return jsonify({})
    except Exception as e:
        logger.error(f"Erreur lors de la lecture des alertes: {e}")
        return jsonify({
            "siret_extractor": {
                "status": "error",
                "message": f"Erreur: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "last_check": datetime.utcnow().isoformat()
            }
        }), 500


@app.route('/api/scripts-status')
def get_scripts_status():
    """Obtenir le statut de tous les scripts Python en temps réel avec auto-restart"""
    import subprocess
    from pathlib import Path

    try:
        # Obtenir la liste des processus
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout

        # Scripts à monitorer avec configuration de relance
        scripts_config = {
            'app.py': {
                'name': 'API Flask',
                'icon': '🌐',
                'category': 'core',
                'auto_restart': False,
                'critical': True,
                'description': 'Interface web principale qui expose toutes les API et sert le dashboard'
            },
            'campaign_sender.py': {
                'name': 'Envoi Campagnes',
                'icon': '📧',
                'category': 'email',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 campaign_sender.py >> campaign_sender.log 2>&1 &',
                'critical': True,
                'description': 'Envoie automatiquement les emails de campagnes selon les scénarios programmés'
            },
            'continuous_campaign_worker.py': {
                'name': 'Worker Campagnes',
                'icon': '⚙️',
                'category': 'email',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 continuous_campaign_worker.py --interval 30 >> continuous_campaign_worker.log 2>&1 &',
                'critical': True,
                'description': 'Traite en continu les campagnes d\'emails en attente dans la queue'
            },
            'extract_siret_leaders.py': {
                'name': 'SIRET/Dirigeants',
                'icon': '🏢',
                'category': 'extraction',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 extract_siret_leaders.py --batch-size 50 --delay 2 >> siret_extractor.log 2>&1 &',
                'critical': True,
                'description': 'Enrichit les sites avec les données SIRET et informations des dirigeants via API Pappers'
            },
            'scrape_backlinks_async.py': {
                'name': 'Scraping Backlinks',
                'icon': '🔗',
                'category': 'scraping',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 scrape_backlinks_async.py >> scrape_backlinks.log 2>&1 &',
                'critical': True,
                'description': 'Crawle les sites vendeurs de backlinks pour découvrir les acheteurs et leurs emails'
            },
            'validate_emails_daemon.py': {
                'name': 'Validation Emails',
                'icon': '✉️',
                'category': 'email',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 validate_emails_daemon.py --batch-size 100 --check-interval 30 >> email_validation_daemon.log 2>&1 &',
                'critical': True,
                'description': 'Vérifie la validité des adresses emails via vérification syntaxique et DNS MX'
            },
            'rescrape_no_emails_async.py': {
                'name': 'Recherche Emails',
                'icon': '🔍',
                'category': 'email',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 rescrape_no_emails_async.py --limit 1000 --concurrent 25 >> rescrape_emails.log 2>&1 &',
                'critical': True,
                'description': 'Re-scrape les sites où aucun email n\'a été trouvé pour tenter d\'en découvrir'
            },
            'scenario_daemon.py': {
                'name': 'Scénarios Auto',
                'icon': '🎯',
                'category': 'automation',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 scenario_daemon.py >> scenario_daemon.log 2>&1 &',
                'critical': True,
                'description': 'Exécute automatiquement les scénarios d\'emails selon les règles définies'
            },
            'scenario_orchestrator.py': {
                'name': 'Orchestrateur',
                'icon': '🎼',
                'category': 'automation',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 scenario_orchestrator.py >> scenario_orchestrator.log 2>&1 &',
                'critical': True,
                'description': 'Coordonne et orchestre l\'exécution des différents scénarios d\'automation'
            },
            'cms_detector_daemon.py': {
                'name': 'Détection CMS',
                'icon': '🔍',
                'category': 'extraction',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 cms_detector_daemon.py --batch-size 150 --interval 15 >> cms_detector.log 2>&1 &',
                'critical': False,
                'description': 'Détecte le CMS utilisé par chaque site (WordPress, Prestashop, Shopify, etc.)'
            },
            'find_any_valid_email_daemon.py': {
                'name': 'Guessing Emails',
                'icon': '🎯',
                'category': 'email',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 find_any_valid_email_daemon.py --check-interval 300 --batch-size 50 --limit-per-run 500 >> find_any_valid_email_daemon.log 2>&1 &',
                'critical': True,
                'description': 'Teste des emails génériques (contact@, info@, etc.) sur les sites sans email et les valide via SMTP'
            },
            'language_detector_daemon.py': {
                'name': 'Détection de Langue',
                'icon': '🌍',
                'category': 'detection',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 language_detector_daemon.py --batch-size 100 --interval 30 >> language_detector.log 2>&1 &',
                'critical': False,
                'description': 'Détecte automatiquement la langue principale de chaque site (français, anglais, espagnol, etc.)'
            },
            'extract_contact_names_daemon.py': {
                'name': 'Extraction Contacts',
                'icon': '👤',
                'category': 'extraction',
                'auto_restart': True,
                'command': 'cd /var/www/Scrap_Email && nohup python3 extract_contact_names_daemon.py --check-interval 60 --batch-size 100 --limit-per-run 1000 >> extract_contact_names_daemon.log 2>&1 &',
                'critical': False,
                'description': 'Extrait les prénoms et noms depuis les adresses email (ex: jean.dupont@mail.com → Jean Dupont)'
            },
        }

        active_scripts = []
        inactive_scripts = []
        restart_attempts = []

        # Analyser les processus
        for script_name, config in scripts_config.items():
            is_running = script_name in processes

            if is_running:
                # Script actif
                for line in processes.split('\n'):
                    if script_name in line and 'python' in line.lower():
                        parts = line.split()
                        if len(parts) >= 11:
                            active_scripts.append({
                                'script': script_name,
                                'name': config['name'],
                                'icon': config['icon'],
                                'category': config['category'],
                                'status': 'running',
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'critical': config.get('critical', False),
                                'description': config.get('description', '')
                            })
                        break
            else:
                # Script inactif
                script_info = {
                    'script': script_name,
                    'name': config['name'],
                    'icon': config['icon'],
                    'category': config['category'],
                    'status': 'stopped',
                    'critical': config.get('critical', False),
                    'auto_restart': config.get('auto_restart', False)
                }

                # Relancer si auto_restart activé
                if config.get('auto_restart', False) and config.get('command'):
                    try:
                        logger.info(f"Relance automatique: {script_name}")
                        subprocess.Popen(config['command'], shell=True, cwd='/var/www/Scrap_Email')
                        script_info['restart_attempted'] = True
                        script_info['restart_status'] = 'success'
                        restart_attempts.append({
                            'script': script_name,
                            'name': config['name'],
                            'status': 'restarted',
                            'message': 'Relancé automatiquement'
                        })
                    except Exception as e:
                        logger.error(f"Échec relance {script_name}: {e}")
                        script_info['restart_attempted'] = True
                        script_info['restart_status'] = 'failed'
                        script_info['error'] = str(e)
                        restart_attempts.append({
                            'script': script_name,
                            'name': config['name'],
                            'status': 'failed',
                            'message': f'Échec: {str(e)}'
                        })

                inactive_scripts.append(script_info)

        # Lire alertes
        alert_file = Path('/var/www/Scrap_Email/process_alerts.json')
        alerts = {}
        if alert_file.exists():
            try:
                with open(alert_file, 'r') as f:
                    alerts = json.load(f)
            except json.JSONDecodeError:
                # Fichier corrompu, le réparer
                try:
                    with open(alert_file, 'w') as f:
                        json.dump({}, f)
                except:
                    pass
                alerts = {}

        # Ajouter les crawl workers (locaux et distants)
        crawl_workers = {
            'local': {'count': 0, 'workers': [], 'min_required': 1},
            'remote': {'count': 0, 'workers': [], 'min_required': 8, 'host': 'ns500898 (192.99.44.191)'},
            'remote2': {'count': 0, 'workers': [], 'min_required': 4, 'host': 'prestashop (137.74.26.28)'}
        }

        try:
            # Workers locaux
            for line in processes.split('\n'):
                if 'crawl_worker_multi.py' in line and 'python3' in line and 'bash -c' not in line:
                    parts = line.split()
                    if len(parts) >= 11:
                        crawl_workers['local']['workers'].append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'started': parts[8] if len(parts) > 8 else 'N/A'
                        })
            crawl_workers['local']['count'] = len(crawl_workers['local']['workers'])

            # Workers distants ns500898 via SSH (avec timeout augmenté)
            try:
                remote_result = subprocess.run(
                    ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                     'debian@192.99.44.191',
                     "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                    capture_output=True, text=True, timeout=60
                )
                for line in remote_result.stdout.strip().split('\n'):
                    if line.strip() and 'crawl_worker_multi.py' in line:
                        parts = line.split()
                        if len(parts) >= 11 and parts[1].isdigit():
                            crawl_workers['remote']['workers'].append({
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'started': parts[8] if len(parts) > 8 else 'N/A'
                            })
                crawl_workers['remote']['count'] = len(crawl_workers['remote']['workers'])
            except (subprocess.TimeoutExpired, Exception) as e:
                crawl_workers['remote']['error'] = str(e)

            # Workers distants prestashop via SSH (avec timeout augmenté)
            try:
                remote2_result = subprocess.run(
                    ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                     'debian@137.74.26.28',
                     "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                    capture_output=True, text=True, timeout=60
                )
                for line in remote2_result.stdout.strip().split('\n'):
                    if line.strip() and 'crawl_worker_multi.py' in line:
                        parts = line.split()
                        if len(parts) >= 11 and parts[1].isdigit():
                            crawl_workers['remote2']['workers'].append({
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'started': parts[8] if len(parts) > 8 else 'N/A'
                            })
                crawl_workers['remote2']['count'] = len(crawl_workers['remote2']['workers'])
            except (subprocess.TimeoutExpired, Exception) as e:
                crawl_workers['remote2']['error'] = str(e)
        except Exception as e:
            logger.error(f"Erreur récupération crawl workers: {e}")

        return jsonify({
            'active_scripts': active_scripts,
            'inactive_scripts': inactive_scripts,
            'restart_attempts': restart_attempts,
            'alerts': alerts,
            'crawl_workers': crawl_workers,
            'total_active': len(active_scripts),
            'total_inactive': len(inactive_scripts),
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Erreur statut scripts: {e}")
        return jsonify({'error': str(e)}), 500


def load_daily_stats_cache():
    """Charger les stats daily depuis le cache si disponible et récent"""
    if DAILY_STATS_CACHE_FILE.exists():
        try:
            with open(DAILY_STATS_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cached_at = datetime.fromisoformat(cache.get('cached_at', '2000-01-01'))
            if (datetime.utcnow() - cached_at).total_seconds() < DAILY_STATS_CACHE_MAX_AGE:
                return cache.get('data')
        except Exception as e:
            logger.warning(f"Erreur lecture cache daily stats: {e}")
    return None


def save_daily_stats_cache(data):
    """Sauvegarder les stats daily dans le cache"""
    try:
        cache = {
            'cached_at': datetime.utcnow().isoformat(),
            'data': data
        }
        with open(DAILY_STATS_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"Erreur écriture cache daily stats: {e}")


def compute_daily_stats_background():
    """Calculer les stats daily en arrière-plan et mettre à jour le cache"""
    if not daily_stats_update_lock.acquire(blocking=False):
        return
    try:
        logger.info("🔄 Calcul des stats daily en arrière-plan...")
        data = compute_daily_stats_data()
        save_daily_stats_cache(data)
        logger.info("✅ Stats daily mises à jour dans le cache")
    finally:
        daily_stats_update_lock.release()


def compute_daily_stats_data():
    """Calculer les stats daily depuis la DB (fonction lourde)"""
    session = get_session()
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_data = []

        for i in range(30, -1, -1):
            date = datetime.utcnow() - timedelta(days=i)
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start + timedelta(days=1)

            sites_crawled = session.query(Site).filter(
                Site.created_at >= date_start,
                Site.created_at < date_end
            ).count()

            buyers_found = session.query(Site).filter(
                Site.purchased_from.isnot(None),
                Site.purchased_at >= date_start,
                Site.purchased_at < date_end
            ).count()

            emails_found = session.query(Site).filter(
                Site.email_found_at >= date_start,
                Site.email_found_at < date_end,
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != 'NO EMAIL FOUND'
            ).count()

            siret_found = session.query(Site).filter(
                Site.updated_at >= date_start,
                Site.updated_at < date_end,
                Site.siret.isnot(None),
                Site.siret != '',
                Site.siret != 'NON TROUVÉ'
            ).count()

            leaders_found = session.query(Site).filter(
                Site.leaders_found_at >= date_start,
                Site.leaders_found_at < date_end,
                Site.leaders.isnot(None),
                Site.leaders != ''
            ).count()

            daily_data.append({
                'date': date_start.strftime('%Y-%m-%d'),
                'sites_crawled': sites_crawled,
                'buyers_found': buyers_found,
                'siret_found': siret_found,
                'leaders_found': leaders_found,
                'emails_found': emails_found
            })

        total_sites = session.query(Site).filter(Site.created_at >= thirty_days_ago).count()
        total_buyers = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.purchased_at >= thirty_days_ago
        ).count()
        total_siret = session.query(Site).filter(
            Site.updated_at >= thirty_days_ago,
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ'
        ).count()
        total_leaders = session.query(Site).filter(
            Site.leaders_found_at >= thirty_days_ago,
            Site.leaders.isnot(None),
            Site.leaders != ''
        ).count()
        total_emails = session.query(Site).filter(
            Site.email_found_at >= thirty_days_ago,
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        return {
            'daily': daily_data,
            'summary_30_days': {
                'total_sites_crawled': total_sites,
                'total_buyers_found': total_buyers,
                'total_siret_found': total_siret,
                'total_leaders_found': total_leaders,
                'total_emails_found': total_emails,
                'avg_sites_per_day': round(total_sites / 30, 1),
                'avg_buyers_per_day': round(total_buyers / 30, 1),
                'avg_siret_per_day': round(total_siret / 30, 1),
                'avg_leaders_per_day': round(total_leaders / 30, 1),
                'avg_emails_per_day': round(total_emails / 30, 1)
            }
        }
    finally:
        session.close()


@app.route('/api/stats/daily')
def get_daily_stats():
    """Obtenir les statistiques quotidiennes (30 derniers jours) avec cache"""
    # Essayer de charger depuis le cache
    cached_data = load_daily_stats_cache()
    if cached_data:
        return jsonify(cached_data)

    # Pas de cache valide - lancer le calcul en arrière-plan
    threading.Thread(target=compute_daily_stats_background, daemon=True).start()

    # Retourner le cache périmé s'il existe
    if DAILY_STATS_CACHE_FILE.exists():
        try:
            with open(DAILY_STATS_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            return jsonify(cache.get('data', {}))
        except:
            pass

    # Retourner des valeurs par défaut pendant le premier calcul
    return jsonify({
        'daily': [],
        'summary_30_days': {
            'total_sites_crawled': 0,
            'total_buyers_found': 0,
            'total_siret_found': 0,
            'total_leaders_found': 0,
            'total_emails_found': 0,
            'avg_sites_per_day': 0,
            'avg_buyers_per_day': 0,
            'avg_siret_per_day': 0,
            'avg_leaders_per_day': 0,
            'avg_emails_per_day': 0
        },
        'loading': True
    })


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
        cms_filter = request.args.get('cms')
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

        # Filtre CMS
        if cms_filter:
            if cms_filter == 'no_cms':
                query = query.filter(
                    (Site.cms.is_(None)) | (Site.cms == '')
                )
            else:
                query = query.filter(Site.cms == cms_filter)

        # Total
        total = query.count()

        # Tri par date de découverte d'email (plus récents en premier), puis date de mise à jour
        query = query.order_by(Site.email_found_at.desc().nullslast(), Site.updated_at.desc())

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
        safe_commit(session)

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
        safe_commit(session)

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
        safe_commit(session)

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
        safe_commit(session)

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
        safe_commit(session)

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
        safe_commit(session)

        return jsonify({
            'success': True,
            'site': site.to_dict()
        })

    finally:
        session.close()


# ============================================================================
# API - JOBS
# ============================================================================

@app.route('/api/database-health')
def get_database_health():
    """Vérifier la santé de la base de données et les erreurs récentes"""
    import os
    import subprocess
    from datetime import datetime, timedelta

    health = {
        'status': 'healthy',
        'alerts': [],
        'database_locked_errors': 0,
        'last_check': datetime.utcnow().isoformat(),
        'wal_size_mb': 0,
        'active_connections': 0
    }

    try:
        # Vérifier la taille du fichier WAL
        wal_path = os.path.join(os.path.dirname(__file__), 'scrap_email.db-wal')
        if os.path.exists(wal_path):
            wal_size = os.path.getsize(wal_path) / (1024 * 1024)
            health['wal_size_mb'] = round(wal_size, 2)
            if wal_size > 50:  # Plus de 50MB
                health['alerts'].append({
                    'type': 'warning',
                    'message': f'Fichier WAL volumineux: {wal_size:.1f} MB',
                    'icon': 'exclamation-triangle'
                })

        # Compter les erreurs "database locked" dans les logs récents
        log_files = [
            'email_validation_daemon.log',
            'cms_detector.log',
            'language_detector.log',
            'scraping_output.log',
            'find_any_valid_email.log'
        ]

        total_errors = 0
        errors_by_log = {}

        for log_file in log_files:
            log_path = os.path.join(os.path.dirname(__file__), log_file)
            if os.path.exists(log_path):
                try:
                    # Lire les 500 dernières lignes
                    result = subprocess.run(
                        ['tail', '-500', log_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    count = result.stdout.lower().count('database is locked')
                    if count > 0:
                        errors_by_log[log_file] = count
                        total_errors += count
                except:
                    pass

        health['database_locked_errors'] = total_errors
        health['errors_by_log'] = errors_by_log

        if total_errors > 0:
            health['status'] = 'warning' if total_errors < 10 else 'critical'
            health['alerts'].append({
                'type': 'danger' if total_errors >= 10 else 'warning',
                'message': f'{total_errors} erreurs "database locked" détectées récemment',
                'icon': 'database-x',
                'details': errors_by_log
            })

        # Compter les connexions actives (via lsof)
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'scrap_email.db')
            result = subprocess.run(
                ['lsof', db_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Compter les lignes (moins l'en-tête)
            connections = len(result.stdout.strip().split('\n')) - 1 if result.stdout.strip() else 0
            health['active_connections'] = max(0, connections)

            if connections > 20:
                health['alerts'].append({
                    'type': 'warning',
                    'message': f'{connections} connexions actives à la base de données',
                    'icon': 'plug'
                })
        except:
            pass

    except Exception as e:
        health['status'] = 'error'
        health['alerts'].append({
            'type': 'danger',
            'message': f'Erreur lors de la vérification: {str(e)}',
            'icon': 'x-circle'
        })

    return jsonify(health)

@app.route('/api/force-wal-checkpoint', methods=['POST'])
def force_wal_checkpoint():
    """Forcer un checkpoint WAL pour libérer de l'espace"""
    import sqlite3
    import os

    try:
        db_path = os.path.join(os.path.dirname(__file__), 'scrap_email.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Forcer un checkpoint complet
        cursor.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        result = cursor.fetchone()

        conn.close()

        # Vérifier la nouvelle taille du WAL
        wal_path = db_path + '-wal'
        new_size = os.path.getsize(wal_path) / (1024 * 1024) if os.path.exists(wal_path) else 0

        return jsonify({
            'success': True,
            'message': 'Checkpoint WAL effectué',
            'blocked': result[0],
            'log_frames': result[1],
            'checkpointed': result[2],
            'new_wal_size_mb': round(new_size, 2)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        safe_commit(session)

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

        safe_commit(session)
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


@app.route('/api/cms/stats')
def get_cms_stats():
    """Statistiques de détection CMS"""
    session = get_session()

    try:
        from sqlalchemy import func

        # Total de sites actifs
        total_sites = session.query(Site).filter(Site.is_active == True).count()

        # Sites avec CMS détecté
        total_with_cms = session.query(Site).filter(
            Site.cms.isnot(None),
            Site.cms != ''
        ).count()

        # Répartition par CMS
        cms_distribution = session.query(
            Site.cms,
            func.count(Site.id).label('count')
        ).filter(
            Site.cms.isnot(None),
            Site.cms != ''
        ).group_by(Site.cms).order_by(func.count(Site.id).desc()).all()

        cms_list = [{'name': cms, 'count': count} for cms, count in cms_distribution]

        # Sites avec email ET CMS
        with_email_and_cms = session.query(Site).filter(
            Site.cms.isnot(None),
            Site.cms != '',
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        return jsonify({
            'total_sites': total_sites,
            'total_with_cms': total_with_cms,
            'pending_detection': total_sites - total_with_cms,
            'detection_rate': round((total_with_cms / total_sites * 100) if total_sites > 0 else 0, 1),
            'cms_distribution': cms_list,
            'with_email_and_cms': with_email_and_cms
        })

    finally:
        session.close()


@app.route('/api/validation/status')
def get_validation_script_status():
    """Vérifier si le script find_any_valid_email.py tourne"""
    import subprocess
    import os
    from datetime import datetime, timedelta

    try:
        # Vérifier si le processus tourne
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )

        is_running = 'find_any_valid_email.py' in result.stdout

        # Récupérer les derniers emails trouvés (dernières 24h)
        session = get_session()
        try:
            yesterday = datetime.utcnow() - timedelta(hours=24)

            # Derniers emails trouvés par le script
            recent_emails = session.query(Site).filter(
                Site.email_source.in_(['any_valid_email', 'generic_validated']),
                Site.email_found_at >= yesterday
            ).order_by(Site.email_found_at.desc()).limit(10).all()

            recent_list = []
            for site in recent_emails:
                recent_list.append({
                    'domain': site.domain,
                    'email': site.emails,
                    'source': site.email_source,
                    'found_at': site.email_found_at.isoformat() if site.email_found_at else None,
                    'deliverable': site.email_deliverable
                })

            # Compter les emails trouvés dans les dernières 24h
            count_24h = session.query(Site).filter(
                Site.email_source.in_(['any_valid_email', 'generic_validated']),
                Site.email_found_at >= yesterday
            ).count()

            return jsonify({
                'is_running': is_running,
                'recent_emails': recent_list,
                'found_last_24h': count_24h
            })
        finally:
            session.close()

    except Exception as e:
        return jsonify({
            'is_running': False,
            'error': str(e),
            'recent_emails': [],
            'found_last_24h': 0
        })


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
    from campaign_database import get_campaign_session, Campaign
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

        # Ajouter le segment_id si fourni et préparer automatiquement
        if 'segment_id' in data and data.get('segment_id'):
            # Utiliser la session du manager pour mettre à jour le segment_id
            campaign_from_manager = manager.campaign_session.query(Campaign).get(campaign.id)
            if campaign_from_manager:
                campaign_from_manager.segment_id = int(data.get('segment_id'))
                manager.campaign_safe_commit(session)

                # Préparer automatiquement la campagne
                try:
                    prepare_result = manager.prepare_campaign(campaign.id)
                    logger.info(f"Campagne {campaign.id} préparée automatiquement: {prepare_result['total_recipients']} destinataires")
                except Exception as e:
                    logger.error(f"Erreur lors de la préparation automatique: {e}")

                # Rafraîchir pour obtenir les dernières données
                manager.campaign_session.expire(campaign_from_manager)
                manager.campaign_session.refresh(campaign_from_manager)
                result = campaign_from_manager.to_dict()
                return jsonify(result), 201

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
    from campaign_manager import CampaignManager

    data = request.json or {}
    limit = data.get('limit', None)

    try:
        manager = CampaignManager()
        stats = manager.run_campaign(campaign_id, limit=limit)

        return jsonify({
            'success': True,
            'sent': stats['sent'],
            'failed': stats['failed'],
            'remaining': stats['remaining'],
            'duration': stats['duration']
        })
    except Exception as e:
        logger.error(f"Erreur campagne: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'sent': 0
        }), 500


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
        safe_commit(session)

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
        safe_commit(session)

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
        safe_commit(session)

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


@app.route('/api/campaigns/<int:campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    """Supprimer une campagne"""
    from campaign_database import get_campaign_session, Campaign, CampaignEmail

    session = get_campaign_session()
    try:
        campaign = session.query(Campaign).get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campagne non trouvée'}), 404

        campaign_name = campaign.name

        # Supprimer tous les emails de la campagne
        session.query(CampaignEmail).filter(
            CampaignEmail.campaign_id == campaign_id
        ).delete()

        # Supprimer la campagne
        session.delete(campaign)
        safe_commit(session)

        logger.info(f"🗑️  Campagne '{campaign_name}' (ID: {campaign_id}) supprimée")

        return jsonify({
            'success': True,
            'campaign_id': campaign_id,
            'message': f"Campagne '{campaign_name}' supprimée avec succès"
        })

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur lors de la suppression de la campagne {campaign_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ============================================================================
# ROUTES - CAMPAIGN REPLIES
# ============================================================================

@app.route('/replies')
def replies_page():
    """Page de gestion des réponses"""
    return render_template('replies.html')


@app.route('/api/replies', methods=['GET'])
def get_replies():
    """Récupérer les réponses avec filtres"""
    from campaign_database import get_campaign_session, CampaignReply, Campaign, ReplyStatus, ReplySentiment

    session = get_campaign_session()

    try:
        # Paramètres de pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        # Filtres
        status_filter = request.args.get('status', '')
        sentiment_filter = request.args.get('sentiment', '')
        campaign_id = request.args.get('campaign_id', type=int)
        search = request.args.get('search', '').strip()

        # Query de base
        query = session.query(CampaignReply)

        # Appliquer les filtres
        if status_filter:
            query = query.filter(CampaignReply.status == ReplyStatus[status_filter.upper()])

        if sentiment_filter:
            query = query.filter(CampaignReply.sentiment == ReplySentiment[sentiment_filter.upper()])

        if campaign_id:
            query = query.filter(CampaignReply.campaign_id == campaign_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (CampaignReply.from_email.like(search_pattern)) |
                (CampaignReply.subject.like(search_pattern)) |
                (CampaignReply.body_text.like(search_pattern))
            )

        # Trier par date de réception (plus récent en premier)
        query = query.order_by(CampaignReply.received_at.desc())

        # Pagination
        total = query.count()
        replies = query.limit(per_page).offset((page - 1) * per_page).all()

        # Enrichir avec le nom de la campagne
        replies_data = []
        for reply in replies:
            reply_dict = reply.to_dict()

            if reply.campaign_id:
                campaign = session.query(Campaign).get(reply.campaign_id)
                if campaign:
                    reply_dict['campaign_name'] = campaign.name

            replies_data.append(reply_dict)

        return jsonify({
            'replies': replies_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        logger.error(f"Erreur récupération réponses: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/replies/<int:reply_id>', methods=['GET'])
def get_reply(reply_id):
    """Récupérer une réponse spécifique"""
    from campaign_database import get_campaign_session, CampaignReply, Campaign

    session = get_campaign_session()

    try:
        reply = session.query(CampaignReply).get(reply_id)

        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        reply_dict = reply.to_dict()

        # Enrichir avec info campagne
        if reply.campaign_id:
            campaign = session.query(Campaign).get(reply.campaign_id)
            if campaign:
                reply_dict['campaign_name'] = campaign.name

        return jsonify(reply_dict)

    except Exception as e:
        logger.error(f"Erreur récupération réponse {reply_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/replies/<int:reply_id>/mark-read', methods=['POST'])
def mark_reply_read(reply_id):
    """Marquer une réponse comme lue"""
    from campaign_database import get_campaign_session, CampaignReply, ReplyStatus

    session = get_campaign_session()

    try:
        reply = session.query(CampaignReply).get(reply_id)

        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        reply.status = ReplyStatus.READ
        reply.read_at = datetime.utcnow()
        safe_commit(session)

        return jsonify({'success': True})

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur marquage lu {reply_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/replies/<int:reply_id>/send-reply', methods=['POST'])
def send_reply_to_email(reply_id):
    """Envoyer une réponse"""
    from campaign_database import get_campaign_session, CampaignReply, ReplyStatus
    from ses_manager import SESManager

    data = request.json
    reply_subject = data.get('subject')
    reply_body = data.get('body')

    if not reply_subject or not reply_body:
        return jsonify({'error': 'Sujet et corps requis'}), 400

    session = get_campaign_session()

    try:
        reply = session.query(CampaignReply).get(reply_id)

        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        # Envoyer via SES
        ses = SESManager()

        # Email d'envoi des réponses
        from_email = "david@perfect-cocon-seo.fr"

        result = ses.send_email(
            to_email=reply.from_email,
            subject=reply_subject,
            html_body=reply_body,
            text_body=reply_body,
            reply_to=from_email
        )

        if result['success']:
            # Mettre à jour la réponse
            reply.status = ReplyStatus.REPLIED
            reply.replied_at = datetime.utcnow()
            reply.our_reply_subject = reply_subject
            reply.our_reply_body = reply_body
            reply.our_reply_sent_at = datetime.utcnow()
            safe_commit(session)

            return jsonify({
                'success': True,
                'message': 'Réponse envoyée avec succès'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erreur inconnue')
            }), 500

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur envoi réponse {reply_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/replies/<int:reply_id>/update-status', methods=['POST'])
def update_reply_status(reply_id):
    """Mettre à jour le statut d'une réponse"""
    from campaign_database import get_campaign_session, CampaignReply, ReplyStatus

    data = request.json
    new_status = data.get('status')

    if not new_status:
        return jsonify({'error': 'Statut requis'}), 400

    session = get_campaign_session()

    try:
        reply = session.query(CampaignReply).get(reply_id)

        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        reply.status = ReplyStatus[new_status.upper()]
        safe_commit(session)

        return jsonify({'success': True})

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur mise à jour statut {reply_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/replies/stats', methods=['GET'])
def get_replies_stats():
    """Statistiques des réponses"""
    from campaign_database import get_campaign_session, CampaignReply, ReplyStatus, ReplySentiment
    from sqlalchemy import func

    session = get_campaign_session()

    try:
        # Total réponses
        total = session.query(CampaignReply).count()

        # Par statut
        by_status = {}
        for status in ReplyStatus:
            count = session.query(CampaignReply).filter(
                CampaignReply.status == status
            ).count()
            by_status[status.value] = count

        # Par sentiment
        by_sentiment = {}
        for sentiment in ReplySentiment:
            count = session.query(CampaignReply).filter(
                CampaignReply.sentiment == sentiment
            ).count()
            by_sentiment[sentiment.value] = count

        # Nouvelles réponses (non lues)
        new_count = by_status.get('new', 0)

        return jsonify({
            'total': total,
            'new': new_count,
            'by_status': by_status,
            'by_sentiment': by_sentiment
        })

    except Exception as e:
        logger.error(f"Erreur stats réponses: {e}")
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

        # Incrémenter le compteur de la campagne
        if campaign_id:
            campaign = campaign_session.query(Campaign).get(int(campaign_id))
            if campaign:
                campaign.emails_unsubscribed = (campaign.emails_unsubscribed or 0) + 1

        safe_commit(campaign_session)

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
# ROUTES - TRACKING (OPEN & CLICK)
# ============================================================================

@app.route('/track/open/<int:email_id>')
def track_open(email_id):
    """
    Tracking pixel pour les ouvertures d'emails
    Retourne une image GIF transparente 1x1 pixel
    """
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    campaign_session = get_campaign_session()

    try:
        # Trouver l'email
        campaign_email = campaign_session.query(CampaignEmail).filter(
            CampaignEmail.id == email_id
        ).first()

        if campaign_email:
            # Mettre à jour le statut si c'est la première ouverture
            if campaign_email.status == EmailStatus.DELIVERED:
                campaign_email.status = EmailStatus.OPENED

            # Enregistrer l'ouverture
            if not campaign_email.opened_at:
                campaign_email.opened_at = datetime.utcnow()

                # Incrémenter le compteur de la campagne (première ouverture uniquement)
                if campaign_email.campaign_id:
                    campaign = campaign_session.query(Campaign).get(campaign_email.campaign_id)
                    if campaign:
                        campaign.emails_opened += 1
                        logger.info(f"📧 Open tracked: Campaign '{campaign.name}', Email ID {email_id}")

            # Incrémenter le compteur d'ouvertures de l'email
            campaign_email.open_count += 1

            # Trigger scenario events if applicable
            if campaign_email.sequence_id:
                try:
                    from scenario_orchestrator import ScenarioOrchestrator
                    orchestrator = ScenarioOrchestrator()
                    orchestrator.handle_event('opened', campaign_email)
                    orchestrator.close()
                except Exception as e:
                    logger.error(f"❌ Erreur scenario event: {e}")

            safe_commit(campaign_session)

    except Exception as e:
        campaign_session.rollback()
        logger.error(f"❌ Erreur tracking open: {e}")
    finally:
        campaign_session.close()

    # Retourner une image GIF transparente 1x1 pixel
    from flask import Response
    import base64

    # GIF transparent 1x1 pixel
    gif_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

    response = Response(gif_data, mimetype='image/gif')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


@app.route('/track/click/<int:email_id>')
def track_click(email_id):
    """
    Tracking des clics sur les liens
    Redirige vers l'URL originale après avoir enregistré le clic
    """
    from campaign_database import CampaignEmail, Campaign, EmailStatus

    # Récupérer l'URL de destination
    url = request.args.get('url', '')

    if not url:
        return "URL manquante", 400

    campaign_session = get_campaign_session()

    try:
        # Trouver l'email
        campaign_email = campaign_session.query(CampaignEmail).filter(
            CampaignEmail.id == email_id
        ).first()

        if campaign_email:
            # Mettre à jour le statut
            if campaign_email.status in [EmailStatus.DELIVERED, EmailStatus.OPENED]:
                campaign_email.status = EmailStatus.CLICKED

            # Enregistrer le clic
            if not campaign_email.clicked_at:
                campaign_email.clicked_at = datetime.utcnow()

                # Incrémenter le compteur de la campagne (premier clic uniquement)
                if campaign_email.campaign_id:
                    campaign = campaign_session.query(Campaign).get(campaign_email.campaign_id)
                    if campaign:
                        campaign.emails_clicked += 1
                        logger.info(f"🖱️  Click tracked: Campaign '{campaign.name}', Email ID {email_id}, URL: {url}")

            # Incrémenter le compteur de clics de l'email
            campaign_email.click_count += 1

            # Trigger scenario events if applicable
            if campaign_email.sequence_id:
                try:
                    from scenario_orchestrator import ScenarioOrchestrator
                    orchestrator = ScenarioOrchestrator()
                    orchestrator.handle_event('clicked', campaign_email)
                    orchestrator.close()
                except Exception as e:
                    logger.error(f"❌ Erreur scenario event: {e}")

            safe_commit(campaign_session)

    except Exception as e:
        campaign_session.rollback()
        logger.error(f"❌ Erreur tracking click: {e}")
    finally:
        campaign_session.close()

    # Rediriger vers l'URL originale
    return redirect(url)


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

            # Log pour debug
            logger.info(f"📬 Webhook: Type={notification_type}, Message ID={message.get('mail', {}).get('messageId', 'N/A')}")

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

                campaign_safe_commit(session)
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
    from campaign_database import CampaignEmail, Campaign, EmailStatus, EmailBlacklist

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
        bounce_type_value = 'hard' if bounce_type == 'Permanent' else 'soft'
        campaign_email.bounce_type = bounce_type_value
        bounce_reason = bounce.get('bouncedRecipients', [{}])[0].get('diagnosticCode', '')
        campaign_email.bounce_reason = bounce_reason
        campaign_email.error_message = bounce_reason

        # Ajouter l'email à la blacklist (hard et soft)
        blacklist_entry = session.query(EmailBlacklist).filter(
            EmailBlacklist.email == campaign_email.to_email
        ).first()

        if blacklist_entry:
            # Mettre à jour l'entrée existante
            blacklist_entry.bounce_count += 1
            blacklist_entry.last_bounced_at = datetime.utcnow()
            blacklist_entry.bounce_type = bounce_type_value
            blacklist_entry.bounce_reason = bounce_reason
            blacklist_entry.campaign_id = campaign_email.campaign_id
            logger.info(f"  🔄 Blacklist mise à jour pour {campaign_email.to_email} (count: {blacklist_entry.bounce_count})")
        else:
            # Créer une nouvelle entrée
            blacklist_entry = EmailBlacklist(
                email=campaign_email.to_email,
                bounce_type=bounce_type_value,
                bounce_reason=bounce_reason,
                campaign_id=campaign_email.campaign_id
            )
            session.add(blacklist_entry)
            logger.info(f"  🚫 Email {campaign_email.to_email} ajouté à la blacklist ({bounce_type_value})")

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

            # Incrémenter le compteur de désinscrits de la campagne
            if campaign:
                campaign.emails_unsubscribed = (campaign.emails_unsubscribed or 0) + 1

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
            if campaign_email.campaign_id:
                campaign = session.query(Campaign).get(campaign_email.campaign_id)
                if campaign:
                    campaign.emails_opened += 1

        campaign_email.open_count += 1

        # Déclencher les suivis de scénario si applicable
        if campaign_email.sequence_id:
            try:
                from scenario_orchestrator import ScenarioOrchestrator
                from campaign_database import StepTemplateVariant

                # Mettre à jour les stats de la variante A/B si applicable
                if campaign_email.variant_id:
                    variant = session.query(StepTemplateVariant).get(campaign_email.variant_id)
                    if variant:
                        variant.opened_count += 1
                        logger.info(f"✅ Stats A/B: variante '{variant.variant_name}' - ouverture enregistrée")

                orchestrator = ScenarioOrchestrator()
                orchestrator.handle_event('opened', campaign_email)
                orchestrator.close()
                logger.info(f"✅ Événement 'opened' traité pour email {campaign_email.id}")
            except Exception as e:
                logger.error(f"❌ Erreur traitement événement scenario: {e}", exc_info=True)


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
            if campaign_email.campaign_id:
                campaign = session.query(Campaign).get(campaign_email.campaign_id)
                if campaign:
                    campaign.emails_clicked += 1

        campaign_email.click_count += 1

        # Déclencher les suivis de scénario si applicable
        if campaign_email.sequence_id:
            try:
                from scenario_orchestrator import ScenarioOrchestrator
                from campaign_database import StepTemplateVariant

                # Mettre à jour les stats de la variante A/B si applicable
                if campaign_email.variant_id:
                    variant = session.query(StepTemplateVariant).get(campaign_email.variant_id)
                    if variant:
                        variant.clicked_count += 1
                        logger.info(f"✅ Stats A/B: variante '{variant.variant_name}' - clic enregistré")

                orchestrator = ScenarioOrchestrator()
                orchestrator.handle_event('clicked', campaign_email)
                orchestrator.close()
                logger.info(f"✅ Événement 'clicked' traité pour email {campaign_email.id}")
            except Exception as e:
                logger.error(f"❌ Erreur traitement événement scenario: {e}", exc_info=True)


@app.route('/api/scripts-progress')
def get_scripts_progress():
    """Obtenir la progression des scripts d'extraction"""
    session = get_session()

    try:
        # Total de sites actifs
        total_sites = session.query(Site).filter(Site.is_active == True).count()

        # Sites avec email trouvé
        sites_with_email = session.query(Site).filter(
            Site.email_checked == True,
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Sites avec email vérifié (checked)
        sites_email_checked = session.query(Site).filter(
            Site.email_checked == True
        ).count()

        # Sites avec SIRET trouvé
        sites_with_siret = session.query(Site).filter(
            Site.siret_checked == True,
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ'
        ).count()

        # Sites avec SIRET vérifié (checked)
        sites_siret_checked = session.query(Site).filter(
            Site.siret_checked == True
        ).count()

        # Sites avec leaders trouvés
        sites_with_leaders = session.query(Site).filter(
            Site.leaders_checked == True,
            Site.leaders.isnot(None),
            Site.leaders != '',
            Site.leaders != 'NON TROUVÉ'
        ).count()

        # Sites avec leaders vérifié (checked)
        sites_leaders_checked = session.query(Site).filter(
            Site.leaders_checked == True
        ).count()

        # Sites avec CMS détecté (exclure NONE)
        sites_with_cms = session.query(Site).filter(
            Site.cms.isnot(None),
            Site.cms != '',
            Site.cms != 'NONE'
        ).count()

        # Sites acheteurs (buyers)
        sites_buyers = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.purchased_from != ''
        ).count()

        # Stats Guessing Emails (sites sans email qui n'ont pas encore été testés avec guessing)
        sites_without_email = session.query(Site).filter(
            Site.is_active == True,
            Site.blacklisted == False,
            (Site.emails == "NO EMAIL FOUND") | (Site.emails == None) | (Site.emails == "")
        ).count()

        # Sites testés avec guessing (any_valid dans email_source)
        sites_guessing_tested = session.query(Site).filter(
            Site.email_source.like('%any_valid%')
        ).count()

        # Sites où guessing a trouvé un email
        sites_guessing_found = session.query(Site).filter(
            Site.email_source == 'any_valid_email'
        ).count()

        # Sites où guessing générique a trouvé un email
        sites_generic_found = session.query(Site).filter(
            Site.email_source == 'generic_validated'
        ).count()

        # Total à traiter par guessing = sites sans email qui n'ont pas encore été testés
        sites_guessing_pending = session.query(Site).filter(
            Site.is_active == True,
            Site.blacklisted == False,
            (Site.emails == "NO EMAIL FOUND") | (Site.emails == None) | (Site.emails == ""),
            ~Site.email_source.like('%any_valid%')
        ).count()

        # Sites avec contact extrait
        sites_with_contacts = session.query(Site).filter(
            Site.contact_firstname.isnot(None),
            Site.contact_lastname.isnot(None)
        ).count()

        # Sites avec email qui peuvent avoir un contact extrait
        sites_with_email_total = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND',
            Site.is_active == True
        ).count()

        # Sites en attente d'extraction contact
        sites_contacts_pending = sites_with_email_total - sites_with_contacts

        # Calculer les pourcentages
        email_progress = round((sites_email_checked / total_sites * 100) if total_sites > 0 else 0, 1)
        siret_progress = round((sites_siret_checked / total_sites * 100) if total_sites > 0 else 0, 1)
        leaders_progress = round((sites_leaders_checked / total_sites * 100) if total_sites > 0 else 0, 1)
        cms_progress = round((sites_with_cms / total_sites * 100) if total_sites > 0 else 0, 1)
        contacts_progress = round((sites_with_contacts / sites_with_email_total * 100) if sites_with_email_total > 0 else 0, 1)

        # Progression guessing = sites testés / (sites testés + sites en attente)
        guessing_total = sites_guessing_tested + sites_guessing_pending
        guessing_progress = round((sites_guessing_tested / guessing_total * 100) if guessing_total > 0 else 0, 1)

        return jsonify({
            'total_sites': total_sites,
            'email': {
                'checked': sites_email_checked,
                'found': sites_with_email,
                'progress': email_progress,
                'pending': total_sites - sites_email_checked
            },
            'siret': {
                'checked': sites_siret_checked,
                'found': sites_with_siret,
                'progress': siret_progress,
                'pending': total_sites - sites_siret_checked
            },
            'leaders': {
                'checked': sites_leaders_checked,
                'found': sites_with_leaders,
                'progress': leaders_progress,
                'pending': total_sites - sites_leaders_checked
            },
            'cms': {
                'detected': sites_with_cms,
                'progress': cms_progress,
                'pending': total_sites - sites_with_cms
            },
            'buyers': {
                'found': sites_buyers
            },
            'guessing': {
                'tested': sites_guessing_tested,
                'found': sites_guessing_found + sites_generic_found,
                'found_on_site': sites_guessing_found,
                'generic_validated': sites_generic_found,
                'pending': sites_guessing_pending,
                'progress': guessing_progress,
                'total_without_email': sites_without_email
            },
            'contacts': {
                'extracted': sites_with_contacts,
                'total_with_email': sites_with_email_total,
                'pending': sites_contacts_pending,
                'progress': contacts_progress
            }
        })

    finally:
        session.close()


@app.route('/api/sync-campaign-stats', methods=['POST'])
def sync_campaign_stats_api():
    """Synchroniser les statistiques des campagnes"""
    import subprocess
    try:
        # Lancer le script de synchronisation
        result = subprocess.run(
            ['python3', 'sync_campaign_stats.py', '--quiet'],
            cwd='/var/www/Scrap_Email',
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Récupérer les statistiques après sync
            from sync_campaign_stats import get_overall_stats
            stats = get_overall_stats()

            return jsonify({
                'success': True,
                'message': 'Statistiques synchronisées avec succès',
                'stats': stats
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr or 'Erreur inconnue'
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Timeout lors de la synchronisation'
        }), 500
    except Exception as e:
        logger.error(f"Erreur sync campaign stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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

    app.run(debug=debug_mode, host=host, port=port, threaded=True)
