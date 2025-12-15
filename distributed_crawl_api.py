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
import os
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request
from database import get_session, Site, safe_commit
from sqlalchemy import func

logger = logging.getLogger(__name__)

# ============================================================================
# Détection de langue via Claude API (pour les sites sans attribut HTML lang)
# ============================================================================

# Configuration Anthropic
CLAUDE_CREDENTIALS_PATH = '/home/debian/.claude/.credentials.json'
_anthropic_client = None

def get_anthropic_client():
    """Retourne un client Anthropic singleton"""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client

    # Récupérer la clé API
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        try:
            if os.path.exists(CLAUDE_CREDENTIALS_PATH):
                with open(CLAUDE_CREDENTIALS_PATH, 'r') as f:
                    creds = json.load(f)
                    api_key = creds.get('apiKey') or creds.get('anthropicApiKey') or ''
        except Exception:
            pass

    if not api_key:
        return None

    try:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
        return _anthropic_client
    except Exception as e:
        logger.warning(f"Impossible d'initialiser Anthropic: {e}")
        return None

def detect_language_with_claude(text_sample: str) -> tuple:
    """
    Utilise Claude pour détecter la langue d'un texte.
    Retourne (language_code, confidence) ou (None, None) en cas d'erreur.
    """
    if not text_sample or len(text_sample) < 20:
        return None, None

    client = get_anthropic_client()
    if not client:
        return None, None

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"Quelle est la langue de ce texte ? Réponds UNIQUEMENT par le code ISO 639-1 (ex: fr, en, es, de, it, pt, nl). Texte: {text_sample[:300]}"
            }]
        )

        lang_code = response.content[0].text.strip().lower()[:2]

        # Valider le code langue (2 lettres alphabétiques)
        if len(lang_code) == 2 and lang_code.isalpha():
            return lang_code, 0.85  # Confiance 85% pour détection par Claude
        return None, None

    except Exception as e:
        logger.warning(f"Erreur détection langue Claude: {e}")
        return None, None

# Blueprint Flask pour les routes de crawl distribué
crawl_api = Blueprint('crawl_api', __name__)

# Fichier de suivi des workers
WORKERS_FILE = Path('/var/www/Scrap_Email/crawl_workers.json')
DAILY_PAGES_FILE = Path('/var/www/Scrap_Email/crawl_daily_pages.json')
WORKER_TIMEOUT = 60  # 60 secondes sans heartbeat = worker considéré comme mort (heartbeat toutes les 30s)

# Configuration centralisée des serveurs
SERVERS_CONFIG = {
    'local': {
        'name': 'ns3132232 (local)',
        'ssh': None,  # Pas de SSH pour le serveur local
        'min_required': 1,
        'worker_path': '/var/www/Scrap_Email'
    },
    'remote': {
        'name': 'ns500898',
        'ssh': 'debian@192.99.44.191',
        'min_required': 8,
        'worker_path': '/home/debian/crawl_worker'
    },
    'remote2': {
        'name': 'prestashop',
        'ssh': 'debian@137.74.26.28',
        'min_required': 4,
        'worker_path': '/home/debian/crawl_worker'
    },
    'remote3': {
        'name': 'betterweb',
        'ssh': 'datch@51.178.78.138',
        'min_required': 4,
        'worker_path': '/home/datch/crawl_worker'
    },
    'remote4': {
        'name': 'wordpress',
        'ssh': 'debian@137.74.31.238',
        'min_required': 2,
        'worker_path': '/home/debian/crawl_worker'
    },
    'remote5': {
        'name': 'ladd-prod3',
        'ssh': 'apps@server-prod3.ladd.guru',
        'min_required': 1,
        'worker_path': '/home/apps/crawl_worker'
    },
    'remote6': {
        'name': 'ladd-prod6',
        'ssh': 'apps@51.77.13.24',
        'min_required': 1,
        'worker_path': '/home/apps/crawl_worker'
    }
}


