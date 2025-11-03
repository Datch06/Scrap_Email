# Guide de Déploiement - admin.perfect-cocon-seo.fr

## 📋 Prérequis

1. Nom de domaine configuré : `admin.perfect-cocon-seo.fr` pointant vers votre serveur
2. Accès root ou sudo sur le serveur
3. Python 3 installé

---

## 🚀 Installation complète

### Étape 1 : Installer les dépendances Python

```bash
cd /var/www/Scrap_Email
pip3 install sqlalchemy flask flask-cors gunicorn
```

### Étape 2 : Initialiser la base de données

```bash
python3 database.py
```

### Étape 3 : Importer les données existantes (optionnel)

```bash
python3 import_existing_data.py
```

---

## 🔧 Option A : Déploiement avec Gunicorn (Recommandé)

### 1. Installer Gunicorn

```bash
pip3 install gunicorn
```

### 2. Tester Gunicorn

```bash
cd /var/www/Scrap_Email
gunicorn --bind 127.0.0.1:5000 wsgi:app
```

### 3. Créer le service systemd

```bash
sudo cp scrap-email-interface.service /etc/systemd/system/
```

Modifier le fichier pour utiliser Gunicorn :

```bash
sudo nano /etc/systemd/system/scrap-email-interface.service
```

Remplacer la ligne `ExecStart` par :

```ini
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 wsgi:app
```

### 4. Activer et démarrer le service

```bash
sudo systemctl daemon-reload
sudo systemctl enable scrap-email-interface
sudo systemctl start scrap-email-interface
sudo systemctl status scrap-email-interface
```

---

## 🌐 Option B : Configuration du serveur web

### Avec Nginx (Recommandé)

#### 1. Installer Nginx

```bash
sudo apt update
sudo apt install nginx
```

#### 2. Copier la configuration

```bash
sudo cp nginx_config.conf /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
sudo ln -s /etc/nginx/sites-available/admin.perfect-cocon-seo.fr /etc/nginx/sites-enabled/
```

#### 3. Tester et redémarrer Nginx

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### Avec Apache

#### 1. Installer Apache et modules

```bash
sudo apt update
sudo apt install apache2
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
```

#### 2. Copier la configuration

```bash
sudo cp apache_config.conf /etc/apache2/sites-available/admin.perfect-cocon-seo.fr.conf
sudo a2ensite admin.perfect-cocon-seo.fr.conf
```

#### 3. Redémarrer Apache

```bash
sudo systemctl restart apache2
```

---

## 🔒 Activer HTTPS avec Let's Encrypt

### Avec Nginx

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

### Avec Apache

```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d admin.perfect-cocon-seo.fr
```

Let's Encrypt configurera automatiquement HTTPS et les redirections.

---

## 🔐 Ajouter une authentification

Pour sécuriser l'accès à l'interface, ajoutez une authentification HTTP Basic :

### Avec Nginx

```bash
# Installer apache2-utils pour htpasswd
sudo apt install apache2-utils

# Créer le fichier de mots de passe
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Éditer la configuration Nginx
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Ajouter dans le bloc `location /` :

```nginx
auth_basic "Scrap Email Manager - Zone restreinte";
auth_basic_user_file /etc/nginx/.htpasswd;
```

```bash
# Redémarrer Nginx
sudo systemctl restart nginx
```

### Avec Apache

```bash
# Créer le fichier de mots de passe
sudo htpasswd -c /etc/apache2/.htpasswd admin

# Éditer la configuration Apache
sudo nano /etc/apache2/sites-available/admin.perfect-cocon-seo.fr.conf
```

Ajouter dans le VirtualHost :

```apache
<Location />
    AuthType Basic
    AuthName "Scrap Email Manager - Zone restreinte"
    AuthUserFile /etc/apache2/.htpasswd
    Require valid-user
</Location>
```

```bash
# Redémarrer Apache
sudo systemctl restart apache2
```

---

## 🔍 Vérification et tests

### 1. Vérifier que le service tourne

```bash
sudo systemctl status scrap-email-interface
```

### 2. Vérifier que l'application répond

```bash
curl http://127.0.0.1:5000
```

### 3. Vérifier via le domaine

Ouvrir dans un navigateur : **http://admin.perfect-cocon-seo.fr**

---

## 📊 Gestion du service

### Démarrer

```bash
sudo systemctl start scrap-email-interface
```

### Arrêter

```bash
sudo systemctl stop scrap-email-interface
```

### Redémarrer

```bash
sudo systemctl restart scrap-email-interface
```

### Voir les logs

```bash
sudo journalctl -u scrap-email-interface -f
```

---

## 🐛 Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u scrap-email-interface -n 50

# Vérifier les permissions
ls -la /var/www/Scrap_Email/scrap_email.db

# Tester manuellement
cd /var/www/Scrap_Email
python3 app.py
```

### Nginx ou Apache ne démarre pas

```bash
# Nginx
sudo nginx -t
sudo journalctl -u nginx -n 50

# Apache
sudo apache2ctl configtest
sudo journalctl -u apache2 -n 50
```

### L'interface n'est pas accessible

1. Vérifier que le DNS pointe vers le serveur
   ```bash
   nslookup admin.perfect-cocon-seo.fr
   ```

2. Vérifier que le pare-feu autorise le port 80/443
   ```bash
   sudo ufw status
   sudo ufw allow 80
   sudo ufw allow 443
   ```

3. Vérifier les logs du serveur web
   ```bash
   # Nginx
   sudo tail -f /var/log/nginx/scrap-email-error.log

   # Apache
   sudo tail -f /var/log/apache2/scrap-email-error.log
   ```

---

## 📝 Configuration avancée

### Augmenter le nombre de workers Gunicorn

Éditer `/etc/systemd/system/scrap-email-interface.service` :

```ini
ExecStart=/usr/local/bin/gunicorn --workers 5 --bind 127.0.0.1:5000 wsgi:app
```

### Ajouter un timeout plus long

```ini
ExecStart=/usr/local/bin/gunicorn --workers 3 --timeout 120 --bind 127.0.0.1:5000 wsgi:app
```

### Logs de Gunicorn

```ini
ExecStart=/usr/local/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:5000 \
    --access-logfile /var/log/scrap-email-access.log \
    --error-logfile /var/log/scrap-email-error.log \
    wsgi:app
```

---

## ✅ Checklist de déploiement

- [ ] Dépendances Python installées
- [ ] Base de données créée et testée
- [ ] Gunicorn installé et testé
- [ ] Service systemd créé et activé
- [ ] Nginx/Apache installé et configuré
- [ ] DNS configuré pour admin.perfect-cocon-seo.fr
- [ ] Pare-feu configuré (ports 80 et 443)
- [ ] HTTPS activé avec Let's Encrypt
- [ ] Authentification HTTP Basic configurée
- [ ] Tests de l'interface réussis
- [ ] Sauvegarde de la base de données planifiée

---

## 🎉 Déploiement terminé !

Votre interface est maintenant accessible sur : **https://admin.perfect-cocon-seo.fr**

Pour toute question, consultez les logs :
```bash
sudo journalctl -u scrap-email-interface -f
```
