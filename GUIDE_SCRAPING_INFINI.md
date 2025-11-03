# 🚀 Guide du Scraping Infini - Acheteurs de Backlinks

## 📋 Résumé des Modifications

Toutes les limites ont été **supprimées** pour permettre un scraping **illimité** de tous les sites acheteurs de backlinks.

---

## ✅ Scripts Modifiés

### 1. **extract_emails_db.py**
Scraping d'emails pour tous les sites en base

**Avant:**
- Limite par défaut: 50 sites
- Max pages: 5

**Après:**
- Limite par défaut: **AUCUNE (illimité)**
- Max pages: **10**

**Usage:**
```bash
# Scraper TOUS les sites sans email
python3 extract_emails_db.py

# Ou avec limite personnalisée si besoin
python3 extract_emails_db.py --limit 1000 --max-pages 15
```

---

### 2. **find_new_prospects.py**
Découverte automatique de nouveaux acheteurs

**Avant:**
- MAX_NEW_PROSPECTS = 500
- MAX_PAGES_PER_SITE = 200
- MAX_SELLER_SITES = 30

**Après:**
- MAX_NEW_PROSPECTS = **None (illimité)**
- MAX_PAGES_PER_SITE = **500**
- MAX_SELLER_SITES = **None (tous)**
- MAX_DEPTH = **5**

**Usage:**
```bash
# Crawle TOUS les sites vendeurs pour trouver TOUS les acheteurs
python3 find_new_prospects.py
```

---

### 3. **scrape_backlinks_infinite.py** ⭐ NOUVEAU!
Script de scraping continu infini

**Caractéristiques:**
- ♾️ Tourne **indéfiniment** jusqu'à épuisement complet
- 🔄 Crawle **tous** les sites vendeurs de backlinks
- 📧 Extrait **tous** les emails des acheteurs
- 💾 Stocke tout dans la base de données
- 🔁 Recommence automatiquement quand tous les sites sont explorés
- 📊 Statistiques en temps réel

**Configuration:**
```python
MAX_PAGES_PER_SELLER_SITE = 500  # Pages crawlées par site vendeur
MAX_DEPTH = 5                     # Profondeur de crawl
PAUSE_BETWEEN_SITES = 0.1         # Secondes entre chaque site
BATCH_SIZE = 100                  # Sync tous les 100 sites
```

---

## 🎯 Mode d'Emploi du Scraping Infini

### Option 1: Exécution Interactive

```bash
cd /var/www/Scrap_Email

# Lancer le scraping infini
python3 scrape_backlinks_infinite.py
```

**Sortie:**
```
================================================================================
🚀 SCRAPING INFINI - TOUS LES ACHETEURS DE BACKLINKS
================================================================================

Configuration:
  - Pages par site vendeur: 500
  - Profondeur max: 5
  - Pause entre sites: 0.1s
  - Batch size: 100

================================================================================
CYCLE #1 - 2025-10-18 15:30:00
================================================================================

📊 Progression:
  - Total sites vendeurs: 450
  - Déjà explorés: 0
  - Restants: 450

[1/450] Site vendeur: https://example-backlinks.fr
  Crawling https://example-backlinks.fr...
    → 342 domaines acheteurs trouvés
    [1/342] site1.fr... ✓ contact@site1.fr
    [2/342] site2.fr... ✗ Pas d'email
    ...
```

### Option 2: Exécution en Arrière-Plan (Recommandé)

Pour laisser tourner **24/7**:

```bash
cd /var/www/Scrap_Email

# Lancer en arrière-plan avec nohup
nohup python3 scrape_backlinks_infinite.py > scraping_infini.log 2>&1 &

# Récupérer le PID du processus
echo $!

# Suivre les logs en temps réel
tail -f scraping_infini.log

# Arrêter proprement (remplacer PID par le numéro du processus)
kill -SIGINT PID
```

### Option 3: Service Systemd (Production)

Créer un service systemd pour démarrage automatique:

```bash
sudo nano /etc/systemd/system/scrap-backlinks-infinite.service
```

Contenu:
```ini
[Unit]
Description=Scraping Infini Acheteurs Backlinks
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/Scrap_Email
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /var/www/Scrap_Email/scrape_backlinks_infinite.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/scrap-backlinks-infinite.log
StandardError=append:/var/log/scrap-backlinks-infinite.log

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scrap-backlinks-infinite.service
sudo systemctl start scrap-backlinks-infinite.service

# Vérifier le statut
sudo systemctl status scrap-backlinks-infinite.service

# Voir les logs
sudo journalctl -u scrap-backlinks-infinite.service -f
```

---

## 📊 Monitoring & Statistiques

### Vérifier la Progression

```bash
# Via l'API
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool

# Via le script de monitoring
python3 check_progress.py

# Compter les sites explorés
wc -l explored_seller_sites.txt
```

### Statistiques en Temps Réel

```bash
# Suivre les logs
tail -f scraping_infini.log

# Filtrer uniquement les statistiques
tail -f scraping_infini.log | grep "Stats globales"

# Compter les emails trouvés
grep "✓" scraping_infini.log | wc -l
```

---

## 🔧 Configuration Avancée

### Ajuster la Vitesse de Scraping

Éditer [scrape_backlinks_infinite.py](/var/www/Scrap_Email/scrape_backlinks_infinite.py):

```python
# Plus lent (éviter blocages)
PAUSE_BETWEEN_SITES = 0.5
PAUSE_BETWEEN_PAGES = 0.2

# Plus rapide (risque de blocage)
PAUSE_BETWEEN_SITES = 0.05
PAUSE_BETWEEN_PAGES = 0.01

# Équilibré (recommandé)
PAUSE_BETWEEN_SITES = 0.1
PAUSE_BETWEEN_PAGES = 0.05
```

