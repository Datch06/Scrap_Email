#!/usr/bin/env python3
"""
Nettoyer TOUS les emails invalides avec validation stricte
"""

from database import get_session, Site
from datetime import datetime, timedelta
import re

def is_valid_email(email):
    """Validation STRICTE d'un email"""
    if not email or '@' not in email:
        return False

    # Split
    try:
        local, domain = email.split('@', 1)
    except:
        return False

    # Le local ne doit pas contenir @ (plusieurs @)
    if '@' in local:
        return False

    # Vérifier le domaine
    if '.' not in domain:
        return False

    parts = domain.split('.')
    if len(parts) < 2:
        return False

    # TLD valides
    valid_tlds = {
        'com', 'fr', 'org', 'net', 'eu', 'de', 'be', 'ch', 'uk',
        'co', 'info', 'io', 'ai', 'tech', 'xyz', 'online', 'site',
        'email', 'pro', 'biz', 'us', 'ca', 'es', 'it', 'nl', 'br',
        'ru', 'jp', 'cn', 'in', 'au', 'pl', 'se', 'no', 'fi', 'dk'
    }

    tld = parts[-1].lower()
    if tld not in valid_tlds:
        return False

    # Le domaine ne doit pas être juste des mots
    # Pattern: si ça ressemble à du texte français/allemand, c'est faux
    text_patterns = [
        'fe@ure', 'signific@', 'pr@ique', 'complic@', 'justific@',
        'prest@', 'in@ten', 'intern@', 'consomm@', 'utilis@',
        'am@eur', 'irrit@', 'feugi@', 'ipsum@', 'cookied@',
        'gre@', 'ach@', 'c@her', 'ec@-', 'pl@t', 'st@ues',
        'wh@would', 'gust@', 'anti-inflamm@', 'intr@ent',
        'vpncre@', 'sportsd@', 'deco-st@', 'gr@uit',
        'ch@-', 'dicocit@', 'explor@', 'alis@', 'duc@',
        'entrepreneuri@', 'inform@', 'cor@', 'transl@',
        'Online-Lernpl@', 'Unternehmensber@', 'Zertifik@'
    ]

    email_lower = email.lower()
    if any(pattern in email_lower for pattern in text_patterns):
        return False

    # Le local ne doit pas commencer par . ou - ou +
    if local.startswith('.') or local.startswith('-') or local.startswith('+'):
        return False

    # Le local ne doit pas finir par . ou -
    if local.endswith('.') or local.endswith('-'):
        return False

    # Pattern basique d'email valide
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$', email):
        return False

    return True


def clean_all_invalid():
    """Nettoyer tous les emails invalides"""
    print("\n" + "="*80)
    print("🧹 NETTOYAGE COMPLET DES EMAILS INVALIDES")
    print("="*80)

    db_session = get_session()

    # Tous les sites avec des emails (pas "NO EMAIL FOUND")
    sites = db_session.query(Site).filter(
        Site.emails != "NO EMAIL FOUND",
        Site.emails != None,
        Site.emails != ""
    ).all()

    print(f"\n📊 Sites à vérifier: {len(sites):,}")

    cleaned = 0
    kept = 0

    for site in sites:
        if not site.emails:
            continue

        # Split par ";" pour avoir tous les emails
        emails = [e.strip() for e in site.emails.split(';')]

        # Valider chaque email
        valid_emails = [e for e in emails if is_valid_email(e)]

        if not valid_emails:
            # Aucun email valide
            print(f"❌ {site.domain[:40]:40} → {site.emails[:60]}")
            site.emails = "NO EMAIL FOUND"
            site.email_found_at = None
            cleaned += 1
        elif len(valid_emails) < len(emails):
            # Quelques emails invalides
            site.emails = "; ".join(valid_emails)
            print(f"⚠️  {site.domain[:40]:40} → Gardé {len(valid_emails)}/{len(emails)}")
            cleaned += (len(emails) - len(valid_emails))
            kept += len(valid_emails)
        else:
            # Tous les emails sont valides
            kept += len(valid_emails)

    db_session.commit()
    db_session.close()

    print("\n" + "="*80)
    print("✅ NETTOYAGE TERMINÉ!")
    print("="*80)
    print(f"   Emails invalides supprimés: {cleaned:,}")
    print(f"   Emails valides conservés: {kept:,}")
    print("="*80)


if __name__ == "__main__":
    clean_all_invalid()
