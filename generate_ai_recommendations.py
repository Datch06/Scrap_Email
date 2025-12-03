#!/usr/bin/env python3
"""
Générateur de recommandations AI pour le dashboard
À exécuter manuellement depuis une session Claude Code active

Usage: claude -p "$(cat /var/www/Scrap_Email/generate_ai_recommendations.py)"
"""

import os
import sys
import json
import sqlite3
import hashlib
from datetime import datetime

# Configuration
PROJECT_PATH = '/var/www/Scrap_Email'
ANALYSIS_DB = os.path.join(PROJECT_PATH, 'ai_analysis.db')

def init_database():
    """Initialise la base de données si nécessaire"""
    conn = sqlite3.connect(ANALYSIS_DB)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            code_suggestion TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            impact_score INTEGER DEFAULT 0,
            effort_score INTEGER DEFAULT 0,
            hash TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_type TEXT NOT NULL,
            summary TEXT,
            full_response TEXT,
            tokens_used INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def collect_metrics():
    """Collecte les métriques système"""
    metrics = {}

    try:
        sys.path.insert(0, PROJECT_PATH)
        from database import get_session, Site
        session = get_session()

        metrics['total_sites'] = session.query(Site).count()
        metrics['sites_with_email'] = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()
        metrics['sites_with_siret'] = session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != ''
        ).count()

        session.close()
    except Exception as e:
        print(f"Erreur métriques sites: {e}")

    try:
        import psutil
        metrics['cpu_percent'] = psutil.cpu_percent()
        metrics['memory_percent'] = psutil.virtual_memory().percent
        metrics['disk_percent'] = psutil.disk_usage('/').percent
    except:
        pass

    return metrics

def save_recommendations(recommendations):
    """Sauvegarde les recommandations dans la base"""
    conn = sqlite3.connect(ANALYSIS_DB)
    cursor = conn.cursor()

    saved = 0
    for rec in recommendations:
        hash_content = f"{rec.get('title', '')}{rec.get('description', '')}"
        rec_hash = hashlib.md5(hash_content.encode()).hexdigest()

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO recommendations
                (category, priority, title, description, code_suggestion,
                 file_path, impact_score, effort_score, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rec.get('category', 'code_quality'),
                rec.get('priority', 'medium'),
                rec.get('title', ''),
                rec.get('description', ''),
                rec.get('code_suggestion'),
                rec.get('file_path'),
                rec.get('impact_score', 5),
                rec.get('effort_score', 5),
                rec_hash
            ))
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"Erreur sauvegarde: {e}")

    conn.commit()
    conn.close()
    return saved

