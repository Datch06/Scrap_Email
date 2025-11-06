#!/bin/bash
# Script de monitoring du re-scraping

echo "======================================================================"
echo "📊 MONITORING DU RE-SCRAPING"
echo "======================================================================"
echo ""

# Vérifier si le processus tourne
if pgrep -f "rescrape_no_emails_async" > /dev/null; then
    echo "✅ Processus en cours"
    echo ""

    # Afficher les dernières lignes du log
    echo "📝 Dernières lignes du log:"
    echo "----------------------------------------------------------------------"
    tail -20 /tmp/rescrape_full.log 2>/dev/null || echo "Log non disponible"
    echo ""

    # Stats de la base
    echo "----------------------------------------------------------------------"
    python3 check_stats.py

    # Uptime du processus
    echo "⏱️  Temps d'exécution:"
    ps -p $(pgrep -f "rescrape_no_emails_async") -o etime= | xargs echo

else
    echo "❌ Processus non actif"
    echo ""
    echo "📝 Fin du log:"
    echo "----------------------------------------------------------------------"
    tail -30 /tmp/rescrape_full.log 2>/dev/null || echo "Log non disponible"
fi

echo ""
echo "======================================================================"
