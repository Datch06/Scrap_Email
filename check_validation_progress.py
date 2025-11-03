#!/usr/bin/env python3
"""
Afficher la progression de la validation en temps réel
"""

from database import get_session, Site
from datetime import datetime
import time
import sys

def get_stats():
    """Récupérer les statistiques"""
    session = get_session()

    try:
        # Total emails
        total_emails = session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()

        # Validés
        validated = session.query(Site).filter(Site.email_validated == True).count()
        valid = session.query(Site).filter(Site.email_validation_status == 'valid').count()
        invalid = session.query(Site).filter(Site.email_validation_status == 'invalid').count()
        risky = session.query(Site).filter(Site.email_validation_status == 'risky').count()
        deliverable = session.query(Site).filter(Site.email_deliverable == True).count()

        # Reste à valider
        remaining = total_emails - validated

        # Progression
        progress = (validated / total_emails * 100) if total_emails > 0 else 0

        return {
            'total_emails': total_emails,
            'validated': validated,
            'valid': valid,
            'invalid': invalid,
            'risky': risky,
            'deliverable': deliverable,
            'remaining': remaining,
            'progress': progress
        }
    finally:
        session.close()

def display_progress(stats, refresh=False):
    """Afficher la progression"""
    if refresh:
        # Effacer l'écran (compatible Unix)
        print('\033[2J\033[H', end='')

    print("=" * 70)
    print(f"📊 PROGRESSION DE LA VALIDATION - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    print()

    # Barre de progression
    bar_length = 50
    filled = int(bar_length * stats['progress'] / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"Progression: [{bar}] {stats['progress']:.1f}%")
    print()

    # Stats
    print(f"📧 Total emails:        {stats['total_emails']:,}")
    print(f"✓  Validés:             {stats['validated']:,}")
    print(f"⏳ Reste à valider:     {stats['remaining']:,}")
    print()

    print(f"✅ Valides:             {stats['valid']:,} ({stats['valid']/stats['validated']*100:.1f}%)" if stats['validated'] > 0 else "✅ Valides:             0")
    print(f"❌ Invalides:           {stats['invalid']:,} ({stats['invalid']/stats['validated']*100:.1f}%)" if stats['validated'] > 0 else "❌ Invalides:           0")
    print(f"⚠️  Risqués:            {stats['risky']:,} ({stats['risky']/stats['validated']*100:.1f}%)" if stats['validated'] > 0 else "⚠️  Risqués:            0")
    print(f"📤 Délivrables:         {stats['deliverable']:,}")
    print()

    # Estimation du temps restant (basé sur ~2.5s par email)
    if stats['remaining'] > 0:
        estimated_seconds = stats['remaining'] * 2.5
        hours = int(estimated_seconds // 3600)
        minutes = int((estimated_seconds % 3600) // 60)
        print(f"⏱️  Temps estimé restant: ~{hours}h {minutes}m")
    else:
        print("✅ Validation terminée !")

    print()
    print("=" * 70)

def watch_progress(interval=10):
    """Surveiller la progression en continu"""
    print("👀 Surveillance de la progression (Ctrl+C pour arrêter)")
    print()

    try:
        first = True
        while True:
            stats = get_stats()
            display_progress(stats, refresh=not first)
            first = False

            if stats['remaining'] == 0:
                print("\n🎉 Tous les emails ont été validés !")
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt de la surveillance")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Suivre la progression de la validation')
    parser.add_argument('--watch', '-w', action='store_true', help='Surveiller en continu')
    parser.add_argument('--interval', '-i', type=int, default=10, help='Intervalle de rafraîchissement (défaut: 10s)')

    args = parser.parse_args()

    if args.watch:
        watch_progress(args.interval)
    else:
        stats = get_stats()
        display_progress(stats)
