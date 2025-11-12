#!/usr/bin/env python3
"""
Routes API pour la gestion des scénarios d'automatisation
"""

from flask import request, jsonify, render_template
from campaign_database import (
    get_campaign_session,
    Scenario, ScenarioStep, ScenarioStatus, StepTrigger,
    ContactSequence, SequenceStatus
)
import logging

logger = logging.getLogger(__name__)


def register_scenario_routes(app):
    """Enregistrer toutes les routes des scénarios"""

    # ============================================================================
    # PAGES
    # ============================================================================

    @app.route('/scenarios')
    def scenarios_page():
        """Page de gestion des scénarios"""
        return render_template('scenarios.html')


    # ============================================================================
    # API - SCÉNARIOS CRUD
    # ============================================================================

    @app.route('/api/scenarios', methods=['GET'])
    def get_scenarios():
        """Lister tous les scénarios"""
        session = get_campaign_session()
        try:
            scenarios = session.query(Scenario).order_by(Scenario.created_at.desc()).all()
            return jsonify([s.to_dict() for s in scenarios])
        except Exception as e:
            logger.error(f"Erreur get_scenarios: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios', methods=['POST'])
    def create_scenario():
        """Créer un nouveau scénario"""
        session = get_campaign_session()
        try:
            data = request.get_json()

            # Validation
            if not data.get('name'):
                return jsonify({'error': 'Le nom est requis'}), 400

            # Créer le scénario
            scenario = Scenario(
                name=data['name'],
                description=data.get('description'),
                status=ScenarioStatus(data.get('status', 'draft')),
                entry_template_id=data.get('entry_template_id'),
                daily_cap=data.get('daily_cap', 500),
                cooldown_days=data.get('cooldown_days', 3),
                send_window_start=data.get('send_window_start', '09:00'),
                send_window_end=data.get('send_window_end', '17:30'),
                send_days=data.get('send_days', 'mon,tue,wed,thu,fri'),
                timezone=data.get('timezone', 'Europe/Paris'),
                min_validation_score=data.get('min_validation_score', 80),
                only_deliverable=data.get('only_deliverable', True),
                include_unsubscribe=data.get('include_unsubscribe', True),
                stop_on_reply=data.get('stop_on_reply', True),
                stop_on_unsubscribe=data.get('stop_on_unsubscribe', True)
            )

            session.add(scenario)
            session.commit()

            logger.info(f"Nouveau scénario créé: {scenario.name} (ID: {scenario.id})")

            return jsonify(scenario.to_dict()), 201

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur create_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios/<int:scenario_id>', methods=['GET'])
    def get_scenario(scenario_id):
        """Obtenir les détails d'un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            return jsonify(scenario.to_dict())

        except Exception as e:
            logger.error(f"Erreur get_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios/<int:scenario_id>', methods=['PUT'])
    def update_scenario(scenario_id):
        """Mettre à jour un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            data = request.get_json()

            # Mettre à jour les champs
            if 'name' in data:
                scenario.name = data['name']
            if 'description' in data:
                scenario.description = data['description']
            if 'status' in data:
                scenario.status = ScenarioStatus(data['status'])
            if 'daily_cap' in data:
                scenario.daily_cap = data['daily_cap']
            if 'cooldown_days' in data:
                scenario.cooldown_days = data['cooldown_days']
            if 'send_window_start' in data:
                scenario.send_window_start = data['send_window_start']
            if 'send_window_end' in data:
                scenario.send_window_end = data['send_window_end']
            if 'send_days' in data:
                scenario.send_days = data['send_days']
            if 'timezone' in data:
                scenario.timezone = data['timezone']
            if 'min_validation_score' in data:
                scenario.min_validation_score = data['min_validation_score']
            if 'only_deliverable' in data:
                scenario.only_deliverable = data['only_deliverable']

            session.commit()

            logger.info(f"Scénario {scenario_id} mis à jour")

            return jsonify(scenario.to_dict())

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur update_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios/<int:scenario_id>', methods=['DELETE'])
    def delete_scenario(scenario_id):
        """Supprimer un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            # Vérifier qu'il n'y a pas de séquences actives
            active_count = session.query(ContactSequence).filter_by(
                scenario_id=scenario_id,
                status=SequenceStatus.ACTIVE
            ).count()

            if active_count > 0:
                return jsonify({'error': f'Impossible de supprimer: {active_count} séquences actives'}), 400

            session.delete(scenario)
            session.commit()

            logger.info(f"Scénario {scenario_id} supprimé")

            return jsonify({'success': True, 'message': 'Scénario supprimé'})

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur delete_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    # ============================================================================
    # API - ÉTAPES
    # ============================================================================

    @app.route('/api/scenarios/<int:scenario_id>/steps', methods=['PUT'])
    def update_scenario_steps(scenario_id):
        """Mettre à jour toutes les étapes d'un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            data = request.get_json()
            new_steps = data.get('steps', [])

            # Supprimer les anciennes étapes
            session.query(ScenarioStep).filter_by(scenario_id=scenario_id).delete()

            # Créer les nouvelles étapes
            for step_data in new_steps:
                step = ScenarioStep(
                    scenario_id=scenario_id,
                    step_order=step_data.get('step_order', 0),
                    step_name=step_data.get('step_name'),
                    trigger_type=StepTrigger(step_data.get('trigger_type', 'entry')),
                    delay_days=step_data.get('delay_days', 0),
                    delay_hours=step_data.get('delay_hours', 0),
                    parent_step_id=step_data.get('parent_step_id'),
                    template_id=step_data.get('template_id')
                )
                session.add(step)

            session.commit()

            logger.info(f"Étapes du scénario {scenario_id} mises à jour: {len(new_steps)} étapes")

            # Recharger le scénario avec les nouvelles étapes
            session.refresh(scenario)
            return jsonify(scenario.to_dict())

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur update_scenario_steps: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    # ============================================================================
    # API - CONTRÔLE DU SCÉNARIO
    # ============================================================================

    @app.route('/api/scenarios/<int:scenario_id>/start', methods=['POST'])
    def start_scenario(scenario_id):
        """Démarrer un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            if scenario.status == ScenarioStatus.ACTIVE:
                return jsonify({'error': 'Le scénario est déjà actif'}), 400

            # Vérifier qu'il y a au moins une étape
            steps_count = session.query(ScenarioStep).filter_by(scenario_id=scenario_id).count()
            if steps_count == 0:
                return jsonify({'error': 'Le scénario doit avoir au moins une étape'}), 400

            # Activer le scénario
            scenario.status = ScenarioStatus.ACTIVE
            session.commit()

            logger.info(f"Scénario {scenario_id} démarré")

            # Lancer l'orchestrateur dans un thread séparé
            import threading
            from scenario_orchestrator import ScenarioOrchestrator

            def run_orchestrator():
                try:
                    orchestrator = ScenarioOrchestrator()
                    result = orchestrator.start_scenario(scenario_id)
                    logger.info(f"Orchestrateur terminé: {result['metrics']}")
                    orchestrator.close()
                except Exception as e:
                    logger.error(f"Erreur orchestrateur: {e}", exc_info=True)

            thread = threading.Thread(target=run_orchestrator, daemon=True)
            thread.start()

            return jsonify({
                'success': True,
                'scenario_id': scenario_id,
                'status': scenario.status.value,
                'message': f"Scénario '{scenario.name}' démarré"
            })

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur start_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios/<int:scenario_id>/pause', methods=['POST'])
    def pause_scenario(scenario_id):
        """Mettre en pause un scénario"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            if scenario.status != ScenarioStatus.ACTIVE:
                return jsonify({'error': 'Le scénario doit être actif'}), 400

            scenario.status = ScenarioStatus.PAUSED
            session.commit()

            logger.info(f"Scénario {scenario_id} mis en pause")

            return jsonify({
                'success': True,
                'scenario_id': scenario_id,
                'status': scenario.status.value,
                'message': f"Scénario '{scenario.name}' mis en pause"
            })

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur pause_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    @app.route('/api/scenarios/<int:scenario_id>/resume', methods=['POST'])
    def resume_scenario(scenario_id):
        """Reprendre un scénario en pause"""
        session = get_campaign_session()
        try:
            scenario = session.query(Scenario).get(scenario_id)
            if not scenario:
                return jsonify({'error': 'Scénario non trouvé'}), 404

            if scenario.status != ScenarioStatus.PAUSED:
                return jsonify({'error': 'Le scénario doit être en pause'}), 400

            scenario.status = ScenarioStatus.ACTIVE
            session.commit()

            logger.info(f"Scénario {scenario_id} repris")

            return jsonify({
                'success': True,
                'scenario_id': scenario_id,
                'status': scenario.status.value,
                'message': f"Scénario '{scenario.name}' repris"
            })

        except Exception as e:
            session.rollback()
            logger.error(f"Erreur resume_scenario: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()


    logger.info("Routes des scénarios enregistrées")
