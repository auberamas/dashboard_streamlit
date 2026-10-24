"""Page 1: what the dataset contains and the two territories the dashboard compares"""

import numpy as np
import pandas as pd
import streamlit as st

from utils import viz
from utils.compute import fmt_int, fmt_num, fmt_pct
from utils.config import MAINLAND_LABEL, MATERNITY_CODE, OVERSEAS_LABEL, SEX_COLORS, SEX_VIEWS, TYPE_ORDER
from utils.io import get_data
from utils.prep import age_key
from utils.ui import build_filters, kpi, lecture, params, section, selected_codes, varies

tables = get_data()
filters = build_filters(tables, show=("period", "category", "sex"))

nat_cat, nat_age = tables["nat_cat"], tables["nat_age"]
dim, meta, reg_pop = tables["dim_patho"], tables["meta"], tables["reg_pop"]
first_year, last_year = filters.years
codes = selected_codes(filters, dim)

# every chart of this page uses the mean over the chosen period so both ends of the slider act
in_period = nat_cat["year"].between(first_year, last_year)
both_sexes = nat_cat["sex"] == 9
period_rows = (nat_cat[in_period & both_sexes]
               .groupby(["patho_code", "patho_label", "patho_l1", "patho_l2", "level", "motif_type"], as_index=False)
               .agg(nb_patients=("nb_patients", "mean"), prev=("prev", "mean")))

st.title("Soins enregistrés en France : métropole et outre-mer, 2015-2024")
st.write(
    "Ce dashboard est consacré à une analyse des disparités territoriales entre l'outre-mer et la métropole "
    "concernant les pathologies et plus largement l'accès aux soins. Cette analyse est effectuée sur le jeu de "
    "données [Pathologies : effectif de patients par pathologie, sexe, classe d'âge et territoire (département, "
    "région)](https://www.data.gouv.fr/datasets/pathologies-effectif-de-patients-par-pathologie-sexe-classe-dage-et-territoire-departement-region)"
    " fourni par la Caisse nationale de l'Assurance Maladie (Cnam). Cette première page présente le jeu de "
    "données pour mieux comprendre l'analyse présentée sur la deuxième page."
)
st.subheader("Que contiennent les données de l'Assurance Maladie ?")

# ** WHAT THE DATASET IS **

st.write(
    "Les données comptent les personnes affiliées à l'Assurance Maladie ayant eu un remboursement "
    "au cours d'une année. La **prévalence** est la part de cette population enregistrée pour une "
    "maladie, un traitement chronique ou un autre motif de recours aux soins. "
    f"Chaque effectif est décliné par année, par classe d'âge ({meta['n_age_groups']} tranches de 5 ans), "
    "par sexe et par territoire.\n\n"
    "Le jeu de données en quelques chiffres :"
)

columns = st.columns(4)
kpi(columns[0], "Nombre de lignes", fmt_int(meta["rows"]), f"{meta['columns']} variables", delta_arrow="off")
kpi(columns[1], "Période", f"{meta['year_min']}-{meta['year_max']}", f"{meta['n_years']} années", delta_arrow="off")
kpi(columns[2], "Territoires", f"{meta['n_regions']} régions", f"et {meta['n_departments']} départements", delta_arrow="off")
kpi(columns[3], "Catégories de soins", f"{meta['n_codes']} codes", "sur 3 niveaux de détail", delta_arrow="off")

# ** 1. COMPOSITION OF THE DATASET **

section(1, "De quoi sont faites les catégories de soins ?",
        text="Deux grilles se croisent : trois niveaux de détail et trois types de motif. "
             "Ils décident de ce qui peut être comparé à quoi.")


def treemap_frame(rows):
    """One row per code with its parent and the size to draw

    A person can be in several sub-groups so the children of a family add up to more than the
    family. Each child is scaled down so the children share the size of their parent in
    proportion to their own count. The true count stays in the real column for the hover
    """
    rows = rows.dropna(subset=["nb_patients"])
    rows = rows.assign(label=rows["patho_label"].str.split(" (", regex=False).str[0], real=rows["nb_patients"])
    level1 = rows[rows["level"] == 1].assign(id=lambda f: f["patho_code"], parent="")
    level2 = rows[rows["level"] == 2].assign(id=lambda f: f["patho_code"])
    level3 = rows[rows["level"] == 3].assign(id=lambda f: f["patho_code"])

    # the parent of a level 2 code is the family with the same level 1 name
    level2["parent"] = level2["patho_l1"].map(level1.set_index("patho_l1")["id"])
    # the parent of a level 3 code is the sub-group with the same level 1 and level 2 names
    keys = level2.set_index(["patho_l1", "patho_l2"])["id"]
    level3["parent"] = [keys.get((one, two)) for one, two in zip(level3["patho_l1"], level3["patho_l2"])]

    frame = pd.concat([level1, level2, level3], ignore_index=True).dropna(subset=["parent"])
    frame["value"] = frame["real"].astype(float)
    for level in (2, 3):
        children = frame["level"] == level
        size = frame.set_index("id")["value"]
        total = frame[children].groupby("parent")["value"].transform("sum")
        room = frame.loc[children, "parent"].map(size)
        # shrink only when the children overflow their parent with a tiny margin for rounding
        factor = (room / total).clip(upper=1) * 0.99999
        frame.loc[children, "value"] = frame.loc[children, "value"] * factor
    return frame[["id", "parent", "label", "value", "real", "motif_type", "level"]]


