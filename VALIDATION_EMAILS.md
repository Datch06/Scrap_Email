# 📧 Système de Validation d'Emails

## Vue d'ensemble

Le système de validation d'emails vérifie la validité et la délivrabilité des emails collectés en 3 niveaux :

1. **Syntaxe** - Vérification du format de l'email
2. **DNS** - Vérification que le domaine existe et possède des serveurs mail (MX)
3. **SMTP** - Vérification que la boîte email existe réellement

## 📊 Statuts de validation

- **✅ VALID** (score 100/100) - Email valide et délivrable
- **❌ INVALID** (score 0-30/100) - Email invalide (syntaxe ou domaine inexistant)
- **⚠️ RISKY** (score 20-60/100) - Email risqué (jetable, serveur SMTP inaccessible, etc.)

## 🚀 Utilisation

### Méthode 1: Ligne de commande

```bash
cd /var/www/Scrap_Email

# Valider tous les emails
python3 validate_emails.py

# Valider uniquement les emails non encore validés
python3 validate_emails.py --only-new

# Limiter le nombre d'emails à valider
python3 validate_emails.py --limit 1000

# Combiner les options
python3 validate_emails.py --only-new --limit 500 --batch-size 50
```

### Méthode 2: Interface web (bientôt disponible)

Accédez à `http://admin.perfect-cocon-seo.fr/validation`

### Méthode 3: API

```bash
# Démarrer la validation
curl -X POST http://localhost:5000/api/validation/start \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "only_new": true}'

# Obtenir les statistiques
curl http://localhost:5000/api/validation/stats
```

## 📈 Champs ajoutés à la base de données

| Champ | Type | Description |
|-------|------|-------------|
| `email_validated` | Boolean | Email a été validé |
| `email_validation_score` | Integer (0-100) | Score de fiabilité |
| `email_validation_status` | String | 'valid', 'invalid', 'risky', 'unknown' |
| `email_validation_details` | JSON | Détails techniques (syntaxe, DNS, SMTP) |
| `email_validation_date` | DateTime | Date de validation |
| `email_deliverable` | Boolean | Email peut recevoir des messages |

## 🔍 Exemples de résultats

### Email valide
```
✅ contact@google.com
   Score: 100/100 | Status: valid
   Deliverable: Oui
   Syntaxe: Syntaxe valide
   DNS: 1 serveur(s) MX trouvé(s)
   SMTP: Boîte email existe (SMTP 250)
```

### Email invalide
```
❌ test@domaine-inexistant.com
   Score: 30/100 | Status: invalid
   Deliverable: Non
   Syntaxe: Syntaxe valide
   DNS: Domaine n'existe pas (NXDOMAIN)
```

### Email risqué
```
⚠️ test@tempmail.com
   Score: 20/100 | Status: risky
   Deliverable: Non
   Syntaxe: Syntaxe valide
   Détails: Email jetable détecté
```

## ⚙️ Configuration

### Timeout SMTP
Par défaut : 10 secondes. Modifiable dans `validate_emails.py` :

```python
self.timeout = 10  # secondes
```

### Cache DNS
Les enregistrements MX sont mis en cache pour accélérer les validations suivantes du même domaine.

### Pause entre validations
Une pause de 0.5 seconde est appliquée entre chaque validation pour ne pas surcharger les serveurs SMTP.

## 📊 Requêtes SQL utiles

### Emails valides uniquement
```sql
SELECT domain, emails, email_validation_score
FROM sites
WHERE email_validation_status = 'valid'
AND email_deliverable = 1
ORDER BY email_validation_score DESC;
```

### Emails à risque
```sql
SELECT domain, emails, email_validation_status, email_validation_details
FROM sites
WHERE email_validation_status = 'risky';
```

### Statistiques globales
```sql
SELECT
  email_validation_status,
  COUNT(*) as count,
  ROUND(AVG(email_validation_score), 1) as avg_score
FROM sites
WHERE email_validated = 1
GROUP BY email_validation_status;
```

## 🎯 Bonnes pratiques

1. **Validez progressivement** - Commencez par 100-500 emails pour tester
2. **Utilisez --only-new** - Évitez de revalider les emails déjà vérifiés
3. **Surveillez les logs** - Fichier `email_validation.log`
4. **Filtrez par score** - Utilisez les emails avec score ≥ 80 pour vos campagnes
5. **Respectez les serveurs** - La pause de 0.5s entre validations est importante

## ⚠️ Limitations

- Certains serveurs SMTP bloquent les vérifications
- Les emails "catch-all" retournent toujours 250 (faux positifs)
- La validation ne garantit pas 100% que l'email sera lu
- Certains domaines (Microsoft, Google) ont des protections anti-scraping

## 🔧 Dépannage

### "Timeout SMTP"
Le serveur mail est trop lent ou bloque les connexions. L'email est marqué comme "risky".

### "Serveur SMTP déconnecté"
Le serveur a fermé la connexion. Peut indiquer un système anti-spam. Email marqué "risky".

### "Email rejeté (SMTP 550)"
La boîte email n'existe pas. Email marqué "risky" ou "invalid".

## 📝 Logs

Les logs de validation sont dans :
- **Console** - Sortie standard
- **Fichier** - `email_validation.log`

Format :
```
2025-10-31 15:24:10,169 - INFO - 🔍 Validation: contact@example.com (example.com)
2025-10-31 15:24:13,169 - INFO -   ✅ VALID (score: 100/100) - Boîte email existe (SMTP 250)
```

## 🎓 Migration

Si vous avez déjà une base de données, exécutez :

```bash
python3 migrate_add_email_validation.py
```

Cela ajoutera les colonnes nécessaires sans perdre vos données existantes.

## 📞 Support

Pour toute question ou problème :
1. Vérifiez les logs : `email_validation.log`
2. Testez avec un email connu : `python3 test_validation.py`
3. Vérifiez la connexion réseau et DNS

---

**Créé le:** 31 octobre 2025
**Version:** 1.0
**Auteur:** Claude Code
