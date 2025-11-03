# Différenciation des Sources d'Emails

Date: 2025-10-18

---

## Objectif

Distinguer dans la base de données et l'interface les emails trouvés par:
1. **Scraping direct** du site web (Feuille 1)
2. **Informations SIRET/SIREN** (Feuille 3)

---

## Modifications Effectuées

### 1. Base de Données

#### Nouvelle Colonne ajoutée
```sql
ALTER TABLE sites
ADD COLUMN email_source VARCHAR(20);
```

**Valeurs possibles**:
- `'scraping'` - Email trouvé par scraping du site web
- `'siret'` - Email trouvé via les informations SIRET/SIREN

#### Migration
✅ Script créé: [migrate_add_email_source.py](migrate_add_email_source.py:1)
✅ Migration exécutée: 51 sites mis à jour avec `email_source='scraping'`

### 2. Modèle de Données

#### Fichier: [database.py](database.py:45)
```python
email_source = Column(String(20), nullable=True)  # "scraping" ou "siret"
```

Le champ est maintenant inclus dans:
- Le modèle `Site`
- La méthode `to_dict()` pour l'API

### 3. Helper Database

#### Fichier: [db_helper.py](db_helper.py:40)
```python
def update_email(self, domain, emails, email_source='scraping'):
    """
    Mettre à jour les emails d'un site

    Args:
        domain: Le nom de domaine
        emails: Les emails trouvés
        email_source: Source de l'email ('scraping' ou 'siret')
    """
```

### 4. API REST

#### Route: `/api/stats`
Nouvelles statistiques ajoutées:
- `emails_from_scraping` - Nombre d'emails trouvés par scraping
- `emails_from_siret` - Nombre d'emails trouvés via SIRET

#### Route: `/api/sites/<id>` (PUT)
Support du champ `email_source` lors de la mise à jour.

#### Route: `/api/sites`
Le champ `email_source` est maintenant inclus dans les réponses JSON.

### 5. Scripts d'Import

#### Nouveau Script: [import_feuille3_emails.py](import_feuille3_emails.py:1)
- Importe les emails depuis la Feuille 3 (Google Sheets)
- Marque automatiquement `email_source='siret'`
- Ne remplace PAS les emails trouvés par scraping
- Logique de priorité: scraping > siret

**Utilisation**:
```bash
python3 import_feuille3_emails.py
```

---

## Statistiques Actuelles

### Répartition des Emails

| Source | Nombre | Pourcentage |
|--------|--------|-------------|
| **Scraping** | 51 | 100% |
| **SIRET** | 0 | 0% |
| **Total** | 51 | 1.8% des sites |

### État Global

- **Total de sites**: 2,841
- **Sites avec email**: 51 (1.8%)
  - Depuis scraping: 51
  - Depuis SIRET: 0
- **Sites avec SIRET**: 810 (28.5%)
- **Sites avec dirigeants**: 64 (2.3%)
- **Sites complets**: 1 (0.0%)

---

## Structure des Google Sheets

### Feuille 1
Contient les sites avec leurs emails trouvés par **scraping direct**:
- Colonne: Site/Domain
- Colonne: Emails

### Feuille 3
Contient les sites avec SIRET et dirigeants:
- Colonne: Domaine
- Colonne: SIRET/SIREN
- Colonne: Dirigeants
- Colonne: Source

**Note**: La Feuille 3 actuelle ne contient **PAS** de colonne "Emails".

Pour utiliser cette fonctionnalité, il faudrait:
1. Soit ajouter une colonne "Emails" dans la Feuille 3
2. Soit récupérer les emails via l'API SIRET/SIREN et les ajouter

---

## Utilisation de l'API

### Obtenir les Statistiques par Source

```bash
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool
```

**Réponse**:
```json
{
  "total_sites": 2841,
  "sites_with_email": 51,
  "emails_from_scraping": 51,
  "emails_from_siret": 0,
  ...
}
```

### Filtrer les Sites par Source d'Email

**Sites avec emails depuis le scraping**:
```bash
curl "https://admin.perfect-cocon-seo.fr/api/sites?has_email=true" \
  | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f'{s[\"domain\"]}: source={s[\"email_source\"]}') for s in data['sites'] if s.get('email_source') == 'scraping']"
```

