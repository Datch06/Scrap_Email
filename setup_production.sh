#!/bin/bash

# Script d'installation automatique pour admin.perfect-cocon-seo.fr

set -e  # Arrêter en cas d'erreur

clear
echo "========================================================================"
echo "     INSTALLATION SCRAP EMAIL INTERFACE - admin.perfect-cocon-seo.fr"
echo "========================================================================"
echo ""

# Vérifier si on est root ou avec sudo
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Ce script doit être exécuté avec sudo"
    echo "Usage: sudo ./setup_production.sh"
    exit 1
fi

INSTALL_DIR="/var/www/Scrap_Email"
DOMAIN="admin.perfect-cocon-seo.fr"

echo "📋 Configuration :"
echo "   Domaine : $DOMAIN"
echo "   Dossier : $INSTALL_DIR"
echo ""

# Menu de choix
echo "Quel serveur web voulez-vous utiliser ?"
echo "1) Nginx (Recommandé)"
echo "2) Apache"
echo "3) Aucun (seulement Flask avec Gunicorn)"
read -p "Votre choix [1-3] : " WEBSERVER_CHOICE

echo ""
echo "========================================================================"
echo "ÉTAPE 1/6 : Installation des dépendances Python"
echo "========================================================================"

pip3 install sqlalchemy flask flask-cors gunicorn

echo "✅ Dépendances Python installées"

echo ""
echo "========================================================================"
echo "ÉTAPE 2/6 : Création du service systemd"
echo "========================================================================"

# Créer le service avec Gunicorn
cat > /etc/systemd/system/scrap-email-interface.service << EOF
[Unit]
Description=Scrap Email Interface Web
After=network.target

[Service]
Type=simple
User=debian
Group=debian
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 --timeout 120 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable scrap-email-interface
systemctl start scrap-email-interface

echo "✅ Service systemd créé et démarré"

# Vérifier que le service tourne
sleep 2
if systemctl is-active --quiet scrap-email-interface; then
    echo "✅ Le service est actif"
else
    echo "❌ Erreur : Le service n'a pas démarré"
    systemctl status scrap-email-interface
    exit 1
fi

echo ""
echo "========================================================================"
echo "ÉTAPE 3/6 : Configuration du serveur web"
echo "========================================================================"