def generate_recommendations_from_analysis():
    """
    Cette fonction doit être appelée avec les recommandations générées par Claude.
    Claude doit analyser le projet et retourner les recommandations au format JSON.
    """

    # Recommandations basées sur l'analyse précédente du projet
    recommendations = [
        {
            "category": "security",
            "priority": "critical",
            "title": "Race conditions dans continuous_campaign_worker",
            "description": "Le continuous_campaign_worker ne utilise pas FOR UPDATE SKIP LOCKED lors de la récupération des destinataires, ce qui peut causer des doublons d'emails envoyés. Ajouter une transaction isolée avec verrouillage.",
            "file_path": "continuous_campaign_worker.py",
            "impact_score": 9,
            "effort_score": 4
        },
        {
            "category": "security",
            "priority": "critical",
            "title": "Ajouter contrainte UNIQUE sur campaign_emails",
            "description": "Ajouter une contrainte UNIQUE sur (campaign_id, to_email) dans la table campaign_emails pour éviter les doublons d'envoi au niveau base de données.",
            "file_path": "campaign_database.py",
            "code_suggestion": "UniqueConstraint('campaign_id', 'to_email', name='uq_campaign_email')",
            "impact_score": 10,
            "effort_score": 2
        },
        {
            "category": "performance",
            "priority": "high",
            "title": "Ajouter index sur colonnes fréquemment filtrées",
            "description": "Les requêtes sur Site filtrent souvent par emails, status, created_at. Ajouter des index composites pour accélérer ces requêtes (actuellement full table scan).",
            "file_path": "database.py",
            "code_suggestion": "Index('idx_site_emails_status', 'emails', 'status')",
            "impact_score": 8,
            "effort_score": 2
        },
        {
            "category": "reliability",
            "priority": "high",
            "title": "Memory leaks dans les daemons",
            "description": "Les daemons (validate_emails_daemon, cms_detector_daemon) tournent indéfiniment sans gc.collect() explicite. Les sessions SQLAlchemy peuvent ne pas être fermées correctement. Ajouter des context managers et gc.collect() périodique.",
            "file_path": "validate_emails_daemon.py",
            "code_suggestion": "import gc; gc.collect()  # Ajouter après chaque batch",
            "impact_score": 7,
            "effort_score": 3
        },
        {
            "category": "performance",
            "priority": "high",
            "title": "Timeout validation email trop court",
            "description": "Le timeout de 10 secondes pour la validation SMTP est insuffisant pour certains serveurs lents, causant des faux INVALID. Augmenter à 20-30 secondes avec retry progressif.",
            "file_path": "validate_emails.py",
            "code_suggestion": "REQUEST_TIMEOUT = 25  # Augmenté de 10",
            "impact_score": 7,
            "effort_score": 1
        },
        {
            "category": "code_quality",
            "priority": "medium",
            "title": "Code dupliqué dans les scrapers LinkAvista",
            "description": "4 versions du scraper LinkAvista existent (scrape_linkavista.py, _complete.py, _ultimate.py, _optimized.py) avec beaucoup de code copié-collé. Créer une classe base ScrapeBase avec la logique commune.",
            "file_path": "scrape_linkavista.py",
            "impact_score": 5,
            "effort_score": 6
        },
        {
            "category": "reliability",
            "priority": "medium",
            "title": "Ajouter monitoring Prometheus",
            "description": "Aucun système de monitoring en place. Ajouter Prometheus pour les métriques (counters, gauges, histograms) et Grafana pour la visualisation. Inclure alertes sur erreurs critiques.",
            "impact_score": 8,
            "effort_score": 7
        },
        {
            "category": "feature",
            "priority": "medium",
            "title": "Ajouter health check endpoint",
            "description": "Créer un endpoint /api/health qui vérifie la connexion DB, les daemons actifs, et l'espace disque. Utile pour le monitoring et les load balancers.",
            "file_path": "app.py",
            "code_suggestion": "@app.route('/api/health')\ndef health_check():\n    return jsonify({'status': 'ok', 'db': check_db(), 'disk': check_disk()})",
            "impact_score": 6,
            "effort_score": 2
        },
        {
            "category": "code_quality",
            "priority": "medium",
            "title": "Utiliser Alembic pour les migrations",
            "description": "30+ scripts de migration ad-hoc existent. Migrer vers Alembic pour un versioning propre du schéma avec possibilité de rollback.",
            "impact_score": 6,
            "effort_score": 8
        },
        {
            "category": "performance",
            "priority": "low",
            "title": "Ajouter cache Redis pour les stats",
            "description": "Les stats du dashboard sont recalculées à chaque requête (même avec cache fichier). Utiliser Redis pour un cache plus performant et partagé entre instances.",
            "impact_score": 5,
            "effort_score": 5
        }
    ]

    return recommendations


if __name__ == '__main__':
    print("=" * 60)
    print("GÉNÉRATEUR DE RECOMMANDATIONS AI")
    print("=" * 60)

    # Initialiser la base
    init_database()
    print("Base de données initialisée")

    # Collecter les métriques
    metrics = collect_metrics()
    print(f"Métriques collectées: {json.dumps(metrics, indent=2)}")

    # Générer et sauvegarder les recommandations
    recommendations = generate_recommendations_from_analysis()
    saved = save_recommendations(recommendations)

    print(f"\n{saved} nouvelles recommandations sauvegardées")
    print(f"Total recommandations générées: {len(recommendations)}")

    # Afficher un résumé
    print("\nRésumé des recommandations:")
    for rec in recommendations:
        print(f"  [{rec['priority'].upper()}] {rec['title']}")

    print("\n" + "=" * 60)
    print("Recommandations disponibles sur le dashboard!")
    print("=" * 60)
