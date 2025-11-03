# Interface de Gestion Scrap Email

Interface web moderne pour gérer et superviser vos opérations de scraping.

## Installation

### 1. Installer les dépendances

```bash
cd /var/www/Scrap_Email
pip install -r requirements_interface.txt
```

### 2. Initialiser la base de données

```bash
python3 database.py
```

Cela va créer le fichier `scrap_email.db` avec toutes les tables nécessaires.

### 3. Importer vos données existantes (optionnel)

Si vous avez déjà des données dans vos fichiers CSV ou JSON, vous pouvez les importer :

```bash
python3 import_existing_data.py
```

## Lancement de l'interface

```bash
python3 app.py
```

L'interface sera accessible sur : **http://localhost:5000**

## Fonctionnalités

### 📊 Dashboard
- Vue d'ensemble avec statistiques en temps réel
- Graphiques interactifs
- Taux de complétion
- Activité récente

### 🌐 Gestion des Sites
- Liste complète de tous les sites
- Filtres avancés (statut, email, SIRET, dirigeants)
- Recherche par domaine
- Ajout/suppression de sites
- Vue détaillée de chaque site

### ⚙️ Gestion des Jobs
- Historique des tâches de scraping
- Suivi de la progression en temps réel
- Statistiques de succès/erreurs

### 📥 Export
- Export CSV de toutes les données
- Données filtrables avant export

## Structure de la base de données

### Table `sites`
Stocke tous les sites découverts avec :
- Domaine
- Statut (découvert, email trouvé, SIRET trouvé, etc.)
- Emails
- SIRET/SIREN
- Dirigeants
- Métadonnées (dates, erreurs, retry count)

### Table `scraping_jobs`
Historique des jobs de scraping :
- Type de job
- Statut
- Progression
- Résultats (succès/erreurs)

## Intégration avec vos scripts existants

### Utiliser le DBHelper

Le module `db_helper.py` facilite l'intégration :

```python
from db_helper import DBHelper

with DBHelper() as db:
    # Ajouter un site
    site = db.add_site('example.fr', source_url='https://...')

    # Mettre à jour avec email
    db.update_email('example.fr', 'contact@example.fr')

    # Mettre à jour avec SIRET
    db.update_siret('example.fr', '12345678901234', 'SIRET')

    # Mettre à jour avec dirigeants
    db.update_leaders('example.fr', ['Jean Dupont', 'Marie Martin'])

    # Récupérer les sites sans email
    sites = db.get_sites_without_email(limit=100)
```

### Modifier vos scripts existants

Exemple pour `extract_emails.py` :

```python
from db_helper import DBHelper

# Au début du script
with DBHelper() as db:
    # Récupérer les sites à traiter
    sites = db.get_sites_without_email(limit=100)

    for site in sites:
        domain = site.domain

        # ... votre code existant pour extraire les emails ...

        # Mettre à jour la base de données
        if emails_found:
            db.update_email(domain, '; '.join(emails_found))
        else:
            db.update_email(domain, 'NO EMAIL FOUND')
```

## API REST

L'interface expose une API REST complète :

### Sites
- `GET /api/sites` - Liste des sites (avec pagination et filtres)
- `GET /api/sites/<id>` - Détails d'un site
- `POST /api/sites` - Créer un site
- `PUT /api/sites/<id>` - Mettre à jour un site
- `DELETE /api/sites/<id>` - Supprimer un site

### Statistiques
- `GET /api/stats` - Statistiques globales

### Jobs
- `GET /api/jobs` - Liste des jobs
- `POST /api/jobs` - Créer un job
- `PUT /api/jobs/<id>` - Mettre à jour un job

### Export
- `GET /api/export/csv` - Exporter en CSV

## Exemples de filtres

### Rechercher des sites
```
GET /api/sites?search=boutique&status=discovered
```

### Sites avec email mais sans SIRET
```
GET /api/sites?has_email=true&has_siret=false
```

### Sites complets (email + SIRET + dirigeants)
```
GET /api/sites?has_email=true&has_siret=true&has_leaders=true
```

## Workflow recommandé

1. **Découverte** : Utiliser `playwright_crawl.py` pour découvrir de nouveaux sites
2. **Import** : Ajouter les sites dans la base de données
3. **Emails** : Lancer l'extraction d'emails sur les sites sans email
4. **SIRET** : Chercher les SIRET pour les sites avec email
5. **Dirigeants** : Extraire les dirigeants pour les sites avec SIRET
6. **Export** : Exporter les données complètes vers Google Sheets ou CSV

## Sécurité

- L'interface est accessible en local uniquement par défaut
- Pour un déploiement en production, configurez :
  - Authentification
  - HTTPS
  - Firewall
  - Variables d'environnement pour les credentials

## Support

Pour toute question ou problème :
1. Vérifiez que la base de données est initialisée
2. Vérifiez que toutes les dépendances sont installées
3. Consultez les logs dans la console

## Prochaines améliorations possibles

- [ ] Authentification utilisateur
- [ ] Planification automatique des jobs (cron)
- [ ] Notifications par email
- [ ] Webhooks pour intégrations externes
- [ ] Dashboard multi-utilisateurs
- [ ] API GraphQL
