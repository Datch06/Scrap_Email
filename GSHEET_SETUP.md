# Configuration Google Sheets API

## Étape 1 : Installation des dépendances

```bash
pip install gspread oauth2client
```

## Étape 2 : Créer les credentials Google Cloud

1. Allez sur https://console.cloud.google.com/
2. Créez un nouveau projet (ou sélectionnez-en un existant)
3. Dans le menu, allez dans **APIs & Services** > **Library**
4. Recherchez et activez **Google Sheets API**
5. Allez dans **APIs & Services** > **Credentials**
6. Cliquez sur **Create Credentials** > **Service Account**
7. Donnez un nom au service account (ex: "sheets-uploader")
8. Cliquez sur **Create and Continue**
9. Sautez les permissions (cliquez **Continue** puis **Done**)
10. Cliquez sur le service account créé
11. Allez dans l'onglet **Keys**
12. Cliquez **Add Key** > **Create new key** > **JSON**
13. Le fichier JSON sera téléchargé - **renommez-le en `credentials.json`**
14. Placez `credentials.json` dans le dossier `/Users/datch/Scrap-Email/`

## Étape 3 : Partager le Google Sheet

1. Ouvrez le fichier `credentials.json` téléchargé
2. Trouvez la ligne `"client_email"` (ex: `"sheets-uploader@projet-123.iam.gserviceaccount.com"`)
3. Copiez cet email
4. Ouvrez votre Google Sheet : https://docs.google.com/spreadsheets/d/19p41GglQIybuD1MynMIOgtmWjNHfOAU9foLEzJN-t6I/edit
5. Cliquez sur **Partager** (en haut à droite)
6. Collez l'email du service account
7. Donnez les droits **Éditeur**
8. Cliquez **Envoyer**

## Étape 4 : Exécuter le script

```bash
cd /Users/datch/Scrap-Email/
python3 upload_to_gsheet.py domains_fr_only.txt
```

Le script va uploader les 131 domaines .fr dans votre Google Sheet !

## Dépannage

**Erreur "Spreadsheet not found"** → Vérifiez que vous avez bien partagé le sheet avec l'email du service account

**Erreur "credentials.json not found"** → Vérifiez que le fichier est bien dans le bon dossier

**Erreur d'import** → Installez les dépendances : `pip install gspread oauth2client`