if [ "$WEBSERVER_CHOICE" == "1" ]; then
    echo "Installation de Nginx..."
    apt update
    apt install -y nginx

    # Créer la configuration Nginx
    cat > /etc/nginx/sites-available/$DOMAIN << 'EOF'
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

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static {
        alias /var/www/Scrap_Email/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Activer le site
    ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    # Tester et redémarrer Nginx
    nginx -t
    systemctl restart nginx
    echo "✅ Nginx configuré et redémarré"

elif [ "$WEBSERVER_CHOICE" == "2" ]; then
    echo "Installation d'Apache..."
    apt update
    apt install -y apache2

    # Activer les modules
    a2enmod proxy
    a2enmod proxy_http
    a2enmod headers

    # Créer la configuration Apache
    cat > /etc/apache2/sites-available/$DOMAIN.conf << 'EOF'
<VirtualHost *:80>
    ServerName admin.perfect-cocon-seo.fr
    ServerAdmin webmaster@perfect-cocon-seo.fr

    ErrorLog ${APACHE_LOG_DIR}/scrap-email-error.log
    CustomLog ${APACHE_LOG_DIR}/scrap-email-access.log combined

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    RequestHeader set X-Forwarded-Proto "http"
    RequestHeader set X-Forwarded-Port "80"
</VirtualHost>
EOF

    # Activer le site
    a2ensite $DOMAIN.conf
    a2dissite 000-default.conf

    # Redémarrer Apache
    systemctl restart apache2
    echo "✅ Apache configuré et redémarré"

else
    echo "⏭️  Pas de serveur web configuré (accès direct via Gunicorn)"
fi

echo ""
echo "========================================================================"
echo "ÉTAPE 4/6 : Configuration du pare-feu"
echo "========================================================================"

if command -v ufw &> /dev/null; then
    echo "Configuration UFW..."
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "✅ Ports 80 et 443 ouverts"
else
    echo "⚠️  UFW non installé, configuration du pare-feu à faire manuellement"
fi

echo ""
echo "========================================================================"
echo "ÉTAPE 5/6 : Configuration de l'authentification"
echo "========================================================================"

read -p "Voulez-vous activer l'authentification HTTP Basic ? (o/n) : " AUTH_CHOICE

if [ "$AUTH_CHOICE" == "o" ] || [ "$AUTH_CHOICE" == "O" ]; then
    apt install -y apache2-utils

    read -p "Nom d'utilisateur : " USERNAME

    if [ "$WEBSERVER_CHOICE" == "1" ]; then
        # Nginx
        htpasswd -c /etc/nginx/.htpasswd "$USERNAME"

        # Ajouter l'auth dans la config
        sed -i '/location \/ {/a \        auth_basic "Scrap Email Manager - Zone restreinte";\n        auth_basic_user_file /etc/nginx/.htpasswd;' /etc/nginx/sites-available/$DOMAIN

        systemctl restart nginx
        echo "✅ Authentification configurée pour Nginx"

    elif [ "$WEBSERVER_CHOICE" == "2" ]; then
        # Apache
        htpasswd -c /etc/apache2/.htpasswd "$USERNAME"

        # Ajouter l'auth dans la config
        sed -i '/<VirtualHost/a \    <Location />\n        AuthType Basic\n        AuthName "Scrap Email Manager - Zone restreinte"\n        AuthUserFile /etc/apache2/.htpasswd\n        Require valid-user\n    </Location>' /etc/apache2/sites-available/$DOMAIN.conf

        systemctl restart apache2
        echo "✅ Authentification configurée pour Apache"
    fi
else
    echo "⏭️  Authentification non configurée"
fi

echo ""
echo "========================================================================"
echo "ÉTAPE 6/6 : Installation de Let's Encrypt (HTTPS)"
echo "========================================================================"

read -p "Voulez-vous installer un certificat SSL avec Let's Encrypt ? (o/n) : " SSL_CHOICE

if [ "$SSL_CHOICE" == "o" ] || [ "$SSL_CHOICE" == "O" ]; then
    if [ "$WEBSERVER_CHOICE" == "1" ]; then
        apt install -y certbot python3-certbot-nginx
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email webmaster@perfect-cocon-seo.fr
        echo "✅ Certificat SSL installé pour Nginx"

    elif [ "$WEBSERVER_CHOICE" == "2" ]; then
        apt install -y certbot python3-certbot-apache
        certbot --apache -d $DOMAIN --non-interactive --agree-tos --email webmaster@perfect-cocon-seo.fr
        echo "✅ Certificat SSL installé pour Apache"
    fi
else
    echo "⏭️  SSL non configuré (vous pourrez le faire plus tard)"
fi

echo ""
echo "========================================================================"
echo "                          ✅ INSTALLATION TERMINÉE !"
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
echo "📊 Commandes utiles :"
echo "   • Voir les logs : sudo journalctl -u scrap-email-interface -f"
echo "   • Redémarrer : sudo systemctl restart scrap-email-interface"
echo "   • Statut : sudo systemctl status scrap-email-interface"
echo ""

if [ "$WEBSERVER_CHOICE" == "1" ]; then
    echo "   • Logs Nginx : sudo tail -f /var/log/nginx/scrap-email-error.log"
elif [ "$WEBSERVER_CHOICE" == "2" ]; then
    echo "   • Logs Apache : sudo tail -f /var/log/apache2/scrap-email-error.log"
fi

echo ""
echo "📚 Documentation complète : $INSTALL_DIR/DEPLOYMENT.md"
echo "========================================================================"
