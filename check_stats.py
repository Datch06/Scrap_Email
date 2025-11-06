#!/usr/bin/env python3
"""Afficher les statistiques de la base de données"""

from database import get_session, Site

session = get_session()

total = session.query(Site).count()
with_emails = session.query(Site).filter(
    Site.emails != 'NO EMAIL FOUND',
    Site.emails != None,
    Site.emails != ''
).count()
no_emails = session.query(Site).filter(
    (Site.emails == 'NO EMAIL FOUND') |
    (Site.emails == None) |
    (Site.emails == '')
).count()
validated = session.query(Site).filter(Site.email_validated == True).count()

print('\n' + '='*60)
print('📊 STATISTIQUES BASE DE DONNÉES')
print('='*60)
print(f'Total sites: {total:,}')
print(f'Sites avec emails: {with_emails:,} ({with_emails/total*100:.1f}%)')
print(f'Sites sans emails: {no_emails:,} ({no_emails/total*100:.1f}%)')
print(f'Emails validés: {validated:,}')
print('='*60 + '\n')

session.close()
