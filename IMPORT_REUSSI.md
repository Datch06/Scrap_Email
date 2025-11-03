# Import des Données Réussi

Date: 2025-10-18

---

## Résumé de l'Import

✅ **Sites de test supprimés**: 4 sites
✅ **Données importées depuis les fichiers locaux**
✅ **Base de données synchronisée**

---

## Statistiques de la Base de Données

### Vue d'Ensemble

| Métrique | Valeur | Taux |
|----------|--------|------|
| **Total de sites** | 2,841 | 100% |
| **Sites avec email** | 51 | 1.8% |
| **Sites avec SIRET** | 810 | 28.5% |
| **Sites avec dirigeants** | 64 | 2.3% |
| **Sites complets** | 1 | 0.0% |

### Répartition par Statut

| Statut | Nombre |
|--------|--------|
| Discovered (à traiter) | 1,999 |
| SIRET trouvé | 747 |
| Leaders trouvés | 62 |
| Email trouvé | 32 |
| Completed | 1 |

### Activité Récente
- **2,841 sites** ajoutés/mis à jour dans les dernières 24h

---

## Sources de Données Importées

### Fichiers CSV
1. ✅ `emails_found.csv` - 929 sites
2. ✅ `emails_formatted.csv` - 131 sites
3. ✅ `emails_cleaned.csv` - Sites supplémentaires

### Fichiers JSON
1. ✅ `feuille1_results.json` - Sites avec SIRET
2. ✅ `feuille2_results.json` - Sites avec informations complètes
3. ✅ `dirigeants_results.json` - Dirigeants d'entreprises

### Listes de Domaines
1. ✅ `domains_fr_only.txt` - Domaines français uniquement
2. ✅ `domains_ladepeche_cleaned.txt` - Domaines La Dépêche
3. ✅ `domains_marca_filtered.txt` - Domaines Marca

---

## Exemples de Données Importées

### Sites avec Emails

**1voix6cordes.fr**
- Email: benjaminguyot8@gmail.com; contact@1voix6cordes.fr
- SIRET: N/A
- Leaders: N/A

**agence-diana-ivanova.fr**
- Email: ivadiana@gmail.com
- SIRET: N/A
- Leaders: N/A

**bouquineriebagneres.fr**
- Email: bouquinerie.bagneres@gmail.com
- SIRET: N/A
- Leaders: N/A

### Sites avec SIRET et Dirigeants

**afm-telethon.fr**
- SIRET: 77560957100739
- SIREN: 775609571
- Leaders: SANTOUL Catherine
- Email: N/A

**leprogres.fr**
- SIRET: 321263683
- SIREN: 321263683
- Leaders: GUILLEMOT Marie
- Email: dpo@ebra.fr; lprventesweb@leprogres.fr

**marcovasco.fr**
- SIRET: 501602007
- SIREN: 501602007
- Leaders: VARON Jean
- Email: N/A

---

## Accès aux Données

### Interface Web
🌐 **https://admin.perfect-cocon-seo.fr**

- Dashboard avec statistiques en temps réel
- Liste des sites avec filtres avancés
- Export CSV disponible

### API REST

```bash
# Statistiques globales
curl https://admin.perfect-cocon-seo.fr/api/stats

# Liste des sites (pagination)
curl "https://admin.perfect-cocon-seo.fr/api/sites?page=1&per_page=50"

# Sites avec email uniquement
curl "https://admin.perfect-cocon-seo.fr/api/sites?has_email=true"

# Sites avec SIRET uniquement
curl "https://admin.perfect-cocon-seo.fr/api/sites?has_siret=true"

# Sites avec dirigeants uniquement
curl "https://admin.perfect-cocon-seo.fr/api/sites?has_leaders=true"

# Export CSV complet
curl -o sites.csv https://admin.perfect-cocon-seo.fr/api/export/csv
```

---

## Prochaines Actions Recommandées

### 1. Compléter les Données Manquantes

