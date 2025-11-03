#!/bin/bash

# Script d'installation Nginx pour admin.perfect-cocon-seo.fr
# À exécuter avec sudo

set -e

DOMAIN="admin.perfect-cocon-seo.fr"
APP_DIR="/var/www/Scrap_Email"
APP_PORT="5000"
EMAIL="webmaster@perfect-cocon-seo.fr"

echo "========================================================================"
echo "   INSTALLATION NGINX POUR admin.perfect-cocon-seo.fr"
echo "========================================================================"
echo ""

# Vérifier sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté avec sudo"
    echo "Usage: sudo ./install_nginx.sh"
    exit 1
fi

echo "📦 Installation de Nginx..."
apt update
apt install -y nginx

echo "✅ Nginx installé"
echo ""

echo "🔧 Configuration de Nginx pour $DOMAIN..."

# Créer la configuration Nginx
cat > /etc/nginx/sites-available/$DOMAIN << 'NGINXCONF'
server {
    listen 80;
    server_name admin.perfect-cocon-seo.fr;

    access_log /var/log/nginx/scrap-email-access.log;
    error_log /var/log/nginx/scrap-email-error.log;

    # Taille max des requêtes
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support (si nécessaire plus tard)
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
NGINXCONF

echo "✅ Configuration Nginx créée"
echo ""

# Activer le site
echo "🔗 Activation du site..."
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Tester la configuration
echo "🧪 Test de la configuration Nginx..."
nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuration valide"
else
    echo "❌ Erreur dans la configuration Nginx"
    exit 1
fi

# Redémarrer Nginx
echo "🔄 Redémarrage de Nginx..."
systemctl restart nginx
systemctl enable nginx

echo "✅ Nginx configuré et actif"
echo ""

echo "========================================================================"
echo "   INSTALLATION SSL AVEC LET'S ENCRYPT"
echo "========================================================================"
echo ""

read -p "Voulez-vous installer SSL maintenant ? (o/n) : " SSL_CHOICE

if [ "$SSL_CHOICE" == "o" ] || [ "$SSL_CHOICE" == "O" ]; then
    echo "📦 Installation de Certbot..."
    apt install -y certbot python3-certbot-nginx

    echo "🔐 Installation du certificat SSL..."
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

    if [ $? -eq 0 ]; then
        echo "✅ SSL installé avec succès !"
        echo "   Interface accessible sur : https://$DOMAIN"
    else
        echo "⚠️  Erreur lors de l'installation SSL"
        echo "   Vous pouvez le faire manuellement : sudo certbot --nginx -d $DOMAIN"
    fi
else
    echo "⏭️  SSL non installé"
    echo "   Interface accessible sur : http://$DOMAIN"
fi

echo ""
echo "========================================================================"
echo "   CONFIGURATION DE L'AUTHENTIFICATION"
echo "========================================================================"
echo ""

read -p "Voulez-vous ajouter une authentification ? (o/n) : " AUTH_CHOICE

if [ "$AUTH_CHOICE" == "o" ] || [ "$AUTH_CHOICE" == "O" ]; then
    apt install -y apache2-utils

    read -p "Nom d'utilisateur : " USERNAME

    htpasswd -c /etc/nginx/.htpasswd "$USERNAME"

    # Ajouter auth dans la config
    sed -i '/location \/ {/a \        auth_basic "Scrap Email Manager - Zone restreinte";\n        auth_basic_user_file /etc/nginx/.htpasswd;' /etc/nginx/sites-available/$DOMAIN

    systemctl reload nginx

    echo "✅ Authentification configurée"
else
    echo "⏭️  Authentification non configurée"
fi

echo ""
echo "========================================================================"
echo "   ✅ INSTALLATION TERMINÉE !"
echo "========================================================================"
echo ""
echo "🎉 Votre interface est maintenant accessible :"
echo ""

if [ "$SSL_CHOICE" == "o" ] || [ "$SSL_CHOICE" == "O" ]; then
    echo "   🔒 https://$DOMAIN"
else
    echo "   🌐 http://$DOMAIN"
fi

echo ""
echo "📊 Vérifications :"
echo "   • Nginx actif : $(systemctl is-active nginx)"
echo "   • Configuration : /etc/nginx/sites-available/$DOMAIN"
echo ""
echo "🔧 Commandes utiles :"
echo "   • Redémarrer Nginx : sudo systemctl restart nginx"
echo "   • Logs Nginx : sudo tail -f /var/log/nginx/scrap-email-error.log"
echo "   • Test config : sudo nginx -t"
echo ""
echo "📚 Prochaine étape : Configurer le service systemd pour l'application"
echo "   → Exécuter : sudo ./install_service.sh"
echo ""
echo "========================================================================"