def load_daily_pages():
    """Charger les stats de pages crawlées par jour (fusion fichier JSON + base de données)"""
    data = {}

    # Charger depuis la base de données d'abord (source de vérité pour l'historique)
    try:
        from sqlalchemy import text
        session = get_session()
        result = session.execute(text("""
            SELECT date, pages_crawled, sellers_crawled, workers_data
            FROM crawl_daily_stats
            ORDER BY date DESC
            LIMIT 30
        """))
        for row in result:
            date_str = row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0])
            workers_raw = row[3]
            if workers_raw:
                if isinstance(workers_raw, str):
                    workers = json.loads(workers_raw)
                else:
                    workers = workers_raw
            else:
                workers = {}
            data[date_str] = {
                'total': row[1] or 0,
                'workers': workers
            }
        session.close()
    except Exception as e:
        logger.error(f"Erreur chargement BDD stats: {e}")

    # Fusionner avec le fichier JSON (peut avoir des données plus récentes pour aujourd'hui)
    if DAILY_PAGES_FILE.exists():
        try:
            with open(DAILY_PAGES_FILE, 'r') as f:
                json_data = json.load(f)
                if json_data:
                    # Fusionner: le JSON prend la priorité pour les données du jour
                    for date_str, day_data in json_data.items():
                        if date_str not in data or (isinstance(day_data, dict) and day_data.get('total', 0) > data.get(date_str, {}).get('total', 0)):
                            data[date_str] = day_data
        except:
            pass

    return data


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


