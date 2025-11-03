# 🌐 Déploiement sur admin.perfect-cocon-seo.fr

## ✅ Fichiers créés pour le déploiement

Tous les fichiers nécessaires ont été créés dans `/var/www/Scrap_Email/` :

### Configuration
- ✅ **app.py** - Modifié pour supporter les variables d'environnement
- ✅ **wsgi.py** - Point d'entrée WSGI pour Gunicorn
- ✅ **scrap-email-interface.service** - Service systemd

### Configuration serveur web
- ✅ **nginx_config.conf** - Configuration Nginx prête à l'emploi
- ✅ **apache_config.conf** - Configuration Apache prête à l'emploi

### Scripts
- ✅ **setup_production.sh** - Installation automatique complète
- ✅ **start_interface.sh** - Script de démarrage simple

### Documentation
- ✅ **DEPLOYMENT.md** - Documentation complète du déploiement
- ✅ **DEPLOIEMENT_RAPIDE.md** - Guide rapide en français
- ✅ **README_DEPLOYMENT.md** - Ce fichier

---

## 🚀 Installation - 3 options

### Option 1 : Installation automatique (RECOMMANDÉ)

```bash
cd /var/www/Scrap_Email
sudo ./setup_production.sh
```

Le script vous guide à travers toutes les étapes :
- Installation de Gunicorn
- Création du service systemd
- Configuration de Nginx ou Apache
- Configuration du pare-feu
- Authentification HTTP Basic
- SSL avec Let's Encrypt

**Temps estimé : 5-10 minutes**

---

### Option 2 : Installation manuelle rapide

```bash
# 1. Installer Gunicorn
pip3 install gunicorn

# 2. Copier et activer le service
sudo cp scrap-email-interface.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scrap-email-interface
sudo systemctl start scrap-email-interface

# 3. Installer Nginx
sudo apt install nginx

# 4. Copier la configuration
sudo cp nginx_config.conf /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
sudo ln -s /etc/nginx/sites-available/admin.perfect-cocon-seo.fr /etc/nginx/sites-enabled/

# 5. Redémarrer Nginx
sudo nginx -t
sudo systemctl restart nginx

# 6. Installer SSL
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

**Temps estimé : 15 minutes**

---

### Option 3 : Test en local d'abord

Si vous voulez d'abord tester localement avant le déploiement :

```bash
cd /var/www/Scrap_Email
./start_interface.sh
```

Puis accédez à : **http://localhost:5000**

---

## 🔐 Sécurité

### Authentification HTTP Basic

Pour protéger l'accès à l'interface :

```bash
# Créer un utilisateur
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd votre_username

# Éditer la config Nginx
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Ajouter dans le bloc `location /` :

```nginx
auth_basic "Scrap Email Manager - Zone restreinte";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Redémarrer Nginx :

```bash
sudo systemctl restart nginx
```

### HTTPS avec Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

Let's Encrypt configure automatiquement :
- Le certificat SSL
- La redirection HTTP → HTTPS
- Le renouvellement automatique

---

## 📊 Architecture

```
Internet
   ↓
[Nginx/Apache] (Port 80/443)
   ↓
[Gunicorn] (127.0.0.1:5000) - 3 workers
   ↓
[Flask App] (app.py)
   ↓
[SQLite Database] (scrap_email.db)
```

### Avantages de cette architecture

- **Nginx/Apache** : Gère SSL, fichiers statiques, et sert de reverse proxy
- **Gunicorn** : Serveur WSGI performant avec plusieurs workers
- **Flask** : Application web légère et rapide
- **SQLite** : Base de données simple et fiable

---

## 🎯 URLs et accès

### Développement (local)
```
http://localhost:5000
```

### Production
```
http://admin.perfect-cocon-seo.fr  (HTTP)
https://admin.perfect-cocon-seo.fr (HTTPS - après Let's Encrypt)
```

### Pages disponibles
- `/` - Dashboard
- `/sites` - Gestion des sites
- `/jobs` - Suivi des jobs
- `/api/stats` - API statistiques
- `/api/sites` - API sites
- `/api/export/csv` - Export CSV

---

## 🔧 Gestion quotidienne

### Démarrer/Arrêter/Redémarrer

```bash
sudo systemctl start scrap-email-interface
sudo systemctl stop scrap-email-interface
sudo systemctl restart scrap-email-interface
```

### Voir les logs

```bash
# Logs de l'application
sudo journalctl -u scrap-email-interface -f

