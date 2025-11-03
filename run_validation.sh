#!/bin/bash
# Script pour lancer la validation d'emails en production

cd /var/www/Scrap_Email

echo "🚀 Démarrage de la validation d'emails"
echo "======================================"
echo ""

# Demander le nombre d'emails à valider
read -p "Nombre d'emails à valider (appuyez sur Entrée pour tous): " LIMIT

# Demander si on valide uniquement les nouveaux
read -p "Valider uniquement les nouveaux emails ? (O/n): " ONLY_NEW

# Construire la commande
CMD="python3 validate_emails.py --batch-size 50"

if [ ! -z "$LIMIT" ]; then
    CMD="$CMD --limit $LIMIT"
fi

if [ "$ONLY_NEW" != "n" ] && [ "$ONLY_NEW" != "N" ]; then
    CMD="$CMD --only-new"
fi

echo ""
echo "Commande: $CMD"
echo ""
read -p "Continuer ? (O/n): " CONFIRM

if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
    echo "❌ Annulé"
    exit 0
fi

echo ""
echo "▶️  Lancement de la validation..."
echo ""

$CMD

echo ""
echo "✅ Validation terminée!"
echo ""
echo "📊 Statistiques disponibles:"
echo "   - Logs: email_validation.log"
echo "   - Dashboard: http://admin.perfect-cocon-seo.fr"
