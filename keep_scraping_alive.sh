#!/bin/bash
################################################################################
# Script de surveillance pour maintenir le scraping actif en permanence
# Ce script vérifie si le processus de scraping est actif et le relance si besoin
################################################################################

# Répertoire de travail
WORK_DIR="/var/www/Scrap_Email"
cd "$WORK_DIR"

# Fichiers de log
LOG_FILE="$WORK_DIR/scraping_watchdog.log"
SCRAPING_LOG="$WORK_DIR/scraping_output.log"

# Script de scraping à surveiller
SCRAPE_SCRIPT="$WORK_DIR/scrape_backlinks_async.py"

# Fichier d'état
STATE_FILE="$WORK_DIR/scraping_state.json"

# Fonction de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Fonction pour vérifier si le scraping est actif
is_scraping_active() {
    # Vérifier si le processus scrape_backlinks_async.py est en cours
    if pgrep -f "python3.*scrape_backlinks_async.py" > /dev/null; then
        return 0  # Actif
    else
        return 1  # Inactif
    fi
}

# Fonction pour vérifier si le fichier d'état est récent (< 5 minutes)
is_state_fresh() {
    if [ ! -f "$STATE_FILE" ]; then
        return 1  # Fichier n'existe pas
    fi

    # Âge du fichier en secondes
    local file_age=$(($(date +%s) - $(stat -c %Y "$STATE_FILE")))

    # Si moins de 5 minutes (300 secondes), c'est actif
    if [ $file_age -lt 300 ]; then
        return 0  # Récent
    else
        return 1  # Ancien
    fi
}

# Fonction pour démarrer le scraping
start_scraping() {
    log "🚀 Démarrage du scraping..."

    # Tuer les anciens processus si présents
    pkill -9 -f "python3.*scrape_backlinks_async.py" 2>/dev/null
    sleep 2

    # Démarrer le scraping en arrière-plan
    nohup python3 "$SCRAPE_SCRIPT" >> "$SCRAPING_LOG" 2>&1 &

    local pid=$!
    log "✅ Scraping démarré (PID: $pid)"

    # Attendre un peu pour vérifier que le processus démarre bien
    sleep 5

    if is_scraping_active; then
        log "✓ Scraping confirmé actif"
        return 0
    else
        log "❌ Échec du démarrage du scraping"
        return 1
    fi
}

# Fonction principale de surveillance
main() {
    log "=========================================="
    log "🔍 Vérification du statut du scraping..."

    # Vérifier si le scraping est actif
    if is_scraping_active && is_state_fresh; then
        log "✓ Scraping actif et opérationnel"
    else
        log "⚠️  Scraping inactif ou bloqué - Relance nécessaire"
        start_scraping
    fi
}

# Boucle infinie avec vérification toutes les 2 minutes
log "=========================================="
log "🎬 Démarrage du système de surveillance du scraping"
log "Intervalle de vérification: 2 minutes"
log "=========================================="

while true; do
    main

    # Attendre 2 minutes avant la prochaine vérification
    sleep 120
done