# Logs Nginx
sudo tail -f /var/log/nginx/scrap-email-error.log

# Dernières 100 lignes
sudo journalctl -u scrap-email-interface -n 100
```

### Vérifier le statut

```bash
sudo systemctl status scrap-email-interface
```

### Recharger la configuration

Après avoir modifié `app.py` ou d'autres fichiers :

```bash
sudo systemctl restart scrap-email-interface
```

---

## 📈 Performance

### Configuration actuelle
- **3 workers Gunicorn** - Peut gérer ~30-60 requêtes simultanées
- **Timeout : 120s** - Pour les requêtes longues

### Augmenter les performances

Éditer `/etc/systemd/system/scrap-email-interface.service` :

```ini
ExecStart=/usr/local/bin/gunicorn --workers 5 --timeout 180 --bind 127.0.0.1:5000 wsgi:app
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl restart scrap-email-interface
```

**Règle générale** : `workers = (2 × nombre_de_CPU) + 1`

---

## 💾 Sauvegarde

### Base de données

```bash
# Sauvegarde manuelle
cp /var/www/Scrap_Email/scrap_email.db /var/www/Scrap_Email/backups/scrap_email_$(date +%Y%m%d).db

# Sauvegarde automatique (cron)
sudo crontab -e
```

Ajouter :

```cron
# Sauvegarde quotidienne à 2h du matin
0 2 * * * cp /var/www/Scrap_Email/scrap_email.db /var/www/Scrap_Email/backups/scrap_email_$(date +\%Y\%m\%d).db
```

### Restauration

```bash
sudo systemctl stop scrap-email-interface
cp /var/www/Scrap_Email/backups/scrap_email_20251017.db /var/www/Scrap_Email/scrap_email.db
sudo systemctl start scrap-email-interface
```

---

## 🐛 Dépannage

### L'interface n'est pas accessible

1. **Vérifier que le service tourne**
   ```bash
   sudo systemctl status scrap-email-interface
   ```

2. **Vérifier les logs**
   ```bash
   sudo journalctl -u scrap-email-interface -n 50
   ```

3. **Tester l'application directement**
   ```bash
   curl http://127.0.0.1:5000
   ```

4. **Vérifier Nginx**
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

5. **Vérifier le DNS**
   ```bash
   nslookup admin.perfect-cocon-seo.fr
   ```

6. **Vérifier le pare-feu**
   ```bash
   sudo ufw status
   ```

### Erreur 502 Bad Gateway

Cela signifie que Nginx ne peut pas joindre l'application :

```bash
# Vérifier que l'app tourne
sudo systemctl status scrap-email-interface

# Redémarrer l'app
sudo systemctl restart scrap-email-interface

# Vérifier les logs
sudo journalctl -u scrap-email-interface -f
```

### Base de données verrouillée

Si vous voyez "database is locked" :

```bash
# Vérifier les processus qui utilisent la DB
lsof /var/www/Scrap_Email/scrap_email.db

# Redémarrer l'application
sudo systemctl restart scrap-email-interface
```

---

## 📚 Documentation

- **Guide complet** : `DEPLOYMENT.md`
- **Guide rapide** : `DEPLOIEMENT_RAPIDE.md`
- **Documentation interface** : `README_INTERFACE.md`
- **Démarrage rapide** : `QUICKSTART.md`

---

## ✅ Checklist de déploiement

- [ ] DNS configuré pour admin.perfect-cocon-seo.fr
- [ ] Dépendances Python installées
- [ ] Base de données créée
- [ ] Service systemd configuré et actif
- [ ] Nginx/Apache installé et configuré
- [ ] Pare-feu ouvert (ports 80 et 443)
- [ ] SSL/HTTPS configuré
- [ ] Authentification activée
- [ ] Sauvegarde automatique configurée
- [ ] Tests de l'interface réussis

---

## 🎉 Prêt à déployer !

**Commande magique** :

```bash
sudo ./setup_production.sh
```

Puis ouvrez : **https://admin.perfect-cocon-seo.fr**

Pour toute question, consultez `DEPLOYMENT.md` ou les logs :

```bash
sudo journalctl -u scrap-email-interface -f
```

**Bon déploiement ! 🚀**