**Sites avec emails depuis SIRET** (quand disponibles):
```bash
curl "https://admin.perfect-cocon-seo.fr/api/sites?has_email=true" \
  | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f'{s[\"domain\"]}: source={s[\"email_source\"]}') for s in data['sites'] if s.get('email_source') == 'siret']"
```

---

## Logique de Priorité

Lorsqu'un site a déjà un email:

1. **Email existant = scraping** → Conservé, pas de remplacement
2. **Email existant = siret** → Peut être remplacé par un email scraping
3. **Pas d'email** → Accepte email de n'importe quelle source

**Justification**: Les emails trouvés par scraping direct du site sont généralement plus fiables car ils sont directement affichés sur le site web.

---

## Prochaines Étapes

### 1. Enrichir la Feuille 3 avec des Emails

Si vous souhaitez ajouter des emails trouvés via SIRET:

a. **Manuellement dans Google Sheets**:
   - Ajouter une colonne "Emails" dans la Feuille 3
   - Remplir avec les emails trouvés via les API SIRET

b. **Via un Script Python**:
   - Créer un script pour récupérer les emails depuis l'API Pappers/Infogreffe
   - Utiliser le SIRET pour trouver les contacts

### 2. Afficher la Source dans l'Interface Web

Modifier les templates HTML pour afficher un badge indiquant la source:
- 🌐 Badge "Scraping" pour les emails trouvés sur le site
- 🏢 Badge "SIRET" pour les emails trouvés via les infos légales

### 3. Export CSV avec Source

Le fichier CSV exporté inclut maintenant le champ `email_source`:

```bash
curl -o sites.csv https://admin.perfect-cocon-seo.fr/api/export/csv
```

Colonnes:
- ID, Domaine, Statut, **Emails**, **Email_Source**, SIRET, SIREN, Dirigeants...

---

## Commandes Utiles

### Vérifier la Répartition

```bash
# Compter les emails par source
python3 -c "
from database import get_session, Site
session = get_session()

scraping = session.query(Site).filter(
    Site.emails.isnot(None),
    Site.emails != '',
    Site.emails != 'NO EMAIL FOUND',
    Site.email_source == 'scraping'
).count()

siret = session.query(Site).filter(
    Site.emails.isnot(None),
    Site.emails != '',
    Site.emails != 'NO EMAIL FOUND',
    Site.email_source == 'siret'
).count()

print(f'Emails depuis scraping: {scraping}')
print(f'Emails depuis SIRET: {siret}')
print(f'Total: {scraping + siret}')

session.close()
"
```

### Exemples de Sites

```bash
# Sites avec email depuis scraping
python3 -c "
from database import get_session, Site
session = get_session()
sites = session.query(Site).filter(Site.email_source == 'scraping').limit(5).all()
for site in sites:
    print(f'{site.domain}: {site.emails} (source: {site.email_source})')
session.close()
"
```

---

## Résumé

✅ **Base de données**: Colonne `email_source` ajoutée
✅ **API**: Statistiques par source disponibles
✅ **Scripts**: Import avec différenciation des sources
✅ **Migration**: Données existantes marquées comme "scraping"
✅ **Documentation**: Complète et à jour

**Accès**: https://admin.perfect-cocon-seo.fr/api/stats

---

## Notes Techniques

### Schéma de la Base de Données

```
Table: sites
├── id (INTEGER)
├── domain (STRING)
├── emails (TEXT)
├── email_source (STRING) ← NOUVEAU
│   ├── 'scraping' - Email trouvé par scraping
│   └── 'siret' - Email trouvé via SIRET
├── email_checked (BOOLEAN)
├── email_found_at (DATETIME)
├── siret (STRING)
├── siren (STRING)
├── leaders (TEXT)
└── ...
```

### Exemples de Requêtes SQL

```sql
-- Emails par source
SELECT email_source, COUNT(*) as count
FROM sites
WHERE emails IS NOT NULL
  AND emails != ''
  AND emails != 'NO EMAIL FOUND'
GROUP BY email_source;

-- Sites sans email_source défini
SELECT domain, emails
FROM sites
WHERE emails IS NOT NULL
  AND emails != 'NO EMAIL FOUND'
  AND email_source IS NULL;
```

---

**Système prêt à différencier les sources d'emails !** 🎉

Pour importer des emails depuis la Feuille 3, ajoutez d'abord une colonne "Emails" dans le Google Sheet, puis relancez le script d'import.
