#!/usr/bin/env python3
"""
Orchestrateur de scénarios d'automatisation d'emails
Gère l'exécution des séquences comportementales
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time

from database import get_session, Site
from campaign_database import (
    get_campaign_session,
    Scenario, ScenarioStep, ScenarioStatus, StepTrigger,
    ContactSequence, SequenceStatus,
    OperationLedger,
    CampaignEmail, EmailStatus,
    EmailTemplate
)
from ses_manager import SESManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScenarioOrchestrator:
    """
    Orchestrateur principal des scénarios d'automatisation.
    Responsable de :
    - Lancement du batch initial
    - Écoute des nouveaux contacts
    - Réaction aux événements (opened, clicked, etc.)
    - Planification des suivis
    """

    def __init__(self):
        self.db_session = get_session()
        self.campaign_session = get_campaign_session()
        self.ses_manager = SESManager()

    def start_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """
        Démarrer un scénario : batch initial + activation du listener
        """
        logger.info(f"🚀 Démarrage du scénario {scenario_id}")

        scenario = self.campaign_session.query(Scenario).get(scenario_id)
        if not scenario:
            raise ValueError(f"Scénario {scenario_id} non trouvé")

        if scenario.status != ScenarioStatus.ACTIVE:
            raise ValueError(f"Le scénario doit être actif (status actuel: {scenario.status.value})")

        # Vérifier qu'il y a au moins une étape entry
        entry_step = self.campaign_session.query(ScenarioStep).filter_by(
            scenario_id=scenario_id,
            trigger_type=StepTrigger.ENTRY
        ).first()

        if not entry_step:
            raise ValueError("Le scénario doit avoir au moins une étape d'entrée (trigger=ENTRY)")

        # 1) Traiter le batch initial
        result = self._process_initial_batch(scenario, entry_step)

        logger.info(f"✅ Scénario {scenario_id} démarré: {result['metrics']['planned_sends']} emails planifiés")

        return result

    def _process_initial_batch(self, scenario: Scenario, entry_step: ScenarioStep) -> Dict[str, Any]:
        """
        Traiter le batch initial : tous les contacts éligibles
        """
        logger.info(f"📦 Traitement du batch initial pour le scénario '{scenario.name}'")

        # Récupérer les contacts éligibles
        eligible_contacts = self._get_eligible_contacts(scenario)

        logger.info(f"   → {len(eligible_contacts)} contacts éligibles trouvés")

        actions = []
        planned = 0
        skipped_cooldown = 0
        skipped_recent = 0

        for contact in eligible_contacts:
            # Vérifier la déduplication (déjà dans ce scénario ?)
            existing_sequence = self.campaign_session.query(ContactSequence).filter_by(
                scenario_id=scenario.id,
                contact_id=contact.id
            ).first()

            if existing_sequence and existing_sequence.status == SequenceStatus.ACTIVE:
                skipped_recent += 1
                continue

            # Vérifier le cooldown
            if self._check_cooldown(contact.id, scenario.cooldown_days):
                skipped_cooldown += 1
                continue

            # Créer la séquence pour ce contact
            sequence = ContactSequence(
                scenario_id=scenario.id,
                contact_id=contact.id,
                current_step_id=entry_step.id,
                status=SequenceStatus.ACTIVE,
                entered_at=datetime.utcnow(),
                next_action_at=self._calculate_send_time(scenario, contact)
            )
            self.campaign_session.add(sequence)

            # Planifier l'envoi
            action = self._plan_email_send(scenario, entry_step, contact, sequence, reason="entry_batch")
            if action:
                actions.append(action)
                planned += 1

        # Commit des séquences
        self.campaign_session.commit()

        # Mettre à jour les stats du scénario
        scenario.total_contacts_entered += planned
        self.campaign_session.commit()

        return {
            'scenario_id': scenario.id,
            'generated_at': datetime.utcnow().isoformat(),
            'actions': actions,
            'metrics': {
                'planned_sends': planned,
                'skipped_due_to_cooldown': skipped_cooldown,
                'skipped_due_to_recent_send': skipped_recent
            }
        }

    def _get_eligible_contacts(self, scenario: Scenario) -> List[Site]:
        """
        Récupérer les contacts éligibles pour un scénario
        """
        query = self.db_session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        )

        # Filtrer par score de validation
        if scenario.min_validation_score > 0:
            query = query.filter(Site.email_validation_score >= scenario.min_validation_score)

        # Filtrer par deliverability
        if scenario.only_deliverable:
            query = query.filter(Site.email_deliverable == True)

        contacts = query.limit(1000).all()  # Limiter pour le moment

        return contacts

    def _check_cooldown(self, contact_id: int, cooldown_days: int) -> bool:
        """
        Vérifier si le contact est en cooldown
        """
        if cooldown_days <= 0:
            return False

        cutoff = datetime.utcnow() - timedelta(days=cooldown_days)

        # Vérifier dans les séquences actives
        recent_action = self.campaign_session.query(ContactSequence).filter(
            ContactSequence.contact_id == contact_id,
            ContactSequence.last_email_sent_at >= cutoff
        ).first()

        return recent_action is not None

    def _calculate_send_time(self, scenario: Scenario, contact: Site) -> datetime:
        """
        Calculer le prochain créneau d'envoi valide selon les contraintes
        """
        now = datetime.utcnow()

        # Pour l'instant, envoyer immédiatement
        # TODO: Implémenter la logique de fenêtre d'envoi + quota journalier
        return now

    def _plan_email_send(
        self,
        scenario: Scenario,
        step: ScenarioStep,
        contact: Site,
        sequence: ContactSequence,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Planifier l'envoi d'un email
        """
        # Générer la clé d'idempotence
        idempotency_key = self._generate_idempotency_key(
            contact.id, step.template_id, scenario.id, step.id
        )

        # Vérifier si déjà exécuté
        if self._is_already_executed(idempotency_key):
            logger.debug(f"   Opération {idempotency_key} déjà exécutée, skip")
            return None

        # Enregistrer dans le ledger
        operation = OperationLedger(
            op_id=idempotency_key,
            op_type='send_email',
            scenario_id=scenario.id,
            contact_id=contact.id,
            step_id=step.id,
            template_id=step.template_id,
            scheduled_at=sequence.next_action_at,
            status='pending',
            reason=reason
        )
        self.campaign_session.add(operation)

        return {
            'type': 'send_email',
            'reason': reason,
            'contact_id': contact.id,
            'template_id': step.template_id,
            'idempotency_key': idempotency_key,
            'run_at': sequence.next_action_at.isoformat() if sequence.next_action_at else None
        }

    def _generate_idempotency_key(
        self,
        contact_id: int,
        template_id: int,
        scenario_id: int,
        step_id: int
    ) -> str:
        """
        Générer une clé d'idempotence unique
        """
        key_data = f"{contact_id}:{template_id}:{scenario_id}:{step_id}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _is_already_executed(self, idempotency_key: str) -> bool:
        """
        Vérifier si une opération a déjà été exécutée
        """
        existing = self.campaign_session.query(OperationLedger).filter_by(
            op_id=idempotency_key,
            status='executed'
        ).first()

        return existing is not None

    def _prepare_email_variables(self, contact: Site, scenario: Scenario, sequence: ContactSequence) -> Dict[str, str]:
        """
        Préparer les variables de personnalisation pour un email
        """
        # Variables de base
        variables = {
            'domain': contact.domain or '',
            'email': contact.emails or '',
            'contact_name': contact.contact or '',
            'siret': contact.siret or '',
            'phone': contact.phone or '',
            'scenario_name': scenario.name,
        }

        # Lien de désinscription
        unsubscribe_link = f"https://votre-domaine.com/unsubscribe?contact_id={contact.id}&scenario_id={scenario.id}"
        variables['unsubscribe_link'] = unsubscribe_link

        # Tracking links (pour les clics)
        tracking_base = f"https://votre-domaine.com/track/click?contact_id={contact.id}&scenario_id={scenario.id}&url="
        variables['tracking_base'] = tracking_base

        return variables

    def _replace_variables(self, text: str, variables: Dict[str, str]) -> str:
        """
        Remplacer les variables dans un texte
        Format: {{variable_name}}
        """
        if not text:
            return text

        result = text
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))

        return result

    def process_pending_operations(self, scenario_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Traiter les opérations en attente (emails à envoyer)
        """
        logger.info("📨 Traitement des opérations en attente")

        query = self.campaign_session.query(OperationLedger).filter(
            OperationLedger.status == 'pending',
            OperationLedger.op_type == 'send_email',
            OperationLedger.scheduled_at <= datetime.utcnow()
        )

        if scenario_id:
            query = query.filter(OperationLedger.scenario_id == scenario_id)

        pending_ops = query.order_by(OperationLedger.scheduled_at).limit(100).all()

        logger.info(f"   → {len(pending_ops)} opérations à traiter")

        sent = 0
        failed = 0

        for operation in pending_ops:
            try:
                # Récupérer le contexte
                contact = self.db_session.query(Site).get(operation.contact_id)
                scenario = self.campaign_session.query(Scenario).get(operation.scenario_id)
                step = self.campaign_session.query(ScenarioStep).get(operation.step_id)

                if not contact or not scenario or not step:
                    operation.status = 'failed'
                    operation.reason = 'Missing context'
                    failed += 1
                    continue

                # Vérifier que le scénario est toujours actif
                if scenario.status != ScenarioStatus.ACTIVE:
                    operation.status = 'skipped'
                    operation.reason = f'Scenario {scenario.status.value}'
                    continue

                # Récupérer le template
                template = self.campaign_session.query(EmailTemplate).get(step.template_id)
                if not template:
                    operation.status = 'failed'
                    operation.reason = f'Template {step.template_id} not found'
                    failed += 1
                    continue

                # Préparer les variables de personnalisation
                variables = self._prepare_email_variables(contact, scenario, sequence)

                # Personnaliser le sujet et le corps
                subject = self._replace_variables(template.subject, variables)
                html_body = self._replace_variables(template.html_body, variables)
                text_body = self._replace_variables(template.text_body, variables) if template.text_body else None

                # Envoyer l'email via SES
                logger.info(f"   📧 Envoi email: {contact.emails} (Template: {template.name})")

                send_result = self.ses_manager.send_email(
                    to_email=contact.emails,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body
                )

                if send_result.get('success'):
                    message_id = send_result.get('message_id')

                    # Mettre à jour la séquence
                    sequence = self.campaign_session.query(ContactSequence).filter_by(
                        scenario_id=scenario.id,
                        contact_id=contact.id,
                        status=SequenceStatus.ACTIVE
                    ).first()

                    # Créer un enregistrement CampaignEmail lié à la séquence
                    campaign_email = CampaignEmail(
                        campaign_id=None,  # Pas de campagne classique, c'est un scénario
                        sequence_id=sequence.id if sequence else None,
                        site_id=contact.id,
                        to_email=contact.emails,
                        to_domain=contact.domain,
                        from_name=scenario.name,
                        from_email=self.ses_manager.sender_email,
                        subject=subject,
                        status=EmailStatus.SENT,
                        message_id=message_id,
                        sent_at=datetime.utcnow()
                    )
                    self.campaign_session.add(campaign_email)
                    self.campaign_session.flush()  # Pour obtenir l'ID

                    # Marquer l'opération comme exécutée
                    operation.status = 'executed'
                    operation.executed_at = datetime.utcnow()
                    operation.extra_data = json.dumps({
                        'message_id': message_id,
                        'campaign_email_id': campaign_email.id,
                        'template_id': step.template_id
                    })

                    if sequence:
                        sequence.total_emails_sent += 1
                        sequence.last_email_sent_at = datetime.utcnow()
                        sequence.last_action_at = datetime.utcnow()

                    # Mettre à jour les stats du scénario
                    scenario.total_emails_sent += 1

                    sent += 1
                    logger.info(f"   ✅ Envoyé avec succès (Message ID: {message_id})")
                else:
                    # Échec de l'envoi
                    error_msg = send_result.get('error', 'Unknown error')
                    logger.error(f"   ❌ Échec envoi: {error_msg}")

                    operation.status = 'failed'
                    operation.reason = error_msg
                    operation.executed_at = datetime.utcnow()

                    failed += 1

            except Exception as e:
                logger.error(f"   ❌ Erreur traitement opération {operation.id}: {e}")
                operation.status = 'failed'
                operation.reason = str(e)
                failed += 1

        self.campaign_session.commit()

        return {
            'processed': len(pending_ops),
            'sent': sent,
            'failed': failed
        }

    def handle_event(self, event_type: str, campaign_email: CampaignEmail) -> None:
        """
        Gérer un événement (opened, clicked, etc.) et déclencher les suivis
        """
        logger.info(f"🎯 Événement {event_type} reçu pour email {campaign_email.id}")

        # Chercher la séquence directement via le lien
        if campaign_email.sequence_id:
            sequence = self.campaign_session.query(ContactSequence).get(campaign_email.sequence_id)
            if sequence and sequence.status == SequenceStatus.ACTIVE:
                self._process_event_for_sequence(sequence, event_type)
            else:
                logger.warning(f"   ⚠️ Séquence {campaign_email.sequence_id} non active ou introuvable")
        else:
            # Fallback: recherche par contact_id (pour les anciens emails)
            if not campaign_email.site_id:
                logger.warning("   ⚠️ Pas de site_id dans l'email, impossible de traiter l'événement")
                return

            active_sequences = self.campaign_session.query(ContactSequence).filter_by(
                contact_id=campaign_email.site_id,
                status=SequenceStatus.ACTIVE
            ).all()

            for sequence in active_sequences:
                self._process_event_for_sequence(sequence, event_type)

    def _process_event_for_sequence(self, sequence: ContactSequence, event_type: str) -> None:
        """
        Traiter un événement pour une séquence spécifique
        """
        scenario = self.campaign_session.query(Scenario).get(sequence.scenario_id)
        if not scenario or scenario.status != ScenarioStatus.ACTIVE:
            return

        # Chercher les étapes déclenchées par cet événement
        trigger_map = {
            'opened': StepTrigger.OPENED,
            'clicked': StepTrigger.CLICKED
        }

        trigger_type = trigger_map.get(event_type)
        if not trigger_type:
            return

        # Trouver les étapes correspondantes
        next_steps = self.campaign_session.query(ScenarioStep).filter_by(
            scenario_id=scenario.id,
            trigger_type=trigger_type,
            parent_step_id=sequence.current_step_id
        ).all()

        for step in next_steps:
            # Calculer le délai
            send_at = datetime.utcnow() + timedelta(
                days=step.delay_days,
                hours=step.delay_hours
            )

            # Mettre à jour la séquence
            sequence.current_step_id = step.id
            sequence.next_action_at = send_at

            # Planifier l'envoi
            contact = self.db_session.query(Site).get(sequence.contact_id)
            if contact:
                self._plan_email_send(
                    scenario, step, contact, sequence,
                    reason=f"{event_type}_followup"
                )

        self.campaign_session.commit()

    def check_not_opened_followups(self, hours_threshold: int = 72) -> Dict[str, Any]:
        """
        Vérifier les emails non ouverts et déclencher les relances
        """
        logger.info(f"🔍 Vérification des emails non ouverts (>{hours_threshold}h)")

        cutoff = datetime.utcnow() - timedelta(hours=hours_threshold)

        # Trouver les séquences actives avec un dernier email non ouvert
        sequences = self.campaign_session.query(ContactSequence).filter(
            ContactSequence.status == SequenceStatus.ACTIVE,
            ContactSequence.last_email_sent_at <= cutoff,
            ContactSequence.last_email_sent_at.isnot(None)
        ).all()

        processed = 0

        for sequence in sequences:
            # Vérifier si l'email a été ouvert
            # TODO: Lier les emails aux séquences pour un suivi précis

            # Chercher une étape "not_opened"
            not_opened_steps = self.campaign_session.query(ScenarioStep).filter_by(
                scenario_id=sequence.scenario_id,
                trigger_type=StepTrigger.NOT_OPENED,
                parent_step_id=sequence.current_step_id
            ).all()

            for step in not_opened_steps:
                if step.delay_days * 24 + step.delay_hours <= hours_threshold:
                    # Temps écoulé suffisant, déclencher
                    contact = self.db_session.query(Site).get(sequence.contact_id)
                    scenario = self.campaign_session.query(Scenario).get(sequence.scenario_id)

                    if contact and scenario:
                        sequence.current_step_id = step.id
                        sequence.next_action_at = datetime.utcnow()

                        self._plan_email_send(
                            scenario, step, contact, sequence,
                            reason="not_opened_followup"
                        )
                        processed += 1

        self.campaign_session.commit()

        return {'processed': processed}

    def close(self):
        """Fermer les connexions"""
        self.db_session.close()
        self.campaign_session.close()


if __name__ == '__main__':
    """Test de l'orchestrateur"""
    orchestrator = ScenarioOrchestrator()

    try:
        # Exemple : démarrer le scénario 1
        # result = orchestrator.start_scenario(1)
        # print(json.dumps(result, indent=2))

        # Traiter les opérations en attente
        result = orchestrator.process_pending_operations()
        print(json.dumps(result, indent=2))

    finally:
        orchestrator.close()
