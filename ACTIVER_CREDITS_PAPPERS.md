# Comment Activer vos 100 Crédits Gratuits Pappers

Date: 2025-10-18

---

## Situation Actuelle

L'API Pappers retourne une erreur **401**:
```
"Vous n'avez plus assez de crédits pour effectuer cette requête"
```

Cela signifie que les 100 crédits gratuits ne sont **pas encore activés** ou ont été consommés.

---

## Étape 1 : Vérifier votre Compte Pappers

1. **Connectez-vous sur** [pappers.fr](https://www.pappers.fr)

2. **Allez dans votre espace membre**
   - Cliquez sur votre nom (en haut à droite)
   - Sélectionnez "Mon espace"

3. **Vérifiez vos crédits**
   - Section "Crédits API" ou "API"
   - Vous devriez voir: "Crédits disponibles: XXX"

---

## Étape 2 : Activer les Crédits Gratuits

### Si vous n'avez PAS les 100 crédits gratuits

**Option A : Offre Nouveau Compte**
- Certains comptes nouveaux ont 100 crédits d'essai
- Vérifiez dans "Offres" ou "Promotions"
- Activez l'offre d'essai si disponible

**Option B : Validation Email**
- Vérifiez que votre email est validé
- Consultez vos emails pour un lien de validation
- Les crédits gratuits nécessitent parfois une validation

**Option C : Support Pappers**
- Contactez le support: contact@pappers.fr
- Mentionnez que vous avez ouvert un compte
- Demandez l'activation des 100 crédits gratuits

---

## Étape 3 : Acheter des Crédits (si nécessaire)

### Pay-as-you-go (Recommandé pour tester)

**Prix**: ~0.02€ par requête

**Pour 100 requêtes**: ~2€
**Pour 791 requêtes** (tous les sites): ~16€

**Comment acheter**:
1. Espace membre → Crédits
2. "Acheter des crédits"
3. Sélectionner le montant
4. Paiement par CB

### Abonnements

| Plan | Prix | Requêtes/mois | Recommandation |
|------|------|---------------|----------------|
| **Starter** | 30€/mois | 2,000 | ✅ Bon pour commencer |
| **Pro** | 100€/mois | 10,000 | Pour usage intensif |
| **Enterprise** | Sur devis | Illimité | Pour grandes entreprises |

---

## Étape 4 : Vérifier que ça Fonctionne

Une fois les crédits activés/achetés:

```bash
cd /var/www/Scrap_Email

# Test rapide
python3 fetch_emails_from_pappers.py test
```

**Résultat attendu**:
```
✅ API fonctionne !
  Email trouvé: contact@exemple.fr
```

---

## Étape 5 : Lancer la Récupération

### Test avec 10 sites (Dry-run)

```bash
python3 fetch_emails_from_pappers.py dry-run 10
```

- ✅ Teste l'API sur 10 sites
- ✅ Affiche les emails trouvés
- ❌ N'écrit PAS en base de données
- 💰 Coût: 0€ (lecture seule)

### Production avec 100 sites

```bash
python3 fetch_emails_from_pappers.py
# Quand demandé, entrer: 100
```

- ✅ Récupère les emails
- ✅ Met à jour la base
- ✅ Marque `email_source='siret'`
- 💰 Coût: ~2€ (100 crédits)

### Production TOUS les sites (791)

```bash
python3 fetch_emails_from_pappers.py
# Quand demandé, appuyer sur Entrée (= tous)
```

- ✅ Traite les 791 sites avec SIRET sans email
- 💰 Coût: ~16€ (791 crédits)

---

## FAQ

### Q: Les 100 crédits gratuits sont-ils renouvelables ?

**R**: Non, généralement c'est une offre unique à l'inscription. Ensuite:
- Soit Pay-as-you-go (paiement à l'usage)
- Soit Abonnement mensuel

### Q: Combien d'emails puis-je obtenir avec 100 crédits ?

**R**:
- **100 requêtes** = 100 SIRET vérifiés
- **~75 emails** trouvés (taux de succès ~75%)
- **Nouveau taux d'emails**: ~4.4% (vs 1.8% actuel)

### Q: Que se passe-t-il si je n'ai plus de crédits ?

**R**: L'API retourne une erreur 401. Le script s'arrête proprement sans casser la base de données.

### Q: Puis-je annuler en cours de route ?

**R**: Oui, Ctrl+C pour arrêter. Les emails déjà récupérés seront sauvegardés.

---

## Alternatives Gratuites

Si vous ne souhaitez pas payer:

### 1. Scraping Manuel

Pour les sites importants, récupérer manuellement:
1. Chercher "nom entreprise SIRET email" sur Google
2. Consulter societe.com
3. Ajouter dans Google Sheets Feuille 3

### 2. API Data.gouv (Gratuite mais limitée)

L'API data.gouv.fr est gratuite mais ne fournit généralement PAS les emails.

### 3. Scraping Progressif

Utiliser le script de scraping web:
```bash
python3 extract_emails_db.py --limit 100
```

**Avantages**: Gratuit
**Inconvénients**: Plus lent, moins fiable

---

## Résumé des Coûts

| Action | Crédits | Coût | Emails attendus |
|--------|---------|------|-----------------|
| **Test (10 sites)** | 10 | ~0.20€ | ~7 |
| **100 sites** | 100 | ~2€ | ~75 |
| **Tous (791)** | 791 | ~16€ | ~593 |

---

## Prochaines Étapes

### ✅ Immédiat
1. Connectez-vous sur pappers.fr
2. Vérifiez vos crédits disponibles
3. Activez les 100 crédits gratuits OU achetez des crédits

### ✅ Ensuite
4. Testez: `python3 fetch_emails_from_pappers.py test`
5. Dry-run: `python3 fetch_emails_from_pappers.py dry-run 10`
6. Production: `python3 fetch_emails_from_pappers.py` (entrer 100)

### ✅ Vérification
7. Statistiques: `curl -s https://admin.perfect-cocon-seo.fr/api/stats`
8. Interface: https://admin.perfect-cocon-seo.fr

---

## Support

**Email Pappers**: contact@pappers.fr
**Documentation API**: https://www.pappers.fr/api/documentation

**En cas de problème avec le script**:
- Logs: `sudo journalctl -u scrap-email-interface.service -n 50`
- Documentation: [INTEGRATION_PAPPERS.md](INTEGRATION_PAPPERS.md:1)

---

**Une fois les crédits activés, vous pourrez récupérer automatiquement des centaines d'emails !** 🚀

Pour vérifier vos crédits: [Mon espace Pappers](https://www.pappers.fr/mon-espace)
