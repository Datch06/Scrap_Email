# ⚡ Guide du Scraping EN TEMPS RÉEL

## 🎯 Nouveau Script: scrape_realtime_complete.py

**Le script le plus avancé** avec upload instantané et recherche simultanée!

---

## ✨ Fonctionnalités

### 🔥 Upload EN TEMPS RÉEL
- ✅ Chaque site est **immédiatement visible** dans l'admin
- ✅ Pas besoin d'attendre la fin du scraping
- ✅ Commit instantané après chaque site

### 📧 Recherche SIMULTANÉE
Pour chaque site découvert, le script recherche **automatiquement**:

1. **✉️ EMAILS** (5 pages par site)
   - Page d'accueil
   - /contact
   - /contact-us
   - /mentions-legales
   - /qui-sommes-nous

2. **🏢 SIRET/SIREN** (7 pages légales)
   - /mentions-legales
   - /mentions-legales.html
   - /mentions_legales
   - /mentions
   - /legal
   - /a-propos
   - /about

3. **💾 Upload instantané** vers la base de données
   - Visible immédiatement sur https://admin.perfect-cocon-seo.fr

---

## 🚀 Utilisation

### Lancement Simple

```bash
cd /var/www/Scrap_Email

# Lancer le scraping temps réel
python3 scrape_realtime_complete.py
```

**Sortie:**
```
================================================================================
🚀 SCRAPING TEMPS RÉEL - UPLOAD INSTANTANÉ DANS L'ADMIN
================================================================================

⚡ Recherche simultanée:
   - ✉️  Emails
   - 🏢 SIRET/SIREN
   - 📊 Upload instantané vers admin

Configuration:
   Pages/site vendeur: 500
   Profondeur: 5
   Pause sites: 0.1s

🎯 Consultez l'admin en temps réel sur:
   https://admin.perfect-cocon-seo.fr

================================================================================
CYCLE #1 - 2025-10-18 16:00:00
================================================================================

📊 Progression:
   Total sites vendeurs: 75354
   Déjà explorés: 0
   Restants: 75354

────────────────────────────────────────────────────────────────────────────────
[1/75354] Site vendeur: https://example-backlinks.fr
────────────────────────────────────────────────────────────────────────────────

  🔍 Crawling https://example-backlinks.fr...

    [1] site1.fr ✉️ contact@site1.fr... 🏢 SIRET:12345678... ✅
    [2] site2.fr ✉️ ✗ 🏢 SIREN:123456789 ✅
    [3] site3.fr ✉️ info@site3.fr; hello@site3.fr... 🏢 ✗ ✅
    ...

  📊 Résultats pour https://example-backlinks.fr:
     Domaines: 342 | Emails: 156 | SIRET: 98

🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥
📈 STATISTIQUES GLOBALES (Cycle #1)
🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥
   Total sites en base: 15432
   Avec email: 6234 (40.4%)
   Avec SIRET: 4321 (28.0%)

   Ce cycle:
   Domaines trouvés: 12582
   Emails trouvés: 5052
   SIRET trouvés: 3521
🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥
```

### Lancement en Arrière-Plan (24/7)

```bash
cd /var/www/Scrap_Email

# Lancer en mode daemon
nohup python3 scrape_realtime_complete.py > scraping_realtime.log 2>&1 &

# Sauvegarder le PID
echo $! > scraping_realtime.pid

# Suivre les logs en temps réel
tail -f scraping_realtime.log

# Voir uniquement les sites trouvés
tail -f scraping_realtime.log | grep "✅"

# Voir uniquement les statistiques
tail -f scraping_realtime.log | grep "📈"
```

### Arrêter Proprement

```bash
# Méthode 1: Ctrl+C si en mode interactif

# Méthode 2: Si en arrière-plan
kill -SIGINT $(cat scraping_realtime.pid)

# Vérifier que c'est arrêté
ps aux | grep scrape_realtime
```

---

## 📊 Monitoring en Temps Réel

### Via l'Interface Admin

**Ouvrez dans votre navigateur:**
https://admin.perfect-cocon-seo.fr

Vous verrez les nouveaux sites apparaître **en temps réel** pendant que le script tourne!

