#!/usr/bin/env python3
"""
Claude AI Analyzer - Système d'analyse et recommandations intelligentes
Utilise l'API Anthropic pour analyser le projet et proposer des optimisations
"""

import os
import json
import sqlite3
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_PATH = '/var/www/Scrap_Email'
ANALYSIS_DB = os.path.join(PROJECT_PATH, 'ai_analysis.db')
ANALYSIS_CACHE_HOURS = 24  # Refaire analyse complète toutes les 24h
CLAUDE_CREDENTIALS_PATH = '/home/debian/.claude/.credentials.json'


def get_anthropic_api_key():
    """Récupère la clé API depuis les credentials Claude Code"""
    # D'abord essayer l'env var
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        return api_key

    # Sinon lire depuis les credentials Claude Code
    try:
        if os.path.exists(CLAUDE_CREDENTIALS_PATH):
            with open(CLAUDE_CREDENTIALS_PATH, 'r') as f:
                creds = json.load(f)
                # Le format peut varier, essayer plusieurs clés
                api_key = creds.get('apiKey') or creds.get('anthropicApiKey') or creds.get('claudeAiApiKey', '')
                if api_key:
                    return api_key
    except Exception as e:
        logger.warning(f"Erreur lecture credentials: {e}")

    return ''


class ClaudeAIAnalyzer:
    """Analyseur intelligent basé sur l'API Anthropic"""

    def __init__(self):
        self.api_key = get_anthropic_api_key()
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("Client Anthropic initialisé avec succès")
            except Exception as e:
                logger.warning(f"Erreur initialisation client Anthropic: {e}")
        else:
            logger.warning("Pas de clé API Anthropic trouvée")
        self.claude_available = self.client is not None
        self.init_database()

    def init_database(self):
        """Initialise la base de données des analyses"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        # Table des recommandations
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

        # Table des métriques système
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_data TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table des analyses
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

    def collect_system_metrics(self):
        """Collecte les métriques système actuelles"""
        metrics = {}

        try:
            # Stats base de données sites
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
            logger.warning(f"Erreur collecte métriques sites: {e}")

        try:
            # Stats campagnes
            from campaign_database import get_campaign_session, Campaign, CampaignEmail
            camp_session = get_campaign_session()

            metrics['total_campaigns'] = camp_session.query(Campaign).count()
            metrics['emails_sent'] = camp_session.query(CampaignEmail).filter(
                CampaignEmail.status == 'sent'
            ).count()
            metrics['emails_opened'] = camp_session.query(CampaignEmail).filter(
                CampaignEmail.status == 'opened'
            ).count()

            camp_session.close()
        except Exception as e:
            logger.warning(f"Erreur collecte métriques campagnes: {e}")

        try:
            # Stats workers
            workers_file = os.path.join(PROJECT_PATH, 'crawl_workers.json')
            if os.path.exists(workers_file):
                with open(workers_file, 'r') as f:
                    workers_data = json.load(f)
                    metrics['active_workers'] = len([w for w in workers_data.values()
                                                    if isinstance(w, dict) and w.get('last_heartbeat')])
        except Exception as e:
            logger.warning(f"Erreur collecte métriques workers: {e}")

        try:
            # Stats validation emails
            from database import get_session, Site
            session = get_session()

            metrics['emails_validated'] = session.query(Site).filter(
                Site.email_validation_status.isnot(None)
            ).count()
            metrics['emails_valid'] = session.query(Site).filter(
                Site.email_validation_status == 'valid'
            ).count()

            session.close()
        except Exception as e:
            logger.warning(f"Erreur collecte métriques validation: {e}")

        try:
            # Performance système
            import psutil
            metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
            metrics['memory_percent'] = psutil.virtual_memory().percent
            metrics['disk_percent'] = psutil.disk_usage('/').percent
        except Exception as e:
            logger.warning(f"Erreur collecte métriques système: {e}")

        # Sauvegarder métriques
        self.save_metrics(metrics)

        return metrics

    def save_metrics(self, metrics):
        """Sauvegarde les métriques dans la base"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                cursor.execute('''
                    INSERT INTO system_metrics (metric_name, metric_value)
                    VALUES (?, ?)
                ''', (name, value))
            else:
                cursor.execute('''
                    INSERT INTO system_metrics (metric_name, metric_data)
                    VALUES (?, ?)
                ''', (name, json.dumps(value)))

        conn.commit()
        conn.close()

    def get_code_samples(self):
        """Récupère des échantillons de code pour analyse"""
        samples = {}

        key_files = [
            'app.py',
            'database.py',
            'campaign_database.py',
            'distributed_crawl_api.py',
            'crawl_worker_multi.py',
            'validate_emails_daemon.py',
            'campaign_sender.py',
            'continuous_campaign_worker.py'
        ]

        for filename in key_files:
            filepath = os.path.join(PROJECT_PATH, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Limiter à 2000 caractères par fichier pour l'API
                        samples[filename] = content[:2000] + ('...' if len(content) > 2000 else '')
                except Exception as e:
                    logger.warning(f"Erreur lecture {filename}: {e}")

        return samples

    def get_recent_errors(self):
        """Récupère les erreurs récentes des logs"""
        errors = []

        log_files = [
            '/var/log/scrap_email/app.log',
            '/var/log/scrap_email/validation.log',
            '/var/log/scrap_email/campaign.log',
            os.path.join(PROJECT_PATH, 'logs', 'app.log'),
            os.path.join(PROJECT_PATH, 'logs', 'validation.log')
        ]

        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    result = subprocess.run(
                        ['tail', '-100', log_file],
                        capture_output=True, text=True, timeout=10
                    )
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'ERROR' in line or 'Exception' in line or 'Traceback' in line:
                            errors.append(line[:200])
                except Exception as e:
                    logger.warning(f"Erreur lecture log {log_file}: {e}")

        return errors[-20:]  # Dernières 20 erreurs

    def analyze_with_claude(self, context_type='full'):
        """Analyse le projet avec l'API Anthropic"""
        if not self.claude_available or not self.client:
            logger.error("Client Anthropic non disponible")
            return {'success': False, 'error': 'Client Anthropic non disponible'}

        # Collecter le contexte
        metrics = self.collect_system_metrics()
        code_samples = self.get_code_samples()
        recent_errors = self.get_recent_errors()

        # Construire le prompt
        prompt = self._build_analysis_prompt(metrics, code_samples, recent_errors, context_type)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            analysis_text = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Sauvegarder l'analyse
            self._save_analysis(context_type, analysis_text, tokens_used)

            # Parser et sauvegarder les recommandations
            recommendations = self._parse_recommendations(analysis_text)
            self._save_recommendations(recommendations)

            return {
                'success': True,
                'analysis': analysis_text,
                'recommendations': recommendations,
                'tokens_used': tokens_used
            }

        except Exception as e:
            logger.error(f"Erreur analyse Claude: {e}")
            return {'success': False, 'error': str(e)}

    def _build_analysis_prompt(self, metrics, code_samples, errors, context_type):
        """Construit le prompt pour Claude"""

        prompt = f"""Tu es un expert en développement Python/Flask et en optimisation de systèmes.
Analyse ce projet de scraping d'emails et de gestion de campagnes.

## MÉTRIQUES ACTUELLES
```json
{json.dumps(metrics, indent=2)}
```

## ÉCHANTILLONS DE CODE (fichiers clés)
"""
        for filename, content in code_samples.items():
            prompt += f"\n### {filename}\n```python\n{content}\n```\n"

        if errors:
            prompt += f"""
## ERREURS RÉCENTES
```
{chr(10).join(errors[:10])}
```
"""

        prompt += """
## TA MISSION
Analyse ce système et génère des recommandations d'optimisation.

Réponds UNIQUEMENT avec un JSON valide dans ce format exact:
```json
{
  "recommendations": [
    {
      "category": "performance|security|reliability|feature|code_quality",
      "priority": "critical|high|medium|low",
      "title": "Titre court de la recommandation",
      "description": "Description détaillée du problème et de la solution",
      "code_suggestion": "Code exemple si applicable (ou null)",
      "file_path": "Fichier concerné (ou null)",
      "impact_score": 1-10,
      "effort_score": 1-10
    }
  ],
  "health_score": 0-100,
  "summary": "Résumé global de l'état du système"
}
```

Génère entre 5 et 10 recommandations prioritaires basées sur:
1. Les erreurs récentes (si présentes)
2. Les métriques de performance
3. La qualité du code
4. La sécurité
5. L'efficacité opérationnelle

Focus sur des améliorations CONCRÈTES et ACTIONNABLES.
"""
        return prompt

    def _save_analysis(self, analysis_type, response_text, tokens_used):
        """Sauvegarde l'analyse dans la base"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO analysis_history (analysis_type, full_response, tokens_used)
            VALUES (?, ?, ?)
        ''', (analysis_type, response_text, tokens_used))

        conn.commit()
        conn.close()

    def _parse_recommendations(self, response_text):
        """Parse les recommandations depuis la réponse Claude"""
        try:
            # Extraire le JSON de la réponse
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Essayer de parser directement
                json_str = response_text

            data = json.loads(json_str)
            return data.get('recommendations', [])
        except Exception as e:
            logger.error(f"Erreur parsing recommandations: {e}")
            return []

    def _save_recommendations(self, recommendations):
        """Sauvegarde les recommandations dans la base"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        for rec in recommendations:
            # Générer un hash unique pour éviter les doublons
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
            except Exception as e:
                logger.warning(f"Erreur sauvegarde recommandation: {e}")

        conn.commit()
        conn.close()

    def get_pending_recommendations(self, limit=20):
        """Récupère les recommandations en attente"""
        conn = sqlite3.connect(ANALYSIS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM recommendations
            WHERE status = 'pending'
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                impact_score DESC,
                created_at DESC
            LIMIT ?
        ''', (limit,))

        recommendations = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return recommendations

    def get_recommendations_stats(self):
        """Récupère les statistiques des recommandations"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        stats = {}

        # Par statut
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM recommendations
            GROUP BY status
        ''')
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Par priorité (pending uniquement)
        cursor.execute('''
            SELECT priority, COUNT(*) as count
            FROM recommendations
            WHERE status = 'pending'
            GROUP BY priority
        ''')
        stats['by_priority'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Par catégorie (pending uniquement)
        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM recommendations
            WHERE status = 'pending'
            GROUP BY category
        ''')
        stats['by_category'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Total
        cursor.execute('SELECT COUNT(*) FROM recommendations WHERE status = "pending"')
        stats['total_pending'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM recommendations WHERE status = "completed"')
        stats['total_completed'] = cursor.fetchone()[0]

        conn.close()

        return stats

    def mark_recommendation_done(self, recommendation_id):
        """Marque une recommandation comme complétée"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE recommendations
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (recommendation_id,))

        conn.commit()
        conn.close()

        return cursor.rowcount > 0

    def dismiss_recommendation(self, recommendation_id):
        """Rejette une recommandation"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE recommendations
            SET status = 'dismissed'
            WHERE id = ?
        ''', (recommendation_id,))

        conn.commit()
        conn.close()

        return cursor.rowcount > 0

    def get_metrics_history(self, metric_name, days=7):
        """Récupère l'historique d'une métrique"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        since = datetime.now() - timedelta(days=days)

        cursor.execute('''
            SELECT metric_value, recorded_at
            FROM system_metrics
            WHERE metric_name = ? AND recorded_at > ?
            ORDER BY recorded_at
        ''', (metric_name, since.isoformat()))

        history = [{'value': row[0], 'date': row[1]} for row in cursor.fetchall()]
        conn.close()

        return history

    def should_run_analysis(self):
        """Vérifie si une nouvelle analyse est nécessaire"""
        conn = sqlite3.connect(ANALYSIS_DB)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT created_at FROM analysis_history
            ORDER BY created_at DESC LIMIT 1
        ''')

        row = cursor.fetchone()
        conn.close()

        if not row:
            return True

        last_analysis = datetime.fromisoformat(row[0])
        hours_since = (datetime.now() - last_analysis).total_seconds() / 3600

        return hours_since >= ANALYSIS_CACHE_HOURS


# API Flask Blueprint
from flask import Blueprint, jsonify, request

ai_analyzer_bp = Blueprint('ai_analyzer', __name__)
analyzer = ClaudeAIAnalyzer()

@ai_analyzer_bp.route('/api/ai/recommendations', methods=['GET'])
def get_recommendations():
    """Récupère les recommandations AI"""
    limit = request.args.get('limit', 20, type=int)
    recommendations = analyzer.get_pending_recommendations(limit)
    stats = analyzer.get_recommendations_stats()

    return jsonify({
        'recommendations': recommendations,
        'stats': stats
    })

@ai_analyzer_bp.route('/api/ai/recommendations/<int:rec_id>/complete', methods=['POST'])
def complete_recommendation(rec_id):
    """Marque une recommandation comme complétée"""
    success = analyzer.mark_recommendation_done(rec_id)
    return jsonify({'success': success})

@ai_analyzer_bp.route('/api/ai/recommendations/<int:rec_id>/dismiss', methods=['POST'])
def dismiss_recommendation(rec_id):
    """Rejette une recommandation"""
    success = analyzer.dismiss_recommendation(rec_id)
    return jsonify({'success': success})

@ai_analyzer_bp.route('/api/ai/analyze', methods=['POST'])
def trigger_analysis():
    """Déclenche une nouvelle analyse"""
    result = analyzer.analyze_with_claude()
    return jsonify(result)

@ai_analyzer_bp.route('/api/ai/metrics', methods=['GET'])
def get_metrics():
    """Récupère les métriques système"""
    metrics = analyzer.collect_system_metrics()
    return jsonify(metrics)

@ai_analyzer_bp.route('/api/ai/metrics/history/<metric_name>', methods=['GET'])
def get_metric_history(metric_name):
    """Récupère l'historique d'une métrique"""
    days = request.args.get('days', 7, type=int)
    history = analyzer.get_metrics_history(metric_name, days)
    return jsonify(history)

@ai_analyzer_bp.route('/api/ai/status', methods=['GET'])
def get_ai_status():
    """Vérifie le statut du système AI"""
    has_api_key = bool(ANTHROPIC_API_KEY)
    needs_analysis = analyzer.should_run_analysis()
    stats = analyzer.get_recommendations_stats()

    return jsonify({
        'configured': has_api_key,
        'needs_analysis': needs_analysis,
        'stats': stats
    })


if __name__ == '__main__':
    # Test du module
    analyzer = ClaudeAIAnalyzer()

    print("Collecte des métriques...")
    metrics = analyzer.collect_system_metrics()
    print(f"Métriques: {json.dumps(metrics, indent=2)}")

    if ANTHROPIC_API_KEY:
        print("\nLancement de l'analyse Claude...")
        result = analyzer.analyze_with_claude()
        print(f"Résultat: {json.dumps(result, indent=2)}")
    else:
        print("\nATTENTION: ANTHROPIC_API_KEY non configurée")
        print("Configurez: export ANTHROPIC_API_KEY='votre-clé'")
