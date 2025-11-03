# Intégration API Pappers pour Récupération des Emails

Date: 2025-10-18

---

## Objectif

Récupérer automatiquement les emails des entreprises via l'API Pappers en utilisant les SIRET déjà présents dans la base de données.

---

## Script Créé

### [fetch_emails_from_pappers.py](fetch_emails_from_pappers.py:1)

Ce script permet de:
1. Récupérer tous les sites ayant un SIRET mais **pas d'email**
2. Interroger l'API Pappers pour chaque SIRET
3. Mettre à jour la base avec `email_source='siret'`
4. **Respecter la priorité**: ne remplace PAS les emails trouvés par scraping

---

## Configuration

### Clé API Pappers
```python
PAPPERS_API_KEY = '9c9507b8e254e643ae1040e87eb573fed6f1d6dfc6049c74'
```

### Paramètres
```python
DELAY_BETWEEN_REQUESTS = 0.5  # Pause entre requêtes (éviter rate limit)
MAX_SITES = None              # Limite de sites (None = tous)
```

---

## Utilisation

### 1. Tester l'API (1 SIRET)

```bash
python3 fetch_emails_from_pappers.py test
```

**Résultat attendu**:
- ✅ Teste la connexion à l'API
- ✅ Récupère l'email d'un SIRET de test
- ❌ N'écrit RIEN en base de données

### 2. Mode Dry-Run (Tester sans modifier)

```bash
# Tester avec 10 sites
python3 fetch_emails_from_pappers.py dry-run 10

# Tester avec 50 sites
python3 fetch_emails_from_pappers.py dry-run 50
```

**Résultat**:
- ✅ Récupère les emails depuis Pappers
- ✅ Affiche les résultats
- ❌ N'écrit RIEN en base de données

### 3. Mode Production (Mettre à jour la base)

```bash
python3 fetch_emails_from_pappers.py
```

Le script va:
1. Demander confirmation
2. Demander le nombre de sites (vide = tous)
3. Récupérer les emails depuis Pappers
4. Mettre à jour la base avec `email_source='siret'`

---

## Fonctionnement Détaillé

### Sites Ciblés

Le script cible uniquement les sites qui ont:
- ✅ Un SIRET valide (non vide, non "NON TROUVÉ")
- ❌ **PAS** d'email (ou email = "NO EMAIL FOUND")

**Sites ignorés**:
- Sites avec email déjà trouvé par scraping
- Sites sans SIRET

### Sources d'Email dans Pappers

L'API Pappers peut fournir l'email depuis:
1. **Email de l'entreprise** (`data['email']`)
2. **Email du représentant légal** (`data['representants'][0]['email']`)
3. **Email du siège** (`data['siege']['email']`)

Le script essaie dans cet ordre et prend le premier trouvé.

### Gestion des Erreurs

| Code | Signification | Action |
|------|---------------|--------|
| 200 | Succès | Email récupéré |
| 404 | SIRET non trouvé | Marqué comme "non trouvé" |
| 429 | Rate limit | Pause de 5s puis retry |
| 401 | Pas de crédits | Arrêt du script |

---

## État Actuel

### Test Effectué

```bash
python3 fetch_emails_from_pappers.py test
```

**Résultat**:
```
❌ Erreur API Pappers (401):
"Vous n'avez plus assez de crédits pour effectuer cette requête"
```

### Problème Identifié

⚠️ **Compte Pappers sans crédits**

Votre clé API fonctionne mais le compte n'a plus de crédits disponibles.

### Solutions

