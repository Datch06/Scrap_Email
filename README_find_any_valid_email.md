# Script find_any_valid_email.py

## 📝 Description

Script intelligent de fallback pour trouver des emails valides sur les sites où aucun email "contact" n'a été trouvé.

## 🎯 Fonctionnalités

### Phase 1 : Recherche sur le site
- Scanne jusqu'à 20 pages du site (accueil, contact, mentions légales, à propos, etc.)
- Extrait TOUS les emails trouvés (pas seulement contact@)
- Valide et score chaque email (syntaxe + DNS + SMTP)

### Phase 2 : Fallback avec emails génériques
Si aucun email trouvé en Phase 1, génère et teste automatiquement :
```
contact@domaine.com
info@domaine.com
hello@domaine.com
bonjour@domaine.com
commercial@domaine.com
vente@domaine.com
sales@domaine.com
support@domaine.com
service@domaine.com
admin@domaine.com
direction@domaine.com
communication@domaine.com
marketing@domaine.com
webmaster@domaine.com
mail@domaine.com
accueil@domaine.com
reception@domaine.com
```

### Validation SMTP complète
Chaque email est testé avec :
1. ✅ **Syntaxe** : Format valide ?
2. ✅ **DNS MX** : Le domaine accepte les emails ?
3. ✅ **SMTP** : La boîte email existe vraiment ? (connexion SMTP code 250)

### Scoring intelligent
Score final = 70% validation + 30% pertinence du préfixe

Préfixe prioritaire (90 pts) :
- contact@, info@, hello@, commercial@, direction@, etc.

Préfixe nominatif (70 pts) :
- prenom.nom@domaine.com

Préfixe générique à éviter (10 pts) :
- noreply@, bounce@, marketing@

## 🚀 Usage

### Test sur petit échantillon
```bash
cd /var/www/Scrap_Email
python3 find_any_valid_email.py --limit 50 --concurrent 10
```

### Traitement complet
```bash
cd /var/www/Scrap_Email
python3 find_any_valid_email.py --concurrent 20 --batch-size 30
```

### En arrière-plan avec logs
```bash
cd /var/www/Scrap_Email
nohup python3 find_any_valid_email.py --concurrent 20 > find_emails.log 2>&1 &

# Suivre la progression
tail -f find_emails.log

# Monitoring
./monitor_find_emails.sh
```

## 📊 Paramètres

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| `--limit` | Nombre max de sites à traiter | Tous |
| `--concurrent` | Requêtes HTTP simultanées | 20 |
| `--batch-size` | Sites par lot | 50 |

## 💾 Données enregistrées

Pour chaque site, le script enregistre :

```python
site.emails = "contact@domaine.fr"           # Meilleur email trouvé
site.email_source = "any_valid_email"        # Ou "generic_validated"
site.email_validated = True
site.email_validation_score = 97            # Score 0-100
site.email_validation_status = "valid"      # valid / invalid / risky
site.email_deliverable = True               # Si SMTP OK
site.email_validation_details = {...}       # JSON détaillé
site.status = SiteStatus.EMAIL_FOUND
```

## 🔍 Sources d'emails

Le champ `email_source` permet d'identifier l'origine :

- **`any_valid_email`** : Email trouvé en scannant le site (Phase 1)
- **`generic_validated`** : Email générique validé SMTP (Phase 2)
- **`any_valid_all_failed`** : Aucun email valide trouvé

## 📈 Statistiques attendues

Basé sur les tests :
- **Taux de succès** : ~35-40%
- **Emails génériques validés** : ~85% des emails trouvés
- **Emails trouvés sur site** : ~15% des emails trouvés
- **Deliverable (SMTP OK)** : 100% des emails enregistrés

## ⚡ Performances

### Vitesse
- ~40 secondes par site (avec validation SMTP de 17 emails génériques)
- ~2-3 sites/minute en mode `--concurrent 20`

### Temps estimés
| Sites | Concurrent 10 | Concurrent 20 | Concurrent 30 |
|-------|---------------|---------------|---------------|
| 100 | ~1h | ~40min | ~30min |
| 1000 | ~10h | ~6-7h | ~5h |
| 5000 | ~50h (2j) | ~30h (1.25j) | ~24h (1j) |

## 🔒 Gestion des verrous DB

Le script utilise une **session SQLite dédiée par site** pour éviter les verrous :
- ✅ Timeout de 30 secondes
- ✅ Retry automatique (3 tentatives)
- ✅ Backoff exponentiel (2s, 4s, 6s)
- ✅ Compatible avec les autres services (Flask, daemon validation, etc.)

## 📝 Logs

Les logs sont enregistrés dans :
- `find_any_valid_email.log` (script principal)
- `find_emails_100.log` (exécution spécifique)

Format des logs :
```
🔍 Recherche email valide pour: domaine.fr
📥 Phase 1: Récupération de tous les emails du site...
✅ 3 email(s) trouvé(s) sur le site
🔍 Validation et scoring des emails trouvés...
  ✅ contact@domaine.fr | Validation: 100/100 | Préfixe: 90/100 | Total: 97/100 | Status: valid
🏆 MEILLEUR EMAIL SÉLECTIONNÉ - EMAIL TROUVÉ SUR SITE
✅ Email enregistré pour domaine.fr
```

## 🛠️ Monitoring

Utiliser le script de monitoring :
```bash
./monitor_find_emails.sh
```

Affiche :
- État du processus (PID, CPU, RAM)
- Nombre de sites traités
- Nombre d'emails trouvés
- Taux de succès
- Dernières lignes du log

## ⚠️ Notes importantes

### Ne traite PAS
- ✅ Les sites déjà avec un email
- ✅ Les sites blacklistés
- ✅ Les sites inactifs

### Traite seulement
- Sites avec `emails = NULL`
- Sites avec `emails = ""`
- Sites avec `emails = "NO EMAIL FOUND"`

### Filtrage automatique
Les emails génériques à risque sont automatiquement filtrés :
- Emails jetables (tempmail.com, guerrillamail.com, etc.)
- Faux positifs JavaScript/CSS
- Emails avec patterns invalides

## 🎯 Cas d'usage

### Campagne emailing
Filtrer les emails validés :
```sql
SELECT * FROM sites
WHERE email_source IN ('any_valid_email', 'generic_validated')
AND email_deliverable = TRUE
AND email_validation_score >= 70
```

### Différencier les sources
```sql
-- Emails trouvés sur site (plus pertinents)
SELECT * FROM sites WHERE email_source = 'any_valid_email'

-- Emails génériques validés (moins pertinents mais valides)
SELECT * FROM sites WHERE email_source = 'generic_validated'
```

## 🔄 Ré-exécution

Le script incrémente `retry_count` à chaque exécution. Pour réessayer les sites en échec :

```bash
# Réinitialiser les sites en échec
UPDATE sites
SET emails = NULL, email_source = NULL
WHERE email_source = 'any_valid_all_failed'
```

## 📞 Support

En cas de problème :
1. Vérifier les logs : `tail -f find_any_valid_email.log`
2. Vérifier le processus : `ps aux | grep find_any_valid_email`
3. Tuer le processus : `pkill -f find_any_valid_email.py`
4. Vérifier la base : `sqlite3 scrap_email.db "SELECT COUNT(*) FROM sites WHERE email_source = 'generic_validated'"`
