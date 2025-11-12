#!/usr/bin/env python3
"""
Daemon pour l'orchestrateur de scénarios
Tourne en continu et traite les opérations en attente
"""

import time
import logging
import argparse
from datetime import datetime
from scenario_orchestrator import ScenarioOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Daemon orchestrateur de scénarios')
    parser.add_argument('--interval', type=int, default=60,
                       help='Intervalle en secondes entre chaque cycle (défaut: 60)')
    parser.add_argument('--check-not-opened-interval', type=int, default=3600,
                       help='Intervalle pour vérifier les not_opened (défaut: 3600s = 1h)')

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("🤖 DAEMON ORCHESTRATEUR DE SCÉNARIOS")
    logger.info("=" * 70)
    logger.info(f"Intervalle de traitement: {args.interval}s")
    logger.info(f"Vérification not_opened: toutes les {args.check_not_opened_interval}s")
    logger.info("=" * 70)
    logger.info("")

    last_not_opened_check = 0

    try:
        while True:
            cycle_start = time.time()
            logger.info(f"🔄 Cycle démarré à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            orchestrator = ScenarioOrchestrator()

            try:
                # 1) Traiter les opérations en attente
                result = orchestrator.process_pending_operations()
                logger.info(f"   📊 Résultats: {result['sent']} envoyés, {result['failed']} échecs")

                # 2) Vérifier les not_opened périodiquement
                now = time.time()
                if now - last_not_opened_check >= args.check_not_opened_interval:
                    logger.info("   🔍 Vérification des not_opened...")
                    not_opened_result = orchestrator.check_not_opened_followups(hours_threshold=72)
                    logger.info(f"   📊 Not_opened: {not_opened_result['processed']} relances déclenchées")
                    last_not_opened_check = now

            except Exception as e:
                logger.error(f"   ❌ Erreur dans le cycle: {e}", exc_info=True)

            finally:
                orchestrator.close()

            # Attendre avant le prochain cycle
            cycle_duration = time.time() - cycle_start
            sleep_time = max(0, args.interval - cycle_duration)

            if sleep_time > 0:
                logger.info(f"   💤 Pause de {sleep_time:.1f}s avant le prochain cycle")
                logger.info("")
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 70)
        logger.info("🛑 Arrêt du daemon demandé")
        logger.info("=" * 70)


if __name__ == '__main__':
    main()
