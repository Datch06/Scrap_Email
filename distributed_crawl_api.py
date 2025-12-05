#!/usr/bin/env python3
"""
API de coordination pour le crawl distribué

Ce module fournit les endpoints API pour coordonner les workers de crawl
déployés sur plusieurs serveurs distants.

Endpoints:
- GET /api/crawl/task : Obtenir un batch de sites à crawler
- POST /api/crawl/result : Soumettre les résultats d'un crawl
- POST /api/crawl/heartbeat : Signal de vie d'un worker
- GET /api/crawl/workers : Liste des workers actifs
- GET /api/crawl/stats : Statistiques globales du crawl distribué
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request
from database import get_session, Site, safe_commit
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Blueprint Flask pour les routes de crawl distribué
crawl_api = Blueprint('crawl_api', __name__)

# Fichier de suivi des workers
WORKERS_FILE = Path('/var/www/Scrap_Email/crawl_workers.json')
DAILY_PAGES_FILE = Path('/var/www/Scrap_Email/crawl_daily_pages.json')
WORKER_TIMEOUT = 600  # 10 minutes sans heartbeat = worker considéré comme mort (heartbeat toutes les 30s)


def load_daily_pages():
    """Charger les stats de pages crawlées par jour (fichier JSON ou base de données)"""
    # Essayer le fichier JSON d'abord
    if DAILY_PAGES_FILE.exists():
        try:
            with open(DAILY_PAGES_FILE, 'r') as f:
                data = json.load(f)
                if data:
                    return data
        except:
            pass

    # Si fichier vide ou corrompu, charger depuis la base de données
    try:
        from sqlalchemy import text
        session = get_session()
        result = session.execute(text("""
            SELECT date, pages_crawled, sellers_crawled, workers_data
            FROM crawl_daily_stats
            ORDER BY date DESC
            LIMIT 30
        """))
        data = {}
        for row in result:
            date_str = row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0])
            workers = json.loads(row[3]) if row[3] else {}
            data[date_str] = {
                'total': row[1] or 0,
                'workers': workers
            }
        session.close()
        if data:
            # Resauvegarder dans le fichier JSON
            with open(DAILY_PAGES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            return data
    except Exception as e:
        logger.error(f"Erreur chargement BDD stats: {e}")

    return {}


def save_daily_pages(data):
    """Sauvegarder les stats de pages crawlées par jour (fichier JSON + base de données)"""
    # Sauvegarder dans le fichier JSON (compatibilité)
    with open(DAILY_PAGES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    # Sauvegarder aussi en base de données pour persistance
    try:
        from sqlalchemy import text
        session = get_session()
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if today in data:
            day_data = data[today]
            pages = day_data.get('total', 0) if isinstance(day_data, dict) else day_data
            workers = day_data.get('workers', {}) if isinstance(day_data, dict) else {}
            sellers = sum(w.get('sellers', 0) for w in workers.values()) if workers else 0

            session.execute(text("""
                INSERT INTO crawl_daily_stats (date, pages_crawled, sellers_crawled, workers_data, updated_at)
                VALUES (:date, :pages, :sellers, :workers, CURRENT_TIMESTAMP)
                ON CONFLICT (date) DO UPDATE SET
                    pages_crawled = EXCLUDED.pages_crawled,
                    sellers_crawled = EXCLUDED.sellers_crawled,
                    workers_data = EXCLUDED.workers_data,
                    updated_at = CURRENT_TIMESTAMP
            """), {
                'date': today,
                'pages': pages,
                'sellers': sellers,
                'workers': json.dumps(workers)
            })
            session.commit()
        session.close()
    except Exception as e:
        logger.error(f"Erreur sauvegarde BDD stats: {e}")


def add_pages_crawled(pages_count, worker_id='unknown'):
    """Ajouter des pages au compteur du jour et par worker"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    data = load_daily_pages()

    # Structure: { "2025-12-02": { "total": 1000, "workers": { "worker_xxx": { "pages": 500, "sellers": 10 } } } }
    if today not in data:
        data[today] = {'total': 0, 'workers': {}}

    # Migration: ancien format (juste un nombre) vers nouveau format
    if isinstance(data[today], int):
        data[today] = {'total': data[today], 'workers': {}}

    data[today]['total'] = data[today].get('total', 0) + pages_count

    if worker_id not in data[today]['workers']:
        data[today]['workers'][worker_id] = {'pages': 0, 'sellers': 0}

    data[today]['workers'][worker_id]['pages'] += pages_count
    data[today]['workers'][worker_id]['sellers'] += 1

    save_daily_pages(data)

# Domaines blacklistés (gouvernementaux, etc.)
BLACKLISTED_DOMAINS = {
    'cnil.fr', 'gouv.fr', 'diplomatie.gouv.fr', 'education.gouv.fr',
    'economie.gouv.fr', 'interieur.gouv.fr', 'service-public.fr',
    'legifrance.gouv.fr', 'senat.fr', 'assemblee-nationale.fr'
}


def load_blacklist():
    """Charger la blacklist depuis le fichier"""
    blacklist = set(BLACKLISTED_DOMAINS)
    blacklist_file = Path('/var/www/Scrap_Email/blacklist.txt')
    if blacklist_file.exists():
        with open(blacklist_file, 'r') as f:
            blacklist.update(line.strip() for line in f if line.strip())
    return blacklist


def load_workers():
    """Charger les informations des workers"""
    if WORKERS_FILE.exists():
        try:
            with open(WORKERS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'workers': {}, 'last_update': None}