left, right = st.columns([3, 2])

with left:
    st.subheader("Trois niveaux de détail")
    varies("period")
    st.caption(
        f"{(dim['level'] == 1).sum()} catégories de niveau 1, {(dim['level'] == 2).sum()} sous-groupes "
        f"de niveau 2 et {(dim['level'] == 3).sum()} détails de niveau 3."
    )
    viz.show(viz.treemap(treemap_frame(period_rows)))
    params(f"France, moyenne annuelle {filters.period}, tous âges, les deux sexes",
           "cliquer sur une case pour zoomer")
    st.caption(
        "Une personne peut appartenir à plusieurs sous-groupes : à l'intérieur d'une catégorie, "
        "les sous-groupes se partagent sa surface au prorata de leurs effectifs. La surface donne "
        "une proportion, le survol donne le vrai nombre de patients."
    )

with right:
    st.subheader("Trois types de motif")
    varies("period")
    by_type = (period_rows[period_rows["level"] == 1].groupby("motif_type", as_index=False)
               .agg(patients=("nb_patients", "sum"), familles=("patho_code", "nunique")))
    by_type["motif_type"] = pd.Categorical(by_type["motif_type"], TYPE_ORDER, ordered=True)
    by_type = by_type.sort_values("motif_type").assign(motif_type=lambda f: f["motif_type"].astype(str))
    st.caption(", ".join(f"{row.motif_type} : {row.familles} catégories " for row in by_type.itertuples()))
    total = by_type["patients"].sum()
    viz.show(viz.donut(by_type, "motif_type", "patients",
                       f"{total / 1e6:.1f} M".replace(".", ",") + "<br>prises en charge"))
    params(f"France, moyenne annuelle {filters.period}, catégorie de niveau 1, tous âges, les deux sexes")
    st.caption(
        "Une personne prise en charge pour plusieurs motifs est comptée une fois par motif : "
        "ce sont des prises en charge, pas des personnes."
    )

shares = by_type.set_index("motif_type")["patients"] / total * 100
biggest_family = period_rows[period_rows["level"] == 1].sort_values("nb_patients", ascending=False).iloc[0]
lecture(
    f"Sur {filters.period}, les maladies identifiées représentent {fmt_pct(shares['Maladie identifiée'])} "
    f"des prises en charge enregistrées, mais les traitements délivrés sans maladie repérée en "
    f"pèsent déjà {fmt_pct(shares['Traitement hors pathologie'])}. "
    f"La catégorie la plus nombreuse est {biggest_family['patho_label'].lower()} "
    f"({fmt_int(biggest_family['nb_patients'])} patients par an en moyenne)."
)

with st.expander("Détail des 3 motifs"):
    st.markdown(
        "* Une *maladie identifiée* est repérée par l'Assurance Maladie à partir des diagnostics, "
        "des affections de longue durée et des médicaments (voir la page Qualité et limites).\n"
        "* Un *traitement hors pathologie* est un traitement chronique délivré sans maladie "
        "repérée : la catégorie est définie par exclusion.\n"
        "* Les *autres motifs* regroupent la maternité, l'hospitalisation pour Covid-19 et les "
        "affections de longue durée pour d'autres causes.\n"
    )

# ** 2. THE TWO TERRITORIES **

section(2, "Outre-mer vs métropole",
        varies_with=("period",),
        text="Toute la suite oppose 13 régions métropolitaines à 5 régions d'outre-mer (Guadeloupe, "
             "La Réunion, Guyane, Martinique et Mayotte). Elles ne pèsent pas le même poids et n'ont "
             "pas la même répartition par âge.")


def age_shares(year):
    """Total population and share of the 65 and over and of the under 20 for each zone"""
    pop = reg_pop[reg_pop["year"] == year]
    totals = pop.groupby("area")["pop"].sum()
    seniors = pop[pop["mid"] >= 65].groupby("area")["pop"].sum() / totals * 100
    young = pop[pop["mid"] < 20].groupby("area")["pop"].sum() / totals * 100
    return totals, seniors, young


totals, seniors, young = age_shares(last_year)
_, seniors_start, _ = age_shares(first_year)

