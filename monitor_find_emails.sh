#!/bin/bash
# Script de monitoring pour find_any_valid_email.py

LOG_FILE="/var/www/Scrap_Email/find_emails_100.log"

echo "=================================="
echo "📊 MONITORING - Find Any Valid Email"
echo "=================================="
echo ""

# Vérifier si le processus tourne
if pgrep -f "find_any_valid_email.py" > /dev/null; then
    echo "✅ Processus actif"
    PID=$(pgrep -f "find_any_valid_email.py")
    echo "   PID: $PID"

    # Temps de fonctionnement
    ELAPSED=$(ps -p $PID -o etime= | xargs)
    echo "   Durée: $ELAPSED"

    # Utilisation CPU et RAM
    CPU=$(ps -p $PID -o %cpu= | xargs)
    MEM=$(ps -p $PID -o rss= | xargs)
    MEM_MB=$((MEM / 1024))
    echo "   CPU: ${CPU}%"
    echo "   RAM: ${MEM_MB} MB"
else
    echo "❌ Processus arrêté"
fi

echo ""
echo "=================================="
echo "📈 STATISTIQUES DU LOG"
echo "=================================="

if [ -f "$LOG_FILE" ]; then
    # Compter les différents statuts
    TOTAL_TRAITES=$(grep -c "🔍 Recherche email valide pour:" "$LOG_FILE")
    EMAILS_TROUVES=$(grep -c "🏆 MEILLEUR EMAIL" "$LOG_FILE")
    GENERIQUES=$(grep -c "EMAIL GÉNÉRIQUE VALIDÉ" "$LOG_FILE")
    SUR_SITE=$(grep -c "EMAIL TROUVÉ SUR SITE" "$LOG_FILE")
    AUCUN=$(grep -c "AUCUN EMAIL VALIDE" "$LOG_FILE")

    echo "Sites traités: $TOTAL_TRAITES"
    echo "Emails trouvés: $EMAILS_TROUVES"
    echo "  ├─ Génériques validés: $GENERIQUES"
    echo "  └─ Trouvés sur site: $SUR_SITE"
    echo "Aucun email: $AUCUN"

    if [ $TOTAL_TRAITES -gt 0 ]; then
        SUCCESS_RATE=$(( EMAILS_TROUVES * 100 / TOTAL_TRAITES ))
        echo ""
        echo "Taux de succès: ${SUCCESS_RATE}%"
    fi

    echo ""
    echo "=================================="
    echo "📝 DERNIÈRES LIGNES DU LOG"
    echo "=================================="
    tail -15 "$LOG_FILE"
else
    echo "❌ Fichier log introuvable: $LOG_FILE"
fi
