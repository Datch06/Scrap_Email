#!/usr/bin/env python3
"""
Réinitialiser le flag backlinks_crawled pour permettre un nouveau crawl
"""
from database import get_session, Site

session = get_session()

print("=" * 80)
print("RÉINITIALISATION DES FLAGS backlinks_crawled")
print("=" * 80)

# Compter les sites à réinitialiser
to_reset = session.query(Site).filter(
    Site.is_linkavista_seller == True,
    Site.backlinks_crawled == True
).count()

print(f"\n✓ {to_reset:,} sites vendeurs à réinitialiser")

# Confirmation
print(f"\nCette opération va réinitialiser backlinks_crawled à False pour {to_reset:,} sites.")
print("Cela permettra de les re-crawler avec le code corrigé.")

# Faire la mise à jour
print("\n⏳ Réinitialisation en cours...")
session.query(Site).filter(
    Site.is_linkavista_seller == True,
    Site.backlinks_crawled == True
).update({
    'backlinks_crawled': False,
    'backlinks_crawled_at': None
})

session.commit()
print("✅ Réinitialisation terminée!")

# Vérification
still_crawled = session.query(Site).filter(
    Site.is_linkavista_seller == True,
    Site.backlinks_crawled == True
).count()

not_crawled = session.query(Site).filter(
    Site.is_linkavista_seller == True,
    (Site.backlinks_crawled == False) | (Site.backlinks_crawled.is_(None))
).count()

print(f"\n📊 Vérification:")
print(f"  - Sites encore crawlés: {still_crawled:,}")
print(f"  - Sites non crawlés (prêts): {not_crawled:,}")

session.close()
