# Système de Scénarios d'Automatisation d'Emails

## 📋 Vue d'ensemble

Système complet d'automatisation d'emails comportementaux avec support du A/B testing, intégration AWS SES, et tracking des événements.

## ✨ Fonctionnalités

### 1. Gestion des scénarios
- **Création de scénarios multi-étapes** avec déclencheurs comportementaux
- **Interface web** complète pour la configuration
- **Contraintes d'envoi** : fenêtres horaires, quota journalier, cooldown
- **Filtres de destinataires** : score de validation, délivrabilité
- **Contrôle** : pause/reprise/arrêt des scénarios

### 2. Déclencheurs disponibles
- `ENTRY` : Point d'entrée du scénario
- `OPENED` : Email ouvert par le destinataire
- `NOT_OPENED` : Email non ouvert après X heures
- `CLICKED` : Lien cliqué dans l'email
- `DELAY` : Délai fixe après l'étape précédente

### 3. A/B Testing
- **Variantes multiples** par étape avec poids personnalisés
- **Sélection pondérée** automatique (ex: 60/40, 70/30)
- **Statistiques en temps réel** : envois, ouvertures, clics par variante
- **Calculs automatiques** : open_rate, click_rate pour chaque variante

### 4. Envoi réel via AWS SES
- **Intégration complète** avec SESManager
- **Personnalisation** des emails avec variables : {{domain}}, {{email}}, etc.
- **Liens de tracking** pour mesurer les clics
- **Lien de désinscription** automatique
- **Gestion des erreurs** avec retry et logging

### 5. Tracking des événements
- **Webhooks SES** : réception des événements via SNS
- **Événements supportés** : delivery, open, click, bounce, complaint
- **Déclenchement automatique** des suivis lors des événements
- **Mise à jour des statistiques** A/B en temps réel

### 6. Idempotence et fiabilité
- **Clés d'idempotence SHA256** pour éviter les doublons
- **Operation Ledger** : journal complet de toutes les opérations
- **État des séquences** : tracking précis de chaque contact
- **Reprise après erreur** : les opérations en attente sont retraitées

## 🏗️ Architecture

### Modèles de données

```python
# Scénario principal
Scenario:
  - Configuration générale (nom, limites, contraintes)
  - Statistiques globales
  - Relations : steps, sequences

# Étapes du scénario
ScenarioStep:
  - Déclencheur (trigger_type)
  - Délai (delay_days, delay_hours)
  - Template par défaut
  - Relations : variantes A/B

# Variantes A/B
StepTemplateVariant:
  - Template alternatif
  - Poids de distribution (weight)
  - Statistiques (sent, opened, clicked)

# État d'un contact dans le scénario
ContactSequence:
  - Contact actuel
  - Étape courante
  - Prochain envoi planifié
  - Statistiques individuelles

# Journal des opérations
OperationLedger:
  - Idempotency key unique
  - Status (pending, executed, failed)
  - Métadonnées (message_id, variant_id)

# Email envoyé
CampaignEmail:
  - Lien vers la séquence (sequence_id)
  - Lien vers la variante (variant_id)
  - Statuts et événements
  - Message ID SES
```

### Flux de traitement

```
1. Création du scénario via l'interface web
   ↓
2. Configuration des étapes et variantes A/B
   ↓
3. Activation du scénario (POST /api/scenarios/:id/start)
   ↓
4. Orchestrator traite le batch initial
   - Récupère les contacts éligibles
   - Crée les ContactSequence
   - Planifie les envois dans OperationLedger
   ↓
5. Daemon traite les opérations pending
   - Sélectionne une variante A/B (si configurée)
   - Personnalise le template
   - Envoie via SES
   - Crée CampaignEmail avec variant_id
   - Met à jour les stats
   ↓
6. Réception des webhooks SES
   - Mise à jour du statut de l'email
   - Incrémentation des stats de la variante
   - Déclenchement des suivis comportementaux
   ↓
7. Orchestrator planifie les suivis
   - Trouve les étapes avec trigger correspondant
   - Calcule le délai
   - Crée de nouvelles opérations pending
```

