#!/bin/bash

# Script d'installation FINAL pour admin.perfect-cocon-seo.fr
# Le DNS fonctionne maintenant !

set -e

echo "========================================================================"
echo "   INSTALLATION FINALE - admin.perfect-cocon-seo.fr"
echo "========================================================================"
echo ""

# Vérifier sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté avec sudo"
    echo "Usage: sudo bash INSTALLATION_MAINTENANT.sh"
    exit 1
fi

DOMAIN="admin.perfect-cocon-seo.fr"
APP_DIR="/var/www/Scrap_Email"

echo "🔍 Vérification du DNS..."
DNS_IP=$(dig +short $DOMAIN @8.8.8.8 | head -1)
echo "   DNS pointe vers: $DNS_IP"

if [ "$DNS_IP" != "217.182.141.69" ]; then
    echo "⚠️  Attention: Le DNS ne pointe pas encore complètement vers 217.182.141.69"
    echo "   Propagation en cours... On continue quand même."
fi

echo ""
echo "📦 ÉTAPE 1/5 : Installation de Nginx..."
apt update > /dev/null 2>&1
apt install -y nginx > /dev/null 2>&1
echo "✅ Nginx installé"

echo ""
echo "🔧 ÉTAPE 2/5 : Configuration de Nginx..."
cat > /etc/nginx/sites-available/$DOMAIN << 'NGINXEOF'
server {
    listen 80;
    server_name admin.perfect-cocon-seo.fr;

    access_log /var/log/nginx/scrap-email-access.log;
    error_log /var/log/nginx/scrap-email-error.log;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /var/www/Scrap_Email/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINXEOF

# Activer le site
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Tester la configuration
nginx -t
systemctl restart nginx
systemctl enable nginx

echo "✅ Nginx configuré"

echo ""
echo "🛑 ÉTAPE 3/5 : Arrêt de l'application Flask manuelle..."
pkill -f "FLASK_HOST=0.0.0.0.*python3 app.py" || true
pkill -f "python3 app.py" || true
sleep 2
echo "✅ Application Flask arrêtée"

echo ""
echo "🔧 ÉTAPE 4/5 : Création du service systemd..."
cat > /etc/systemd/system/scrap-email-interface.service << 'SERVICEEOF'
[Unit]
Description=Scrap Email Interface Web
After=network.target

[Service]
Type=simple
User=debian
Group=debian
WorkingDirectory=/var/www/Scrap_Email
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 --timeout 120 --access-logfile /var/log/scrap-email-access.log --error-logfile /var/log/scrap-email-error.log wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Créer les logs
touch /var/log/scrap-email-access.log
touch /var/log/scrap-email-error.log
chown debian:debian /var/log/scrap-email-*.log

# Démarrer le service
systemctl daemon-reload
systemctl enable scrap-email-interface
systemctl start scrap-email-interface

sleep 3

# Vérifier que ça tourne
if systemctl is-active --quiet scrap-email-interface; then
    echo "✅ Service systemd actif"
else
    echo "❌ Erreur: Le service n'a pas démarré"
    journalctl -u scrap-email-interface -n 20 --no-pager
    exit 1
fi

echo ""
echo "🔐 ÉTAPE 5/5 : Installation SSL avec Let's Encrypt..."
apt install -y certbot python3-certbot-nginx > /dev/null 2>&1

echo ""
echo "⏳ Installation du certificat SSL..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email webmaster@perfect-cocon-seo.fr --redirect

if [ $? -eq 0 ]; then
    echo "✅ SSL installé avec succès !"
else
    echo "⚠️  SSL non installé (le DNS doit se propager complètement)"
    echo "   Vous pourrez l'installer plus tard avec :"
    echo "   sudo certbot --nginx -d $DOMAIN"
fi

echo ""
echo "========================================================================"
echo "   ✅ INSTALLATION TERMINÉE !"
echo "========================================================================"
echo ""
echo "🎉 Votre interface est maintenant accessible sur :"
echo ""

if systemctl is-active --quiet certbot.timer 2>/dev/null; then
    echo "   🔒 https://$DOMAIN"
else
    echo "   🌐 http://$DOMAIN (HTTPS à installer manuellement)"
fi

echo ""
echo "📊 Statut des services :"
echo "   • Nginx : $(systemctl is-active nginx)"
echo "   • Application : $(systemctl is-active scrap-email-interface)"
echo ""
echo "🔧 Commandes utiles :"
echo "   • Logs app : sudo journalctl -u scrap-email-interface -f"
echo "   • Logs Nginx : sudo tail -f /var/log/nginx/scrap-email-error.log"
echo "   • Redémarrer : sudo systemctl restart scrap-email-interface"
echo ""
echo "🧪 Test :"
echo "   curl http://127.0.0.1:5000/api/stats"
echo "   curl https://$DOMAIN"
echo ""
echo "========================================================================"
