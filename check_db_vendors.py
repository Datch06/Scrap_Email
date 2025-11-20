#!/usr/bin/env python3
"""
Script pour vérifier les données des sites vendeurs dans la base
"""
from database import get_session, Site

session = get_session()

print("=" * 80)
print("VÉRIFICATION DES SITES VENDEURS")
print("=" * 80)

# Récupérer quelques vendeurs
vendors = session.query(Site).filter_by(is_linkavista_seller=True).limit(20).all()

print(f"\n✓ {len(vendors)} premiers vendeurs récupérés\n")

for i, vendor in enumerate(vendors, 1):
    print(f"\n--- Vendeur {i}: {vendor.domain} ---")
    print(f"  ID: {vendor.id}")
    print(f"  domain: {repr(vendor.domain)}")
    print(f"  source_url: {repr(vendor.source_url)}")
    print(f"  is_linkavista_seller: {vendor.is_linkavista_seller}")
    print(f"  backlinks_crawled: {vendor.backlinks_crawled}")

    # Test de extract_domain
    from urllib.parse import urlparse

    test_url = vendor.source_url or f"https://{vendor.domain}"
    parsed = urlparse(test_url)
    extracted_domain = parsed.netloc.lower().replace('www.', '')

    print(f"  test_url généré: {repr(test_url)}")
    print(f"  domaine extrait: {repr(extracted_domain)}")
    print(f"  domaine valide? {bool(extracted_domain)}")

print("\n" + "=" * 80)
print("STATISTIQUES")
print("=" * 80)

# Compter les vendeurs par type de données
total_vendors = session.query(Site).filter_by(is_linkavista_seller=True).count()
with_source_url = session.query(Site).filter(
    Site.is_linkavista_seller == True,
    Site.source_url.isnot(None),
    Site.source_url != ''
).count()
with_domain = session.query(Site).filter(
    Site.is_linkavista_seller == True,
    Site.domain.isnot(None),
    Site.domain != ''
).count()

print(f"\nTotal vendeurs: {total_vendors}")
print(f"Avec source_url: {with_source_url} ({100*with_source_url/total_vendors:.1f}%)")
print(f"Avec domain: {with_domain} ({100*with_domain/total_vendors:.1f}%)")

session.close()