def load_workers(clean_inactive: bool = True):
    """Charger les informations des workers et optionnellement nettoyer les inactifs"""
    if WORKERS_FILE.exists():
        try:
            with open(WORKERS_FILE, 'r') as f:
                data = json.load(f)

            # Nettoyer automatiquement les workers inactifs
            if clean_inactive and data.get('workers'):
                now = datetime.utcnow()
                active_workers = {}
                for wid, w in data['workers'].items():
                    if w.get('last_heartbeat'):
                        try:
                            last_hb = datetime.fromisoformat(w['last_heartbeat'].replace('Z', ''))
                            if (now - last_hb).total_seconds() < WORKER_TIMEOUT:
                                active_workers[wid] = w
                        except:
                            pass

                # Si on a supprimé des workers, sauvegarder
                if len(active_workers) < len(data['workers']):
                    data['workers'] = active_workers
                    data['last_update'] = now.isoformat()
                    with open(WORKERS_FILE, 'w') as f:
                        json.dump(data, f, indent=2)

            return data
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
        # On exclut aussi les domaines gouvernementaux directement en SQL (plus efficace)
        # Note: Un site peut être vendeur ET acheteur, donc on filtre sur is_link_seller, pas purchased_from
        sites_raw = session.query(Site).filter(
            Site.is_link_seller == True,
            Site.backlinks_crawled == False,
            Site.blacklisted == False,
            Site.is_active == True,
            ~Site.domain.like('%.gouv.fr'),  # Exclure les domaines gouvernementaux
            ~Site.domain.like('%.senat.fr'),
            ~Site.domain.like('%.assemblee-nationale.fr'),
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
    sitemap_urls = data.get('sitemap_urls', 0)  # Nombre d'URLs dans le sitemap
    missed_interesting = data.get('missed_interesting', 0)  # URLs intéressantes non crawlées
    seller_email = data.get('seller_email')  # Email du vendeur extrait pendant le crawl
    # CMS et langue détectés pendant le crawl
    cms = data.get('cms')
    cms_version = data.get('cms_version')
    language = data.get('language')
    language_confidence = data.get('language_confidence')
    text_sample = data.get('text_sample')  # Échantillon de texte pour détection langue par Claude

    # Si pas de langue détectée mais un text_sample est fourni, utiliser Claude
    if not language and text_sample:
        claude_lang, claude_confidence = detect_language_with_claude(text_sample)
        if claude_lang:
            language = claude_lang
            language_confidence = claude_confidence
            logger.info(f"🤖 Langue détectée par Claude pour {domain}: {language}")

    if not site_id or not domain:
        return jsonify({'error': 'site_id et domain requis'}), 400

    session = get_session()
    try:
        # Marquer le site vendeur comme crawlé (seulement si c'est le résultat final)
        seller = session.query(Site).filter_by(id=site_id).first()
        if seller:
            # Toujours mettre à jour le nombre de pages (même pour les résultats intermédiaires)
            seller.pages_crawled = max(seller.pages_crawled or 0, pages_crawled)

            if not is_intermediate:
                seller.backlinks_crawled = True
                seller.backlinks_crawled_at = datetime.utcnow()
                # Sauvegarder les infos sitemap
                if sitemap_urls > 0:
                    seller.sitemap_urls_count = sitemap_urls
                    seller.sitemap_missed_interesting = missed_interesting
                if error:
                    seller.last_error = error
                # Sauvegarder l'email du vendeur si extrait pendant le crawl (et pas déjà présent)
                if seller_email and not seller.emails:
                    seller.emails = seller_email
                    seller.email_source = 'distributed_crawl'
                    seller.email_found_at = datetime.utcnow()
                    seller.email_crawl_at = datetime.utcnow()
                    logger.info(f"📧 Email vendeur trouvé pour {domain}: {seller_email}")

                # Sauvegarder le CMS si détecté (et pas déjà présent)
                if cms and not seller.cms:
                    seller.cms = cms
                    seller.cms_version = cms_version
                    seller.cms_detected_at = datetime.utcnow()
                    logger.info(f"🔧 CMS détecté pour {domain}: {cms}" + (f" {cms_version}" if cms_version else ""))

                # Sauvegarder la langue si détectée (et pas déjà présente)
                if language and not seller.language:
                    seller.language = language
                    seller.language_confidence = language_confidence
                    seller.language_detected_at = datetime.utcnow()
                    logger.info(f"🌍 Langue détectée pour {domain}: {language} ({language_confidence})")

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
            found_on_url = buyer_data.get('found_on_url')  # URL où le backlink a été trouvé

            # Nouvelles données enrichies
            language = buyer_data.get('language')
            language_confidence = buyer_data.get('language_confidence')
            text_sample = buyer_data.get('text_sample')
            cms = buyer_data.get('cms')
            cms_version = buyer_data.get('cms_version')
            siret = buyer_data.get('siret')
            siren = buyer_data.get('siren')
            siret_type = buyer_data.get('siret_type')

            # Si pas de langue détectée mais text_sample fourni, utiliser Claude
            if not language and text_sample:
                claude_lang, claude_confidence = detect_language_with_claude(text_sample)
                if claude_lang:
                    language = claude_lang
                    language_confidence = claude_confidence

            if not buyer_domain:
                continue

            # Vérifier si le buyer existe déjà
            existing = session.query(Site).filter_by(domain=buyer_domain).first()

            if existing:
                if not existing.purchased_from:
                    existing.purchased_from = seller_domain
                    existing.purchased_on_url = found_on_url
                    existing.purchased_at = datetime.utcnow()
                if buyer_email and not existing.emails:
                    existing.emails = buyer_email
                    existing.email_source = 'distributed_crawl'
                    existing.email_found_at = datetime.utcnow()
                    emails_added += 1
                # Mettre à jour langue si pas encore définie
                if language and not existing.language:
                    existing.language = language
                    existing.language_confidence = language_confidence
                    existing.language_detected_at = datetime.utcnow()
                # Mettre à jour CMS si pas encore défini
                if cms and not existing.cms:
                    existing.cms = cms
                    existing.cms_version = cms_version
                    existing.cms_detected_at = datetime.utcnow()
                # Mettre à jour SIRET si pas encore défini
                if (siret or siren) and not existing.siret and not existing.siren:
                    existing.siret = siret
                    existing.siren = siren
                    existing.siret_type = siret_type
                    existing.siret_found_at = datetime.utcnow()
                    existing.siret_checked = True
            else:
                new_site = Site(
                    domain=buyer_domain,
                    source_url=f"https://{seller_domain}",
                    purchased_from=seller_domain,
                    purchased_on_url=found_on_url,
                    purchased_at=datetime.utcnow(),
                    emails=buyer_email,
                    email_source='distributed_crawl' if buyer_email else None,
                    email_found_at=datetime.utcnow() if buyer_email else None,
                    # Données enrichies
                    language=language,
                    language_confidence=language_confidence,
                    language_detected_at=datetime.utcnow() if language else None,
                    cms=cms,
                    cms_version=cms_version,
                    cms_detected_at=datetime.utcnow() if cms else None,
                    siret=siret,
                    siren=siren,
                    siret_type=siret_type,
                    siret_checked=True if (siret or siren) else False,
                    siret_found_at=datetime.utcnow() if (siret or siren) else None
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
        'local': {'count': 0, 'workers': [], 'min_required': 1, 'host': 'ns3132232 (local)'},
        'remote': {'count': 0, 'workers': [], 'min_required': 8, 'host': 'ns500898 (192.99.44.191)'},
        'remote2': {'count': 0, 'workers': [], 'min_required': 4, 'host': 'prestashop (137.74.26.28)'},
        'remote3': {'count': 0, 'workers': [], 'min_required': 4, 'host': 'betterweb (51.178.78.138)'},
        'remote4': {'count': 0, 'workers': [], 'min_required': 2, 'host': 'wordpress (137.74.31.238)'},
        'remote5': {'count': 0, 'workers': [], 'min_required': 1, 'host': 'ladd-prod3 (141.94.169.126)'},
        'remote6': {'count': 0, 'workers': [], 'min_required': 1, 'host': 'ladd-prod6 (51.77.13.24)'}
    }

    try:
        # Workers locaux via ps aux (cherche crawl_worker.py ET crawl_worker_multi.py)
        local_result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True, text=True, timeout=10
        )
        for line in local_result.stdout.split('\n'):
            if ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line) and 'python3' in line and 'bash -c' not in line and 'ssh ' not in line and '@' not in line:
                parts = line.split()
                if len(parts) >= 11:
                    crawl_workers['local']['workers'].append({
                        'pid': parts[1],
                        'cpu': parts[2],
                        'memory': parts[3],
                        'started': parts[8] if len(parts) > 8 else 'N/A'
                    })
        crawl_workers['local']['count'] = len(crawl_workers['local']['workers'])

        # Workers distants ns500898 via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'debian@192.99.44.191',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line):
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

        # Workers distants prestashop via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote2_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'debian@137.74.26.28',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote2_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line):
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

        # Workers distants betterweb via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote3_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'datch@51.178.78.138',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote3_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line) and 'bash -c' not in line:
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

        # Workers distants wordpress via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote4_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'debian@137.74.31.238',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote4_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line):
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

        # Workers distants ladd-prod3 via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote5_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'apps@server-prod3.ladd.guru',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=60
            )
            for line in remote5_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line):
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

        # Workers distants ladd-prod6 via SSH (cherche crawl_worker.py ET crawl_worker_multi.py)
        try:
            remote6_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
                 'apps@server-prod6.ladd.guru',
                 "ps aux | grep -E 'python3.*(crawl_worker\\.py|crawl_worker_multi\\.py)' | grep -v grep | grep -v 'bash -c'"],
                capture_output=True, text=True, timeout=10
            )
            for line in remote6_result.stdout.strip().split('\n'):
                if line.strip() and ('crawl_worker.py' in line or 'crawl_worker_multi.py' in line):
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
                # Afficher tous les sites (jusqu'à 50 max pour éviter une réponse trop volumineuse)
                sites = worker.get('sites_in_progress', [])[:50]
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


