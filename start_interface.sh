#!/bin/bash

# Script de démarrage de l'interface Scrap Email

clear
echo "========================================================================"
echo "                   INTERFACE SCRAP EMAIL MANAGER"
echo "========================================================================"
echo ""
echo "Vérification des prérequis..."

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi
echo "✅ Python 3 installé"

# Vérifier si la base de données existe
if [ ! -f "scrap_email.db" ]; then
    echo "⚠️  Base de données non trouvée. Création..."
    python3 database.py
    if [ $? -eq 0 ]; then
        echo "✅ Base de données créée"
    else
        echo "❌ Erreur lors de la création de la base"
        exit 1
    fi
else
    echo "✅ Base de données trouvée"
fi

# Vérifier les dépendances Python
echo ""
echo "Vérification des dépendances..."
python3 -c "import sqlalchemy, flask, flask_cors" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Toutes les dépendances sont installées"
else
    echo "⚠️  Installation des dépendances manquantes..."
    pip3 install sqlalchemy flask flask-cors
fi

echo ""
echo "========================================================================"
echo "                        DÉMARRAGE DU SERVEUR"
echo "========================================================================"
echo ""
echo "Interface accessible sur : http://localhost:5000"
echo ""
echo "Pages disponibles :"
echo "  📊 Dashboard    : http://localhost:5000/"
echo "  🌐 Sites        : http://localhost:5000/sites"
echo "  ⚙️  Jobs         : http://localhost:5000/jobs"
echo ""
echo "Pour arrêter le serveur : Ctrl+C"
echo "========================================================================"
echo ""

# Démarrer l'application
python3 app.py