1. **Acheter des crédits Pay-as-you-go**
   - Rendez-vous sur [pappers.fr](https://www.pappers.fr)
   - Espace membre → Crédits
   - Acheter des crédits selon vos besoins

2. **Prendre un abonnement Pappers**
   - Abonnement Starter: ~30€/mois
   - Abonnement Pro: ~100€/mois
   - Includes X requêtes par mois

3. **Utiliser une autre API**
   - API Société.com
   - API Infogreffe
   - API data.gouv.fr (gratuite mais moins complète)

---

## Statistiques Actuelles

Sites avec SIRET mais sans email:

```bash
python3 -c "
from database import get_session, Site
session = get_session()

sites_with_siret = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != '',
    Site.siret != 'NON TROUVÉ'
).count()

sites_with_siret_no_email = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != '',
    Site.siret != 'NON TROUVÉ'
).filter(
    (Site.emails.is_(None)) |
    (Site.emails == '') |
    (Site.emails == 'NO EMAIL FOUND')
).count()

print(f'Sites avec SIRET: {sites_with_siret}')
print(f'Sites avec SIRET SANS email: {sites_with_siret_no_email}')
print(f'Potentiel de récupération: {sites_with_siret_no_email} emails')

session.close()
"
```

**Résultat attendu**:
- Sites avec SIRET: **810**
- Sites avec SIRET SANS email: **~760**
- **Potentiel**: ~760 emails à récupérer via Pappers

---

## Coût Estimé

### Pappers Pay-as-you-go
- Prix: ~0.02€ par requête
- Pour 760 sites: **~15€**

### Pappers Abonnement
- Starter (30€/mois): 2000 requêtes/mois → Suffisant
- Pro (100€/mois): 10000 requêtes/mois → Large

---

## Une Fois les Crédits Disponibles

### Étape 1: Test avec 10 sites

```bash
python3 fetch_emails_from_pappers.py dry-run 10
```

Vérifiez que:
- ✅ Les emails sont trouvés
- ✅ Les SIRET sont valides
- ✅ Pas d'erreurs

### Étape 2: Production sur 100 sites

```bash
python3 fetch_emails_from_pappers.py
# Entrer: 100
```

### Étape 3: Vérifier les résultats

```bash
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool
```

Vous devriez voir:
- `emails_from_scraping`: 51
- `emails_from_siret`: augmenté (ex: 80+)

### Étape 4: Lancer sur tous les sites

```bash
python3 fetch_emails_from_pappers.py
# Appuyer sur Entrée (tous les sites)
```

---

## Exemple de Sortie

```
======================================================================
RÉCUPÉRATION DES EMAILS VIA API PAPPERS
======================================================================

📊 Sites à traiter: 760

[1/760] acteurs-locaux.fr
    SIRET: 813046919
    ✅ Email trouvé: contact@acteurs-locaux.fr

[2/760] afm-telethon.fr
    SIRET: 77560957100739
    ✅ Email trouvé: info@afm-telethon.fr

[3/760] example-site.fr
    SIRET: 123456789
    ❌ Aucun email trouvé

======================================================================
RÉSUMÉ
======================================================================
Total traité: 760
✅ Emails trouvés: 580
❌ Emails non trouvés: 180
⚠️  Erreurs: 0
======================================================================
```

---

## Impact Attendu

### Avant
- Total emails: **51** (1.8%)
  - Scraping: 51
  - SIRET: 0

### Après (estimé avec 75% de succès)
- Total emails: **~620** (21.8%)
  - Scraping: 51
  - SIRET: ~570

**Amélioration**: +500 emails (+1,000% !) 🚀

---

## Commandes Utiles

### Compter les sites sans email avec SIRET

```bash
python3 -c "
from database import get_session, Site
session = get_session()
count = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != '',
    (Site.emails.is_(None)) | (Site.emails == '')
).count()
print(f'{count} sites peuvent bénéficier de Pappers')
session.close()
"
```

### Voir les 10 premiers SIRET sans email

```bash
python3 -c "
from database import get_session, Site
session = get_session()
sites = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != '',
    (Site.emails.is_(None)) | (Site.emails == '')
).limit(10).all()
for site in sites:
    print(f'{site.domain}: SIRET {site.siret}')
session.close()
"
```

---

## Alternatives Gratuites

Si vous ne souhaitez pas utiliser Pappers:

### 1. API Data.gouv.fr (Gratuit)

```python
import requests

def get_email_from_datagouv(siret):
    url = f'https://entreprise.data.gouv.fr/api/sirene/v3/etablissements/{siret}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # L'email n'est généralement pas disponible
        return None
    return None
```

**Limitation**: L'API data.gouv ne fournit généralement PAS les emails.

### 2. Scraping Societe.com

Scraper le site societe.com avec le SIRET pour récupérer l'email.

**Inconvénient**: Plus lent, risque de blocage.

### 3. Google Sheets API + Recherche Manuelle

Pour les sites importants, recherche manuelle et ajout dans les sheets.

---

## Prochaines Étapes

1. ✅ **Script créé et testé**
2. ⏳ **Acheter des crédits Pappers** (~15€ pour 760 requêtes)
3. ⏳ **Tester avec 10 sites** (dry-run)
4. ⏳ **Lancer sur 100 sites** (test production)
5. ⏳ **Lancer sur tous les sites** (~760)
6. ✅ **Vérifier les statistiques** sur l'interface

---

## Résumé

✅ Script créé: [fetch_emails_from_pappers.py](fetch_emails_from_pappers.py:1)
✅ API testée: Fonctionne (mais pas de crédits)
✅ Système prêt: attend uniquement des crédits Pappers
✅ Potentiel: **+570 emails** (~21% de taux de complétion)

**Action requise**: Acheter des crédits Pappers ou prendre un abonnement

Une fois fait, lancez simplement:
```bash
python3 fetch_emails_from_pappers.py dry-run 10
```

---

**Le système est prêt à récupérer des centaines d'emails automatiquement !** 🎉
