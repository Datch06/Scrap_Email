# Guide: Tester une campagne email

## Vue d'ensemble

La fonctionnalité de test de campagne permet d'envoyer des emails de test à vos propres adresses avant de lancer une campagne complète. Cela vous permet de:

- ✅ Vérifier le rendu HTML de l'email
- ✅ Tester la personnalisation (variables dynamiques)
- ✅ Valider le sujet et le contenu
- ✅ S'assurer que tout fonctionne avant l'envoi massif

## Méthode 1: Via script interactif

### Utilisation

```bash
cd /var/www/Scrap_Email
python3 test_campaign_email.py
```

### Étapes

1. Le script liste toutes les campagnes disponibles
2. Vous choisissez la campagne à tester
3. Vous entrez vos adresses email de test (séparées par des virgules)
4. Les emails sont envoyés avec le préfixe **[TEST]** dans le sujet

### Exemple

```
======================================================================
TEST D'ENVOI D'EMAIL DE CAMPAGNE
======================================================================

[1/3] Récupération des campagnes...
✓ 2 campagne(s) trouvée(s)

Campagnes disponibles:
  1. ID 1: Prospection SEO Octobre 2024
     Statut: draft
     Sujet: Boostez votre référencement avec nos backlinks

Choisissez le numéro de campagne à tester: 1

[2/3] Configuration des emails de test...
Emails: votre.email@gmail.com, test@example.com
✓ 2 email(s) de test configuré(s)

[3/3] Envoi des emails de test...

======================================================================
RÉSULTATS D'ENVOI
======================================================================
Campagne: Prospection SEO Octobre 2024
Envoyés: 2
Échoués: 0

✅ Emails envoyés avec succès:
   - votre.email@gmail.com
   - test@example.com

✓ Test terminé!
======================================================================
```

## Méthode 2: Via API

### Endpoint

```
POST /api/campaigns/<campaign_id>/test
```

### Authentification

```
Basic Auth: Datch / 0000cn
```

### Payload

```json
{
  "test_emails": ["votre.email@example.com", "autre@example.com"],
  "test_domain": "site-test-exemple.fr"
}
```

### Exemple avec curl

```bash
curl -X POST http://127.0.0.1:5002/api/campaigns/1/test \
  -u Datch:0000cn \
  -H "Content-Type: application/json" \
  -d '{
    "test_emails": ["votre.email@gmail.com"],
    "test_domain": "test-site.fr"
  }'
```

### Réponse

```json
{
  "campaign_id": 1,
  "campaign_name": "Prospection SEO Octobre 2024",
  "sent": ["votre.email@gmail.com"],
  "failed": [],
  "total_sent": 1,
  "total_failed": 0
}
```

## Méthode 3: Via Python

```python
import requests
from requests.auth import HTTPBasicAuth

API_URL = 'http://127.0.0.1:5002'
AUTH = HTTPBasicAuth('Datch', '0000cn')

response = requests.post(
    f'{API_URL}/api/campaigns/1/test',
    auth=AUTH,
    json={
        'test_emails': ['votre.email@gmail.com'],
        'test_domain': 'test-site.fr'
    },
    timeout=30
)

results = response.json()
print(f"Envoyés: {results['total_sent']}")
print(f"Échoués: {results['total_failed']}")
```

## Variables de personnalisation

Les emails de test utilisent des **données fictives** pour la personnalisation:

| Variable | Valeur de test |
|----------|---------------|
| `{{domain}}` | test.example.com (ou votre test_domain) |
| `{{email}}` | Première adresse de test fournie |
| `{{siret}}` | 12345678901234 |
| `{{siren}}` | 123456789 |
| `{{leaders}}` | Jean Dupont, Marie Martin |
| `{{source_url}}` | https://example.com |
| `{{unsubscribe_link}}` | Lien de désinscription fonctionnel |

## Caractéristiques

✅ **Préfixe [TEST]** automatiquement ajouté au sujet
✅ **Pas d'enregistrement** dans la base de campagne (emails de test non comptabilisés)
✅ **Support multi-destinataires** (plusieurs emails de test en une seule fois)
✅ **Personnalisation complète** (toutes les variables fonctionnent)
✅ **Envoi via AWS SES** (même système que les vraies campagnes)

## Vérifications avant envoi réel

Avant de lancer une campagne sur toute votre base:

1. ✅ Envoyez-vous un email de test
2. ✅ Vérifiez le rendu sur desktop et mobile
3. ✅ Testez tous les liens
4. ✅ Vérifiez le lien de désinscription
5. ✅ Relisez le contenu pour les fautes
6. ✅ Vérifiez que les variables sont bien remplacées
7. ✅ Testez avec différents clients email (Gmail, Outlook, etc.)

## Notes importantes

- Les emails de test arrivent généralement en **moins de 30 secondes**
- Vérifiez aussi votre dossier **Spam/Promotions**
- Les emails de test n'affectent **pas les statistiques** de la campagne
- Le sujet commence toujours par **[TEST]** pour les distinguer

## Support

En cas de problème:
- Vérifiez que AWS SES est configuré correctement
- Consultez les logs: `/tmp/api_server.log`
- Vérifiez que l'email d'expédition est vérifié dans AWS SES