def save_workers(data):
    """Sauvegarder les informations des workers"""
    data['last_update'] = datetime.utcnow().isoformat()
    with open(WORKERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def is_worker_alive(worker_data):
    """Vérifier si un worker est encore actif"""
    if not worker_data.get('last_heartbeat'):
        return False
    last_beat = datetime.fromisoformat(worker_data['last_heartbeat'])
    return (datetime.utcnow() - last_beat).total_seconds() < WORKER_TIMEOUT


@crawl_api.route('/api/crawl/task', methods=['GET'])
def get_crawl_task():
    """
    Obtenir un batch de sites à crawler

    Query params:
    - worker_id: Identifiant unique du worker
    - batch_size: Nombre de sites à récupérer (défaut: 10)

    Returns:
        Liste de sites avec leurs URLs
    """
    worker_id = request.args.get('worker_id', 'unknown')
    batch_size = int(request.args.get('batch_size', 10))

    # Limiter la taille du batch
    batch_size = min(batch_size, 50)

    # Charger la blacklist
    blacklist = load_blacklist()

    session = get_session()
    try:
        # Utiliser FOR UPDATE SKIP LOCKED pour éviter les race conditions
        # Chaque worker verrouille atomiquement les lignes qu'il sélectionne
        from sqlalchemy import case, text

        # Créer un ordre de priorité: .fr = 0 (prioritaire), autres = 1
        priority_order = case(
            (Site.domain.like('%.fr'), 0),
            else_=1
        )

        # Sites assignés récemment (dans les 10 dernières minutes) sont exclus
        lock_threshold = datetime.utcnow() - timedelta(minutes=10)

        # FOR UPDATE SKIP LOCKED: verrouille les lignes et skip celles déjà verrouillées
        # Cela évite les doublons entre workers même en cas de requêtes simultanées
        sites_raw = session.query(Site).filter(
            Site.purchased_from.is_(None),
            Site.backlinks_crawled == False,
            Site.blacklisted == False,
            (Site.updated_at.is_(None)) | (Site.updated_at < lock_threshold)
        ).order_by(priority_order, Site.id).limit(batch_size * 3).with_for_update(skip_locked=True).all()

        # Filtrer la blacklist côté Python (beaucoup plus rapide)
        sites = []
        for site in sites_raw:
            if site.domain not in blacklist:
                # Vérifier aussi les suffixes (ex: .gouv.fr)
                is_blacklisted = False
                for bl_domain in blacklist:
                    if site.domain.endswith('.' + bl_domain):
                        is_blacklisted = True
                        break
                if not is_blacklisted:
                    sites.append(site)
                    if len(sites) >= batch_size:
                        break

        if not sites:
            session.commit()  # Libérer les locks
            return jsonify({
                'status': 'no_tasks',
                'message': 'Aucun site à crawler',
                'sites': []
            })

        now = datetime.utcnow()

        # Préparer les données à retourner ET marquer comme "en cours" atomiquement
        tasks = []
        for site in sites:
            # Construire l'URL du site
            if site.source_url and site.source_url.startswith('http'):
                url = site.source_url
            else:
                url = f"https://{site.domain}"

            tasks.append({
                'id': site.id,
                'domain': site.domain,
                'url': url
            })

            # Mettre à jour updated_at pour indiquer qu'on travaille dessus
            site.updated_at = now

        safe_commit(session)  # Le commit libère les locks

        # Logger l'attribution
        logger.info(f"🚀 Worker {worker_id}: {len(tasks)} tâches attribuées")

        # Mettre à jour les stats du worker
        workers_data = load_workers()
        if worker_id not in workers_data['workers']:
            workers_data['workers'][worker_id] = {
                'first_seen': datetime.utcnow().isoformat(),
                'tasks_assigned': 0,
                'tasks_completed': 0,
                'buyers_found': 0,
                'emails_found': 0,
                'errors': 0
            }

        workers_data['workers'][worker_id]['tasks_assigned'] += len(tasks)
        workers_data['workers'][worker_id]['last_task_at'] = datetime.utcnow().isoformat()
        workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
        save_workers(workers_data)

        return jsonify({
            'status': 'ok',
            'worker_id': worker_id,
            'batch_size': len(tasks),
            'sites': tasks
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_crawl_task: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/result', methods=['POST'])
def submit_crawl_result():
    """
    Soumettre les résultats d'un crawl

    Body JSON:
    {
        "worker_id": "worker_192.99.44.191",
        "site_id": 12345,
        "domain": "example.fr",
        "buyers": [
            {"domain": "buyer1.fr", "email": "contact@buyer1.fr"},
            {"domain": "buyer2.fr", "email": null}
        ],
        "pages_crawled": 150,
        "error": null
    }
    """
    data = request.get_json()

    worker_id = data.get('worker_id', 'unknown')
    site_id = data.get('site_id')
    domain = data.get('domain')
    buyers = data.get('buyers', [])
    pages_crawled = data.get('pages_crawled', 0)
    error = data.get('error')
    is_intermediate = data.get('is_intermediate', False)  # Batch intermédiaire ou résultat final

    if not site_id or not domain:
        return jsonify({'error': 'site_id et domain requis'}), 400

    session = get_session()
    try:
        # Marquer le site vendeur comme crawlé (seulement si c'est le résultat final)
        seller = session.query(Site).filter_by(id=site_id).first()
        if seller and not is_intermediate:
            seller.backlinks_crawled = True
            seller.backlinks_crawled_at = datetime.utcnow()
            if error:
                seller.last_error = error

        # Traiter les acheteurs trouvés
        new_buyers = 0
        emails_found = 0

        for buyer_data in buyers:
            buyer_domain = buyer_data.get('domain')
            buyer_email = buyer_data.get('email')

            if not buyer_domain:
                continue

            # Vérifier si le buyer existe déjà
            existing = session.query(Site).filter_by(domain=buyer_domain).first()

            if existing:
                # Mettre à jour purchased_from si pas défini
                if not existing.purchased_from:
                    existing.purchased_from = domain
                # Mettre à jour l'email si trouvé et pas déjà présent
                if buyer_email and not existing.emails:
                    existing.emails = buyer_email
                    existing.email_source = 'distributed_crawl'
                    existing.email_found_at = datetime.utcnow()
                    emails_found += 1
            else:
                # Créer le nouveau site buyer
                new_site = Site(
                    domain=buyer_domain,
                    source_url=f"https://{domain}",
                    purchased_from=domain,
                    purchased_at=datetime.utcnow(),
                    emails=buyer_email,
                    email_source='distributed_crawl' if buyer_email else None,
                    email_found_at=datetime.utcnow() if buyer_email else None
                )
                session.add(new_site)
                new_buyers += 1
                if buyer_email:
                    emails_found += 1

        safe_commit(session)

        # Mettre à jour les stats du worker
        workers_data = load_workers()
        if worker_id in workers_data['workers']:
            # tasks_completed seulement pour les résultats finaux
            if not is_intermediate:
                workers_data['workers'][worker_id]['tasks_completed'] += 1
            workers_data['workers'][worker_id]['buyers_found'] += len(buyers)
            workers_data['workers'][worker_id]['emails_found'] += emails_found
            if error:
                workers_data['workers'][worker_id]['errors'] += 1
            workers_data['workers'][worker_id]['last_result_at'] = datetime.utcnow().isoformat()
            workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
            save_workers(workers_data)

        # Enregistrer les pages crawlées dans les stats journalières
        if pages_crawled > 0:
            add_pages_crawled(pages_crawled, worker_id)

        if is_intermediate:
            logger.info(f"📤 Worker {worker_id}: {domain} batch - {pages_crawled} pages")
        else:
            logger.info(f"✅ Worker {worker_id}: {domain} terminé - {pages_crawled} pages, {len(buyers)} buyers, {emails_found} emails")

        return jsonify({
            'status': 'ok',
            'new_buyers': new_buyers,
            'emails_found': emails_found,
            'pages_crawled': pages_crawled
        })

    except Exception as e:
        logger.error(f"❌ Erreur submit_crawl_result: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/buyer', methods=['POST'])
def submit_buyer_incremental():
    """
    Upload incrémental d'un acheteur trouvé pendant le crawl.

    Permet de sauvegarder immédiatement chaque acheteur/email trouvé
    au lieu d'attendre la fin du crawl du site complet.

    Body JSON:
    {
        "worker_id": "worker_192.99.44.191",
        "site_id": 12345,
        "seller_domain": "vendeur.fr",
        "buyer_domain": "acheteur.fr",
        "email": "contact@acheteur.fr"  // optionnel
    }
    """
    data = request.get_json()

    worker_id = data.get('worker_id', 'unknown')
    site_id = data.get('site_id')
    seller_domain = data.get('seller_domain')
    buyer_domain = data.get('buyer_domain')
    buyer_email = data.get('email')

    if not buyer_domain or not seller_domain:
        return jsonify({'error': 'seller_domain et buyer_domain requis'}), 400

    session = get_session()
    try:
        # Vérifier si le buyer existe déjà
        existing = session.query(Site).filter_by(domain=buyer_domain).first()

        new_buyer = False
        email_added = False

        if existing:
            # Mettre à jour purchased_from si pas défini
            if not existing.purchased_from:
                existing.purchased_from = seller_domain
                existing.purchased_at = datetime.utcnow()
            # Mettre à jour l'email si trouvé et pas déjà présent
            if buyer_email and not existing.emails:
                existing.emails = buyer_email
                existing.email_source = 'distributed_crawl'
                existing.email_found_at = datetime.utcnow()
                email_added = True
        else:
            # Créer le nouveau site buyer
            new_site = Site(
                domain=buyer_domain,
                source_url=f"https://{seller_domain}",
                purchased_from=seller_domain,
                purchased_at=datetime.utcnow(),
                emails=buyer_email,
                email_source='distributed_crawl' if buyer_email else None,
                email_found_at=datetime.utcnow() if buyer_email else None
            )
            session.add(new_site)
            new_buyer = True
            if buyer_email:
                email_added = True

        safe_commit(session)

        # Mettre à jour les stats du worker (si nouveau buyer ou email)
        if new_buyer or email_added:
            workers_data = load_workers()
            if worker_id in workers_data['workers']:
                if new_buyer:
                    workers_data['workers'][worker_id]['buyers_found'] = \
                        workers_data['workers'][worker_id].get('buyers_found', 0) + 1
                if email_added:
                    workers_data['workers'][worker_id]['emails_found'] = \
                        workers_data['workers'][worker_id].get('emails_found', 0) + 1
                workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
                save_workers(workers_data)

        return jsonify({
            'status': 'ok',
            'new_buyer': new_buyer,
            'email_added': email_added
        })

    except Exception as e:
        logger.error(f"❌ Erreur submit_buyer_incremental: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/buyers_batch', methods=['POST'])
def submit_buyers_batch():
    """
    Upload d'un batch d'acheteurs en une seule requête.
    Plus efficace que /api/crawl/buyer pour plusieurs acheteurs.

    Body JSON:
    {
        "worker_id": "worker_192.99.44.191",
        "site_id": 12345,
        "seller_domain": "vendeur.fr",
        "buyers": [
            {"domain": "acheteur1.fr", "email": "contact@acheteur1.fr"},
            {"domain": "acheteur2.fr", "email": null}
        ]
    }
    """
    data = request.get_json()

    worker_id = data.get('worker_id', 'unknown')
    seller_domain = data.get('seller_domain')
    buyers = data.get('buyers', [])

    if not seller_domain or not buyers:
        return jsonify({'error': 'seller_domain et buyers requis'}), 400

    session = get_session()
    try:
        new_buyers = 0
        emails_added = 0

        for buyer_data in buyers:
            buyer_domain = buyer_data.get('domain')
            buyer_email = buyer_data.get('email')

            if not buyer_domain:
                continue

            # Vérifier si le buyer existe déjà
            existing = session.query(Site).filter_by(domain=buyer_domain).first()

            if existing:
                if not existing.purchased_from:
                    existing.purchased_from = seller_domain
                    existing.purchased_at = datetime.utcnow()
                if buyer_email and not existing.emails:
                    existing.emails = buyer_email
                    existing.email_source = 'distributed_crawl'
                    existing.email_found_at = datetime.utcnow()
                    emails_added += 1
            else:
                new_site = Site(
                    domain=buyer_domain,
                    source_url=f"https://{seller_domain}",
                    purchased_from=seller_domain,
                    purchased_at=datetime.utcnow(),
                    emails=buyer_email,
                    email_source='distributed_crawl' if buyer_email else None,
                    email_found_at=datetime.utcnow() if buyer_email else None
                )
                session.add(new_site)
                new_buyers += 1
                if buyer_email:
                    emails_added += 1

        safe_commit(session)

        # Mettre à jour les stats du worker
        if new_buyers > 0 or emails_added > 0:
            workers_data = load_workers()
            if worker_id in workers_data['workers']:
                workers_data['workers'][worker_id]['buyers_found'] = \
                    workers_data['workers'][worker_id].get('buyers_found', 0) + new_buyers
                workers_data['workers'][worker_id]['emails_found'] = \
                    workers_data['workers'][worker_id].get('emails_found', 0) + emails_added
                workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
                save_workers(workers_data)

        logger.info(f"📥 Worker {worker_id}: batch {seller_domain} - {new_buyers} nouveaux buyers, {emails_added} emails")

        return jsonify({
            'status': 'ok',
            'new_buyers': new_buyers,
            'emails_added': emails_added,
            'total_processed': len(buyers)
        })

    except Exception as e:
        logger.error(f"❌ Erreur submit_buyers_batch: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/heartbeat', methods=['POST'])
def worker_heartbeat():
    """
    Signal de vie d'un worker

    Body JSON:
    {
        "worker_id": "worker_192.99.44.191",
        "hostname": "ns500898",
        "status": "running",
        "current_task": "example.fr",
        "pages_crawled": 45,
        "cpu_usage": 25.5,
        "memory_usage": 1024
    }
    """
    data = request.get_json()
    worker_id = data.get('worker_id', 'unknown')

    workers_data = load_workers()

    if worker_id not in workers_data['workers']:
        workers_data['workers'][worker_id] = {
            'first_seen': datetime.utcnow().isoformat(),
            'tasks_assigned': 0,
            'tasks_completed': 0,
            'buyers_found': 0,
            'emails_found': 0,
            'errors': 0
        }

    # Mettre à jour les infos du worker (sans écraser les stats existantes)
    worker = workers_data['workers'][worker_id]
    worker['last_heartbeat'] = datetime.utcnow().isoformat()

    # Mettre à jour seulement si présent dans le heartbeat
    if data.get('hostname'):
        worker['hostname'] = data.get('hostname')
    if data.get('status'):
        worker['status'] = data.get('status')
    if data.get('current_task') is not None:
        worker['current_task'] = data.get('current_task')
    if data.get('cpu_usage') is not None:
        worker['cpu_usage'] = data.get('cpu_usage')
    if data.get('memory_usage') is not None:
        worker['memory_usage'] = data.get('memory_usage')
    if 'sites_in_progress' in data:
        worker['sites_in_progress'] = data.get('sites_in_progress', [])

    # pages_crawled: prendre le max (ne jamais diminuer)
    if data.get('pages_crawled') is not None:
        worker['pages_crawled'] = max(worker.get('pages_crawled', 0), data.get('pages_crawled', 0))

    # Extraire les stats du worker si présentes (ne jamais diminuer les compteurs)
    stats = data.get('stats', {})
    if stats:
        worker['tasks_completed'] = max(worker.get('tasks_completed', 0), stats.get('tasks_completed', 0))
        worker['buyers_found'] = max(worker.get('buyers_found', 0), stats.get('buyers_found', 0))
        worker['emails_found'] = max(worker.get('emails_found', 0), stats.get('emails_found', 0))

    save_workers(workers_data)

    return jsonify({'status': 'ok', 'worker_id': worker_id})


@crawl_api.route('/api/crawl/workers', methods=['GET'])
def get_workers():
    """
    Liste des workers actifs - compte les processus réels via ps aux
    (même méthode que /api/scripts-status pour cohérence Home/Jobs)

    Returns:
        Comptage des workers par serveur avec total
    """
    import subprocess
    from datetime import datetime

    crawl_workers = {
        'local': {'count': 0, 'workers': [], 'min_required': 0, 'host': 'server-pbn1 (local)'},
        'remote': {'count': 0, 'workers': [], 'min_required': 8, 'host': 'ns500898 (192.99.44.191)'},
        'remote2': {'count': 0, 'workers': [], 'min_required': 4, 'host': 'prestashop (137.74.26.28)'},
        'remote3': {'count': 0, 'workers': [], 'min_required': 4, 'host': 'betterweb (51.178.78.138)'},
        'remote4': {'count': 0, 'workers': [], 'min_required': 2, 'host': 'wordpress (137.74.31.238)'},
        'remote5': {'count': 0, 'workers': [], 'min_required': 1, 'host': 'ladd-prod3 (141.94.169.126)'},
        'remote6': {'count': 0, 'workers': [], 'min_required': 1, 'host': 'ladd-prod6 (51.77.13.24)'}
    }

    try:
        # Workers locaux via ps aux
        local_result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True, text=True, timeout=10
        )
        for line in local_result.stdout.split('\n'):
            if 'crawl_worker_multi.py' in line and 'python3' in line and 'bash -c' not in line and 'ssh ' not in line and '@' not in line:
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

        # Workers distants betterweb via SSH
        try:
            remote3_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'datch@51.178.78.138',
                 "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote3_result.stdout.strip().split('\n'):
                if line.strip() and 'crawl_worker_multi.py' in line:
                    parts = line.split()
                    if len(parts) >= 11 and parts[1].isdigit():
                        crawl_workers['remote3']['workers'].append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'started': parts[8] if len(parts) > 8 else 'N/A'
                        })
            crawl_workers['remote3']['count'] = len(crawl_workers['remote3']['workers'])
        except (subprocess.TimeoutExpired, Exception) as e:
            crawl_workers['remote3']['error'] = str(e)

        # Workers distants wordpress via SSH
        try:
            remote4_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'debian@137.74.31.238',
                 "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote4_result.stdout.strip().split('\n'):
                if line.strip() and 'crawl_worker_multi.py' in line:
                    parts = line.split()
                    if len(parts) >= 11 and parts[1].isdigit():
                        crawl_workers['remote4']['workers'].append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'started': parts[8] if len(parts) > 8 else 'N/A'
                        })
            crawl_workers['remote4']['count'] = len(crawl_workers['remote4']['workers'])
        except (subprocess.TimeoutExpired, Exception) as e:
            crawl_workers['remote4']['error'] = str(e)

        # Workers distants ladd-prod3 via SSH
        try:
            remote5_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'apps@server-prod3.ladd.guru',
                 "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote5_result.stdout.strip().split('\n'):
                if line.strip() and 'crawl_worker_multi.py' in line:
                    parts = line.split()
                    if len(parts) >= 11 and parts[1].isdigit():
                        crawl_workers['remote5']['workers'].append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'started': parts[8] if len(parts) > 8 else 'N/A'
                        })
            crawl_workers['remote5']['count'] = len(crawl_workers['remote5']['workers'])
        except (subprocess.TimeoutExpired, Exception) as e:
            crawl_workers['remote5']['error'] = str(e)

        # Workers distants ladd-prod6 via SSH (timeout court car serveur souvent inaccessible)
        try:
            remote6_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'apps@server-prod6.ladd.guru',
                 "ps aux | grep 'python3.*crawl_worker_multi.py' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=10
            )
            for line in remote6_result.stdout.strip().split('\n'):
                if line.strip() and 'crawl_worker_multi.py' in line:
                    parts = line.split()
                    if len(parts) >= 11 and parts[1].isdigit():
                        crawl_workers['remote6']['workers'].append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'memory': parts[3],
                            'started': parts[8] if len(parts) > 8 else 'N/A'
                        })
            crawl_workers['remote6']['count'] = len(crawl_workers['remote6']['workers'])
        except (subprocess.TimeoutExpired, Exception) as e:
            crawl_workers['remote6']['error'] = str(e)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Calculer le total
    total_count = (crawl_workers['local']['count'] +
                   crawl_workers['remote']['count'] +
                   crawl_workers['remote2']['count'] +
                   crawl_workers['remote3']['count'] +
                   crawl_workers['remote4']['count'] +
                   crawl_workers['remote5']['count'] +
                   crawl_workers['remote6']['count'])

    # Charger les données détaillées des workers depuis crawl_workers.json
    active_workers = []
    try:
        workers_data = load_workers()
        for worker_id, worker in workers_data.get('workers', {}).items():
            # Vérifier si le worker est encore actif (heartbeat récent)
            if is_worker_alive(worker):
                # Limiter à 8 sites pour éviter une réponse trop volumineuse
                sites = worker.get('sites_in_progress', [])[:8]
                # Limiter aussi les URLs récentes à 3 par site
                for site in sites:
                    if 'recent_urls' in site:
                        site['recent_urls'] = site['recent_urls'][-3:]

                active_workers.append({
                    'worker_id': worker_id,
                    'hostname': worker.get('hostname', '?'),
                    'status': worker.get('status', 'unknown'),
                    'current_task': worker.get('current_task', '')[:100],  # Limiter la taille
                    'pages_crawled': worker.get('pages_crawled', 0),
                    'tasks_completed': worker.get('tasks_completed', 0),
                    'buyers_found': worker.get('buyers_found', 0),
                    'emails_found': worker.get('emails_found', 0),
                    'sites_in_progress': sites,
                    'sites_total': len(worker.get('sites_in_progress', [])),
                    'last_heartbeat': worker.get('last_heartbeat')
                })
    except Exception as e:
        logger.error(f"Erreur chargement workers détaillés: {e}")

    return jsonify({
        'active_count': total_count,
        'crawl_workers': crawl_workers,
        'active_workers': active_workers,
        'local_count': crawl_workers['local']['count'],
        'remote_count': crawl_workers['remote']['count'],
        'remote2_count': crawl_workers['remote2']['count'],
        'remote3_count': crawl_workers['remote3']['count'],
        'remote4_count': crawl_workers['remote4']['count'],
        'timestamp': datetime.utcnow().isoformat()
    })


