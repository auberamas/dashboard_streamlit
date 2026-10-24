# Écarts territoriaux de soins enregistrés en France (2015-2024)

Tableau de bord Streamlit sur les effectifs de patients par pathologie, sexe, classe d'âge et
territoire publiés par l'[Assurance Maladie](https://www.data.gouv.fr/datasets/pathologies-effectif-de-patients-par-pathologie-sexe-classe-dage-et-territoire-departement-region)
([licence ODbL](https://opendatacommons.org/licenses/odbl/summary/)).

**Question** : comment les profils de soins enregistrés diffèrent entre la métropole et l'outre-mer,
quelles catégories creusent les écarts et ces écarts bougent-ils entre 2015 et 2024 ?

## Installation pas à pas

**Prérequis** : Python 3.12 et environ 3 Go d'espace disque si les données doivent être téléchargées.

1. Décompresser le projet puis ouvrir un terminal dans le dossier du projet.
2. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

4. Lancer le tableau de bord :

   ```bash
   python run.py
   ```

   Le navigateur s'ouvre sur http://localhost:8501.

**Premier lancement** : si le dossier `data/` contient déjà les fichiers, le tableau de bord s'ouvre
tout de suite. Sinon `run.py` télécharge `effectifs.csv` (environ 950 Mo) depuis data.gouv.fr puis
le nettoie, ce qui prend quelques minutes une seule fois.

**Relancer plus tard** : la même commande `python run.py`. Elle vérifie au passage si une nouvelle
version des données est publiée. Si la vérification échoue (pas de réseau par exemple), le tableau
de bord démarre quand même avec les données déjà présentes.

**Arrêter** : `Ctrl+C` dans le terminal

| Option de `run.py` | Effet |
|---|---|
| `--skip-update` | ne cherche pas de nouvelle version des données |
| `--port 8502` | change le port si 8501 est déjà pris |
| `--no-browser` | n'ouvre pas le navigateur |

## Le tableau de bord

| Page | Contenu |
|---|---|
| Les données | composition du jeu de données, les deux territoires comparés, classement national, profils par âge et par sexe, évolution sur dix ans |
| Analyse territoriale | profils de population, heatmap région x catégorie, sous-catégories de niveau 2, cartes, évolution des écarts, maladies et traitements |
| Qualité et limites | valeurs masquées, méthode des comparaisons avec un exemple de calcul interactif, limites d'interprétation |

Les filtres de la barre latérale (période, région, catégorie, comparaison brute ou standardisée,
sexe) sont partagés entre les pages. Chaque page n'affiche que ceux qui agissent sur elle.

## Données et mise à jour

`python cleaning_analysis/clean.py` relance seul le nettoyage. Il produit `data/effectifs_clean.csv`,
`processing/measures.csv` et `processing/tables.pkl`. Chaque fichier est écrit sous un nom
temporaire puis renommé, donc un échec en cours de route ne laisse jamais de fichier tronqué.

## Organisation

```
├── run.py                      # point d'entrée unique : données puis tableau de bord
├── app.py                      # application Streamlit : style, en-tête, pages et pied de page
├── views/                      # les trois pages
├── cleaning_analysis/
│   ├── clean.py                # nettoyage, utilisable seul
│   └── analyse_effectifs.ipynb # exploration et choix des analyses
├── utils/
│   ├── config.py               # constantes, couleurs et chemins
│   ├── prep.py                 # construction des tables
│   ├── tables.py               # lecture et écriture des tables
│   ├── datagouv.py             # téléchargement depuis data.gouv.fr
│   ├── state.py                # version locale des données (data/state.json)
│   ├── io.py                   # cache du tableau de bord
│   ├── compute.py              # mesures et formats
│   ├── viz.py                  # graphiques
│   └── ui.py                   # style, en-tête, pied de page et filtres
├── processing/                 # tables préparées et sous-catégories retenues
├── tests/                      # tests du lanceur
└── image/                      # logo
```
