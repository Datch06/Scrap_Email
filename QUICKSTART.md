# Guide de Démarrage Rapide - Interface Scrap Email

## 🚀 Installation en 3 minutes

### Étape 1 : Installer les dépendances

```bash
cd /var/www/Scrap_Email
pip3 install sqlalchemy flask flask-cors
```

### Étape 2 : Initialiser la base de données

```bash
python3 database.py
```

Vous verrez : `✓ Base de données créée avec succès : scrap_email.db`

### Étape 3 : Importer vos données existantes (optionnel)

Si vous avez déjà des fichiers CSV/JSON avec des données :

```bash
python3 import_existing_data.py
```

### Étape 4 : Lancer l'interface

```bash
python3 app.py
```

### Étape 5 : Ouvrir l'interface

Ouvrez votre navigateur : **http://localhost:5000**

---

## 📊 Utilisation de l'interface

### Dashboard (Page d'accueil)
- **Statistiques en temps réel** : Total sites, emails trouvés, SIRET, dirigeants
- **Graphiques interactifs** : Répartition par statut, taux de complétion
- **Actions rapides** : Accès direct aux filtres et exports

### Page Sites
- **Tableau complet** de tous vos sites
- **Filtres** : Par statut, email, SIRET, dirigeants
- **Recherche** : Rechercher un domaine spécifique
- **Actions** : Voir détails, supprimer
- **Ajouter** : Ajouter manuellement de nouveaux sites

### Page Jobs
- **Historique** des tâches de scraping
- **Progression** en temps réel
- **Statistiques** de succès/erreurs

---

## 🔧 Intégrer vos scripts existants

### Exemple 1 : Ajouter des domaines découverts

```python
from db_helper import DBHelper

domains = ['site1.fr', 'site2.fr', 'site3.fr']

with DBHelper() as db:
    for domain in domains:
        db.add_site(domain, source_url='https://source.com')
```

### Exemple 2 : Mettre à jour avec des emails

```python
from db_helper import DBHelper

results = {
    'site1.fr': 'contact@site1.fr',
    'site2.fr': 'NO EMAIL FOUND',
    'site3.fr': 'info@site3.fr; sales@site3.fr'
}

with DBHelper() as db:
    for domain, emails in results.items():
        db.update_email(domain, emails)
```

### Exemple 3 : Workflow complet

```python
from db_helper import DBHelper

with DBHelper() as db:
    # Récupérer les sites sans email
    sites = db.get_sites_without_email(limit=10)

    for site in sites:
        domain = site.domain

        # Votre code pour extraire l'email
        emails = extract_emails_from_domain(domain)

        # Mettre à jour la base
        if emails:
            db.update_email(domain, '; '.join(emails))
        else:
            db.update_email(domain, 'NO EMAIL FOUND')
```

---

## 📤 Export des données

### Depuis l'interface web
1. Cliquer sur **"Exporter CSV"** dans le dashboard
2. Le fichier sera téléchargé automatiquement

### Via API
```bash
curl http://localhost:5000/api/export/csv -o export.csv
```

### Vers Google Sheets
Utilisez vos scripts existants `upload_to_gsheet.py` en récupérant les données depuis la base :

```python
from db_helper import DBHelper

with DBHelper() as db:
    # Récupérer tous les sites avec email + SIRET + dirigeants
    query = db.session.query(Site).filter(
        Site.emails.isnot(None),
        Site.siret.isnot(None),
        Site.leaders.isnot(None)
    ).all()

    # Préparer pour Google Sheets
    data = [[site.domain, site.emails, site.siret, site.leaders]
            for site in query]
```

---

## 🎯 Workflows recommandés

### Workflow 1 : Découverte de nouveaux sites
```bash
# 1. Crawl pour découvrir des sites
python3 playwright_crawl.py --start https://www.ladepeche.fr/ --max-pages 100

# 2. Extraire les domaines
python3 extract_domains.py

# 3. Importer dans la base
python3 import_existing_data.py

# 4. Vérifier dans l'interface
# Ouvrir http://localhost:5000/sites
```

### Workflow 2 : Extraire les emails
```bash
# 1. Lister les sites sans email via l'interface
# Filtre : has_email=false

# 2. Lancer l'extraction (modifié pour utiliser la DB)
python3 extract_emails_db.py --limit 50

# 3. Voir les résultats dans l'interface
# Rafraîchir la page Sites
```

### Workflow 3 : Compléter avec SIRET et dirigeants
```bash
# 1. Sites avec email mais sans SIRET
# Filtre : has_email=true, has_siret=false

# 2. Chercher SIRET
python3 find_siret_db.py --limit 20

# 3. Sites avec SIRET mais sans dirigeants
# Filtre : has_siret=true, has_leaders=false

# 4. Chercher dirigeants
python3 find_leaders_db.py --limit 10
```

---

## 🔍 API REST

### Obtenir des statistiques
```bash
curl http://localhost:5000/api/stats
```

### Lister les sites
```bash
# Tous les sites
curl http://localhost:5000/api/sites

# Avec filtres
curl "http://localhost:5000/api/sites?has_email=true&has_siret=false"
```

### Ajouter un site
```bash
curl -X POST http://localhost:5000/api/sites \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.fr", "source_url": "https://source.com"}'
```

### Mettre à jour un site
```bash
curl -X PUT http://localhost:5000/api/sites/1 \
  -H "Content-Type: application/json" \
  -d '{"emails": "contact@example.fr"}'
```

---

## 🐛 Dépannage

### Problème : "ModuleNotFoundError: No module named 'sqlalchemy'"
**Solution** :
```bash
pip3 install sqlalchemy flask flask-cors
```

### Problème : "database is locked"
**Solution** : Une seule instance de l'application peut accéder à la base à la fois. Fermez les autres processus.

### Problème : L'interface ne charge pas
**Solution** :
1. Vérifiez que le serveur est lancé : `python3 app.py`
2. Vérifiez l'URL : http://localhost:5000
3. Regardez les logs dans le terminal

### Problème : Pas de données affichées
**Solution** :
1. Importez vos données : `python3 import_existing_data.py`
2. Ou ajoutez manuellement via l'interface

---

## 📝 Notes importantes

- **Sauvegarde** : La base de données est dans le fichier `scrap_email.db`. Sauvegardez-le régulièrement !
- **Performance** : SQLite est parfait pour jusqu'à ~100 000 sites. Au-delà, envisagez PostgreSQL
- **Sécurité** : Par défaut, l'interface est accessible uniquement en local. Pour un déploiement distant, ajoutez une authentification
- **Auto-refresh** : Le dashboard se rafraîchit automatiquement toutes les 30 secondes

---

## 🎉 Vous êtes prêt !

L'interface est maintenant opérationnelle. Bon scraping ! 🚀