### Ajouter Plus de Sites Vendeurs

```bash
# Éditer la liste des sites vendeurs
nano site_urls.txt

# Ajouter vos URLs (une par ligne)
https://nouveau-site-backlinks.fr
https://annuaire-backlinks.fr
...
```

### Réinitialiser le Scraping

```bash
# Effacer l'historique des sites explorés (recommence du début)
rm explored_seller_sites.txt

# Relancer
python3 scrape_backlinks_infinite.py
```

---

## 📈 Estimations de Performance

### Capacités Théoriques

Avec la configuration actuelle:

- **Sites vendeurs**: ~450 sites
- **Pages par site vendeur**: 500 pages
- **Domaines par site vendeur**: ~300-500 (moyenne)
- **Taux d'emails trouvés**: ~40%

**Estimation totale:**
- **Domaines acheteurs potentiels**: 450 × 400 = **180,000 sites**
- **Emails attendus**: 180,000 × 40% = **72,000 emails**

### Temps Estimé

Avec pauses de sécurité:
- **Temps par domaine**: ~1 seconde (scraping + pauses)
- **Temps total**: 180,000 secondes = **50 heures**

**En mode 24/7**: Environ **2-3 jours** pour un cycle complet!

---

## ⚠️ Points d'Attention

### Rate Limiting
- Les pauses sont configurées pour éviter les blocages
- Si vous êtes bloqué, augmenter les pauses
- Utiliser des proxies rotatifs si nécessaire

### Ressources Serveur
- **CPU**: Faible (~5-10%)
- **RAM**: ~200-500 MB
- **Disque**: ~1 GB pour 100k sites
- **Réseau**: ~10-50 KB/s

### Gestion des Erreurs
- Le script reprend automatiquement après une erreur
- Les sites problématiques sont ignorés
- Logs détaillés dans `scraping_infini.log`

### Stockage
- Base SQLite peut gérer **millions** d'entrées
- Prévoir ~10 KB par site en moyenne
- Pour 100k sites: ~1 GB d'espace disque

---

## 🛑 Arrêt & Reprise

### Arrêter Proprement

```bash
# Si lancé en interactif
Ctrl + C

# Si lancé en arrière-plan (trouver le PID d'abord)
ps aux | grep scrape_backlinks_infinite
kill -SIGINT <PID>

# Si lancé comme service
sudo systemctl stop scrap-backlinks-infinite.service
```

### Reprendre

Le script reprend **automatiquement** là où il s'était arrêté grâce au fichier `explored_seller_sites.txt`.

```bash
# Relancer simplement
python3 scrape_backlinks_infinite.py
```

---

## 📞 Commandes Utiles

```bash
# Statistiques rapides
curl -s https://admin.perfect-cocon-seo.fr/api/stats

# Compter les domaines en base
sqlite3 scrap_email.db "SELECT COUNT(*) FROM sites;"

# Compter les emails
sqlite3 scrap_email.db "SELECT COUNT(*) FROM sites WHERE emails IS NOT NULL AND emails != 'NO EMAIL FOUND';"

# Top 10 sites avec le plus d'emails
sqlite3 scrap_email.db "SELECT domain, emails FROM sites WHERE emails IS NOT NULL AND emails != 'NO EMAIL FOUND' ORDER BY length(emails) DESC LIMIT 10;"

# Vérifier l'espace disque
df -h /var/www/Scrap_Email

# Taille de la base
du -h scrap_email.db

# Processus en cours
ps aux | grep python3 | grep scrap
```

---

## 🎯 Workflow Recommandé

### Démarrage Initial

```bash
cd /var/www/Scrap_Email

# 1. Vérifier la configuration
cat site_urls.txt | wc -l

# 2. Lancer en arrière-plan
nohup python3 scrape_backlinks_infinite.py > scraping_infini.log 2>&1 &

# 3. Sauvegarder le PID
echo $! > scraping.pid

# 4. Vérifier que ça tourne
tail -f scraping_infini.log
```

### Monitoring Quotidien

```bash
# Chaque jour, vérifier les stats
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'''
📊 STATISTIQUES DU {data.get('date', 'N/A')}

Total sites: {data['total_sites']}
Avec email: {data['sites_with_email']} ({data['email_rate']}%)
Avec SIRET: {data['sites_with_siret']} ({data['siret_rate']}%)

Sites explorés: {open('explored_seller_sites.txt').read().count(chr(10)) if Path('explored_seller_sites.txt').exists() else 0}
''')
"

# Vérifier que le processus tourne toujours
ps aux | grep scrape_backlinks_infinite
```

### Maintenance

```bash
# Backup hebdomadaire de la base
cp scrap_email.db scrap_email_backup_$(date +%Y%m%d).db

# Nettoyer les vieux backups (garder 7 jours)
find . -name "scrap_email_backup_*.db" -mtime +7 -delete

# Rotation des logs (si très gros)
if [ $(stat -f%z scraping_infini.log) -gt 100000000 ]; then
    mv scraping_infini.log scraping_infini_$(date +%Y%m%d).log
fi
```

---

## 🚀 Résultat Attendu

Après quelques jours de scraping continu:

```
📊 STATISTIQUES FINALES

Total sites découverts: 180,000+
Avec email: 72,000+ (40%)
Avec SIRET: 50,000+ (28%)
Sites complets: 20,000+ (11%)

Cycles terminés: 3
Temps total: 6 jours
```

---

**Bonne chance avec votre scraping infini! 🎯**

Consultez https://admin.perfect-cocon-seo.fr pour suivre la progression en temps réel.
