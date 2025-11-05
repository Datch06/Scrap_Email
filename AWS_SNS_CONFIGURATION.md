# Configuration AWS SNS pour les webhooks SES

Ce guide explique comment configurer AWS Simple Notification Service (SNS) pour recevoir les notifications SES (bounces, plaintes, ouvertures, clics).

## Architecture

```
AWS SES → SNS Topic → HTTP(S) Webhook → Notre serveur Flask
```

## Étapes de configuration

### 1. Créer un Topic SNS

1. Allez dans la console AWS SNS : https://console.aws.amazon.com/sns/
2. Région : **Europe (Stockholm) eu-north-1** (même région que votre SES)
3. Cliquez sur "Create topic"
   - Type : **Standard**
   - Name : `ses-notifications-production`
   - Display name : `SES Notifications`
4. Cliquez sur "Create topic"

### 2. Créer une souscription HTTP(S)

1. Dans votre topic SNS, cliquez sur "Create subscription"
2. Paramètres :
   - Protocol : **HTTPS**
   - Endpoint : `https://admin.perfect-cocon-seo.fr/api/ses/webhook`
   - Enable raw message delivery : **Décoché** (laisser par défaut)
3. Cliquez sur "Create subscription"

**Note** : AWS va envoyer une requête de confirmation à votre webhook. Votre serveur doit confirmer l'abonnement en visitant l'URL fournie dans le message.

### 3. Configurer SES pour envoyer les notifications

#### 3.1 Configuration Set

1. Allez dans SES : https://console.aws.amazon.com/ses/
2. Région : **Europe (Stockholm) eu-north-1**
3. Allez dans "Configuration sets" → "Create set"
   - Configuration set name : `production-tracking`
   - Reputation options : Activé
4. Une fois créé, cliquez dessus

#### 3.2 Event Destinations

Dans votre Configuration Set, ajoutez les Event Destinations :

**Pour les Bounces et Complaints :**
1. Onglet "Event destinations" → "Add destination"
2. Paramètres :
   - Event types : Cochez
     - ✅ Bounce
     - ✅ Complaint
   - Destination : **SNS**
   - SNS topic : Sélectionnez `ses-notifications-production`
3. Sauvegardez

**Pour le Tracking (Opens, Clicks, Delivery) :**
1. Ajoutez une nouvelle destination
2. Paramètres :
   - Event types : Cochez
     - ✅ Send
     - ✅ Delivery
     - ✅ Open
     - ✅ Click
   - Destination : **SNS**
   - SNS topic : Sélectionnez `ses-notifications-production`
3. Sauvegardez

### 4. Utiliser le Configuration Set dans vos emails

Dans votre code `ses_manager.py`, ajoutez le Configuration Set :

```python
params = {
    'Source': f'"{self.sender_name}" <{self.sender_email}>',
    'Destination': {'ToAddresses': [to_email]},
    'Message': message,
    'ConfigurationSetName': 'production-tracking'  # Ajouter cette ligne
}
```

## Confirmation de l'abonnement SNS

Lorsque vous créez la souscription HTTPS, AWS envoie une requête POST à votre webhook avec :

```json
{
  "Type": "SubscriptionConfirmation",
  "SubscribeURL": "https://sns.eu-north-1.amazonaws.com/..."
}
```

**Deux options pour confirmer :**

### Option 1 : Automatique (Recommandé)

Modifiez votre webhook pour confirmer automatiquement :

```python
if message_type == 'SubscriptionConfirmation':
    subscribe_url = data.get('SubscribeURL')

    # Confirmer automatiquement l'abonnement
    import requests
    response = requests.get(subscribe_url)

    if response.status_code == 200:
        logger.info("✅ Abonnement SNS confirmé automatiquement")
        return jsonify({'status': 'subscription_confirmed'}), 200
```

### Option 2 : Manuelle

1. Votre serveur Flask reçoit la requête
2. Il affiche l'URL de confirmation dans les logs
3. Visitez l'URL manuellement dans un navigateur
4. L'abonnement est activé

## Vérification du fonctionnement

### 1. Vérifier que le webhook est accessible

```bash
curl -X POST https://admin.perfect-cocon-seo.fr/api/ses/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook_accessible"}'
```

### 2. Envoyer un email de test

Utilisez le SES Mailbox Simulator :

```python
from ses_manager import SESManager

ses = SESManager()

# Test bounce
ses.send_email(
    to_email='bounce@simulator.amazonses.com',
    subject='Test Bounce',
    html_body='<p>Test</p>'
)

# Test complaint
ses.send_email(
    to_email='complaint@simulator.amazonses.com',
    subject='Test Complaint',
    html_body='<p>Test</p>'
)

# Test succès
ses.send_email(
    to_email='success@simulator.amazonses.com',
    subject='Test Success',
    html_body='<p>Test</p>'
)
```

### 3. Vérifier les logs

```bash
tail -f /tmp/api_server.log | grep -E "Bounce|Complaint|Delivery"
```

