# 🚀 Déploiement Rapide - admin.perfect-cocon-seo.fr

## Installation automatique (Recommandé)

```bash
cd /var/www/Scrap_Email
sudo ./setup_production.sh
```

Le script vous demandera :
1. Quel serveur web utiliser (Nginx/Apache/Aucun)
2. Si vous voulez activer l'authentification
3. Si vous voulez installer SSL avec Let's Encrypt

**C'est tout ! L'interface sera accessible sur http://admin.perfect-cocon-seo.fr**

---

## Installation manuelle rapide

### Étape 1 : Installer Gunicorn

```bash
pip3 install gunicorn
```

### Étape 2 : Créer le service systemd

```bash
sudo nano /etc/systemd/system/scrap-email-interface.service
```

Coller :

```ini
[Unit]
Description=Scrap Email Interface Web
After=network.target

[Service]
Type=simple
User=debian
Group=debian
WorkingDirectory=/var/www/Scrap_Email
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activer :

```bash
sudo systemctl daemon-reload
sudo systemctl enable scrap-email-interface
sudo systemctl start scrap-email-interface
```

### Étape 3 : Installer et configurer Nginx

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Coller :

```nginx
server {
    listen 80;
    server_name admin.perfect-cocon-seo.fr;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer :

```bash
sudo ln -s /etc/nginx/sites-available/admin.perfect-cocon-seo.fr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Étape 4 : Installer SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

### Étape 5 : Ajouter une authentification

```bash
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

Éditer la config Nginx :

```bash
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Ajouter dans `location /` :

```nginx
auth_basic "Zone restreinte";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Redémarrer :

```bash
sudo systemctl restart nginx
```

---

## ✅ Vérification

### Tester localement

```bash
curl http://127.0.0.1:5000
```

### Tester via le domaine

```bash
curl http://admin.perfect-cocon-seo.fr
```

Ou ouvrir dans un navigateur : **http://admin.perfect-cocon-seo.fr**

---

## 🔧 Commandes utiles

### Voir les logs de l'application

```bash
sudo journalctl -u scrap-email-interface -f
```

### Redémarrer l'application

```bash
sudo systemctl restart scrap-email-interface
```

### Voir le statut

```bash
sudo systemctl status scrap-email-interface
```

### Logs Nginx

```bash
sudo tail -f /var/log/nginx/scrap-email-error.log
sudo tail -f /var/log/nginx/scrap-email-access.log
```

---

## 🐛 Dépannage rapide

### L'application ne démarre pas

```bash
# Tester manuellement
cd /var/www/Scrap_Email
python3 app.py

# Voir les erreurs
sudo journalctl -u scrap-email-interface -n 50
```

### Le domaine n'est pas accessible

```bash
# Vérifier le DNS
nslookup admin.perfect-cocon-seo.fr

# Vérifier Nginx
sudo nginx -t
sudo systemctl status nginx

# Vérifier le pare-feu
sudo ufw status
sudo ufw allow 80
sudo ufw allow 443
```

### Erreur 502 Bad Gateway

```bash
# Vérifier que l'application tourne
sudo systemctl status scrap-email-interface

# Redémarrer
sudo systemctl restart scrap-email-interface
sudo systemctl restart nginx
```

---

## 🎯 Résumé

**Installation automatique** : `sudo ./setup_production.sh`

**Accès** : http://admin.perfect-cocon-seo.fr (ou https:// si SSL activé)

**Logs** : `sudo journalctl -u scrap-email-interface -f`

**Documentation complète** : Voir `DEPLOYMENT.md`

---

C'est tout ! Votre interface est maintenant en production ! 🎉
