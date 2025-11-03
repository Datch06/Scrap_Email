# 🔒 Installation HTTPS - admin.perfect-cocon-seo.fr

## Guide complet pour rendre l'interface accessible via HTTPS

---

## ✅ Prérequis

1. ✅ L'application Flask fonctionne (déjà fait !)
2. ✅ Base de données créée (déjà fait !)
3. 🔲 DNS configuré : `admin.perfect-cocon-seo.fr` → `217.182.141.69`
4. 🔲 Accès sudo au serveur

---

## 🚀 Installation en 2 commandes

### Étape 1 : Installer Nginx et configurer le reverse proxy

```bash
cd /var/www/Scrap_Email
sudo ./install_nginx.sh
```

Ce script va :
- ✅ Installer Nginx
- ✅ Créer la configuration pour admin.perfect-cocon-seo.fr
- ✅ Activer le site
- ✅ Installer SSL avec Let's Encrypt
- ✅ Configurer l'authentification (optionnel)

### Étape 2 : Installer le service systemd

```bash
sudo ./install_service.sh
```

Ce script va :
- ✅ Créer le service systemd
- ✅ Arrêter l'application Flask manuelle
- ✅ Démarrer l'application avec Gunicorn
- ✅ Activer le démarrage automatique

---

## 📋 Instructions détaillées

### 1. Vérifier le DNS

Avant de commencer, vérifiez que le DNS est configuré :

```bash
nslookup admin.perfect-cocon-seo.fr
```

Vous devriez voir l'IP : `217.182.141.69`

Si ce n'est pas le cas, configurez votre DNS chez votre registrar :

```
Type : A
Nom : admin
Valeur : 217.182.141.69
```

---

### 2. Installer Nginx

```bash
cd /var/www/Scrap_Email
sudo ./install_nginx.sh
```

Le script vous demandera :
1. **Installer SSL ?** → Répondez `o` (oui)
2. **Ajouter authentification ?** → Répondez `o` et choisissez un nom d'utilisateur et mot de passe

**Résultat** : Nginx sera configuré sur le port 80 (et 443 si SSL)

---

### 3. Installer le service systemd

```bash
sudo ./install_service.sh
```

**Résultat** : L'application tournera automatiquement avec Gunicorn

---

### 4. Tester l'installation

```bash
# Tester localement
curl http://127.0.0.1:5000

# Tester via Nginx (sans SSL)
curl http://admin.perfect-cocon-seo.fr

# Tester via Nginx (avec SSL)
curl https://admin.perfect-cocon-seo.fr
```

Ou ouvrez dans un navigateur : **https://admin.perfect-cocon-seo.fr**

---

## 🔧 Configuration manuelle (alternative)

Si vous préférez tout faire manuellement :

### 1. Installer Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### 2. Créer la configuration

```bash
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Collez :

```nginx
server {
    listen 80;
    server_name admin.perfect-cocon-seo.fr;

    access_log /var/log/nginx/scrap-email-access.log;
    error_log /var/log/nginx/scrap-email-error.log;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/Scrap_Email/static;
        expires 30d;
    }
}
```

### 3. Activer le site

```bash
sudo ln -s /etc/nginx/sites-available/admin.perfect-cocon-seo.fr /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Installer SSL

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

### 5. Créer le service systemd

```bash
sudo nano /etc/systemd/system/scrap-email-interface.service
```

Collez :

```ini
[Unit]
Description=Scrap Email Interface Web
After=network.target

[Service]
Type=simple
User=debian
Group=debian
WorkingDirectory=/var/www/Scrap_Email
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 --timeout 120 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6. Activer le service

```bash
# Arrêter l'application Flask manuelle
pkill -f "python3 app.py"

# Démarrer le service
sudo systemctl daemon-reload
sudo systemctl enable scrap-email-interface
sudo systemctl start scrap-email-interface
```

---

## 🔐 Ajouter l'authentification

### Créer un utilisateur

```bash
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

### Modifier la configuration Nginx

```bash
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Ajouter dans le bloc `location /` :

```nginx
auth_basic "Scrap Email Manager - Zone restreinte";
auth_basic_user_file /etc/nginx/.htpasswd;
```

### Redémarrer Nginx

```bash
sudo systemctl reload nginx
```

---

## 🎯 Résultat final

Après l'installation, votre interface sera accessible sur :

### **https://admin.perfect-cocon-seo.fr**

Avec :
- ✅ HTTPS (certificat SSL Let's Encrypt)
- ✅ Authentification HTTP Basic
- ✅ Démarrage automatique au boot
- ✅ 3 workers Gunicorn pour la performance
- ✅ Logs dans `/var/log/`

---

## 🔧 Gestion quotidienne

### Redémarrer l'application

```bash
sudo systemctl restart scrap-email-interface
```

### Voir les logs

```bash
# Logs de l'application
sudo journalctl -u scrap-email-interface -f

# Logs Nginx
sudo tail -f /var/log/nginx/scrap-email-error.log

# Logs applicatifs
sudo tail -f /var/log/scrap-email-error.log
```

### Voir le statut

```bash
sudo systemctl status scrap-email-interface
```

### Recharger Nginx

```bash
sudo systemctl reload nginx
```

---

## 🐛 Dépannage

### Nginx ne démarre pas

```bash
# Tester la configuration
sudo nginx -t

# Voir les logs
sudo tail -f /var/log/nginx/error.log
```

### L'application ne démarre pas

```bash
# Voir les logs du service
sudo journalctl -u scrap-email-interface -n 50

# Tester manuellement
cd /var/www/Scrap_Email
gunicorn --bind 127.0.0.1:5000 wsgi:app
```

### Erreur 502 Bad Gateway

Cela signifie que Nginx ne peut pas joindre l'application :

```bash
# Vérifier que le service tourne
sudo systemctl status scrap-email-interface

# Redémarrer
sudo systemctl restart scrap-email-interface

# Tester directement
curl http://127.0.0.1:5000
```

### Problème SSL

```bash
# Renouveler le certificat
sudo certbot renew

# Tester le certificat
sudo certbot certificates
```

---

## ✅ Checklist finale

- [ ] DNS configuré (admin.perfect-cocon-seo.fr → 217.182.141.69)
- [ ] Nginx installé et configuré
- [ ] SSL/HTTPS actif
- [ ] Service systemd créé et actif
- [ ] Authentification configurée
- [ ] Application accessible sur https://admin.perfect-cocon-seo.fr
- [ ] Logs vérifiés
- [ ] Démarrage automatique testé

---

## 📞 Commandes rapides

```bash
# Installation complète (2 commandes)
sudo ./install_nginx.sh
sudo ./install_service.sh

# Vérification
sudo systemctl status scrap-email-interface
sudo systemctl status nginx
curl https://admin.perfect-cocon-seo.fr

# Logs
sudo journalctl -u scrap-email-interface -f
```

---

## 🎉 C'est terminé !

Votre interface Scrap Email est maintenant accessible en HTTPS avec :
- Certificat SSL automatique
- Authentification sécurisée
- Démarrage automatique
- Logs centralisés

**Accédez à votre interface sur : https://admin.perfect-cocon-seo.fr** 🚀
