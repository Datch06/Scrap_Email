# Guide de Démarrage Rapide

## Accès à l'Interface

🌐 **URL**: https://admin.perfect-cocon-seo.fr

---

## Première Connexion

Ouvrez votre navigateur et accédez à:

**https://admin.perfect-cocon-seo.fr**

Vous verrez le **Dashboard** avec:
- Statistiques globales
- Nombre de sites
- Taux de complétion
- Jobs récents

---

## Navigation

### 1. Dashboard (/)
Aperçu rapide de vos données:
- Total de sites scrapés
- Pourcentage de sites avec emails
- Pourcentage de sites avec SIRET
- Pourcentage de sites avec dirigeants
- Activité récente

### 2. Sites (/sites)
Gestion complète de vos sites:
- **Recherche**: Filtrer par nom de domaine
- **Filtres**: Par statut, avec/sans email, SIRET, dirigeants
- **Actions**: Voir détails, modifier, supprimer
- **Pagination**: 50 sites par page

### 3. Jobs (/jobs)
Historique des tâches de scraping:
- Status des jobs (en cours, terminé, erreur)
- Nombre de sites traités
- Taux de réussite
- Durée d'exécution

---

## Utilisation de l'API

Toutes les requêtes API utilisent HTTPS.

### Obtenir les Statistiques

```bash
curl https://admin.perfect-cocon-seo.fr/api/stats
```

Réponse:
```json
{
  "total_sites": 4,
  "sites_with_email": 2,
  "email_rate": 50.0,
  "sites_complete": 2,
  "completion_rate": 50.0
}
```

### Lister les Sites

```bash
# Page 1, 50 résultats
curl "https://admin.perfect-cocon-seo.fr/api/sites?page=1&per_page=50"

# Avec filtre
curl "https://admin.perfect-cocon-seo.fr/api/sites?status=completed"

# Recherche
curl "https://admin.perfect-cocon-seo.fr/api/sites?search=example.com"
```

### Exporter en CSV

```bash
curl -o sites.csv https://admin.perfect-cocon-seo.fr/api/export/csv
```

Le fichier CSV contient:
- ID, Domaine, Statut
- Emails, SIRET, SIREN
- Dirigeants, Source
- Dates de création/mise à jour

---

## Ajouter un Site

Via l'API:

```bash
curl -X POST https://admin.perfect-cocon-seo.fr/api/sites \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "source_url": "https://source.com"
  }'
```

---

## Lancer un Job de Scraping

```bash
curl -X POST https://admin.perfect-cocon-seo.fr/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "scrape_emails",
    "config": {
      "max_sites": 100,
      "timeout": 30
    }
  }'
```

---

## Commandes de Gestion Rapide

### Redémarrer l'Application

```bash
sudo systemctl restart scrap-email-interface.service
```

### Voir les Logs

```bash
# Logs de l'application
sudo journalctl -u scrap-email-interface.service -f

# Logs Nginx
sudo tail -f /var/log/nginx/scrap-email-access.log
```

### Vérifier le Statut

```bash
# Application
sudo systemctl status scrap-email-interface.service

# Nginx
sudo systemctl status nginx

# SSL
sudo certbot certificates
```

---

## Sauvegarde de la Base de Données

```bash
# Créer une sauvegarde
cd /var/www/Scrap_Email
cp scrap_email.db backup_$(date +%Y%m%d_%H%M%S).db

# Restaurer une sauvegarde
cp backup_20251018_123456.db scrap_email.db
sudo systemctl restart scrap-email-interface.service
```

---

## Troubleshooting

### Le site ne répond pas

1. Vérifier le service Flask:
   ```bash
   sudo systemctl status scrap-email-interface.service
   ```

2. Vérifier Nginx:
   ```bash
   sudo systemctl status nginx
   ```

3. Vérifier les logs:
   ```bash
   sudo journalctl -u scrap-email-interface.service -n 50
   ```

### Erreur 502 Bad Gateway

Le service Flask n'est pas démarré:
```bash
sudo systemctl restart scrap-email-interface.service
```

### Erreur SSL/Certificat

Renouveler le certificat:
```bash
sudo certbot renew
sudo systemctl reload nginx
```

### Base de données corrompue

Restaurer une sauvegarde:
```bash
cd /var/www/Scrap_Email
cp backup_YYYYMMDD.db scrap_email.db
sudo systemctl restart scrap-email-interface.service
```

---

## Filtres Disponibles (Page Sites)

| Filtre | Valeurs | Description |
|--------|---------|-------------|
| status | discovered, email_found, completed, error | Statut du site |
| has_email | true/false | Avec ou sans email |
| has_siret | true/false | Avec ou sans SIRET |
| has_leaders | true/false | Avec ou sans dirigeants |
| search | texte | Recherche dans le domaine |

Exemple:
```
/sites?status=completed&has_email=true&search=.fr
```

---

## Développement

### Mode Debug Local

Pour tester en local:

```bash
cd /var/www/Scrap_Email
export FLASK_DEBUG=True
export FLASK_PORT=5002
python3 app.py
```

Accessible sur: http://localhost:5002

### Fichiers Importants

- [app.py](app.py:1) - Application Flask principale
- [database.py](database.py:1) - Modèles de base de données
- [templates/](templates/) - Templates HTML
- [static/](static/) - CSS et JavaScript
- [scrap_email.db](scrap_email.db:1) - Base de données SQLite

---

## Scripts Python Disponibles

| Script | Description |
|--------|-------------|
| extract_emails_db.py | Extraire les emails et les enregistrer en DB |
| fetch_dirigeants_slow.py | Récupérer les dirigeants |
| update_feuille1.py | Mettre à jour la feuille Google Sheets |
| import_existing_data.py | Importer des données existantes |

---

## Support

Pour plus d'informations, consultez:

- [INSTALLATION_COMPLETE.md](INSTALLATION_COMPLETE.md:1) - Documentation complète
- [README_INTERFACE.md](README_INTERFACE.md:1) - Guide de l'interface
- [DEPLOYMENT.md](DEPLOYMENT.md:1) - Guide de déploiement

---

**Tout est prêt !** 🚀

Commencez par visiter https://admin.perfect-cocon-seo.fr
