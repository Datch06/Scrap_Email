#!/usr/bin/env python3
"""
Test du workflow complet des scénarios
"""

import json
from datetime import datetime
from campaign_database import (
    get_campaign_session,
    Scenario, ScenarioStep, ScenarioStatus, StepTrigger,
    EmailTemplate,
    StepTemplateVariant
)
from scenario_orchestrator import ScenarioOrchestrator

def test_complete_workflow():
    """Tester le workflow complet"""
    print("=" * 70)
    print("TEST: Workflow complet des scénarios avec A/B testing")
    print("=" * 70)
    print()

    session = get_campaign_session()

    try:
        # 1. Créer un template d'email
        print("📝 Étape 1: Création d'un template d'email")
        template = EmailTemplate(
            name="Test Prospection",
            description="Email de test pour prospection",
            category="test",
            subject="Bonjour {{domain}}!",
            html_body="""
            <html>
            <body>
                <h1>Bonjour!</h1>
                <p>Nous avons trouvé votre site {{domain}} et souhaitions vous contacter.</p>
                <p>Email: {{email}}</p>
                <p><a href="{{tracking_base}}https://example.com">Cliquez ici</a> pour plus d'infos</p>
                <p><small><a href="{{unsubscribe_link}}">Se désinscrire</a></small></p>
            </body>
            </html>
            """,
            text_body="Bonjour! Nous avons trouvé votre site {{domain}}.",
            available_variables='["domain", "email", "tracking_base", "unsubscribe_link"]',
            is_active=True
        )
        session.add(template)
        session.flush()
        print(f"✅ Template créé: ID={template.id}, Nom='{template.name}'")

        # 2. Créer une variante A/B
        print("\n📝 Étape 2: Création d'une variante A/B")
        template_variant = EmailTemplate(
            name="Test Prospection - Variante B",
            description="Version plus directe",
            category="test",
            subject="Opportunité pour {{domain}}",
            html_body="""
            <html>
            <body>
                <h1>Une opportunité pour {{domain}}</h1>
                <p>Votre site mérite plus de visibilité!</p>
                <p>Contact: {{email}}</p>
                <p><a href="{{tracking_base}}https://example.com">En savoir plus</a></p>
                <p><small><a href="{{unsubscribe_link}}">Se désinscrire</a></small></p>
            </body>
            </html>
            """,
            text_body="Une opportunité pour {{domain}}",
            available_variables='["domain", "email", "tracking_base", "unsubscribe_link"]',
            is_active=True
        )
        session.add(template_variant)
        session.flush()
        print(f"✅ Variante créée: ID={template_variant.id}, Nom='{template_variant.name}'")

        # 3. Créer un scénario
        print("\n📝 Étape 3: Création d'un scénario")
        scenario = Scenario(
            name="Test Workflow Complet",
            description="Scénario de test avec A/B testing",
            status=ScenarioStatus.DRAFT,
            daily_cap=10,
            cooldown_days=7,
            send_window_start='09:00',
            send_window_end='18:00',
            send_days='mon,tue,wed,thu,fri',
            timezone='Europe/Paris',
            min_validation_score=50,
            only_deliverable=False,  # Pour le test
            include_unsubscribe=True,
            stop_on_reply=True,
            stop_on_unsubscribe=True
        )
        session.add(scenario)
        session.flush()
        print(f"✅ Scénario créé: ID={scenario.id}, Nom='{scenario.name}'")

        # 4. Créer une étape d'entrée
        print("\n📝 Étape 4: Création de l'étape d'entrée")
        entry_step = ScenarioStep(
            scenario_id=scenario.id,
            step_order=1,
            step_name="Email initial",
            trigger_type=StepTrigger.ENTRY,
            delay_days=0,
            delay_hours=0,
            template_id=template.id
        )
        session.add(entry_step)
        session.flush()
        print(f"✅ Étape créée: ID={entry_step.id}, Nom='{entry_step.step_name}'")

        # 5. Ajouter des variantes A/B
        print("\n📝 Étape 5: Configuration A/B testing")
        variant_a = StepTemplateVariant(
            step_id=entry_step.id,
            template_id=template.id,
            weight=60,
            variant_name="Version douce"
        )
        variant_b = StepTemplateVariant(
            step_id=entry_step.id,
            template_id=template_variant.id,
            weight=40,
            variant_name="Version directe"
        )
        session.add(variant_a)
        session.add(variant_b)
        session.commit()
        print(f"✅ Variante A: 60% - '{variant_a.variant_name}'")
        print(f"✅ Variante B: 40% - '{variant_b.variant_name}'")

        # 6. Ajouter une étape de suivi "opened"
        print("\n📝 Étape 6: Ajout d'une étape de suivi")
        followup_template = EmailTemplate(
            name="Suivi - Email ouvert",
            description="Email de suivi après ouverture",
            category="test",
            subject="Vous avez consulté notre message",
            html_body="""
            <html>
            <body>
                <h1>Merci de votre intérêt!</h1>
                <p>Vous avez consulté notre message pour {{domain}}.</p>
                <p>Voulez-vous discuter?</p>
                <p><a href="{{tracking_base}}https://example.com/contact">Prenons contact</a></p>
            </body>
            </html>
            """,
            text_body="Merci de votre intérêt!",
            is_active=True
        )
        session.add(followup_template)
        session.flush()

        followup_step = ScenarioStep(
            scenario_id=scenario.id,
            step_order=2,
            step_name="Suivi après ouverture",
            trigger_type=StepTrigger.OPENED,
            delay_days=1,
            delay_hours=0,
            parent_step_id=entry_step.id,
            template_id=followup_template.id
        )
        session.add(followup_step)
        session.commit()
        print(f"✅ Étape de suivi créée: ID={followup_step.id}")

        # 7. Afficher le résumé
        print("\n" + "=" * 70)
        print("📊 RÉSUMÉ DE LA CONFIGURATION")
        print("=" * 70)
        print(f"Scénario: {scenario.name} (ID: {scenario.id})")
        print(f"Status: {scenario.status.value}")
        print(f"Étapes: 2 (entry + opened)")
        print(f"A/B Testing: 2 variantes (60/40)")
        print(f"Templates: 3 au total")
        print()

        # 8. Tester la sélection de variante
        print("🔬 TEST: Sélection de variantes (10 essais)")
        orchestrator = ScenarioOrchestrator()

        variant_counts = {'Version douce': 0, 'Version directe': 0}
        for i in range(10):
            selected_template, selected_variant = orchestrator._select_template_for_step(entry_step)
            if selected_variant:
                variant_counts[selected_variant.variant_name] += 1
                print(f"   Essai {i+1}: {selected_variant.variant_name} (Template ID: {selected_template.id})")
            else:
                print(f"   Essai {i+1}: Aucune variante (Template ID: {selected_template.id})")

        print(f"\n📊 Distribution:")
        print(f"   Version douce: {variant_counts['Version douce']}/10 ({variant_counts['Version douce']*10}%)")
        print(f"   Version directe: {variant_counts['Version directe']}/10 ({variant_counts['Version directe']*10}%)")

        orchestrator.close()

        print("\n" + "=" * 70)
        print("✅ TEST RÉUSSI!")
        print("=" * 70)
        print()
        print("📝 Pour démarrer le scénario:")
        print(f"   curl -X POST http://localhost:5002/api/scenarios/{scenario.id}/start")
        print()
        print("📝 Pour traiter les opérations en attente:")
        print("   python3 scenario_orchestrator.py")
        print()

        return True

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return False

    finally:
        session.close()

if __name__ == '__main__':
    import sys
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