columns = st.columns(4)
kpi(columns[0], f"Population, {MAINLAND_LABEL}", fmt_int(totals[MAINLAND_LABEL]), "consommants")
kpi(columns[1], f"Population, {OVERSEAS_LABEL}", fmt_int(totals[OVERSEAS_LABEL]),
    f"{fmt_num(100 * totals[OVERSEAS_LABEL] / totals.sum())} % du total")
kpi(columns[2], "65 ans et plus, outre-mer", fmt_pct(seniors[OVERSEAS_LABEL]),
    f"contre {fmt_pct(seniors[MAINLAND_LABEL])} en métropole")
kpi(columns[3], "Moins de 20 ans, outre-mer", fmt_pct(young[OVERSEAS_LABEL]),
    f"contre {fmt_pct(young[MAINLAND_LABEL])} en métropole")
params(f"population consommante en {last_year}, les deux sexes")

text = (
    f"L'outre-mer pèse {fmt_num(100 * totals[OVERSEAS_LABEL] / totals.sum())} % de la population "
    f"consommante et sa population est nettement plus jeune : {fmt_pct(seniors[OVERSEAS_LABEL])} "
    f"de 65 ans et plus contre {fmt_pct(seniors[MAINLAND_LABEL])} en métropole. "
)
if first_year < last_year:
    gain_overseas = seniors[OVERSEAS_LABEL] - seniors_start[OVERSEAS_LABEL]
    gain_mainland = seniors[MAINLAND_LABEL] - seniors_start[MAINLAND_LABEL]
    faster = "plus vite" if gain_overseas > gain_mainland else "moins vite"
    text += (
        f"\n\nEntre {first_year} et {last_year}, la part des 65 ans et plus gagne "
        f"{fmt_num(gain_overseas)} points en outre-mer contre {fmt_num(gain_mainland)} en métropole : "
        f"l'outre-mer vieillit {faster} que la métropole. Un écart mesuré sur des prévalences brutes "
        "bougerait donc au fil des années pour des raisons purement démographiques."
    )
lecture(text)

# ** 3. NATIONAL RANKING **

section(3, "Quelles catégories de soins ressortent au niveau national ?",
        varies_with=("period", "category"),
        text="Les catégories de soins de niveau 1 sont classées par prévalence moyenne sur la période. "
             "La couleur distingue les maladies identifiées des traitements délivrés sans "
             "maladie repérée.")

viz.show(viz.ranking_bar(filters.ranking, highlight=None if filters.all_categories else filters.category_label))
params(f"France entière, tous âges, les deux sexes, {filters.period}",
       "l'hospitalisation pour Covid-19 n'existe qu'à partir de 2020")

top = filters.ranking.sort_values("prev", ascending=False).reset_index(drop=True)
treatments = filters.ranking[filters.ranking["motif_type"] == "Traitement hors pathologie"]["prev"].sum()
text = (
    f"Les deux premières positions ne sont pas des maladies : les traitements délivrés hors "
    f"pathologie repérée pèsent {fmt_pct(treatments)} de la population consommante, devant "
    f"{top['patho_label'].iloc[2].lower()} ({fmt_pct(top['prev'].iloc[2])}). "
    "Lire ces données uniquement par le prisme des maladies ferait donc perdre une partie importante."
)
if not filters.all_categories and filters.category_label in top["patho_label"].values:
    rank = int(top.index[top["patho_label"] == filters.category_label][0]) + 1
    value = top.loc[rank - 1, "prev"]
    text += (
        f" La catégorie choisie, {filters.category_label.lower()}, arrive en position {rank} sur {len(top)} "
        f"avec {fmt_pct(value)} de la population consommante."
    )
lecture(text)

# ** 4. WHO IS CONCERNED: AGE AND SEX **

section(4, "Qui est concerné : âge et sexe",
        varies_with=("period", "category", "sex"),
        text="Presque toutes les catégories deviennent plus fréquentes avec l'âge. C'est le "
             "premier facteur à prendre en compte avant de comparer deux territoires qui n'ont pas "
             "la même répartition d'âges.")

ages_in_period = nat_age[nat_age["year"].between(first_year, last_year)]
left, right = st.columns(2)

with left:
    st.subheader("Profil par âge")
    varies("period", "category", "sex")
    if filters.all_categories:
        st.info("Choisissez une catégorie dans la barre latérale pour voir son profil par âge.")
    else:
        sexes = SEX_VIEWS[filters.sex_view]
        profile = (ages_in_period[ages_in_period["patho_code"].isin(codes) & ages_in_period["sex"].isin(sexes)]
                   .groupby(["age_gp", "sex"], as_index=False)["prev"].mean())
        profile["Sexe"] = profile["sex"].map(sexes)
        order = sorted(profile["age_gp"].unique(), key=age_key)
        viz.show(viz.category_line(
            profile.sort_values("age_gp", key=lambda s: s.map(age_key)),
            x="age_gp", y="prev", color="Sexe", order=order, colors=SEX_COLORS,
            labels={"age_gp": "Classe d'âge", "prev": "Prévalence (%)", "Sexe": ""},
        ))
        params(filters.category_label, f"France, moyenne annuelle {filters.period}", filters.sex_view.lower())