## 📁 Fichiers principaux

### Backend
- `campaign_database.py` : Modèles SQLAlchemy (Scenario, ScenarioStep, StepTemplateVariant, ContactSequence, OperationLedger, CampaignEmail)
- `scenario_orchestrator.py` : Logique d'exécution des scénarios
- `scenario_routes.py` : API REST pour la gestion des scénarios
- `scenario_daemon.py` : Daemon de traitement en continu
- `app.py` : Webhooks SES et intégration avec l'orchestrator

### Frontend
- `templates/scenarios.html` : Interface web complète
- `templates/base.html` : Navigation

### Migrations
- `migrate_add_scenarios.py` : Tables initiales
- `migrate_link_emails_to_sequences.py` : Liaison emails-séquences
- `migrate_add_ab_testing.py` : Support A/B testing

### Tests
- `test_scenario_workflow.py` : Test complet du workflow

## 🚀 Utilisation

### 1. Lancer les migrations

```bash
cd /var/www/Scrap_Email
python3 migrate_add_scenarios.py
python3 migrate_link_emails_to_sequences.py
python3 migrate_add_ab_testing.py
```

### 2. Créer un scénario via l'API

```bash
curl -X POST http://localhost:5002/api/scenarios \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Prospection initiale",
    "description": "Séquence de prospection automatique",
    "daily_cap": 500,
    "cooldown_days": 3,
    "min_validation_score": 80,
    "only_deliverable": true
  }'
```

### 3. Ajouter des étapes

```bash
curl -X PUT http://localhost:5002/api/scenarios/1/steps \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {
        "step_order": 1,
        "step_name": "Email initial",
        "trigger_type": "entry",
        "delay_days": 0,
        "template_id": 1
      },
      {
        "step_order": 2,
        "step_name": "Suivi si ouvert",
        "trigger_type": "opened",
        "delay_days": 2,
        "parent_step_id": 1,
        "template_id": 2
      }
    ]
  }'
```

### 4. Configurer l'A/B testing (via Python)

```python
from campaign_database import get_campaign_session, StepTemplateVariant

session = get_campaign_session()

# Variante A : 60%
variant_a = StepTemplateVariant(
    step_id=1,
    template_id=1,
    weight=60,
    variant_name="Version classique"
)

# Variante B : 40%
variant_b = StepTemplateVariant(
    step_id=1,
    template_id=3,
    weight=40,
    variant_name="Version courte"
)

session.add_all([variant_a, variant_b])
session.commit()
```

### 5. Démarrer le scénario

```bash
curl -X POST http://localhost:5002/api/scenarios/1/start
```

### 6. Lancer le daemon de traitement

```bash
# En mode interactif
python3 scenario_daemon.py

# En arrière-plan
nohup python3 scenario_daemon.py --interval 60 &
```

### 7. Consulter les statistiques

```bash
curl http://localhost:5002/api/scenarios/1
```

## 📊 Variables disponibles dans les templates

- `{{domain}}` : Domaine du contact
- `{{email}}` : Email du contact
- `{{contact_name}}` : Nom du contact
- `{{siret}}` : SIRET de l'entreprise
- `{{phone}}` : Téléphone
- `{{scenario_name}}` : Nom du scénario
- `{{unsubscribe_link}}` : Lien de désinscription
- `{{tracking_base}}` : Base URL pour tracking des clics

## 🎯 Exemple de template

```html
<html>
<body>
    <h1>Bonjour {{domain}}!</h1>
    <p>Nous avons découvert votre site et souhaitions vous proposer...</p>
    <p>Contact: {{email}}</p>
    <p>
        <a href="{{tracking_base}}https://votre-site.com/offer">
            Découvrir notre offre
        </a>
    </p>
    <hr>
    <p style="font-size: 12px; color: #666;">
        <a href="{{unsubscribe_link}}">Se désinscrire</a>
    </p>
</body>
</html>
```

## 🔧 Configuration

### Contraintes d'envoi