# ============================================================================
# GESTION DES WORKERS LOCAUX
# ============================================================================

def run_ssh_command(server_key, command, timeout=60, background=False):
    """Exécuter une commande sur un serveur distant via SSH"""
    import subprocess

    if server_key not in SERVERS_CONFIG:
        raise ValueError(f"Serveur inconnu: {server_key}")

    server = SERVERS_CONFIG[server_key]

    if server['ssh'] is None:
        # Commande locale
        result = subprocess.run(
            command if isinstance(command, list) else ['bash', '-c', command],
            capture_output=True, text=True, timeout=timeout
        )
    else:
        # Commande SSH (-f pour forcer la déconnexion si background=True)
        ssh_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'BatchMode=yes'
        ]
        if background:
            ssh_cmd.append('-f')
        ssh_cmd.extend([
            server['ssh'],
            command if isinstance(command, str) else ' '.join(command)
        ])
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)

    return result


@crawl_api.route('/api/crawl/workers/start', methods=['POST'])
def start_workers():
    """
    Lancer des workers de crawl sur un serveur

    Body JSON:
    {
        "server": "local",       // Serveur cible (local, remote, remote2, etc.)
        "count": 2,              // Nombre de workers à lancer
        "parallel_sites": 100,   // Sites en parallèle par worker
        "concurrent": 10         // Requêtes simultanées par site
    }
    """
    import subprocess

    data = request.get_json() or {}
    server_key = data.get('server', 'local')
    count = min(data.get('count', 1), 10)  # Max 10 workers
    parallel_sites = min(data.get('parallel_sites', 100), 500)  # Max 500 sites
    concurrent = min(data.get('concurrent', 10), 50)  # Max 50 requêtes/site

    if server_key not in SERVERS_CONFIG:
        return jsonify({'error': f'Serveur inconnu: {server_key}'}), 400

    server = SERVERS_CONFIG[server_key]
    started = 0
    pids = []

    try:
        for i in range(count):
            worker_id = f"{server['name']}-worker-{i+1}"
            worker_path = server['worker_path']

            if server['ssh'] is None:
                # Lancement local
                cmd = [
                    'python3', '-u', f'{worker_path}/crawl_worker_multi.py',
                    '--parallel-sites', str(parallel_sites),
                    '--concurrent', str(concurrent),
                    '--worker-id', worker_id
                ]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                pids.append(process.pid)
            else:
                # Lancement distant via SSH avec screen pour détacher proprement
                screen_name = f"crawl_{worker_id.replace(' ', '_').replace('(', '').replace(')', '')}"
                remote_cmd = f"screen -dmS {screen_name} bash -c 'cd {worker_path} && python3 -u crawl_worker_multi.py --parallel-sites {parallel_sites} --concurrent {concurrent} --worker-id {worker_id}'"
                result = run_ssh_command(server_key, remote_cmd, timeout=30)
                if result.returncode == 0:
                    pids.append(screen_name)
                else:
                    logger.error(f"Erreur lancement distant: {result.stderr}")

            started += 1
            logger.info(f"🚀 Worker {worker_id} lancé sur {server['name']} (sites: {parallel_sites}, concurrent: {concurrent})")

        return jsonify({
            'status': 'ok',
            'server': server_key,
            'started': started,
            'pids': pids,
            'config': {
                'parallel_sites': parallel_sites,
                'concurrent': concurrent
            }
        })

    except Exception as e:
        logger.error(f"❌ Erreur lancement workers sur {server_key}: {e}")
        return jsonify({'error': str(e)}), 500