@crawl_api.route('/api/crawl/stats', methods=['GET'])
def get_crawl_stats():
    """
    Statistiques globales du crawl distribué
    """
    session = get_session()
    workers_data = load_workers()

    try:
        # Stats depuis la DB
        total_sellers = session.query(Site).filter(Site.purchased_from.is_(None)).count()
        sellers_crawled = session.query(Site).filter(
            Site.purchased_from.is_(None),
            Site.backlinks_crawled == True
        ).count()
        sellers_remaining = total_sellers - sellers_crawled

        total_buyers = session.query(Site).filter(Site.purchased_from.isnot(None)).count()
        buyers_with_email = session.query(Site).filter(
            Site.purchased_from.isnot(None),
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Stats des workers
        total_tasks_completed = sum(
            w.get('tasks_completed', 0)
            for w in workers_data.get('workers', {}).values()
        )
        total_buyers_found = sum(
            w.get('buyers_found', 0)
            for w in workers_data.get('workers', {}).values()
        )
        total_emails_found = sum(
            w.get('emails_found', 0)
            for w in workers_data.get('workers', {}).values()
        )

        # Calculer la vitesse (sites/jour)
        active_workers = [
            w for w in workers_data.get('workers', {}).values()
            if is_worker_alive(w)
        ]

        # Estimation basée sur les dernières 24h
        yesterday = datetime.utcnow() - timedelta(days=1)
        crawled_last_24h = session.query(Site).filter(
            Site.purchased_from.is_(None),
            Site.backlinks_crawled == True,
            Site.backlinks_crawled_at >= yesterday
        ).count()

        # Estimation du temps restant
        if crawled_last_24h > 0:
            days_remaining = sellers_remaining / crawled_last_24h
        else:
            days_remaining = None

        return jsonify({
            'sellers': {
                'total': total_sellers,
                'crawled': sellers_crawled,
                'remaining': sellers_remaining,
                'progress_percent': round(sellers_crawled / total_sellers * 100, 1) if total_sellers > 0 else 0
            },
            'buyers': {
                'total': total_buyers,
                'with_email': buyers_with_email,
                'email_rate': round(buyers_with_email / total_buyers * 100, 1) if total_buyers > 0 else 0
            },
            'workers': {
                'active': len(active_workers),
                'total': len(workers_data.get('workers', {})),
                'tasks_completed': total_tasks_completed,
                'buyers_found': total_buyers_found,
                'emails_found': total_emails_found
            },
            'speed': {
                'sites_per_day': crawled_last_24h,
                'days_remaining': round(days_remaining, 1) if days_remaining else None
            }
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_crawl_stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/daily-stats', methods=['GET'])
def get_crawl_daily_stats():
    """
    Statistiques journalières du crawl (pages, acheteurs, emails par jour)
    """
    from sqlalchemy import func
    session = get_session()

    try:
        # Charger les stats de pages journalières
        pages_data = load_daily_pages()

        # Stats des 14 derniers jours
        daily_stats = []

        for i in range(14):
            day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            next_day = day + timedelta(days=1)
            day_str = day.strftime('%Y-%m-%d')

            # Pages crawlées ce jour (depuis le fichier JSON backlinks + sites email)
            day_data = pages_data.get(day_str, {})
            # Support ancien format (int) et nouveau format (dict)
            if isinstance(day_data, int):
                pages_crawled = day_data
                workers_stats = {}
            else:
                pages_crawled = day_data.get('total', 0)
                workers_stats = day_data.get('workers', {})

            # Ajouter les sites traités par l'extraction email
            emails_day_data = load_daily_emails().get(day_str, {})
            if isinstance(emails_day_data, dict):
                sites_email_crawled = emails_day_data.get('sites', 0)
                pages_crawled += sites_email_crawled  # Ajouter les sites email aux pages

            # Sites vendeurs crawlés ce jour (tous les sites crawlés, pas seulement les vendeurs sans purchased_from)
            sellers_crawled = session.query(Site).filter(
                Site.is_link_seller == True,
                Site.backlinks_crawled == True,
                Site.backlinks_crawled_at >= day,
                Site.backlinks_crawled_at < next_day
            ).count()

            # Acheteurs trouvés ce jour
            buyers_found = session.query(Site).filter(
                Site.purchased_from.isnot(None),
                Site.created_at >= day,
                Site.created_at < next_day
            ).count()

            # Emails trouvés ce jour - inclure aussi les emails de l'extraction distribuée
            # 1. Emails des nouveaux acheteurs découverts ce jour
            emails_buyers = session.query(Site).filter(
                Site.purchased_from.isnot(None),
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != 'NO EMAIL FOUND',
                Site.created_at >= day,
                Site.created_at < next_day
            ).count()

            # 2. Emails trouvés par l'extraction distribuée (depuis le fichier JSON)
            emails_data = load_daily_emails()
            emails_extracted = emails_data.get(day_str, {}).get('emails', 0) if isinstance(emails_data.get(day_str), dict) else 0

            # Total des emails trouvés ce jour
            emails_found = emails_buyers + emails_extracted

            daily_stats.append({
                'date': day_str,
                'date_display': day.strftime('%d/%m'),
                'day_name': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'][day.weekday()],
                'pages_crawled': pages_crawled,
                'sellers_crawled': sellers_crawled,
                'buyers_found': buyers_found,
                'emails_found': emails_found,
                'workers': workers_stats
            })

        return jsonify({
            'daily_stats': daily_stats,
            'total_14_days': {
                'pages_crawled': sum(d['pages_crawled'] for d in daily_stats),
                'sellers_crawled': sum(d['sellers_crawled'] for d in daily_stats),
                'buyers_found': sum(d['buyers_found'] for d in daily_stats),
                'emails_found': sum(d['emails_found'] for d in daily_stats)
            }
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_crawl_daily_stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/worker/<worker_id>', methods=['DELETE'])
def remove_worker(worker_id):
    """Supprimer un worker de la liste"""
    workers_data = load_workers()

    if worker_id in workers_data.get('workers', {}):
        del workers_data['workers'][worker_id]
        save_workers(workers_data)
        return jsonify({'status': 'ok', 'message': f'Worker {worker_id} supprimé'})

    return jsonify({'error': 'Worker non trouvé'}), 404


# ============================================================
# ENDPOINTS POUR EXTRACTION D'EMAILS DISTRIBUÉE
# ============================================================

DAILY_EMAILS_FILE = Path('/var/www/Scrap_Email/crawl_daily_emails.json')


def load_daily_emails():
    """Charger les stats d'emails extraits par jour"""
    if DAILY_EMAILS_FILE.exists():
        try:
            with open(DAILY_EMAILS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_daily_emails(data):
    """Sauvegarder les stats d'emails extraits par jour"""
    with open(DAILY_EMAILS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_emails_extracted(emails_count, sites_count, worker_id='unknown'):
    """Ajouter des emails au compteur du jour"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    data = load_daily_emails()

    if today not in data:
        data[today] = {'emails': 0, 'sites': 0, 'workers': {}}

    data[today]['emails'] += emails_count
    data[today]['sites'] += sites_count

    if worker_id not in data[today]['workers']:
        data[today]['workers'][worker_id] = {'emails': 0, 'sites': 0}

    data[today]['workers'][worker_id]['emails'] += emails_count
    data[today]['workers'][worker_id]['sites'] += sites_count

    save_daily_emails(data)


@crawl_api.route('/api/crawl/email-task', methods=['GET'])
def get_email_extraction_task():
    """
    Obtenir un batch de sites pour extraction d'email.

    Ces sites ont été découverts mais n'ont pas encore d'email.
    Permet d'utiliser les workers inactifs pour extraire des emails.

    Query params:
    - worker_id: Identifiant unique du worker
    - batch_size: Nombre de sites à récupérer (défaut: 20)
    - sellers_first: Prioriser les vendeurs LinkAvista (défaut: true)
    """
    from sqlalchemy import or_, case, text

    worker_id = request.args.get('worker_id', 'unknown')
    batch_size = int(request.args.get('batch_size', 20))
    sellers_first = request.args.get('sellers_first', 'true').lower() == 'true'

    # Limiter la taille du batch
    batch_size = min(batch_size, 100)

    session = get_session()
    try:
        # Ordre de priorité: sellers d'abord, puis .fr
        priority_order = case(
            (Site.purchased_from.is_(None), 0),
            (Site.domain.like('%.fr'), 1),
            else_=2
        )

        # Sites sans email, pas traités récemment
        lock_threshold = datetime.utcnow() - timedelta(minutes=30)

        # FOR UPDATE SKIP LOCKED pour éviter les doublons
        sites = session.query(Site).filter(
            or_(
                Site.emails.is_(None),
                Site.emails == '',
                Site.emails == 'NO EMAIL FOUND'
            ),
            Site.blacklisted == False,
            # Pas traité récemment pour email
            or_(
                Site.email_crawl_at.is_(None),
                Site.email_crawl_at < lock_threshold
            )
        ).order_by(
            priority_order if sellers_first else Site.id,
            Site.id
        ).limit(batch_size * 2).with_for_update(skip_locked=True).all()

        if not sites:
            session.commit()
            return jsonify({
                'status': 'no_tasks',
                'message': 'Aucun site sans email à traiter',
                'sites': []
            })

        now = datetime.utcnow()
        tasks = []

        for site in sites[:batch_size]:
            # Construire l'URL
            if site.source_url and site.source_url.startswith('http'):
                url = site.source_url
            else:
                url = f"https://{site.domain}"

            tasks.append({
                'id': site.id,
                'domain': site.domain,
                'url': url,
                'is_seller': site.purchased_from is None or False
            })

            # Marquer comme en cours de traitement
            site.email_crawl_at = now

        safe_commit(session)

        logger.info(f"📧 Worker {worker_id}: {len(tasks)} sites pour extraction email")

        # Mettre à jour les stats du worker
        workers_data = load_workers()
        if worker_id not in workers_data['workers']:
            workers_data['workers'][worker_id] = {
                'first_seen': datetime.utcnow().isoformat(),
                'tasks_assigned': 0,
                'tasks_completed': 0,
                'buyers_found': 0,
                'emails_found': 0,
                'errors': 0,
                'email_extractions': 0
            }

        workers_data['workers'][worker_id]['email_tasks_assigned'] = \
            workers_data['workers'][worker_id].get('email_tasks_assigned', 0) + len(tasks)
        workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
        save_workers(workers_data)

        return jsonify({
            'status': 'ok',
            'worker_id': worker_id,
            'batch_size': len(tasks),
            'task_type': 'email_extraction',
            'sites': tasks
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_email_extraction_task: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/email-result', methods=['POST'])
def submit_email_result():
    """
    Soumettre les résultats d'extraction d'email.

    Body JSON:
    {
        "worker_id": "worker_xxx",
        "site_id": 12345,
        "domain": "example.fr",
        "emails": "contact@example.fr; info@example.fr",
        "pages_checked": 5,
        "error": null
    }
    """
    data = request.get_json()

    worker_id = data.get('worker_id', 'unknown')
    site_id = data.get('site_id')
    domain = data.get('domain')
    emails = data.get('emails')  # String séparé par ;
    pages_checked = data.get('pages_checked', 0)
    error = data.get('error')

    if not site_id or not domain:
        return jsonify({'error': 'site_id et domain requis'}), 400

    session = get_session()
    try:
        site = session.query(Site).filter_by(id=site_id).first()

        if site:
            site.email_crawl_at = datetime.utcnow()

            if emails and emails.strip():
                site.emails = emails.strip()
                site.email_found_at = datetime.utcnow()
                site.email_source = 'distributed_email_extraction'

                # Compter le nombre d'emails
                email_count = len([e for e in emails.split(';') if e.strip()])
                add_emails_extracted(email_count, 1, worker_id)

                logger.info(f"✅ Worker {worker_id}: {domain} - {email_count} email(s) trouvé(s)")
            else:
                site.emails = 'NO EMAIL FOUND'
                add_emails_extracted(0, 1, worker_id)

            if error:
                site.last_error = error

        safe_commit(session)

        # Mettre à jour les stats du worker
        workers_data = load_workers()
        if worker_id in workers_data['workers']:
            workers_data['workers'][worker_id]['email_extractions'] = \
                workers_data['workers'][worker_id].get('email_extractions', 0) + 1
            if emails and emails.strip():
                email_count = len([e for e in emails.split(';') if e.strip()])
                workers_data['workers'][worker_id]['emails_found'] = \
                    workers_data['workers'][worker_id].get('emails_found', 0) + email_count
            workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
            save_workers(workers_data)

        return jsonify({
            'status': 'ok',
            'domain': domain,
            'emails_found': len([e for e in (emails or '').split(';') if e.strip()])
        })

    except Exception as e:
        logger.error(f"❌ Erreur submit_email_result: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/email-results-batch', methods=['POST'])
def submit_email_results_batch():
    """
    Soumettre les résultats d'extraction d'email en batch.
    Plus efficace pour plusieurs sites à la fois.

    Body JSON:
    {
        "worker_id": "worker_xxx",
        "results": [
            {"site_id": 123, "domain": "site1.fr", "emails": "a@site1.fr"},
            {"site_id": 456, "domain": "site2.fr", "emails": null}
        ]
    }
    """
    data = request.get_json()

    worker_id = data.get('worker_id', 'unknown')
    results = data.get('results', [])

    if not results:
        return jsonify({'error': 'results requis'}), 400

    session = get_session()
    try:
        total_emails = 0
        sites_processed = 0

        for result in results:
            site_id = result.get('site_id')
            emails = result.get('emails')

            site = session.query(Site).filter_by(id=site_id).first()
            if site:
                site.email_crawl_at = datetime.utcnow()

                if emails and emails.strip():
                    site.emails = emails.strip()
                    site.email_found_at = datetime.utcnow()
                    site.email_source = 'distributed_email_extraction'
                    total_emails += len([e for e in emails.split(';') if e.strip()])
                else:
                    site.emails = 'NO EMAIL FOUND'

                sites_processed += 1

        safe_commit(session)

        # Stats journalières
        add_emails_extracted(total_emails, sites_processed, worker_id)

        # Mettre à jour les stats du worker
        workers_data = load_workers()
        if worker_id in workers_data['workers']:
            workers_data['workers'][worker_id]['email_extractions'] = \
                workers_data['workers'][worker_id].get('email_extractions', 0) + sites_processed
            workers_data['workers'][worker_id]['emails_found'] = \
                workers_data['workers'][worker_id].get('emails_found', 0) + total_emails
            workers_data['workers'][worker_id]['last_heartbeat'] = datetime.utcnow().isoformat()
            save_workers(workers_data)

        logger.info(f"📧 Worker {worker_id}: batch {sites_processed} sites, {total_emails} emails")

        return jsonify({
            'status': 'ok',
            'sites_processed': sites_processed,
            'emails_found': total_emails
        })

    except Exception as e:
        logger.error(f"❌ Erreur submit_email_results_batch: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/email-stats', methods=['GET'])
def get_email_extraction_stats():
    """
    Statistiques de l'extraction d'emails distribuée
    """
    from sqlalchemy import or_

    session = get_session()
    try:
        # Sites sans email
        sites_without_email = session.query(Site).filter(
            or_(
                Site.emails.is_(None),
                Site.emails == '',
                Site.emails == 'NO EMAIL FOUND'
            )
        ).count()

        # Sites avec email
        sites_with_email = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Sellers sans email
        sellers_without_email = session.query(Site).filter(
            Site.purchased_from.is_(None),
            or_(
                Site.emails.is_(None),
                Site.emails == '',
                Site.emails == 'NO EMAIL FOUND'
            )
        ).count()

        # Emails extraits aujourd'hui
        daily_data = load_daily_emails()
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_stats = daily_data.get(today, {'emails': 0, 'sites': 0, 'workers': {}})

        # Stats des 7 derniers jours
        weekly_stats = []
        for i in range(7):
            day = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            day_data = daily_data.get(day, {'emails': 0, 'sites': 0})
            weekly_stats.append({
                'date': day,
                'emails': day_data.get('emails', 0),
                'sites': day_data.get('sites', 0)
            })

        return jsonify({
            'status': 'ok',
            'totals': {
                'sites_without_email': sites_without_email,
                'sites_with_email': sites_with_email,
                'sellers_without_email': sellers_without_email,
                'email_rate': round(sites_with_email / (sites_with_email + sites_without_email) * 100, 1) if (sites_with_email + sites_without_email) > 0 else 0
            },
            'today': {
                'emails_found': today_stats.get('emails', 0),
                'sites_processed': today_stats.get('sites', 0),
                'workers': today_stats.get('workers', {})
            },
            'weekly': weekly_stats
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_email_extraction_stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
