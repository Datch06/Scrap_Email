# Guide des Scripts - Scrap_Email

## 📋 Table des Matières
- [Scripts Principaux](#scripts-principaux)
- [Scripts de Base de Données](#scripts-de-base-de-données)
- [Scripts d'Import/Export](#scripts-dimportexport)
- [Scripts de Scraping](#scripts-de-scraping)
- [Scripts Google Sheets](#scripts-google-sheets)
- [Scripts de Test](#scripts-de-test)
- [Scripts Utilitaires](#scripts-utilitaires)

---

## 🚀 Scripts Principaux

### **app.py**
**Interface web Flask pour gérer le scraping d'emails**
- Lance l'interface admin sur le port 5002
- API REST pour consulter/gérer les sites
- Endpoints principaux:
  - `GET /api/stats` - Statistiques globales
  - `GET /api/sites` - Liste des sites avec pagination
  - `GET /api/sites/<domain>` - Détails d'un site
  - `POST /api/scrape` - Lancer un scraping
- Accessible via: https://admin.perfect-cocon-seo.fr

**Usage:**
```bash
python3 app.py
# ou via systemd:
sudo systemctl start scrap-email-interface.service
```

### **wsgi.py**
**Point d'entrée WSGI pour déploiement production**
- Utilisé par Gunicorn ou autre serveur WSGI
- Configure l'application Flask pour production

---

## 💾 Scripts de Base de Données

### **database.py**
**Modèles SQLAlchemy de la base de données**
- Définit la structure de la table `sites`
- Champs principaux:
  - `domain` - Nom de domaine
  - `emails` - Emails trouvés (séparés par `;`)
  - `email_source` - Source: 'scraping' ou 'siret'
  - `siret` / `siren` - Identifiants entreprise
  - `leaders` - Dirigeants de l'entreprise
  - `status` - Statut du site (enum)
- Enums: `SiteStatus`, `ScrapingJobStatus`

### **db_helper.py**
**Helper pour faciliter les opérations en base**
- Context manager pour gérer les sessions
- Méthodes principales:
  - `add_site(domain)` - Ajouter un site
  - `update_email(domain, emails, source)` - Mettre à jour les emails
  - `update_siret(domain, siret, type)` - Mettre à jour SIRET
  - `update_leaders(domain, leaders)` - Mettre à jour dirigeants
  - `get_stats()` - Obtenir les statistiques

**Usage:**
```python
from db_helper import DBHelper

with DBHelper() as db:
    db.add_site('example.fr')
    db.update_email('example.fr', 'contact@example.fr', 'scraping')
```

### **migrate_add_email_source.py**
**Migration pour ajouter la colonne email_source**
- Ajoute la colonne `email_source` à la table sites
- Marque les emails existants comme source='scraping'
- ⚠️ À exécuter une seule fois (déjà fait)

---

## 📥 Scripts d'Import/Export

### **import_feuille1_emails.py** ⭐
**Importe les emails depuis Google Sheets Feuille 1**
- Source: Emails trouvés par scraping
- Structure du sheet (sans en-tête):
  - Colonne 0: Domain
  - Colonne 1: Emails (séparés par `;`)
  - Colonne 2: Date
  - Colonne 3: SIRET/SIREN
  - Colonne 5+: Dirigeants
- Marque tous les emails comme `email_source='scraping'`
- **Résultat**: 1182 emails importés

**Usage:**
```bash
python3 import_feuille1_emails.py
```

### **import_feuille3_emails.py**
**Importe les emails depuis Google Sheets Feuille 3**
- Source: Emails trouvés via recherche SIRET/SIREN
- Marque les emails comme `email_source='siret'`
- Ne remplace pas les emails déjà trouvés par scraping

**Usage:**
```bash
python3 import_feuille3_emails.py
```

### **import_existing_data.py**
**Import initial depuis fichiers CSV et JSON**
- Importe depuis:
  - `emails_found.csv`
  - `emails_formatted.csv`
  - `emails_cleaned.csv`
  - `feuille1_results.json`
  - `feuille2_results.json`
  - `dirigeants_results.json`
  - Fichiers TXT de domaines
- ⚠️ Script historique, utiliser plutôt import_feuille1_emails.py

### **import_cleaned_emails.py**
**Importe depuis emails_cleaned.csv**
- Emails déjà filtrés et formatés
- Concatène les emails par domaine
- Filtre les "NO EMAIL FOUND"

### **reimport_emails_improved.py**
**Version améliorée de l'import CSV**
- Groupe les emails par domaine
- Filtre les emails de tracking (sentry, etc.)
- Concatène plusieurs emails avec des virgules

### **extract_emails_db.py**
**Exporte les emails de la base vers CSV**
- Génère un CSV avec tous les sites et leurs emails
- Utile pour backup ou analyse

**Usage:**
```bash
python3 extract_emails_db.py
```

---

## 🕷️ Scripts de Scraping

### **extract_emails.py**
**Scraper principal pour extraire les emails**
- Lit une liste de domaines
- Crawl chaque site pour trouver des emails
- Sauvegarde dans la base de données
- Filtre les emails invalides

**Usage:**
```bash
python3 extract_emails.py domains.txt
```

### **playwright_crawl.py**
**Scraper utilisant Playwright (navigateur headless)**
- Plus robuste que requests pour les sites JS
- Simule un vrai navigateur
- Gère les cookies, redirections, etc.

### **selenium_crawl.py**
**Scraper utilisant Selenium**
- Alternative à Playwright
- Pour sites nécessitant interaction JavaScript

### **crawl_backlinks.py**
**Crawl les backlinks d'un site**
- Trouve les sites qui pointent vers un domaine
- Utile pour découvrir de nouveaux prospects

---

## 📊 Scripts Google Sheets

### **upload_to_gsheet.py**
**Upload les données vers Google Sheets**
- Met à jour la Feuille 1 avec les résultats
- Synchronise base de données → Google Sheets

### **upload_emails_to_gsheet.py**
**Upload uniquement les emails trouvés**
- Version spécialisée pour les emails

### **upload_no_email_to_sheet.py**
**Upload les sites sans email vers une feuille**
- Utile pour identifier les sites à retraiter

### **update_feuille1.py**
**Met à jour la Feuille 1**
- Synchronisation bidirectionnelle

### **update_feuille2_batch.py**
**Met à jour la Feuille 2 par batch**
- Pour éviter les timeouts sur gros volumes

### **create_feuille3.py**
**Crée la Feuille 3 avec les emails trouvés via SIRET**
- Sépare les sources d'emails (scraping vs SIRET)

### **update_sheet_with_leaders_playwright.py**
**Met à jour le sheet avec les dirigeants (Playwright)**
- Scrape les informations de dirigeants
- Version Playwright (plus fiable)

### **update_sheet_with_leaders.py**
**Version requests du script précédent**

### **update_feuille2_with_leaders_playwright.py**
**Spécifique à la Feuille 2**

### **update_feuille2_with_leaders.py**
**Version requests**

---

## 🔍 Scripts de Recherche SIRET/Dirigeants

### **find_company_leaders.py**
**Trouve les dirigeants d'une entreprise**
- Utilise API Pappers ou scraping societe.com
- Stocke dans le champ `leaders`

**Usage:**
```bash
python3 find_company_leaders.py
```

### **fetch_dirigeants_slow.py**
**Version "slow" avec rate limiting**
- Évite de se faire bloquer
- Ajoute des délais entre requêtes

### **fetch_emails_from_pappers.py**
**Récupère les emails via l'API Pappers**
- Utilise les SIRET pour trouver emails
- Clé API: `9c9507b8e254e643ae1040e87eb573fed6f1d6dfc6049c74`
- ⚠️ Nécessite des crédits API (100 gratuits)

**Modes:**
```bash
# Mode test (1 domaine)
python3 fetch_emails_from_pappers.py test

# Mode dry-run (simulation)
python3 fetch_emails_from_pappers.py --dry-run

# Mode production
python3 fetch_emails_from_pappers.py
```

### **check_pappers_potential.py**
**Analyse le potentiel de l'API Pappers**
- Compte combien de sites ont SIRET mais pas email
- Estime le coût en crédits API
- Projette le taux d'emails après utilisation

**Usage:**
```bash
python3 check_pappers_potential.py
```

---

## 🔧 Scripts Utilitaires

### **check_progress.py**
**Affiche la progression du scraping**
- Statistiques en temps réel
- Nombre de sites traités, emails trouvés, etc.

**Usage:**
```bash
python3 check_progress.py
```

### **clean_emails.py**
**Nettoie les emails trouvés**
- Filtre les emails invalides
- Supprime les doublons
- Retire les emails de tracking (sentry, etc.)

### **clean_feuille2.py**
**Nettoie la Feuille 2 du Google Sheet**

### **clean_unwanted_domains.py**
**Supprime les domaines non désirés**
- Filtre selon patterns (spam, parked domains, etc.)

### **extract_domains.py**
**Extrait les domaines d'une source**
- Parse HTML, CSV, ou autre pour extraire domaines

### **find_new_prospects.py**
**Trouve de nouveaux prospects**
- Algorithmes de découverte de domaines similaires

### **format_for_gsheet.py**
**Formate les données pour Google Sheets**
- Prépare les données au bon format

### **retry_failed_domains.py**
**Retente les domaines en erreur**
- Relance le scraping pour les sites failed

**Usage:**
```bash
python3 retry_failed_domains.py
```

---

## 🧪 Scripts de Test

### **test_20min.py**
**Test de scraping sur 20minutes.fr**

### **test_bordas.py**
**Test de scraping sur bordas.fr**

### **test_pappers.py**
**Test de l'API Pappers**
- Vérifie la connexion et les crédits

**Usage:**
```bash
python3 test_pappers.py
```

### **test_playwright_siret.py**
**Test de recherche SIRET avec Playwright**

### **test_societe_playwright.py**
**Test de scraping societe.com avec Playwright**

### **scraper_bijouxenvogue.fr**
**Test spécifique pour un site e-commerce**

---

## 📈 Workflow Recommandé

### 1️⃣ **Import Initial**
```bash
# Importer les emails depuis Google Sheets Feuille 1
python3 import_feuille1_emails.py

# Vérifier les stats
python3 check_progress.py
```

### 2️⃣ **Scraping de Nouveaux Sites**
```bash
# Ajouter des domaines
echo "example.fr" >> domains_new.txt

# Lancer le scraping
python3 extract_emails.py domains_new.txt

# Ou via l'API
curl -X POST https://admin.perfect-cocon-seo.fr/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"domains": ["example.fr"]}'
```

### 3️⃣ **Enrichissement via SIRET**
```bash
# Vérifier le potentiel
python3 check_pappers_potential.py

# Lancer la recherche (si crédits disponibles)
python3 fetch_emails_from_pappers.py
```

### 4️⃣ **Synchronisation Google Sheets**
```bash
# Upload vers Google Sheets
python3 upload_to_gsheet.py

# Ou import depuis Google Sheets
python3 import_feuille1_emails.py
```

### 5️⃣ **Vérification & Monitoring**
```bash
# Statistiques via API
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool

# Ou via interface web
# https://admin.perfect-cocon-seo.fr
```

---

## 🔐 Configuration Requise

### Fichiers de Configuration
- `credentials.json` - Credentials Google Sheets API
- `scrap_email.db` - Base de données SQLite
- `.env` - Variables d'environnement (optionnel)

### Services Système
- `scrap-email-interface.service` - Service systemd pour l'app Flask
- Nginx reverse proxy configuré sur port 443 (HTTPS)
- Certificat SSL Let's Encrypt actif

### APIs Utilisées
- **Google Sheets API** - Synchronisation données
- **Pappers API** - Recherche d'emails via SIRET
  - Clé: `9c9507b8e254e643ae1040e87eb573fed6f1d6dfc6049c74`
  - Crédits: 100 gratuits (à activer)

---

## 📊 État Actuel de la Base

### Statistiques (au 18 octobre 2025)
- **Total sites**: 2850
- **Sites avec email**: 1182 (41.5%)
  - Scraping: 1182
  - SIRET: 0
- **Sites avec SIRET**: 820 (28.8%)
- **Sites avec dirigeants**: 74 (2.6%)
- **Sites complets**: 74 (2.6%)

### Potentiel d'Amélioration
- ~750 sites ont SIRET mais pas email
- Utilisation API Pappers → estimé +560 emails (75% succès)
- Coût estimé: 15€ (750 × 0.02€)

---

## 🚨 Points d'Attention

### ⚠️ Ne PAS Exécuter Plusieurs Fois
- `migrate_add_email_source.py` - Migration déjà effectuée

### 🔄 Scripts de Maintenance Régulière
- `check_progress.py` - Monitoring
- `retry_failed_domains.py` - Relance erreurs
- `import_feuille1_emails.py` - Sync Google Sheets → DB

### 🛡️ Rate Limiting
- Utiliser les versions `_slow` pour éviter blocages
- Respecter les ToS des sites scrapés
- API Pappers: limites selon abonnement

---

## 📞 Support & Documentation

### Logs
```bash
# Logs du service Flask
sudo journalctl -u scrap-email-interface.service -f

# Logs Nginx
sudo tail -f /var/log/nginx/error.log
```

### Commandes Utiles
```bash
# Redémarrer le service
sudo systemctl restart scrap-email-interface.service

# Vérifier l'état
sudo systemctl status scrap-email-interface.service

# Tester Nginx
sudo nginx -t
```

### URLs Importantes
- **Interface Admin**: https://admin.perfect-cocon-seo.fr
- **API Stats**: https://admin.perfect-cocon-seo.fr/api/stats
- **Google Sheet**: https://docs.google.com/spreadsheets/d/19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I

---

**Dernière mise à jour**: 18 octobre 2025