Vous devriez voir :
```
📫 Bounce reçu - Type: Permanent, Message ID: xxx
⚠️ Plainte reçue - Message ID: xxx
✅ Email xxx marqué comme bounced
```

## Types de notifications reçues

### Bounce (Rebond)

```json
{
  "notificationType": "Bounce",
  "bounce": {
    "bounceType": "Permanent",  // ou "Temporary"
    "bouncedRecipients": [
      {
        "emailAddress": "user@example.com",
        "diagnosticCode": "smtp; 550 5.1.1 user unknown"
      }
    ]
  }
}
```

### Complaint (Plainte spam)

```json
{
  "notificationType": "Complaint",
  "complaint": {
    "complainedRecipients": [
      {
        "emailAddress": "user@example.com"
      }
    ],
    "complaintFeedbackType": "abuse"
  }
}
```

### Delivery (Livraison réussie)

```json
{
  "notificationType": "Delivery",
  "delivery": {
    "timestamp": "2025-11-05T10:00:00.000Z"
  }
}
```

### Open (Ouverture)

```json
{
  "notificationType": "Open",
  "open": {
    "timestamp": "2025-11-05T10:05:00.000Z",
    "userAgent": "Mozilla/5.0..."
  }
}
```

### Click (Clic)

```json
{
  "notificationType": "Click",
  "click": {
    "link": "https://example.com",
    "timestamp": "2025-11-05T10:10:00.000Z"
  }
}
```

## Actions automatiques

Notre système effectue automatiquement :

### Sur Bounce (Hard)
- ✅ Marque l'email comme `BOUNCED`
- ✅ Enregistre le type de bounce (hard/soft)
- ✅ Incrémente le compteur de bounces de la campagne
- ✅ Enregistre le code d'erreur

### Sur Complaint (Plainte)
- ✅ Marque l'email comme `COMPLAINED`
- ✅ **Ajoute automatiquement à la liste de désinscription**
- ✅ Incrémente le compteur de plaintes
- ⚠️ **Ne lui enverra plus jamais d'email**

### Sur Delivery
- ✅ Marque l'email comme `DELIVERED`
- ✅ Enregistre l'heure de livraison
- ✅ Incrémente le compteur de livraisons

### Sur Open
- ✅ Marque l'email comme `OPENED`
- ✅ Enregistre l'heure de première ouverture
- ✅ Incrémente le compteur d'ouvertures
- ✅ Compte le nombre total d'ouvertures

### Sur Click
- ✅ Marque l'email comme `CLICKED`
- ✅ Enregistre l'heure du premier clic
- ✅ Incrémente le compteur de clics
- ✅ Compte le nombre total de clics

## Statistiques dans l'interface admin

Une fois SNS configuré, vous verrez dans l'interface `/campaigns` :

- 📊 **Délivrés** : Emails livrés avec succès
- 📧 **Ouverts** : Taux d'ouverture en %
- 🖱️ **Cliqués** : Taux de clic en %
- ⚠️ **Bounces** : Nombre + pourcentage (en rouge si > 0)
- 🚨 **Plaintes** : Nombre (en orange si > 0)

## Bonnes pratiques

1. **Surveiller le taux de bounces** :
   - < 2% : Excellent ✅
   - 2-5% : Acceptable ⚠️
   - > 5% : Problématique ❌ (risque de suspension AWS)

2. **Surveiller le taux de plaintes** :
   - < 0.1% : Excellent ✅
   - 0.1-0.5% : Attention ⚠️
   - > 0.5% : Critique ❌ (risque de suspension AWS)

3. **Actions recommandées** :
   - Nettoyez régulièrement les hard bounces
   - Ne jamais envoyer aux emails qui ont complaint
   - Analysez les bounces pour améliorer votre liste

## Troubleshooting

### Le webhook ne reçoit rien

1. Vérifiez que l'URL est accessible publiquement
2. Vérifiez les logs Flask : `tail -f /tmp/api_server.log`
3. Vérifiez le statut de l'abonnement SNS (doit être "Confirmed")
4. Vérifiez que le Configuration Set est bien utilisé

### Erreur 403 ou 500 sur le webhook

1. Vérifiez les logs : `tail -f /tmp/api_server.log`
2. Testez manuellement :
   ```bash
   curl -X POST https://admin.perfect-cocon-seo.fr/api/ses/webhook \
     -H "Content-Type: application/json" \
     -H "x-amz-sns-message-type: Notification" \
     -d '{...}'
   ```

### Les statistiques ne s'affichent pas

1. Vérifiez que les données sont bien en base :
   ```python
   from campaign_database import get_campaign_session, Campaign
   session = get_campaign_session()
   c = session.query(Campaign).first()
   print(f"Bounces: {c.emails_bounced}")
   print(f"Complained: {c.emails_complained}")
   ```

2. Rechargez la page `/campaigns`

## Support AWS

Si vous avez besoin d'aide :
- Documentation SNS : https://docs.aws.amazon.com/sns/
- Documentation SES Events : https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-using-notifications.html
- Support AWS : https://console.aws.amazon.com/support/
