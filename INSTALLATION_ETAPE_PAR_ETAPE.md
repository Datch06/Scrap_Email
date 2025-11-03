# Installation Étape par Étape

Si le script automatique ne fonctionne pas, suivez ces étapes manuellement :

## Étape 1 : Installer Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

## Étape 2 : Créer la configuration Nginx

```bash
sudo nano /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
```

Collez ce contenu :

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

Sauvegardez : `Ctrl+O`, `Entrée`, `Ctrl+X`

## Étape 3 : Activer le site

```bash
sudo ln -s /etc/nginx/sites-available/admin.perfect-cocon-seo.fr /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## Étape 4 : Arrêter Flask manuel

```bash
pkill -f "python3 app.py"
```

## Étape 5 : Créer le service systemd

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

Sauvegardez : `Ctrl+O`, `Entrée`, `Ctrl+X`

## Étape 6 : Démarrer le service

```bash
sudo systemctl daemon-reload
sudo systemctl enable scrap-email-interface
sudo systemctl start scrap-email-interface
sudo systemctl status scrap-email-interface
```

## Étape 7 : Installer SSL

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d admin.perfect-cocon-seo.fr
```

## Étape 8 : Tester

Ouvrez : https://admin.perfect-cocon-seo.fr

---

## Vérifications

```bash
# Nginx actif ?
sudo systemctl status nginx

# Service actif ?
sudo systemctl status scrap-email-interface

# Application répond ?
curl http://127.0.0.1:5000/api/stats

# Via Nginx ?
curl http://admin.perfect-cocon-seo.fr
```