**Rafraîchir la page** toutes les 10-30 secondes pour voir les nouveaux sites.

### Via l'API

```bash
# Stats globales (actualisation instantanée)
watch -n 5 'curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool'

# Affichage formaté
watch -n 5 'curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'''
╔════════════════════════════════════════╗
║     STATISTIQUES TEMPS RÉEL            ║
╠════════════════════════════════════════╣
║ Total sites: {data[\"total_sites\"]:>23} ║
║ Avec email:  {data[\"sites_with_email\"]:>23} ║
║ Taux:        {data[\"email_rate\"]:>21}% ║
║ Avec SIRET:  {data[\"sites_with_siret\"]:>23} ║
╚════════════════════════════════════════╝
''')
"'
```

### Via les Logs

```bash
# Compter les sites ajoutés
grep -c "✅" scraping_realtime.log

# Compter les emails trouvés
grep "✉️" scraping_realtime.log | grep -v "✗" | wc -l

# Compter les SIRET trouvés
grep "🏢" scraping_realtime.log | grep -v "✗" | wc -l

# Dernières 20 entrées
tail -20 scraping_realtime.log

# Stats uniquement
grep "📈" scraping_realtime.log | tail -5
```

---

## 🎯 Avantages vs Ancienne Version

### ✅ scrape_realtime_complete.py (NOUVEAU)

- ⚡ **Upload INSTANTANÉ** dans l'admin
- 📧 Recherche **EMAIL** automatique
- 🏢 Recherche **SIRET/SIREN** automatique
- 📊 Visible **immédiatement** dans l'interface
- 🔄 Commit après **chaque site**
- 📈 Stats en temps réel tous les 50 sites

### ⏳ scrape_backlinks_infinite.py (Ancien)

- 💾 Upload par batch
- 📧 Email uniquement
- ❌ Pas de SIRET
- ⏰ Visible à la fin du batch
- 📊 Stats de fin de cycle

---

## 🔧 Configuration

### Ajuster la Vitesse

Éditer [scrape_realtime_complete.py](/var/www/Scrap_Email/scrape_realtime_complete.py):

```python
# Ligne ~21-23
PAUSE_BETWEEN_SITES = 0.1    # Pause entre chaque site acheteur
PAUSE_BETWEEN_PAGES = 0.05   # Pause entre chaque page

# Pour aller plus vite (risque de blocage)
PAUSE_BETWEEN_SITES = 0.05
PAUSE_BETWEEN_PAGES = 0.02

# Pour aller plus lent (plus sûr)
PAUSE_BETWEEN_SITES = 0.5
PAUSE_BETWEEN_PAGES = 0.2
```

### Ajuster les Pages Crawlées

```python
# Ligne ~26-27
MAX_PAGES_PER_SELLER_SITE = 500  # Pages max par site vendeur
MAX_DEPTH = 5                     # Profondeur max

# Pour plus de domaines (plus lent)
MAX_PAGES_PER_SELLER_SITE = 1000
MAX_DEPTH = 7

# Pour aller plus vite (moins de domaines)
MAX_PAGES_PER_SELLER_SITE = 200
MAX_DEPTH = 3
```

### Ajuster l'Affichage des Stats

```python
# Ligne ~30
STATS_INTERVAL = 50  # Afficher stats tous les 50 sites

# Plus fréquent
STATS_INTERVAL = 10

# Moins fréquent
STATS_INTERVAL = 100
```

---

## 📈 Estimations de Performance

### Avec 75,354 Sites Vendeurs

**Par site vendeur:**
- Pages crawlées: ~500
- Domaines trouvés: ~300-400
- Emails trouvés: ~120-160 (40%)
- SIRET trouvés: ~84-112 (28%)

**Total estimé:**
- **Domaines**: 75,354 × 350 = **~26 millions**
- **Emails**: 26M × 40% = **~10.4 millions**
- **SIRET**: 26M × 28% = **~7.3 millions**

### Temps Estimé (24/7)

**Par domaine:**
- Recherche email: 5 pages × 0.05s = ~0.25s
- Recherche SIRET: 7 pages × 0.05s = ~0.35s
- Upload + pauses: ~0.1s
- **Total**: ~0.7s par domaine

