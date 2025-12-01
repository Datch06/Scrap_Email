#!/bin/bash
# Script de gestion des workers de crawl
# Usage: ./manage_workers.sh <nombre_workers>

WORKERS_DIR="/var/www/Scrap_Email"
WORKER_SCRIPT="crawl_worker_multi.py"
PARALLEL_SITES=100
CONCURRENT=50

# Detecter le repertoire sur les serveurs distants
if [ -d "/home/debian/crawl_worker" ]; then
    WORKERS_DIR="/home/debian/crawl_worker"
fi

TARGET_COUNT=${1:-0}

# Compter les workers actuels (seulement les processus python3, pas les bash parents)
current_count() {
    pgrep -f "python3.*$WORKER_SCRIPT" 2>/dev/null | wc -l
}

# Lister les PIDs des workers (seulement python3)
list_pids() {
    pgrep -f "python3.*$WORKER_SCRIPT" 2>/dev/null
}

# Tuer N workers (les plus anciens)
kill_workers() {
    local to_kill=$1
    local pids=$(list_pids | head -n $to_kill)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null
    fi
}

# Lancer N workers
start_workers() {
    local to_start=$1
    cd "$WORKERS_DIR"
    for i in $(seq 1 $to_start); do
        local log_num=$(($(current_count) + 1))
        nohup python3 -u "$WORKER_SCRIPT" --parallel-sites $PARALLEL_SITES --concurrent $CONCURRENT > "crawl_worker_${log_num}_$$.log" 2>&1 &
        sleep 0.5
    done
}

# Afficher l'etat
show_status() {
    echo "Workers actifs: $(current_count)"
    echo "PIDs: $(list_pids | tr '\n' ' ')"
}

# Main
CURRENT=$(current_count)

if [ "$TARGET_COUNT" -eq 0 ]; then
    # Juste afficher le status
    show_status
    exit 0
fi

echo "Cible: $TARGET_COUNT workers"
echo "Actuels: $CURRENT workers"

if [ "$CURRENT" -gt "$TARGET_COUNT" ]; then
    # Trop de workers, en tuer
    TO_KILL=$((CURRENT - TARGET_COUNT))
    echo "Arret de $TO_KILL worker(s)..."
    kill_workers $TO_KILL
    sleep 2
elif [ "$CURRENT" -lt "$TARGET_COUNT" ]; then
    # Pas assez, en lancer
    TO_START=$((TARGET_COUNT - CURRENT))
    echo "Lancement de $TO_START worker(s)..."
    start_workers $TO_START
    sleep 3
else
    echo "Nombre correct de workers"
fi

echo "=== Resultat ==="
show_status
