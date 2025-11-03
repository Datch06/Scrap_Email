#!/usr/bin/env python3
from database import get_session, Site

session = get_session()

# Sites avec SIRET mais sans email
sites_potentiel = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != "",
    Site.siret != "NON TROUVÉ"
).filter(
    (Site.emails.is_(None)) |
    (Site.emails == "") |
    (Site.emails == "NO EMAIL FOUND")
).count()

# Sites avec SIRET
total_siret = session.query(Site).filter(
    Site.siret.isnot(None),
    Site.siret != "",
    Site.siret != "NON TROUVÉ"
).count()

# Total
total = session.query(Site).count()

print("=" * 70)
print("POTENTIEL DE RÉCUPÉRATION VIA API PAPPERS")
print("=" * 70)
print(f"\nTotal de sites: {total}")
print(f"Sites avec SIRET: {total_siret} ({total_siret/total*100:.1f}%)")
print(f"\nSites avec SIRET SANS email: {sites_potentiel}")
print(f"  → Peuvent bénéficier de l'API Pappers")
print(f"\nEstimation (75% de succès):")
print(f"  → {int(sites_potentiel * 0.75)} emails supplémentaires")
print(f"  → Nouveau taux d'emails: {(51 + sites_potentiel * 0.75)/total*100:.1f}%")
print(f"\nCoût estimé (Pappers):")
print(f"  → {sites_potentiel} requêtes × 0.02€ = {sites_potentiel * 0.02:.2f}€")
print("=" * 70)

session.close()