@crawl_api.route('/api/crawl/workers/stop-all', methods=['POST'])
def stop_all_workers():
    """
    Arrêter tous les workers de crawl sur un serveur
    """
    import subprocess
    import time

    data = request.get_json() or {}
    server_key = data.get('server', 'local')

    if server_key not in SERVERS_CONFIG:
        return jsonify({'error': f'Serveur inconnu: {server_key}'}), 400

    server = SERVERS_CONFIG[server_key]

    try:
        if server['ssh'] is None:
            # Local
            result = subprocess.run(['pgrep', '-f', 'crawl_worker_multi.py'], capture_output=True, text=True)
            pids = [p for p in result.stdout.strip().split('\n') if p]

            for pid in pids:
                subprocess.run(['kill', '-TERM', pid], check=False)

            time.sleep(0.5)

            for pid in pids:
                subprocess.run(['kill', '-9', pid], check=False)

            stopped = len(pids)
        else:
            # Distant via SSH
            kill_cmd = "pkill -9 -f crawl_worker_multi.py; pgrep -f crawl_worker_multi.py | wc -l"
            result = run_ssh_command(server_key, kill_cmd)
            # Compter combien on a tué (avant - après)
            stopped = 0 if result.stdout.strip() == '0' else int(result.stdout.strip() or 0)
            # Relancer pkill pour être sûr
            run_ssh_command(server_key, "pkill -9 -f crawl_worker_multi.py")
            stopped = max(stopped, 1)  # Au moins signaler qu'on a essayé

        logger.info(f"🛑 {stopped} worker(s) arrêté(s) sur {server['name']}")

        return jsonify({
            'status': 'ok',
            'server': server_key,
            'stopped': stopped
        })

    except Exception as e:
        logger.error(f"❌ Erreur arrêt workers sur {server_key}: {e}")
        return jsonify({'error': str(e)}), 500