```python
scenario.daily_cap = 500              # Max 500 emails/jour
scenario.cooldown_days = 3            # Attendre 3 jours entre 2 contacts
scenario.send_window_start = '09:00'  # Envoyer entre 9h
scenario.send_window_end = '17:30'    # et 17h30
scenario.send_days = 'mon,tue,wed,thu,fri'  # Jours ouvrés seulement
scenario.timezone = 'Europe/Paris'    # Fuseau horaire
```

### Filtres de destinataires

```python
scenario.min_validation_score = 80   # Score minimum de validation email
scenario.only_deliverable = True     # Uniquement emails délivrables
scenario.exclude_domains = 'gmail.com,yahoo.com'  # Domaines exclus
```

### Comportement

```python
scenario.stop_on_reply = True         # Arrêter si réponse reçue
scenario.stop_on_unsubscribe = True   # Arrêter si désinscription
scenario.include_unsubscribe = True   # Inclure lien désinscription
```

## 📈 Monitoring

### Voir les opérations en attente

```python
from campaign_database import get_campaign_session, OperationLedger

session = get_campaign_session()
pending = session.query(OperationLedger).filter_by(
    status='pending'
).count()

print(f"{pending} opérations en attente")
```

### Voir les séquences actives

```python
from campaign_database import get_campaign_session, ContactSequence, SequenceStatus

session = get_campaign_session()
active = session.query(ContactSequence).filter_by(
    scenario_id=1,
    status=SequenceStatus.ACTIVE
).count()

print(f"{active} contacts actifs dans le scénario 1")
```

### Voir les stats A/B

```python
from campaign_database import get_campaign_session, StepTemplateVariant

session = get_campaign_session()
variants = session.query(StepTemplateVariant).filter_by(
    step_id=1
).all()

for v in variants:
    print(f"{v.variant_name}:")
    print(f"  Envoyés: {v.sent_count}")
    print(f"  Ouvertures: {v.opened_count} ({v.opened_count/v.sent_count*100:.1f}%)")
    print(f"  Clics: {v.clicked_count} ({v.clicked_count/v.sent_count*100:.1f}%)")
```

## 🔒 Sécurité et conformité

### Idempotence
Chaque opération a une clé unique SHA256 basée sur :
- contact_id
- template_id
- scenario_id
- step_id

Empêche l'envoi de doublons même en cas de retry.

### Cooldown
Empêche de contacter un même contact trop fréquemment.

### Désinscription
Lien automatique dans chaque email (si `include_unsubscribe=True`).
La séquence s'arrête automatiquement si le contact se désinscrit.

### Détection des réponses
Si `stop_on_reply=True`, la séquence s'arrête dès qu'une réponse est détectée.

## 🐛 Débogage

### Activer les logs détaillés

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Vérifier une opération spécifique

```python
from campaign_database import get_campaign_session, OperationLedger

session = get_campaign_session()
op = session.query(OperationLedger).get(operation_id)

print(f"Status: {op.status}")
print(f"Reason: {op.reason}")
print(f"Extra data: {op.extra_data}")
```

### Réinitialiser un scénario de test

```python
from campaign_database import get_campaign_session, ContactSequence, OperationLedger

session = get_campaign_session()

# Supprimer toutes les séquences
session.query(ContactSequence).filter_by(scenario_id=2).delete()

# Supprimer toutes les opérations
session.query(OperationLedger).filter_by(scenario_id=2).delete()

session.commit()
```

## 📚 Ressources

- Code source : `/var/www/Scrap_Email/`
- Interface web : `http://localhost:5002/scenarios`
- API REST : `http://localhost:5002/api/scenarios`
- Webhooks SES : `http://localhost:5002/api/ses/webhook`

## 🎉 Améliorations futures possibles

1. **Interface drag-and-drop** pour créer les flux visuellement
2. **Analytics avancées** : conversion, ROI, attribution
3. **Templates conditionnels** : choisir le template selon des critères
4. **Optimisation automatique A/B** : basculer vers la meilleure variante
5. **Scoring prédictif** : prédire la probabilité de conversion
6. **Intégration CRM** : synchronisation bidirectionnelle
7. **Webhooks personnalisés** : notifier des systèmes externes
8. **Multi-canal** : SMS, push notifications, etc.
