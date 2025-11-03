# 🎉 Nouvelle Interface de Gestion - Scrap Email

## Résumé de l'amélioration

Vous disposez maintenant d'une **interface web complète** pour gérer votre système de scraping avec :

- ✅ **Base de données SQLite** pour stocker tous les sites et leur état
- ✅ **Dashboard interactif** avec statistiques en temps réel
- ✅ **Suivi détaillé** de chaque étape (découverte → email → SIRET → dirigeants)
- ✅ **API REST** pour intégration avec vos scripts
- ✅ **Filtres avancés** et recherche
- ✅ **Export CSV** et Google Sheets

---

## 📁 Nouveaux fichiers créés

### Backend
- **`database.py`** - Modèles de base de données (Sites, Jobs)
- **`app.py`** - Application Flask avec API REST
- **`db_helper.py`** - Utilitaire pour faciliter l'intégration

### Frontend
- **`templates/base.html`** - Template de base
- **`templates/index.html`** - Dashboard avec graphiques
- **`templates/sites.html`** - Gestion des sites
- **`templates/jobs.html`** - Suivi des jobs
- **`static/css/style.css`** - Styles personnalisés

### Utilitaires
- **`import_existing_data.py`** - Import de vos données existantes
- **`extract_emails_db.py`** - Exemple de script avec DB
- **`requirements_interface.txt`** - Dépendances Python

### Documentation
- **`README_INTERFACE.md`** - Documentation complète
- **`QUICKSTART.md`** - Guide de démarrage rapide
- **`NOUVELLE_INTERFACE.md`** - Ce fichier

---

## 🚀 Mise en route (3 commandes)

```bash
# 1. Installer les dépendances
pip3 install sqlalchemy flask flask-cors

# 2. Créer la base de données
python3 database.py

# 3. Lancer l'interface
python3 app.py
```

Ouvrez ensuite : **http://localhost:5000**

---

## 📊 Fonctionnalités principales

### 1. Dashboard (/)
![Dashboard]
- **Cartes de statistiques** : Total sites, emails, SIRET, dirigeants
- **Graphiques** :
  - Répartition par statut (camembert)
  - Taux de complétion (barres)
- **Actions rapides** : Liens vers filtres prédéfinis
- **Auto-refresh** : Mise à jour automatique toutes les 30s

### 2. Gestion des Sites (/sites)
- **Tableau paginé** avec tous vos sites (50 par page)
- **Filtres** :
  - Par statut (découvert, email trouvé, SIRET trouvé, etc.)
  - Par présence d'email (oui/non)
  - Par présence de SIRET (oui/non)
  - Par présence de dirigeants (oui/non)
  - Recherche par domaine
- **Actions** :
  - Voir détails complets d'un site
  - Supprimer un site
  - Ajouter manuellement un site
- **Export** : Télécharger en CSV

### 3. Suivi des Jobs (/jobs)
- **Historique** de toutes les tâches de scraping
- **Progression** en temps réel avec barre de progression
- **Statistiques** : Succès/Erreurs par job
- **Durée** d'exécution

---

## 🔄 Statuts des sites

La base de données suit automatiquement l'état de chaque site :

1. **`discovered`** - Site découvert, non traité
2. **`email_found`** - Email trouvé
3. **`email_not_found`** - Email non trouvé
4. **`siret_found`** - SIRET/SIREN trouvé
5. **`siret_not_found`** - SIRET non trouvé
6. **`leaders_found`** - Dirigeants trouvés
7. **`completed`** - Toutes les données récupérées
8. **`error`** - Erreur lors du traitement

---

## 🔌 Intégration avec vos scripts

### Méthode 1 : Utiliser le DBHelper

```python
from db_helper import DBHelper

with DBHelper() as db:
    # Ajouter un site
    site = db.add_site('example.fr', 'https://source.com')

    # Mettre à jour avec email
    db.update_email('example.fr', 'contact@example.fr')

    # Mettre à jour avec SIRET
    db.update_siret('example.fr', '12345678901234', 'SIRET')

    # Mettre à jour avec dirigeants
    db.update_leaders('example.fr', ['Jean Dupont', 'Marie Martin'])

    # Récupérer les sites à traiter
    sites_sans_email = db.get_sites_without_email(limit=100)
    sites_sans_siret = db.get_sites_without_siret(limit=100)
    sites_sans_leaders = db.get_sites_without_leaders(limit=100)
```

### Méthode 2 : Utiliser l'API REST

```bash
# Ajouter un site
curl -X POST http://localhost:5000/api/sites \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.fr"}'

# Mettre à jour un site
curl -X PUT http://localhost:5000/api/sites/1 \
  -H "Content-Type: application/json" \
  -d '{"emails": "contact@example.fr"}'

# Récupérer les statistiques
curl http://localhost:5000/api/stats
```

---

## 📖 Exemples de workflows