@crawl_api.route('/api/crawl/workers/stop-all-servers', methods=['POST'])
def stop_all_workers_all_servers():
    """
    Arrêter tous les workers sur TOUS les serveurs
    """
    import subprocess
    import time

    results = {}
    total_stopped = 0

    for server_key, server in SERVERS_CONFIG.items():
        try:
            if server['ssh'] is None:
                # Local
                result = subprocess.run(['pgrep', '-f', 'crawl_worker_multi.py'], capture_output=True, text=True)
                pids = [p for p in result.stdout.strip().split('\n') if p]
                for pid in pids:
                    subprocess.run(['kill', '-9', pid], check=False)
                stopped = len(pids)
            else:
                # Distant via SSH
                run_ssh_command(server_key, "pkill -9 -f crawl_worker_multi.py", timeout=30)
                stopped = 1  # On ne peut pas facilement compter

            results[server_key] = {'stopped': stopped, 'status': 'ok'}
            total_stopped += stopped
            logger.info(f"🛑 Workers arrêtés sur {server['name']}")

        except Exception as e:
            results[server_key] = {'stopped': 0, 'status': 'error', 'error': str(e)}
            logger.error(f"❌ Erreur arrêt workers sur {server_key}: {e}")

    return jsonify({
        'status': 'ok',
        'total_stopped': total_stopped,
        'servers_count': len(SERVERS_CONFIG),
        'results': results
    })


@crawl_api.route('/api/crawl/workers/stop/<pid>', methods=['POST'])
def stop_worker(pid):
    """
    Arrêter un worker spécifique par son PID sur un serveur
    """
    import subprocess
    import time

    data = request.get_json() or {}
    server_key = data.get('server', 'local')

    if server_key not in SERVERS_CONFIG:
        return jsonify({'error': f'Serveur inconnu: {server_key}'}), 400

    server = SERVERS_CONFIG[server_key]

    try:
        if server['ssh'] is None:
            # Local - vérifier que c'est bien un worker crawl
            result = subprocess.run(['ps', '-p', pid, '-o', 'cmd='], capture_output=True, text=True)
            if 'crawl_worker' not in result.stdout:
                return jsonify({'error': 'PID invalide ou pas un worker crawl'}), 400

            subprocess.run(['kill', '-TERM', pid], check=False)
            time.sleep(0.5)
            subprocess.run(['kill', '-9', pid], check=False)
        else:
            # Distant via SSH
            kill_cmd = f"kill -9 {pid}"
            run_ssh_command(server_key, kill_cmd)

        logger.info(f"🛑 Worker PID {pid} arrêté sur {server['name']}")

        return jsonify({
            'status': 'ok',
            'server': server_key,
            'stopped_pid': pid
        })

    except Exception as e:
        logger.error(f"❌ Erreur arrêt worker {pid} sur {server_key}: {e}")
        return jsonify({'error': str(e)}), 500