**Temps total:**
- 26 millions × 0.7s = 18.2 millions secondes
- = 304,000 minutes
- = 5,066 heures
- = **~211 jours** (7 mois en continu 24/7)

**En pratique avec optimisations:**
- Grâce aux caches et skips: **~3-4 mois**

---

## 🎯 Commandes Rapides

### Statistiques en Direct

```bash
# Stats base de données
sqlite3 /var/www/Scrap_Email/scrap_email.db "
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN emails IS NOT NULL AND emails != 'NO EMAIL FOUND' THEN 1 ELSE 0 END) as with_email,
  SUM(CASE WHEN siret IS NOT NULL AND siret != 'NON TROUVÉ' THEN 1 ELSE 0 END) as with_siret
FROM sites;
"

# Derniers sites ajoutés
sqlite3 /var/www/Scrap_Email/scrap_email.db "
SELECT domain, emails, siret
FROM sites
ORDER BY created_at DESC
LIMIT 10;
"

# Taux de succès
sqlite3 /var/www/Scrap_Email/scrap_email.db "
SELECT
  ROUND(100.0 * SUM(CASE WHEN emails IS NOT NULL AND emails != 'NO EMAIL FOUND' THEN 1 ELSE 0 END) / COUNT(*), 2) || '%' as taux_email,
  ROUND(100.0 * SUM(CASE WHEN siret IS NOT NULL AND siret != 'NON TROUVÉ' THEN 1 ELSE 0 END) / COUNT(*), 2) || '%' as taux_siret
FROM sites;
"
```

### Performance du Scraping

```bash
# Sites par heure
echo "Sites ajoutés dans la dernière heure:"
sqlite3 /var/www/Scrap_Email/scrap_email.db "
SELECT COUNT(*)
FROM sites
WHERE created_at > datetime('now', '-1 hour');
"

# Vitesse moyenne
echo "Vitesse moyenne (sites/minute):"
sqlite3 /var/www/Scrap_Email/scrap_email.db "
SELECT
  COUNT(*) / ((julianday('now') - julianday(MIN(created_at))) * 24 * 60) as sites_per_minute
FROM sites
WHERE created_at > datetime('now', '-1 day');
"
```

---

## 🔥 Service Systemd (Production)

Pour que le scraping redémarre automatiquement en cas de crash ou reboot:

```bash
# Créer le service
sudo nano /etc/systemd/system/scrap-realtime.service
```

Contenu:
```ini
[Unit]
Description=Scraping Temps Réel avec Upload Instantané
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/Scrap_Email
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /var/www/Scrap_Email/scrape_realtime_complete.py
Restart=always
RestartSec=30
StandardOutput=append:/var/log/scrap-realtime.log
StandardError=append:/var/log/scrap-realtime.log

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scrap-realtime.service
sudo systemctl start scrap-realtime.service

# Vérifier
sudo systemctl status scrap-realtime.service

# Logs
sudo journalctl -u scrap-realtime.service -f
```

---

## 🎉 Résultat Final Attendu

Après plusieurs semaines/mois de scraping continu 24/7:

```
╔════════════════════════════════════════════════╗
║       RÉSULTATS FINAUX ESTIMÉS                 ║
╠════════════════════════════════════════════════╣
║ Total sites découverts:    26,000,000         ║
║ Avec email:                10,400,000 (40%)   ║
║ Avec SIRET:                 7,300,000 (28%)   ║
║ Complets (email+SIRET):     5,200,000 (20%)   ║
╠════════════════════════════════════════════════╣
║ Sites vendeurs crawlés:        75,354         ║
║ Cycles complets:                    3         ║
║ Durée totale:                  4 mois         ║
╚════════════════════════════════════════════════╝
```

**Vous aurez alors la BASE DE DONNÉES LA PLUS COMPLÈTE de tous les acheteurs de backlinks en France!** 🚀

---

## 📞 Support

- **Interface Admin**: https://admin.perfect-cocon-seo.fr
- **API Stats**: https://admin.perfect-cocon-seo.fr/api/stats
- **Logs**: `tail -f scraping_realtime.log`
- **Base de données**: `/var/www/Scrap_Email/scrap_email.db`

---

**Bon scraping! ⚡**