**Emails manquants**: 2,790 sites (98.2%)
```bash
# Lancer le scraping d'emails
python3 extract_emails_db.py --limit 100
```

**SIRET manquants**: 2,031 sites (71.5%)
```bash
# Récupérer les SIRET depuis societe.com
python3 update_feuille1.py
```

**Dirigeants manquants**: 2,777 sites (97.7%)
```bash
# Récupérer les dirigeants
python3 fetch_dirigeants_slow.py
```

### 2. Nettoyer les Données

Certains emails semblent être des exemples ou des faux positifs:
- `vous@domaine.com` (assurance-prevention.fr)
- `dpo@opper.io` (blogs.mediapart.fr)

Recommandation: Créer un script de nettoyage pour filtrer ces emails.

### 3. Synchroniser avec Google Sheets

Pour mettre à jour les Google Sheets avec les nouvelles données:

```bash
# Mettre à jour la feuille 1 (SIRET)
python3 update_feuille1.py

# Mettre à jour la feuille 2 (dirigeants)
python3 update_feuille2_batch.py
```

### 4. Lancer des Jobs de Scraping

Via l'interface web ou l'API, vous pouvez lancer des jobs pour:
- Scraper les emails manquants
- Récupérer les SIRET
- Trouver les dirigeants

---

## Utilisation de l'Interface

### Filtres Disponibles

1. **Par statut**
   - Discovered (1,999 sites)
   - SIRET trouvé (747 sites)
   - Email trouvé (32 sites)
   - Leaders trouvés (62 sites)
   - Completed (1 site)

2. **Par présence de données**
   - Avec email: 51 sites
   - Avec SIRET: 810 sites
   - Avec dirigeants: 64 sites
   - Complets (tout): 1 site

3. **Recherche par domaine**
   - Recherche textuelle dans le nom de domaine

### Export des Données

L'export CSV contient toutes les colonnes:
- ID, Domaine, Statut
- Emails, SIRET, SIREN
- Dirigeants, Source
- Dates de création et mise à jour

---

## Performance et Optimisation

### Temps d'Import
- **Total**: ~2-3 minutes pour 2,841 sites
- **Déduplication**: Automatique (sites existants ignorés)

### Base de Données
- **Type**: SQLite
- **Localisation**: [/var/www/Scrap_Email/scrap_email.db](scrap_email.db:1)
- **Taille**: ~1-2 MB

### Sauvegarde

Créer une sauvegarde après l'import:
```bash
cd /var/www/Scrap_Email
cp scrap_email.db scrap_email.db.backup_$(date +%Y%m%d)
```

---

## État Actuel du Système

✅ Base de données nettoyée (sites de test supprimés)
✅ Données importées depuis fichiers locaux (CSV + JSON)
✅ 2,841 sites en base de données
✅ Interface web accessible sur https://admin.perfect-cocon-seo.fr
✅ API REST fonctionnelle
✅ Export CSV disponible

---

## Commandes Rapides

### Vérifier les statistiques
```bash
curl -s https://admin.perfect-cocon-seo.fr/api/stats | python3 -m json.tool
```

### Voir des exemples de sites
```bash
python3 -c "
from database import get_session, Site
session = get_session()
sites = session.query(Site).limit(10).all()
for site in sites:
    print(f'{site.domain}: {site.status.value if site.status else \"None\"}')
session.close()
"
```

### Sauvegarder la base
```bash
cp scrap_email.db backup_$(date +%Y%m%d_%H%M%S).db
```

---

## Conclusion

L'import des données a été réalisé avec succès !

- **2,841 sites** sont maintenant dans la base de données
- **810 sites** ont déjà un SIRET
- **51 sites** ont déjà un email
- **64 sites** ont déjà des dirigeants

Les prochaines étapes consistent à compléter les données manquantes en lançant les scripts de scraping appropriés.

**L'interface web est accessible à tout moment sur**: https://admin.perfect-cocon-seo.fr
