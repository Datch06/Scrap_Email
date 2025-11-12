#!/bin/bash
# Script de monitoring pour l'extraction des dirigeants

echo "=================================="
echo "📊 MONITORING - Extraction Dirigeants"
echo "=================================="
echo ""

# Vérifier si le processus tourne
if pgrep -f "extract_siret_leaders.py" > /dev/null; then
    echo "✅ Processus actif"
    PID=$(pgrep -f "extract_siret_leaders.py" | head -1)
    echo "   PID: $PID"

    # Temps de fonctionnement
    ELAPSED=$(ps -p $PID -o etime= 2>/dev/null | xargs)
    echo "   Durée: $ELAPSED"

    # Utilisation CPU et RAM
    CPU=$(ps -p $PID -o %cpu= 2>/dev/null | xargs)
    MEM=$(ps -p $PID -o rss= 2>/dev/null | xargs)
    MEM_MB=$((MEM / 1024))
    echo "   CPU: ${CPU}%"
    echo "   RAM: ${MEM_MB} MB"
else
    echo "❌ Processus arrêté"
fi

echo ""
echo "=================================="
echo "📈 STATISTIQUES BASE DE DONNÉES"
echo "=================================="

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('scrap_email.db')
cursor = conn.cursor()

# Stats SIRET
cursor.execute("SELECT COUNT(*) FROM sites WHERE siren IS NOT NULL AND siren != 'NON TROUVÉ'")
total_siren = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sites WHERE siret_checked = 1")
siret_checked = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sites")
total_sites = cursor.fetchone()[0]

# Stats Dirigeants
cursor.execute("SELECT COUNT(*) FROM sites WHERE leaders IS NOT NULL AND leaders != 'NON TROUVÉ'")
valid_leaders = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sites WHERE leaders = 'NON TROUVÉ'")
no_leaders = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sites WHERE leaders_checked = 1")
leaders_checked = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sites WHERE leaders_checked = 0 AND siren IS NOT NULL AND siren != 'NON TROUVÉ'")
pending_leaders = cursor.fetchone()[0]

# Derniers dirigeants ajoutés
cursor.execute("""
    SELECT domain, leaders, leaders_found_at
    FROM sites
    WHERE leaders IS NOT NULL
    AND leaders != 'NON TROUVÉ'
    ORDER BY leaders_found_at DESC
    LIMIT 5
""")
recent_leaders = cursor.fetchall()

print("SIRET:")
print(f"  Total sites: {total_sites:,}")
print(f"  SIRET vérifiés: {siret_checked:,} ({siret_checked/total_sites*100:.1f}%)")
print(f"  SIREN trouvés: {total_siren:,}")
print()

print("DIRIGEANTS:")
print(f"  Vérifiés: {leaders_checked:,}")
print(f"  Valides: {valid_leaders:,}")
print(f"  Non trouvés: {no_leaders:,}")
print(f"  En attente: {pending_leaders:,}")

if total_siren > 0:
    success_rate = (valid_leaders / total_siren) * 100
    print(f"  Taux de succès: {success_rate:.1f}%")

print()
print("Derniers dirigeants trouvés:")
for domain, leaders, found_at in recent_leaders:
    print(f"  • {domain[:40]:40} → {leaders[:40]}")

conn.close()
EOF

echo ""
echo "=================================="
echo "📝 DERNIÈRES LIGNES DU LOG"
echo "=================================="
if [ -f "extract_siret_leaders.log" ]; then
    tail -10 extract_siret_leaders.log
else
    echo "❌ Fichier log introuvable"
fi
