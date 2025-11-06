#!/usr/bin/env python3
"""
Nettoyer les faux positifs d'emails ajoutés par le re-scraper
"""

from database import get_session, Site
from datetime import datetime, timedelta

def clean_false_positives():
    """Nettoyer les faux positifs"""
    print("\n" + "="*80)
    print("🧹 NETTOYAGE DES FAUX POSITIFS")
    print("="*80)

    db_session = get_session()

    # Patterns de faux positifs
    false_positive_patterns = [
        'gst@ic', 'flo@-', 'separ@e', 'fe@ured', 'anim@ion', 'rel@ed',
        'gener@', 'd@aset', 'l@est', '@tachment', '@tribute', 'grav@ar',
        'c@egory', 'templ@', 'form@', 'transl@', '@tentes', 'inform@',
        'cor@', 'alis@', 'explor@', 'duc@', 'entrepreneuri@', 'pl@eformes',
        'administr@', 'bersch@', 'blumendekor@', 'temper@', 'pexels_',
        'et_anim@', 'filter-fe@', 'bei-temper@', '.js', '.css', '.svg',
        '.png', '.jpg', '.jpeg', '.gif', 'navig@or', 'cotis@ion'
    ]

    # Trouver les sites avec des faux positifs (ajoutés dans les dernières 24h)
    cutoff_time = datetime.utcnow() - timedelta(hours=24)

    sites = db_session.query(Site).filter(
        Site.email_source == "async_rescraping",
        Site.updated_at >= cutoff_time
    ).all()

    print(f"\n📊 Sites à vérifier: {len(sites)}")

    cleaned = 0
    kept = 0

    for site in sites:
        if not site.emails or site.emails == "NO EMAIL FOUND":
            continue

        # Vérifier si l'email contient des patterns de faux positifs
        is_false_positive = any(pattern in site.emails.lower() for pattern in false_positive_patterns)

        if is_false_positive:
            print(f"❌ Nettoyage: {site.domain[:40]:40} → {site.emails[:60]}")
            site.emails = "NO EMAIL FOUND"
            site.email_found_at = None
            site.status = site.status  # Garder le statut
            cleaned += 1
        else:
            print(f"✅ Valide: {site.domain[:40]:40} → {site.emails[:60]}")
            kept += 1

    db_session.commit()
    db_session.close()

    print("\n" + "="*80)
    print("✅ NETTOYAGE TERMINÉ!")
    print("="*80)
    print(f"   Faux positifs nettoyés: {cleaned}")
    print(f"   Emails valides conservés: {kept}")
    print("="*80)


if __name__ == "__main__":
    clean_false_positives()