### Workflow 1 : Import de données existantes

```bash
# Importer tous vos fichiers CSV/JSON/TXT existants
python3 import_existing_data.py

# Vérifier dans l'interface
# → http://localhost:5000
```

### Workflow 2 : Extraction d'emails

```bash
# Lancer l'extraction pour 50 sites
python3 extract_emails_db.py --limit 50

# Voir les résultats en temps réel dans l'interface
# → http://localhost:5000/sites?has_email=true
```

### Workflow 3 : Recherche SIRET et dirigeants

```python
# Créer un script similaire pour SIRET
from db_helper import DBHelper
from find_company_leaders import find_siret_siren, fetch_company_leaders

with DBHelper() as db:
    # Récupérer sites avec email mais sans SIRET
    sites = db.get_sites_without_siret(limit=20)

    for site in sites:
        siret, siret_type = find_siret_siren(site.domain, opener)
        if siret:
            db.update_siret(site.domain, siret, siret_type)

            # Chercher dirigeants
            leaders = fetch_company_leaders(siret, siret_type, opener)
            if leaders:
                db.update_leaders(site.domain, leaders)
```

---

## 📈 Avantages de la nouvelle architecture

### Avant (fichiers CSV/JSON)
- ❌ Difficile de suivre l'état des sites
- ❌ Données dispersées dans plusieurs fichiers
- ❌ Pas de vue d'ensemble
- ❌ Risque de traiter deux fois les mêmes sites
- ❌ Difficile de reprendre après une erreur

### Maintenant (Base de données + Interface)
- ✅ **État centralisé** : Tout dans une seule base
- ✅ **Suivi en temps réel** : Voir la progression dans l'interface
- ✅ **Éviter les doublons** : La base vérifie automatiquement
- ✅ **Reprise sur erreur** : Voir exactement quels sites ont échoué
- ✅ **Filtres puissants** : Trouver rapidement ce que vous cherchez
- ✅ **Statistiques** : Graphiques et métriques automatiques
- ✅ **Export facile** : CSV en un clic

---

## 🎯 Cas d'usage typiques

### 1. "Je veux voir tous les sites avec email mais sans SIRET"
→ http://localhost:5000/sites?has_email=true&has_siret=false

### 2. "Combien de sites complets j'ai ?"
→ Dashboard → Carte "Sites Complets"

### 3. "Quels sites ont eu des erreurs ?"
→ http://localhost:5000/sites?status=error

### 4. "Je veux exporter tous les sites avec dirigeants"
→ Filtrer → has_leaders=true → Exporter CSV

### 5. "Reprendre l'extraction d'emails après une interruption"
```bash
python3 extract_emails_db.py --limit 100
# La base sait automatiquement quels sites n'ont pas encore été traités
```

---

## 🔐 Sécurité et bonnes pratiques

1. **Sauvegarde** : Sauvegardez régulièrement `scrap_email.db`
   ```bash
   cp scrap_email.db scrap_email_backup_$(date +%Y%m%d).db
   ```

2. **Accès local uniquement** : Par défaut, l'interface n'est accessible que depuis localhost

3. **Rate limiting** : Continuez à respecter les délais entre requêtes dans vos scripts

4. **Logs** : Les erreurs sont enregistrées dans la base (colonne `last_error`)

---

## 📊 Structure de la base de données

### Table `sites`
```sql
- id (PRIMARY KEY)
- domain (UNIQUE)
- status (discovered, email_found, etc.)
- emails
- siret / siren / siret_type
- leaders
- created_at / updated_at
- last_error
- retry_count
```

### Table `scraping_jobs`
```sql
- id (PRIMARY KEY)
- job_type (crawl, email, siret, leaders)
- status (pending, running, completed, failed)
- total_sites / processed_sites
- success_count / error_count
- start_time / end_time
```

---

## 🚀 Prochaines étapes recommandées

1. **Importer vos données** : `python3 import_existing_data.py`
2. **Tester l'interface** : `python3 app.py`
3. **Adapter vos scripts** : Utiliser `DBHelper` dans vos scripts existants
4. **Automatiser** : Créer des scripts cron pour lancer automatiquement les extractions

---

## 📞 Support

Pour toute question :
1. Consultez `README_INTERFACE.md` pour la documentation complète
2. Consultez `QUICKSTART.md` pour le guide rapide
3. Testez avec `db_helper.py` pour vérifier l'installation

---

## 🎊 Félicitations !

Vous avez maintenant une solution professionnelle pour gérer votre scraping de données ! 🚀

L'interface vous permet de :
- ✅ Suivre l'état de chaque site en temps réel
- ✅ Visualiser vos statistiques avec des graphiques
- ✅ Filtrer et rechercher facilement
- ✅ Exporter vos données
- ✅ Éviter les doublons automatiquement
- ✅ Reprendre après une erreur

**Bon scraping ! 🎯**