with right:
    st.subheader("Hommes et femmes, une catégorie par point")
    varies("period", "category")
    sex_wide = (nat_cat[in_period & (nat_cat["level"] == 1) & nat_cat["sex"].isin([1, 2])]
                .pivot_table(index="patho_label", columns="sex", values="prev", aggfunc="mean")
                .rename(columns={1: "Hommes", 2: "Femmes"}).dropna().reset_index())
    viz.show(viz.scatter(
        sex_wide, x="Hommes", y="Femmes", color=None, hover="patho_label", diagonal=True,
        labels={"Hommes": "Prévalence chez les hommes (%)", "Femmes": "Prévalence chez les femmes (%)"},
        height=390, highlight=None if filters.all_categories else filters.category_label,
    ))
    params(f"France, moyenne annuelle {filters.period}, tous âges",
           "au-dessus de la diagonale : plus fréquent chez les femmes")

text = (
    "Le profil par âge explique l'essentiel des écarts de prévalence et les écarts entre sexes "
    "restent modestes en dehors de la maternité et des cancers spécifiques. "
    "Une comparaison entre territoires devra donc d'abord corriger l'effet de l'âge."
)
# the largest gap between men and women once maternity is left aside
maternity_label = dim.loc[dim["patho_code"] == MATERNITY_CODE, "patho_label"]
gaps = sex_wide[~sex_wide["patho_label"].isin(maternity_label)].copy()
gaps["gap"] = np.log(gaps["Femmes"] / gaps["Hommes"]).abs()
if not gaps.empty:
    widest = gaps.sort_values("gap", ascending=False).iloc[0]
    text += (
        f"\n\nHors maternité, l'écart entre sexes le plus marqué concerne {widest['patho_label'].lower()} : "
        f"{fmt_pct(widest['Femmes'])} des femmes contre {fmt_pct(widest['Hommes'])} des hommes."
    )
if not filters.all_categories and not profile.empty:
    by_age = profile.groupby("age_gp")["prev"].mean()
    young_age, old_age = by_age.get("40-44"), by_age.get("75-79")
    if young_age and old_age:
        text += (
            f" Pour {filters.category_label.lower()}, la prévalence passe de {fmt_pct(young_age)} "
            f"chez les 40-44 ans à {fmt_pct(old_age)} chez les 75-79 ans, soit "
            f"{fmt_num(old_age / young_age)} fois plus."
        )
lecture(text)

# ** 5. TEN YEARS OF NATIONAL CHANGE **

section(5, "Dix ans d'évolution nationale",
        varies_with=("period", "category"),
        text="Les niveaux de prévalence sont très différents d'une catégorie à l'autre, donc chaque courbe "
             "est ramenée à 100 sur la première année de la période pour comparer les rythmes d'évolution.")

biggest = filters.ranking.sort_values("prev", ascending=False)["patho_label"].head(8).tolist()
if not filters.all_categories and filters.category_label not in biggest:
    biggest.append(filters.category_label)

trend = nat_cat[both_sexes & in_period & (nat_cat["level"] == 1) & nat_cat["patho_label"].isin(biggest)].copy()
base = trend.sort_values("year").groupby("patho_label")["prev"].transform("first")
trend["indice"] = 100 * trend["prev"] / base

if trend["year"].nunique() >= 2:
    viz.show(viz.line(
        trend, x="year", y="indice", color="patho_label", hline=100, height=430,
        labels={"year": "Année", "indice": f"Prévalence (base 100 en {first_year})", "patho_label": ""},
        highlight=None if filters.all_categories else filters.category_label,
    ))
    params(f"France, tous âges, les deux sexes, {filters.period}",
           "les 8 catégories les plus fréquentes et la catégorie sélectionnée")
    change = trend.sort_values("year").groupby("patho_label")["indice"].last().sort_values()
    rising = int((change > 100).sum())
    lecture(
        f"Sur la période, {change.index[-1].lower()} progresse le plus vite "
        f"(indice {change.iloc[-1]:.0f}) et {change.index[0].lower()} est la prévalence qui diminue le plus "
        f"(indice {change.iloc[0]:.0f}). {rising} des {len(change)} catégories affichées progressent, "
        "ce qui suit le vieillissement de la population.\n\n"
        "Ces moyennes nationales ne disent cependant rien des territoires : c'est l'objet de la "
        "page suivante."
    )
else:
    st.info("Choisissez une période d'au moins deux années pour voir l'évolution.")
