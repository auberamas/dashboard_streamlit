"""Page 3: what the data hides, how the comparisons are computed and what they cannot say"""

import pandas as pd
import streamlit as st

from utils import viz
from utils.compute import comparable_codes, fmt_int, fmt_num, fmt_pct, fmt_ratio
from utils.config import MAINLAND_LABEL, MIN_COVERAGE, MIN_REGION_SHARE, OVERSEAS_LABEL
from utils.io import get_data
from utils.prep import age_key
from utils.ui import build_filters, kpi, lecture, params, section

tables = get_data()
build_filters(tables, show=())

quality, meta = tables["quality"], tables["meta"]
checks = quality["checks"]
reg_cat, reg_age, nat_age, nat_cat = tables["reg_cat"], tables["reg_age"], tables["nat_age"], tables["nat_cat"]
dim, dim_region = tables["dim_patho"], tables["dim_region"]

CNAM_SOURCE = (
    "Cnam, *Méthodologie médicale de la cartographie des pathologies et des dépenses*, "
    "version G13 (années 2015 à 2024, tous régimes), mise à jour février 2026 "
)


def latex_number(value, digits=0):
    """Number written for LaTeX: thin space between thousands and a decimal comma"""
    text = f"{value:,.{digits}f}".replace(",", " ").replace(".", "{,}")
    return text.replace(" ", r"\,")


st.title("Qualité des données et limites")

# ** CHECKS **

columns = st.columns(4)
kpi(columns[0], "Lignes vérifiées", fmt_int(checks["rows"]))
kpi(columns[1], "Observations en doublon", fmt_int(checks["duplicated_observations"]),
    help="Même année, code, âge, sexe et territoire. Zéro doublon attendu.")
kpi(columns[2], "Effectifs masqués", fmt_pct(quality["missing_pct"]["nb_patients"]),
    help="Part des lignes où le producteur cache l'effectif, car il est trop petit.")
kpi(columns[3], "Contrôle : toutes régions", f"x{checks['national_std_ratio']:.3f}".replace(".", ","),
    help="Le rapport standardisé de toutes les régions réunies doit valoir 1,000. "
         "Le petit écart vient des cellules masquées et des arrondis.")

st.write(
    "Aucune observation en doublon et  la somme hommes plus femmes correspond aux valeurs indiquées "
    "pour les deux sexes (aux arrondis près). "
    f"Les rapports standardisés sont disponibles pour {fmt_pct(checks['std_available_pct'])} "
    "des couples région, catégorie et année (les autres sont trop masqués pour être calculés)."
)

# ** 1. MISSING VALUES **

section(1, "Trois sortes de valeurs manquantes",
        text="Le masquage n'est pas réparti au hasard : il touche les petits territoires et les "
             "catégories rares, donc d'abord l'outre-mer.")

st.markdown(
    """
| Colonnes | Cause | Traitement |
|---|---|---|
| `patho_l2`, `patho_l3` | **Manque structurel** : la ligne est un total, il n'y a rien à mettre au niveau inférieur. | Remplies par `full`, ce qui sert à identifier le niveau de chaque code. |
| `nb_patients`, `prev` | **Masquage** : effectif trop petit, caché par le producteur pour éviter de réidentifier des personnes. | Laissées vides, jamais remplacées par zéro et signalées par `is_masked`. |
"""
)

masked_by_area = reg_cat.groupby("area")["nb_patients"].apply(lambda column: 100 * column.isna().mean())
columns = st.columns(2)
kpi(columns[0], f"Effectifs régionaux masqués, {MAINLAND_LABEL}", fmt_pct(masked_by_area.get(MAINLAND_LABEL)))
kpi(columns[1], f"Effectifs régionaux masqués, {OVERSEAS_LABEL}", fmt_pct(masked_by_area.get(OVERSEAS_LABEL)),
    help="Catégories de niveau 1 et 2, toutes années. Le masquage frappe surtout les petites "
         "populations, donc l'outre-mer.")
params("plus la part est élevée, moins les comparaisons de cette zone sont solides")

left, right = st.columns(2)
with left:
    geo = quality["masked_pct_by_geo"].rename("part").reset_index()
    geo.columns = ["Niveau géographique", "Effectifs masqués (%)"]
    viz.show(viz.plain_bar(geo, x="Niveau géographique", y="Effectifs masqués (%)", text=".1f"))
    params("plus le territoire est fin, plus le masquage est fréquent")
with right:
    age = quality["masked_pct_age_by_region"].rename("part").reset_index()
    age.columns = ["Région", "Cellules d'âge masquées (%)"]
    viz.show(viz.plain_bar(age.sort_values("Cellules d'âge masquées (%)"),
                           x="Cellules d'âge masquées (%)", y="Région", orientation="h"))
    params("catégories de niveau 1, croisement région et classe d'âge")

worst = quality["masked_pct_age_by_region"].sort_values(ascending=False)
lecture(
    f"{worst.index[0]} et {worst.index[1]} concentrent le masquage ({fmt_pct(worst.iloc[0])} et "
    f"{fmt_pct(worst.iloc[1])} des cellules d'âge) : leurs rapports standardisés sont souvent "
    "indisponibles et leurs valeurs brutes doivent être lues avec prudence."
)

category = quality["masked_pct_by_category"].rename("part").reset_index()
category.columns = ["Catégorie", "Effectifs régionaux masqués (%)"]
category = category[category["Effectifs régionaux masqués (%)"] > 0]
if not category.empty:
    with st.expander("Masquage par catégorie de soins"):
        viz.show(viz.plain_bar(category.sort_values("Effectifs régionaux masqués (%)"),
                               x="Effectifs régionaux masqués (%)", y="Catégorie", orientation="h",
                               height=max(300, 30 * len(category) + 100)))

# ** 2. LIMITS **

section(3, "Limites d'interprétation")

st.markdown(
    """
* **Soins sont enregistrés** : il n'est pas question d'un état de santé. Les catégories ne sont pas déclarées par les patients :
  ce sont des algorithmes de la Cnam appliqués aux affections de longue durée, aux médicaments et aux
  hospitalisations. Une prévalence basse peut traduire moins de maladie, moins de dépistage ou moins de
  recours aux soins, sans qu'on puisse les départager.
* **Maladies et traitements sont liés par construction.** Un traitement hors pathologie exclut les
  personnes déjà repérées pour la maladie : mieux repérer la maladie fait baisser le traitement seul.
* **Standardisation sur l'âge seulement,** la précarité et l'offre de soins ne sont pas pris en compte.
* **La taille des territoires.** Mayotte et la Guyane ont des effectifs faibles et beaucoup de valeurs masquées.
"""
)

st.caption("Source de la méthode de repérage : " + CNAM_SOURCE)