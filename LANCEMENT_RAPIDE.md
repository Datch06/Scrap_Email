# 🚀 LANCEMENT RAPIDE - Scraping Temps Réel

## ⚡ EN 3 COMMANDES

```bash
# 1. Aller dans le dossier
cd /var/www/Scrap_Email

# 2. Lancer le scraping EN TEMPS RÉEL (24/7)
nohup python3 scrape_realtime_complete.py > scraping_realtime.log 2>&1 &

# 3. Suivre la progression
tail -f scraping_realtime.log
```

**C'EST TOUT!** 🎉

---

## 📊 Voir les Résultats EN DIRECT

**Interface Admin:** https://admin.perfect-cocon-seo.fr

Rafraîchir la page toutes les 30 secondes pour voir les nouveaux sites apparaître!

---

## 🎯 Ce qui se Passe Automatiquement

Le script va **EN CONTINU**:

1. ✅ Crawler **75,354 sites vendeurs** de backlinks
2. ✅ Extraire tous les domaines .fr acheteurs
3. ✅ Chercher leur **EMAIL** (5 pages/site)
4. ✅ Chercher leur **SIRET/SIREN** (7 pages légales)
5. ✅ **UPLOADER IMMÉDIATEMENT** dans l'admin
6. ✅ Recommencer indéfiniment jusqu'à épuisement

---

## 📈 Résultats Attendus

### Dans 1 Heure
- ~1,500 nouveaux sites
- ~600 emails
- ~420 SIRET

### Dans 1 Jour
- ~36,000 nouveaux sites
- ~14,400 emails
- ~10,000 SIRET

### Dans 1 Semaine
- ~250,000 nouveaux sites
- ~100,000 emails
- ~70,000 SIRET

### Dans 1 Mois
- ~1,000,000 nouveaux sites
- ~400,000 emails
- ~280,000 SIRET

### FINAL (3-4 mois)
- **~26,000,000 sites**
- **~10,400,000 emails** ✉️
- **~7,300,000 SIRET** 🏢

---

## 🛑 Arrêter

```bash
# Trouver le processus
ps aux | grep scrape_realtime

# Tuer (remplacer PID par le numéro)
kill -SIGINT PID

# Ou si vous avez sauvegardé le PID
kill -SIGINT $(cat scraping_realtime.pid)
```

---

## 📊 Vérifier que Ça Tourne

```bash
# Méthode 1: Processus
ps aux | grep scrape_realtime

# Méthode 2: Logs récents
tail -20 scraping_realtime.log

# Méthode 3: Stats API
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool

# Méthode 4: Compter les nouveaux sites
sqlite3 scrap_email.db "SELECT COUNT(*) FROM sites WHERE created_at > datetime('now', '-1 hour');"
```

---

## ⚙️ Configuration (Optionnel)

**Fichier:** `scrape_realtime_complete.py`

### Vitesse
```python
PAUSE_BETWEEN_SITES = 0.1   # Plus petit = plus rapide (risque blocage)
PAUSE_BETWEEN_PAGES = 0.05
```

### Profondeur
```python
MAX_PAGES_PER_SELLER_SITE = 500  # Plus = plus de domaines trouvés
MAX_DEPTH = 5
```

---

## 🔥 Stats en Temps Réel

```bash
# Dashboard auto-refresh (toutes les 5 secondes)
watch -n 5 'curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"\"\"
Sites: {d[\"total_sites\"]}
Emails: {d[\"sites_with_email\"]} ({d[\"email_rate\"]}%)
SIRET: {d[\"sites_with_siret\"]} ({d[\"siret_rate\"]}%)
\"\"\")"'
```

---

## 📁 Fichiers Importants

- **Script**: `scrape_realtime_complete.py`
- **Logs**: `scraping_realtime.log`
- **Base**: `scrap_email.db`
- **Progression**: `explored_seller_sites.txt`
- **Sites vendeurs**: `site_urls.txt` (75,354 sites)

---

## ✅ Checklist de Vérification

- [ ] Script lancé en arrière-plan
- [ ] Logs qui défilent (tail -f)
- [ ] Nouveaux sites dans l'admin
- [ ] Stats qui augmentent
- [ ] Espace disque suffisant (df -h)

---

## 🎯 Commande Ultime (Tout-en-Un)

```bash
cd /var/www/Scrap_Email && \
nohup python3 scrape_realtime_complete.py > scraping_realtime.log 2>&1 & \
echo $! > scraping_realtime.pid && \
echo "✅ Scraping lancé! PID: $(cat scraping_realtime.pid)" && \
echo "📊 Admin: https://admin.perfect-cocon-seo.fr" && \
echo "📝 Logs: tail -f scraping_realtime.log" && \
sleep 2 && \
tail -f scraping_realtime.log
```

**Copy-paste cette commande et c'est parti!** 🚀

---

## 📞 Aide Rapide

### Problème: Pas de nouveaux sites

```bash
# Vérifier que le script tourne
ps aux | grep scrape_realtime

# Vérifier les erreurs
tail -50 scraping_realtime.log | grep -i error
```

### Problème: Trop lent

```bash
# Réduire les pauses (dans scrape_realtime_complete.py)
PAUSE_BETWEEN_SITES = 0.05
PAUSE_BETWEEN_PAGES = 0.02
```

### Problème: Espace disque plein

```bash
# Vérifier l'espace
df -h /var/www

# Nettoyer les vieux logs
rm scraping_realtime_*.log

# Compresser la base si nécessaire
sqlite3 scrap_email.db "VACUUM;"
```

---

**Vous êtes prêt! Lancez et regardez les millions de sites arriver!** 🎉
