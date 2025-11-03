#!/bin/bash
# Script de sauvegarde automatique de la base de données
# Exécuté quotidiennement via cron

set -e  # Arrêter en cas d'erreur

# Configuration
BACKUP_DIR="/var/www/Scrap_Email/backups"
DB_DIR="/var/www/Scrap_Email"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="scrap_email_backup_${DATE}.tar.gz"
RETENTION_DAYS=7

# Créer le dossier de backup s'il n'existe pas
mkdir -p "$BACKUP_DIR"

# Log
echo "=========================================="
echo "Backup démarré: $(date)"
echo "=========================================="

# Créer le backup compressé
echo "Compression des bases de données..."
cd "$DB_DIR"
tar -czf "$BACKUP_DIR/$BACKUP_FILE" scrap_email.db campaigns.db

# Vérifier la taille du backup
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "✅ Backup créé: $BACKUP_FILE ($BACKUP_SIZE)"

# Compter les sites et emails
STATS=$(python3 << 'EOF'
from database import get_session, Site

session = get_session()
total_sites = session.query(Site).count()
emails_found = session.query(Site).filter(Site.emails != None, Site.emails != 'NO EMAIL FOUND').count()
session.close()

print(f"{total_sites:,} sites | {emails_found:,} emails")
EOF
)

echo "📊 Statistiques: $STATS"

# Supprimer les anciens backups (garder les 7 derniers jours)
echo "Nettoyage des anciens backups (>${RETENTION_DAYS} jours)..."
find "$BACKUP_DIR" -name "scrap_email_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete
REMAINING=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)
echo "📁 Backups conservés: $REMAINING"

# Pousser vers GitHub (optionnel, décommenter si souhaité)
echo "Push vers GitHub..."
cd "$DB_DIR"
git add backups/
git commit -m "Auto backup: $(date '+%Y-%m-%d %H:%M') - $STATS" || echo "Rien à committer"
GIT_TERMINAL_PROMPT=0 git push origin main || echo "⚠️  Push GitHub échoué (normal si pas de changement)"

echo "=========================================="
echo "✅ Backup terminé: $(date)"
echo "=========================================="
