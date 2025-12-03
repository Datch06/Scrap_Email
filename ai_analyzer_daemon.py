#!/usr/bin/env python3
"""
AI Analyzer Daemon - Analyse continue du projet avec Claude AI
Exécute des analyses périodiques et met à jour les recommandations
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime

# Configuration
ANALYSIS_INTERVAL_HOURS = 6  # Analyse toutes les 6 heures
METRICS_INTERVAL_MINUTES = 30  # Collecte métriques toutes les 30 min
LOG_FILE = '/var/log/scrap_email/ai_analyzer.log'

# Setup logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ai_analyzer_daemon')

# Ajouter le chemin du projet
sys.path.insert(0, '/var/www/Scrap_Email')

# Flag pour arrêt propre
running = True

def signal_handler(signum, frame):
    global running
    logger.info(f"Signal {signum} reçu, arrêt en cours...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def run_daemon():
    """Boucle principale du daemon"""
    global running

    logger.info("=== Démarrage AI Analyzer Daemon ===")

    # Vérifier Claude CLI
    claude_cli = '/home/debian/.nvm/versions/node/v20.19.5/bin/claude'
    if not os.path.exists(claude_cli):
        logger.warning("Claude CLI non trouvé - mode metrics seulement")
    else:
        logger.info(f"Claude CLI trouvé: {claude_cli}")

    try:
        from claude_ai_analyzer import ClaudeAIAnalyzer
        analyzer = ClaudeAIAnalyzer()
    except Exception as e:
        logger.error(f"Erreur initialisation analyzer: {e}")
        return

    last_analysis = None
    last_metrics = None

    while running:
        now = datetime.now()

        try:
            # Collecte des métriques (toutes les 30 min)
            if last_metrics is None or (now - last_metrics).total_seconds() > METRICS_INTERVAL_MINUTES * 60:
                logger.info("Collecte des métriques système...")
                metrics = analyzer.collect_system_metrics()
                logger.info(f"Métriques collectées: {len(metrics)} valeurs")
                last_metrics = now

            # Analyse complète (toutes les 6 heures)
            if analyzer.claude_available and (last_analysis is None or (now - last_analysis).total_seconds() > ANALYSIS_INTERVAL_HOURS * 3600):
                if analyzer.should_run_analysis():
                    logger.info("Lancement analyse Claude Code CLI...")
                    result = analyzer.analyze_with_claude()

                    if result and result.get('success'):
                        recs = result.get('recommendations', [])
                        tokens = result.get('tokens_used', 0)
                        logger.info(f"Analyse terminée: {len(recs)} recommandations, {tokens} tokens")
                    else:
                        logger.error(f"Erreur analyse: {result.get('error', 'Unknown')}")

                    last_analysis = now
                else:
                    logger.debug("Analyse récente existe, skip")

        except Exception as e:
            logger.error(f"Erreur dans la boucle: {e}", exc_info=True)

        # Attendre 5 minutes avant la prochaine vérification
        for _ in range(300):  # 5 min = 300 secondes
            if not running:
                break
            time.sleep(1)

    logger.info("=== Arrêt AI Analyzer Daemon ===")


if __name__ == '__main__':
    run_daemon()
