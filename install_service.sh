#!/bin/bash

# Script d'installation du service systemd
# À exécuter avec sudo

set -e

APP_DIR="/var/www/Scrap_Email"
SERVICE_NAME="scrap-email-interface"
USER="debian"

echo "========================================================================"
echo "   INSTALLATION SERVICE SYSTEMD"
echo "========================================================================"
echo ""

# Vérifier sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté avec sudo"
    echo "Usage: sudo ./install_service.sh"
    exit 1
fi

echo "🔧 Création du service systemd..."

# Créer le fichier service
cat > /etc/systemd/system/$SERVICE_NAME.service << SERVICEEOF
[Unit]
Description=Scrap Email Interface Web
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 --timeout 120 --access-logfile /var/log/scrap-email-access.log --error-logfile /var/log/scrap-email-error.log wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "✅ Service créé : /etc/systemd/system/$SERVICE_NAME.service"
echo ""

# Créer les fichiers de logs
touch /var/log/scrap-email-access.log
touch /var/log/scrap-email-error.log
chown $USER:$USER /var/log/scrap-email-access.log
chown $USER:$USER /var/log/scrap-email-error.log

echo "📁 Fichiers de logs créés"
echo ""

# Arrêter les processus Flask/Gunicorn existants
echo "🛑 Arrêt des processus existants..."
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "gunicorn.*wsgi:app" 2>/dev/null || true
sleep 2

# Recharger systemd
echo "🔄 Rechargement de systemd..."
systemctl daemon-reload

# Activer et démarrer le service
echo "🚀 Activation et démarrage du service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Attendre un peu
sleep 3

# Vérifier le statut
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ Service actif et fonctionnel"
else
    echo "❌ Erreur : Le service n'a pas démarré"
    echo ""
    echo "Logs :"
    journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

echo ""
echo "========================================================================"
echo "   ✅ SERVICE INSTALLÉ ET ACTIF !"
echo "========================================================================"
echo ""
echo "📊 Informations :"
echo "   • Service : $SERVICE_NAME"
echo "   • Statut : $(systemctl is-active $SERVICE_NAME)"
echo "   • Port : 5000 (local)"
echo ""
echo "🔧 Commandes utiles :"
echo "   • Voir le statut : sudo systemctl status $SERVICE_NAME"
echo "   • Redémarrer : sudo systemctl restart $SERVICE_NAME"
echo "   • Arrêter : sudo systemctl stop $SERVICE_NAME"
echo "   • Voir les logs : sudo journalctl -u $SERVICE_NAME -f"
echo "   • Logs applicatifs : sudo tail -f /var/log/scrap-email-error.log"
echo ""
echo "🌐 Test de l'application :"
echo "   curl http://127.0.0.1:5000"
echo ""
echo "========================================================================"

# Test de l'application
echo ""
echo "🧪 Test de l'application..."
sleep 2

if curl -s http://127.0.0.1:5000 > /dev/null; then
    echo "✅ Application répond correctement !"
else
    echo "⚠️  L'application ne répond pas sur le port 5000"
    echo "   Vérifiez les logs : sudo journalctl -u $SERVICE_NAME -n 50"
fi

echo ""
echo "🎉 Installation terminée !"
echo ""