@crawl_api.route('/api/crawl/stats', methods=['GET'])
def get_crawl_stats():
    """
    Statistiques globales du crawl distribué
    """
    session = get_session()
    workers_data = load_workers()

    try:
        # Stats depuis la DB
        # Note: Un site peut être vendeur ET acheteur, donc on filtre sur is_link_seller
        total_sellers = session.query(Site).filter(Site.is_link_seller == True).count()
        sellers_crawled = session.query(Site).filter(
            Site.is_link_seller == True,
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

            # Sites crawlés ce jour (vendeurs ET acheteurs avec backlinks crawlés)
            sellers_crawled = session.query(Site).filter(
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

            # Emails trouvés ce jour - basé sur email_found_at (date réelle de découverte)
            emails_found = session.query(Site).filter(
                Site.emails.isnot(None),
                Site.emails != '',
                Site.emails != '[]',
                Site.emails != 'NO EMAIL FOUND',
                Site.email_found_at >= day,
                Site.email_found_at < next_day
            ).count()

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


# ============================================================================
# ENRICHISSEMENT DES ACHETEURS EXISTANTS
# ============================================================================

@crawl_api.route('/api/crawl/enrich-buyers-task', methods=['GET'])
def get_enrich_buyers_task():
    """
    Obtenir un batch d'acheteurs à enrichir.

    Ces acheteurs existent déjà dans la base mais n'ont pas toutes leurs données
    (email, langue, CMS, SIRET manquants).

    Query params:
    - worker_id: Identifiant unique du worker
    - batch_size: Nombre d'acheteurs à récupérer (défaut: 30)
    - priority: 'email' pour prioriser ceux sans email, 'language' pour ceux sans langue
    """
    from sqlalchemy import or_, case, and_

    worker_id = request.args.get('worker_id', 'unknown')
    batch_size = int(request.args.get('batch_size', 30))
    priority = request.args.get('priority', 'email')  # email ou language

    # Limiter la taille du batch
    batch_size = min(batch_size, 100)

    session = get_session()
    try:
        # Ordre de priorité selon le paramètre
        if priority == 'language':
            priority_order = case(
                (Site.language.is_(None), 0),
                (or_(Site.emails.is_(None), Site.emails == ''), 1),
                else_=2
            )
        else:
            priority_order = case(
                (or_(Site.emails.is_(None), Site.emails == ''), 0),
                (Site.language.is_(None), 1),
                else_=2
            )

        # Acheteurs non blacklistés, pas traités récemment
        lock_threshold = datetime.utcnow() - timedelta(minutes=30)

        # Critères: est acheteur (purchased_from NOT NULL) ET manque des données
        buyers = session.query(Site).filter(
            Site.purchased_from.isnot(None),  # C'est un acheteur
            Site.blacklisted == False,
            Site.is_active == True,
            # Manque au moins une donnée importante
            or_(
                Site.emails.is_(None),
                Site.emails == '',
                Site.language.is_(None),
                Site.cms.is_(None)
            ),
            # Pas traité récemment
            or_(
                Site.email_crawl_at.is_(None),
                Site.email_crawl_at < lock_threshold
            )
        ).order_by(
            priority_order,
            Site.id
        ).limit(batch_size * 2).with_for_update(skip_locked=True).all()

        if not buyers:
            session.commit()
            return jsonify({
                'status': 'no_tasks',
                'message': 'Aucun acheteur à enrichir',
                'sites': []
            })

        now = datetime.utcnow()
        tasks = []

        for buyer in buyers[:batch_size]:
            # Indiquer ce qui manque
            missing = []
            if not buyer.emails:
                missing.append('email')
            if not buyer.language:
                missing.append('language')
            if not buyer.cms:
                missing.append('cms')
            if buyer.domain.endswith('.fr') and not buyer.siret:
                missing.append('siret')

            tasks.append({
                'id': buyer.id,
                'domain': buyer.domain,
                'purchased_from': buyer.purchased_from,
                'missing': missing
            })

            # Marquer comme en cours de traitement
            buyer.email_crawl_at = now

        safe_commit(session)

        logger.info(f"🔄 Worker {worker_id}: {len(tasks)} acheteurs à enrichir")

        return jsonify({
            'status': 'ok',
            'worker_id': worker_id,
            'count': len(tasks),
            'sites': tasks
        })

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur get_enrich_buyers_task: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/enrich-buyers-results', methods=['POST'])
def submit_enrich_buyers_results():
    """
    Soumettre les résultats d'enrichissement des acheteurs.

    Body JSON:
    {
        "worker_id": "xxx",
        "results": [
            {
                "site_id": 123,
                "domain": "example.com",
                "emails": "contact@example.com",
                "language": "fr",
                "language_confidence": 0.95,
                "cms": "WordPress",
                "cms_version": "6.4",
                "siret": "12345678901234",
                "siren": "123456789",
                "text_sample": "..."  // Pour détection langue via Claude si nécessaire
            }
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data'}), 400

    worker_id = data.get('worker_id', 'unknown')
    results = data.get('results', [])

    if not results:
        return jsonify({'status': 'ok', 'message': 'No results', 'updated': 0})

    session = get_session()
    updated_count = 0
    emails_found = 0
    languages_found = 0

    try:
        for result in results:
            site_id = result.get('site_id')
            if not site_id:
                continue

            site = session.query(Site).filter(Site.id == site_id).first()
            if not site:
                continue

            now = datetime.utcnow()

            # Email
            emails = result.get('emails')
            if emails and emails not in ['', 'NO EMAIL FOUND']:
                if not site.emails or site.emails == 'NO EMAIL FOUND':
                    site.emails = emails
                    site.email_found_at = now
                    site.email_source = 'enrichment'
                    emails_found += 1

            # Langue
            language = result.get('language')
            language_confidence = result.get('language_confidence')
            text_sample = result.get('text_sample')

            # Si pas de langue détectée mais texte fourni, utiliser Claude
            if not language and text_sample:
                language, language_confidence = detect_language_with_claude(text_sample)

            if language and not site.language:
                site.language = language
                site.language_confidence = language_confidence or 0.85
                site.language_detected_at = now
                languages_found += 1

            # CMS
            cms = result.get('cms')
            cms_version = result.get('cms_version')
            if cms and not site.cms:
                site.cms = cms
                site.cms_version = cms_version
                site.cms_detected_at = now

            # SIRET (seulement pour .fr)
            siret = result.get('siret')
            siren = result.get('siren')
            if site.domain.endswith('.fr'):
                if siret and not site.siret:
                    site.siret = siret
                    site.siret_type = 'SIRET'
                    site.siret_found_at = now
                    site.siret_checked = True
                elif siren and not site.siren:
                    site.siren = siren
                    site.siret_type = 'SIREN'
                    site.siret_found_at = now
                    site.siret_checked = True

            site.updated_at = now
            updated_count += 1

        safe_commit(session)

        logger.info(f"🔄 Worker {worker_id}: {updated_count} acheteurs enrichis "
                    f"(emails: {emails_found}, langues: {languages_found})")

        return jsonify({
            'status': 'ok',
            'updated': updated_count,
            'emails_found': emails_found,
            'languages_found': languages_found
        })

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur submit_enrich_buyers_results: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@crawl_api.route('/api/crawl/enrich-buyers-stats', methods=['GET'])
def get_enrich_buyers_stats():
    """
    Statistiques sur l'enrichissement des acheteurs.
    """
    from sqlalchemy import or_, and_

    session = get_session()
    try:
        # Total acheteurs
        total_buyers = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False
        ).scalar() or 0

        # Avec email
        with_email = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).scalar() or 0

        # Avec langue
        with_language = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.language.isnot(None)
        ).scalar() or 0

        # Avec CMS
        with_cms = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.cms.isnot(None)
        ).scalar() or 0

        # Acheteurs .fr
        buyers_fr = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.domain.like('%.fr')
        ).scalar() or 0

        # Acheteurs .fr avec SIRET
        with_siret = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.domain.like('%.fr'),
            or_(Site.siret.isnot(None), Site.siren.isnot(None))
        ).scalar() or 0

        # À enrichir (manque email OU langue)
        to_enrich = session.query(func.count(Site.id)).filter(
            Site.purchased_from.isnot(None),
            Site.blacklisted == False,
            Site.is_active == True,
            or_(
                Site.emails.is_(None),
                Site.emails == '',
                Site.language.is_(None)
            )
        ).scalar() or 0

        return jsonify({
            'status': 'ok',
            'totals': {
                'total_buyers': total_buyers,
                'with_email': with_email,
                'with_language': with_language,
                'with_cms': with_cms,
                'buyers_fr': buyers_fr,
                'with_siret': with_siret,
                'to_enrich': to_enrich
            },
            'percentages': {
                'email': round(with_email / total_buyers * 100, 1) if total_buyers > 0 else 0,
                'language': round(with_language / total_buyers * 100, 1) if total_buyers > 0 else 0,
                'cms': round(with_cms / total_buyers * 100, 1) if total_buyers > 0 else 0,
                'siret_fr': round(with_siret / buyers_fr * 100, 1) if buyers_fr > 0 else 0
            }
        })

    except Exception as e:
        logger.error(f"❌ Erreur get_enrich_buyers_stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
