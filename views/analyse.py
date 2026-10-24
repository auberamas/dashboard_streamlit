"""Page 2: how the five overseas regions part from the mainland and what explains it"""

import numpy as np
import pandas as pd
import streamlit as st

from utils import viz
from utils.compute import (
    annual_ratio, category_ratio, fmt_num, fmt_pct, fmt_ratio, fmt_signed, gap_trend,
    geo_mean, informative_level2, pooled_prevalence, pooled_ratio, ratio_list,
)
from utils.config import (
    AREA_COLORS, CARE_PAIRS, COLORS, HOSPITAL_CODE, MAINLAND, MAINLAND_LABEL, NO_CARE_CODE,
    OVERSEAS, OVERSEAS_LABEL,
)
from utils.io import get_data
from utils.prep import age_key
from utils.ui import (
    build_filters, fact_cards, focus_regions, lecture, params, section, selected_codes,
    tone_of, type_groups, varies,
)

tables = get_data()
filters = build_filters(tables, show=("period", "region", "category", "basis"))

dim, dim_region = tables["dim_patho"], tables["dim_region"]
reference = tables["reference"]
first_year, last_year = filters.years

# ** DATA PREPARATION **

# regional rows of the period with the ratio of the chosen basis in one column
reg = tables["reg_cat"][tables["reg_cat"]["year"].between(first_year, last_year)].copy()
reg["ratio_basis"] = reg[filters.ratio_col]
reg1 = reg[reg["level"] == 1]

focus = focus_regions(filters, dim_region)
codes = selected_codes(filters, dim)
comparable = filters.codes_all

# one mean ratio per region and level 1 category over the period
matrix_rows = reg1.dropna(subset=["ratio_basis"]).groupby(
    ["region", "region_name", "area", "patho_code", "patho_label"], as_index=False,
).agg(prev=("prev", "mean"), prev_france=("prev_france", "mean"), ratio=("ratio_basis", "mean"))

# one value per region for the map
if filters.all_categories:
    in_all = matrix_rows[matrix_rows["patho_code"].isin(comparable)]
    region_values = in_all.groupby(["region", "region_name", "area"], as_index=False).agg(
        ratio=("ratio", geo_mean), n_categories=("ratio", "count"),
    )
    region_values = region_values[region_values["n_categories"] >= 0.8 * len(comparable)]
else:
    region_values = matrix_rows[matrix_rows["patho_code"].isin(codes)][
        ["region", "region_name", "area", "prev", "prev_france", "ratio"]
    ]

# annual ratios of the focus of the mainland and of the overseas regions
focus_years = annual_ratio(reg1, focus, codes, filters.basis)
mainland_years = annual_ratio(reg1, MAINLAND, codes, filters.basis)
overseas_years = focus_years if filters.all_regions else annual_ratio(reg1, OVERSEAS, codes, filters.basis)

# ratio of every comparable category in the focus and in the mainland per year and on average
focus_by_year = category_ratio(reg1, focus, comparable, filters.basis)
focus_by_cat = focus_by_year.groupby("patho_label")["ratio"].mean().sort_values(ascending=False)
mainland_by_cat = category_ratio(reg1, MAINLAND, comparable, filters.basis).groupby("patho_label")["ratio"].mean()


def far_from_france(ratios):
    """Number of categories more than 20 % away from France on the log scale"""
    return int(((ratios < 0.8) | (ratios > 1.25)).sum())


# ** HEADER AND KEY FIGURES **

st.title("Outre-mer et métropole : deux profils de soins enregistrés")
st.subheader(
    "Quelles catégories de soins séparent les cinq régions d'outre-mer de la métropole et ces écarts "
    "se creusent-ils entre 2015 et 2024 ?"
)
st.write(
    "Cette page est consacrée à l'analyse du jeu de données de la Cnam, avec pour axe les disparités "
    "entre les régions d'outre-mer et la métropole.\n\n En quelques chiffres :"
)
st.caption(f"Sélection : {filters.focus_name}, {filters.category_label}, {filters.period}, {filters.basis_text}")

if len(focus_by_cat):
    top, bottom = focus_by_cat.index[0], focus_by_cat.index[-1]
    fact_cards([
        {
            "label": f"Catégories éloignées de la France ({filters.focus_name.lower()})",
            "value": f"{far_from_france(focus_by_cat)} / {len(focus_by_cat)}",
            "delta": f"contre {far_from_france(mainland_by_cat)} / {len(mainland_by_cat)} en métropole",
            "help": "Catégories dont le rapport à la France est sous x0,8 ou au-dessus de x1,25.",
        },
        {
            "label": "Plus fort excès",
            "value": fmt_ratio(focus_by_cat.iloc[0]),
            "delta": f"{top}, métropole {fmt_ratio(mainland_by_cat.get(top))}",
            "tone": "high",
        },
        {
            "label": "Plus fort déficit",
            "value": fmt_ratio(focus_by_cat.iloc[-1]),
            "delta": f"{bottom}, métropole {fmt_ratio(mainland_by_cat.get(bottom))}",
            "tone": "low",
        },
    ], name="top")
else:
    st.info("Aucune valeur comparable pour cette sélection.")
varies("period", "region", "basis")

# ** 1. POPULATION PROFILES **

section(1, "Pourquoi les deux populations ne sont pas comparables telles quelles ?",
        varies_with=("period", "category"),
        text="Avant d'interpréter un écart, il faut savoir ce qui, dans la population, le produit "
             "mécaniquement, c'est-à-dire l'âge ici.")

pop = tables["reg_pop"][tables["reg_pop"]["year"].between(first_year, last_year)]
left, right = st.columns(2)

with left:
    st.subheader("Un outre-mer plus jeune, classe d'âge par classe d'âge")
    varies("period")
    shares = pop.groupby(["area", "age_gp"], as_index=False)["pop"].sum()
    shares["share"] = 100 * shares["pop"] / shares.groupby("area")["pop"].transform("sum")
    age_order = sorted(shares["age_gp"].unique(), key=age_key)
    wide = shares.pivot(index="age_gp", columns="area", values="share").reindex(age_order)
    viz.show(viz.age_gap(age_order, wide[OVERSEAS_LABEL] - wide[MAINLAND_LABEL], height=400))
    params(f"population consommante, {filters.period}, les deux sexes",
           "au-dessus de zéro : la classe d'âge pèse plus en outre-mer")

with right:
    st.subheader("Âge moyen de chaque région")
    varies("period")
    weighted = pop.assign(years=pop["mid"] * pop["pop"])
    ages = weighted.groupby(["region_name", "area"], as_index=False)[["years", "pop"]].sum()
    ages["age_moyen"] = ages["years"] / ages["pop"]
    national_age = weighted["years"].sum() / weighted["pop"].sum()
    viz.show(viz.ranked_bar(ages, "age_moyen", "region_name", reference=national_age, height=430,
                            labels={"age_moyen": "Âge moyen (années)", "region_name": "", "area": ""}))
    params(f"population consommante, {filters.period}",
           f"la ligne pointillée est la moyenne nationale ({fmt_num(national_age)} ans)")

blocks = pop.assign(bloc=np.where(pop["mid"] < 20, "Moins de 20 ans",
                                  np.where(pop["mid"] < 65, "20 à 64 ans", "65 ans et plus")))
blocks = blocks.groupby(["area", "bloc"], as_index=False)["pop"].sum()
blocks["share"] = 100 * blocks["pop"] / blocks.groupby("area")["pop"].transform("sum")
seniors = blocks[blocks["bloc"] == "65 ans et plus"].set_index("area")["share"]
youngest = ages.sort_values("age_moyen").iloc[0]
lecture(
    f"Sur {filters.period}, les 65 ans et plus représentent {fmt_pct(seniors[MAINLAND_LABEL])} de la "
    f"population consommante en métropole contre {fmt_pct(seniors[OVERSEAS_LABEL])} en outre-mer "
    f"et la région la plus jeune est {youngest['region_name']} "
    f"({youngest['age_moyen']:.0f} ans de moyenne contre {national_age:.0f} au niveau national). "
    "Toute catégorie qui augmente avec l'âge y paraîtra moins fréquente, sans qu'aucun soin ne manque."
)

left, right = st.columns(2)

with left:
    st.subheader("Profil par âge, métropole et outre-mer")
    varies("period", "category")
    if filters.all_categories:
        st.info("Choisissez une catégorie dans la barre latérale pour voir son profil par âge.")
    else:
        reg_age = tables["reg_age"]
        age_rows = reg_age[reg_age["year"].between(first_year, last_year) & reg_age["patho_code"].isin(codes)]
        parts = []
        for area, expected in ((MAINLAND_LABEL, len(MAINLAND)), (OVERSEAS_LABEL, len(OVERSEAS))):
            part = pooled_prevalence(age_rows[age_rows["area"] == area], ["age_gp"], expected)
            parts.append(part.assign(area=area))
        area_age = pd.concat(parts, ignore_index=True).dropna(subset=["prev"])
        viz.show(viz.category_line(
            area_age.sort_values("age_gp", key=lambda s: s.map(age_key)),
            x="age_gp", y="prev", color="area", order=age_order, colors=AREA_COLORS,
            labels={"age_gp": "Classe d'âge", "prev": "Prévalence (%)", "area": ""},
        ) if not area_age.empty else None)
        params(f"{filters.category_label}, {filters.period}, les deux sexes",
               "classes d'âge masquées dans plus de 20 % des régions d'une zone : omises")

with right:
    st.subheader("Ce que la correction par l'âge change")
    varies("period", "category")
    per_code = reg1[reg1["region"].isin(OVERSEAS) & reg1["patho_code"].isin(codes)].groupby(
        ["region_name", "patho_code"], as_index=False,
    ).agg(raw=("raw_ratio", "mean"), std=("std_ratio", "mean"))
    pairs = per_code.groupby("region_name", as_index=False).agg(raw=("raw", geo_mean), std=("std", geo_mean))
    viz.show(viz.dumbbell(pairs, "region_name", "raw", "std", "Prévalence brute", "Standardisé sur l'âge", height=400))
    params(f"{filters.period}, {filters.category_label.lower()}, rapports annuels moyens",
           "un trait vers la droite : la jeunesse cachait une partie de l'excès")

raw_pooled = annual_ratio(reg1, OVERSEAS, codes, "Prévalence brute")["ratio"].mean()
std_pooled = annual_ratio(reg1, OVERSEAS, codes, "Standardisé sur l'âge")["ratio"].mean()
if pd.notna(raw_pooled) and pd.notna(std_pooled):
    if std_pooled > raw_pooled * 1.05:
        verdict = "la jeunesse de la population cachait donc un excès réel"
    elif std_pooled < raw_pooled / 1.05:
        verdict = "l'écart brut était donc en partie un effet d'âge"
    else:
        verdict = "l'âge n'explique donc presque rien ici"
    text = (
        f"Pour {filters.category_label.lower()}, l'outre-mer passe de {fmt_ratio(raw_pooled)} de la "
        f"France en brut à {fmt_ratio(std_pooled)} après correction de l'âge : {verdict}."
    )
    # the same correction for every category shows how general the effect is
    overseas_rows = reg1[reg1["region"].isin(OVERSEAS) & reg1["patho_code"].isin(comparable)]
    raw_by_cat = pooled_ratio(overseas_rows, ["patho_label"], len(OVERSEAS), "Prévalence brute").set_index("patho_label")["ratio"]
    std_by_cat = pooled_ratio(overseas_rows, ["patho_label"], len(OVERSEAS), "Standardisé sur l'âge").set_index("patho_label")["ratio"]
    shift = (std_by_cat - raw_by_cat).dropna().sort_values(ascending=False)
    if len(shift):
        text += (
            f" Sur l'ensemble des catégories, la correction relève le rapport de l'outre-mer pour "
            f"{int((shift > 0).sum())} catégories sur {len(shift)}, jusqu'à {fmt_signed(shift.iloc[0])} "
            f"pour {shift.index[0].lower()} : sans elle, les écarts seraient sous-estimés."
        )
    lecture(text)

# ** 2. WHERE THE TWO ZONES PART **

section(2, "Des disparités fortes entre l'outre-mer et le profil métropolitain",
        varies_with=("period", "category", "basis"),
        text="Chaque case compare une région et une catégorie de soins de niveau 1 à la France entière "
             f"({filters.basis_text}). Les cases en rouge montrent une prévalence plus forte et celle en bleu plus faible.")

row_order = (matrix_rows[["region_name", "area"]].drop_duplicates()
             .sort_values(["area", "region_name"])["region_name"].tolist())
matrix = matrix_rows.pivot_table(index="region_name", columns="patho_label", values="ratio")
matrix = matrix.reindex(index=row_order, columns=filters.category_order)
viz.show(viz.ratio_heatmap(
    matrix,
    split_after=int(matrix_rows[matrix_rows["area"] == MAINLAND_LABEL]["region"].nunique()),
    column_groups=type_groups(filters.ranking),
    highlight=None if filters.all_categories else filters.category_label,
))
params(f"{filters.period}, rapports annuels moyens, {filters.basis_text}",
       "tous âges et les deux sexes", "case vide : valeur masquée ou non calculable")

overseas_by_cat = matrix_rows[matrix_rows["area"] == OVERSEAS_LABEL].groupby("patho_label")["ratio"].mean()
higher = overseas_by_cat[overseas_by_cat >= 1.25].sort_values(ascending=False)
close = matrix_rows.assign(c=matrix_rows["ratio"].between(0.8, 1.25)).groupby("area")["c"].mean() * 100
if len(higher) and {MAINLAND_LABEL, OVERSEAS_LABEL} <= set(close.index):
    lecture(
        f"Les régions métropolitaines restent proches de la France dans "
        f"{close[MAINLAND_LABEL]:.0f} % des cases, contre {close[OVERSEAS_LABEL]:.0f} % en outre-mer : "
        f"l'écart n'est pas diffus, il se concentre sur quelques catégories, menées par "
        f"{ratio_list(higher, 2)}."
    )
else:
    lecture("Les lignes qui quittent le profil national sont celles des régions d'outre-mer.")

st.subheader("Une métropole homogène, un outre-mer dispersé")
varies("period", "basis")
spread = matrix_rows[matrix_rows["ratio"] > 0]
viz.show(viz.area_box(spread, "ratio", labels={"ratio": "Rapport à la France (échelle log)", "area": ""}))
params(f"{filters.period}, un point par couple région et catégorie de niveau 1", filters.basis_text)

quartiles = spread.groupby("area")["ratio"].quantile([0.25, 0.75]).unstack()
if {MAINLAND_LABEL, OVERSEAS_LABEL} <= set(quartiles.index):
    lecture(
        f"La moitié centrale des couples métropolitains tient entre "
        f"{fmt_ratio(quartiles.loc[MAINLAND_LABEL, 0.25])} et {fmt_ratio(quartiles.loc[MAINLAND_LABEL, 0.75])} "
        f"de la France, contre {fmt_ratio(quartiles.loc[OVERSEAS_LABEL, 0.25])} à "
        f"{fmt_ratio(quartiles.loc[OVERSEAS_LABEL, 0.75])} en outre-mer. "
        "L'outre-mer est donc un groupe présentant des rapports à la France à la fois très élevés et très "
        "faibles, contrairement à la métropole qui forme un bloc presque centré sur x1."
    )

# ** 3. SUB-CATEGORIES **

kept_codes = informative_level2()
n_level2 = int((dim["level"] == 2).sum())
level2_codes = kept_codes if kept_codes is not None else dim.loc[dim["level"] == 2, "patho_code"].tolist()
section(3, "Les sous-catégories de soins racontent-elles la même histoire ?",
        varies_with=("period", "basis"),
        text=f"Sur les {n_level2} sous-catégories de niveau 2, {len(level2_codes)} ont leur propre "
             "géographie ou amplifient l'écart de leur famille. Les autres répètent leur total et ne sont "
             "pas montrées, comme tout le niveau 3. Chaque ligne compare l'outre-mer groupé et la "
             "métropole groupée à la France.")

level2 = reg[(reg["level"] == 2) & reg["patho_code"].isin(level2_codes)]
dots = []
for area, regions in ((MAINLAND_LABEL, MAINLAND), (OVERSEAS_LABEL, OVERSEAS)):
    # any region with a value is kept so that all the sub-categories appear
    part = pooled_ratio(level2[level2["region"].isin(regions)], ["patho_l1", "patho_code", "patho_label"], 1, filters.basis)
    dots.append(part.assign(area=area))
dots = pd.concat(dots, ignore_index=True).rename(columns={"patho_l1": "family", "patho_label": "label"})
shown = dots.dropna(subset=["ratio"])
viz.show(viz.level2_dots(shown) if not shown.empty else None)

missing = sorted(set(dim.loc[dim["patho_code"].isin(level2_codes), "patho_label"]) - set(shown["label"]))
thin = shown[(shown["area"] == OVERSEAS_LABEL) & (shown["regions"] < 4)]["label"].tolist()
params(f"{filters.period}, {filters.basis_text}",
       f"{shown['label'].nunique()} sous-catégories affichées sur {len(level2_codes)}",
       f"non calculables : {', '.join(missing)}" if missing else "",
       f"outre-mer calculé sur moins de 4 régions : {', '.join(thin)}" if thin else "")

wide = shown.pivot_table(index=["family", "label"], columns="area", values="ratio").reset_index()
if {MAINLAND_LABEL, OVERSEAS_LABEL} <= set(wide.columns) and not wide.dropna().empty:
    wide = wide.dropna()
    wide["gap"] = np.log(wide[OVERSEAS_LABEL] / wide[MAINLAND_LABEL])
    family_ratio = overseas_by_cat.to_dict()
    top_sub = wide.sort_values(OVERSEAS_LABEL, ascending=False).iloc[0]
    widest = wide.loc[wide["gap"].abs().idxmax()]
    family_value = family_ratio.get(top_sub["family"])
    text = (
        f"Le niveau 2 déplace la lecture : {top_sub['label'].lower()} atteint "
        f"{fmt_ratio(top_sub[OVERSEAS_LABEL])} en outre-mer"
    )
    if family_value is not None and family_value < top_sub[OVERSEAS_LABEL]:
        text += f" alors que sa famille de niveau 1 est à {fmt_ratio(family_value)}"
    text += (
        f". L'écart le plus net entre les deux zones concerne {widest['label'].lower()} : "
        f"{fmt_ratio(widest[OVERSEAS_LABEL])} en outre-mer contre {fmt_ratio(widest[MAINLAND_LABEL])} en "
        "métropole. Un total peut donc masquer des signaux opposés. Calculée sur les prévalences brutes, "
        "la même sélection en retiendrait beaucoup moins : c'est en retirant l'effet de l'âge que ces "
        "sous-catégories laissent voir des specificités territoriales."
    )
    lecture(text)

st.subheader("Les sous-catégories en fonction des régions")
varies("period", "category", "basis")
st.write(
    "Pour visualiser les différences de prévalence des soins entre les régions d'outre-mer et la métropole, "
    "il faut sélectionner différentes catégories de soins. Certaines catégories de niveau 1 regroupent "
    "plusieurs sous-catégories (niveau de détail) qui sont alors proposées."
)
map_values, map_label = region_values, filters.category_label
if not filters.all_categories:
    children = dim[(dim["level"] == 2) & (dim["patho_l1"] == filters.category_label)]
    children = children[children["patho_code"].isin(level2_codes)]
    if len(children):
        choices = dict(zip(children["patho_label"], children["patho_code"]))
        choice = st.selectbox(
            "Niveau de détail", ["Toute la catégorie"] + list(choices),
            help=f"Sur les {n_level2} sous-catégories de niveau 2, {len(level2_codes)} apportent une information "
                 "absente du niveau 1 : elles classent les régions autrement que les autres sous-catégories "
                 "de la même catégorie ou elles amplifient l'écart de leur catégorie. Seules celles-là sont "
                 "proposées ici, le niveau 3 est écarté.",
        )
        if choice != "Toute la catégorie":
            sub = reg[reg["patho_code"] == choices[choice]].dropna(subset=["ratio_basis"])
            map_values = sub.groupby(["region", "region_name", "area"], as_index=False).agg(
                ratio=("ratio_basis", "mean"), prev=("prev", "mean"), prev_france=("prev_france", "mean"),
            )
            map_label = choice

viz.maps(map_values, "ratio", "Région / France", fmt=fmt_ratio)
params(f"{filters.period}, {map_label.lower()}", f"rapport annuel moyen, {filters.basis_text}",
       "tous âges et les deux sexes")

ordered = map_values.dropna(subset=["ratio"]).sort_values("ratio", ascending=False)
if len(ordered) >= 3:
    overseas_names = set(ordered[ordered["area"] == OVERSEAS_LABEL]["region_name"])
    overseas_rank = [name for name in ordered["region_name"] if name in overseas_names]
    lecture(
        f"{ordered['region_name'].iloc[0]} est la région la plus exposée "
        f"({fmt_ratio(ordered['ratio'].iloc[0])} de la France) et {ordered['region_name'].iloc[-1]} "
        f"la moins ({fmt_ratio(ordered['ratio'].iloc[-1])}). "
        + (f"La première région d'outre-mer est {overseas_rank[0]}. " if overseas_rank else "")
    )

# ** 4. EVOLUTION **

section(4, "Les écarts se creusent-ils ?",
        varies_with=("period", "region", "category", "basis"),
        text=f"Les courbes suivent le rapport à la France ({filters.basis_text}) de "
             f"{filters.focus_name.lower()}, face à la métropole et à l'outre-mer groupés. "
             "Une courbe qui s'éloigne de x1 est un écart qui se creuse.")

lines = [mainland_years.assign(ligne=MAINLAND_LABEL), overseas_years.assign(ligne=OVERSEAS_LABEL)]
if not filters.all_regions:
    lines.append(focus_years.assign(ligne=filters.focus_name))
trend = pd.concat(lines, ignore_index=True).dropna(subset=["ratio"])
viz.show(viz.line(
    trend, x="year", y="ratio", color="ligne", hline=1,
    colors={**AREA_COLORS, filters.focus_name: COLORS["focus"]},
    labels={"year": "Année", "ratio": "Rapport à la France", "ligne": ""},
) if not trend.empty else None)
params(f"{filters.category_label.lower()}, {filters.basis_text}",
       "la ligne pointillée est la France (x1)",
       "les valeurs groupées exigent au moins 80 % des régions")

moved = gap_trend(focus_years)
if moved:
    lecture(
        f"{filters.focus_name} passe de {fmt_ratio(moved['first']['ratio'])} en "
        f"{int(moved['first']['year'])} à {fmt_ratio(moved['last']['ratio'])} en "
        f"{int(moved['last']['year'])} : l'écart avec la France {moved['direction']}. "
        "Si on ne selectionne aucune catégorie de" \
        " soin l'outre-mer semble se rapprocher de la France. " \
        "Cependant, cela est due au Covid-19 (pique en 2021) et aux maladies respiratoires qui atteignent un pique en 2023 (certainement en lien avec le Covid)."
    )
else:
    lecture("Choisissez une période d'au moins deux années pour lire l'évolution.")

st.subheader(f"Quelles catégories bougent le plus en {filters.focus_name.lower()} ?")
varies("period", "region", "basis")
change = focus_by_year.sort_values("year").groupby("patho_label")["ratio"].agg(["first", "last"])
# distance to France at the end minus distance at the start
# positive means the region moves away from x1 whatever side it stands on
change["ecart"] = (change["last"] - 1).abs() - (change["first"] - 1).abs()
if first_year < last_year and len(change):
    change = change.sort_values("ecart").reset_index()
    viz.show(viz.diverging_bar(
        change, "ecart",
        f"Variation de la distance à la France entre {first_year} et {last_year}",
        order=change["patho_label"].tolist(),
        names=("L'écart se creuse", "L'écart se réduit"),
        hover={"first": ":.2f", "last": ":.2f", "ecart": ":+.2f"},
    ))
    params(f"{filters.focus_name}, {filters.basis_text}",
           "distance à x1 la dernière année moins distance à x1 la première année",
           "Covid-19 et maternité exclues")
    up, down = change.iloc[-1], change.iloc[0]
    sentences = []
    if up["ecart"] > 0:
        sentences.append(
            f"L'écart avec la France s'est le plus creusé pour {up['patho_label'].lower()} "
            f"({fmt_ratio(up['first'])} puis {fmt_ratio(up['last'])})"
        )
    if down["ecart"] < 0:
        sentences.append(
            f"il s'est le plus réduit pour {down['patho_label'].lower()} "
            f"({fmt_ratio(down['first'])} puis {fmt_ratio(down['last'])})"
        )
    widened = int((change["ecart"] > 0.02).sum())
    narrowed = int((change["ecart"] < -0.02).sum())
    stable = len(change) - widened - narrowed
    joined = " et ".join(sentences)
    lecture(
        (joined[0].upper() + joined[1:] + ". " if joined else "")
        + f"Au total, l'écart se creuse pour {widened} catégories, se réduit pour {narrowed} et reste "
        f"stable pour {stable} : les grands écarts de l'outre-mer sont structurels, ils traversent "
        "toute la période plutôt que de s'ouvrir ou de se fermer."
    )
else:
    change = pd.DataFrame(columns=["patho_label", "ecart"])
    st.info("Choisissez une période d'au moins deux années pour voir les variations.")

# ** 5. DISEASES, TREATMENTS, HOSPITALISATIONS **

section(5, "Maladies, traitements, hospitalisations : trois lectures du même territoire",
        varies_with=("period",),
        text="Une maladie identifiée suppose un diagnostic enregistré, un traitement hors pathologie "
             "suppose une prescription sans maladie repérée. Comparer les deux indique si les "
             "territoires sont décrits de la même façon.")

pair_name = st.radio("Comparaison entre traitements et maladies cardiovasculaires ou psychiatriques:",
    list(CARE_PAIRS), horizontal=True,
    help=("Ce sont les deux seules "
       "catégories qui ont à la fois des données pour le traitement et pour les maladies diagnostiquées.")
)
disease_code, treatment_code = CARE_PAIRS[pair_name]
pair_rows = reg1[reg1["patho_code"].isin([disease_code, treatment_code])].groupby(
    ["region", "region_name", "area", "patho_code"], as_index=False,
).agg(prev=("prev", "mean"))
pair_wide = pair_rows.pivot_table(index=["region", "region_name", "area"], columns="patho_code", values="prev").reset_index()

left, right = st.columns(2)
with left:
    if {disease_code, treatment_code} <= set(pair_wide.columns):
        pair_wide = pair_wide.dropna(subset=[disease_code, treatment_code])
        viz.show(viz.scatter(
            pair_wide, x=disease_code, y=treatment_code, labels={
                disease_code: "Prévalence de la maladie identifiée (%)",
                treatment_code: "Prévalence du traitement seul (%)",
                "area": "",
            },
        ) if not pair_wide.empty else None)
        params(f"{filters.period}, prévalence brute annuelle moyenne", "tous âges et les deux sexes")

with right:
    st.markdown("**Deux indicateurs de contexte**")
    ref = reference[reference["year"].between(first_year, last_year)]
    ref_area = ref.groupby(["area", "patho_code"], as_index=False)["prev"].mean()
    labels = {NO_CARE_CODE: "Aucun soin repéré", HOSPITAL_CODE: "Hospitalisation hors pathologie"}
    ref_area["indicateur"] = ref_area["patho_code"].map(labels)
    viz.show(viz.area_bar(ref_area, x="prev", y="indicateur", height=440,
                          labels={"prev": "Population consommante (%)", "indicateur": "", "area": ""}))
    params(f"{filters.period}, moyenne des régions de chaque zone")

no_care = ref[ref["patho_code"] == NO_CARE_CODE].groupby("area")["prev"].mean()
hospital = ref[ref["patho_code"] == HOSPITAL_CODE].groupby("area")["prev"].mean()
if len(pair_wide) >= 4 and {disease_code, treatment_code} <= set(pair_wide.columns):
    corr = pair_wide[disease_code].corr(pair_wide[treatment_code])
    strength = "fortement" if abs(corr) >= 0.7 else "modérément" if abs(corr) >= 0.4 else "faiblement"
    lecture(
        f"Les régions d'outre mer tendent à avoir moins de maladies identifiée et moins de traitement suel que la métropole."
        "Cet écart est plus marqué pour la psychiatrie.\n\n"
        f"En parallèle, {fmt_pct(no_care[OVERSEAS_LABEL])} de la population consommante d'outre-mer "
        f"n'a aucun soin repéré, contre {fmt_pct(no_care[MAINLAND_LABEL])} en métropole et les "
        f"hospitalisations hors pathologie y sont moins fréquentes ({fmt_pct(hospital[OVERSEAS_LABEL])} "
        f"contre {fmt_pct(hospital[MAINLAND_LABEL])}). Cependant, il ya une nuance à noter : ici les données décrivent avant tout le soin pris en charge ."
    )

# ** TAKEAWAYS **

st.divider()
st.header("À retenir")
varies("period", "region", "category", "basis")
st.write("Chaque carte reprend un chiffre calculé sur la sélection en cours, dans l'ordre des sections ci-dessus.")

facts = []

if {MAINLAND_LABEL, OVERSEAS_LABEL} <= set(close.index):
    facts.append({
        "label": "Cases proches de la France (heat map)",
        "value": f"{close[OVERSEAS_LABEL]:.0f} %",
        "delta": f"contre {close[MAINLAND_LABEL]:.0f} % en métropole",
        "help": "Part des couples région et catégorie situés entre x0,8 et x1,25 de la France.",
    })

if len(higher):
    facts.append({
        "label": f"Plus fort excès, {OVERSEAS_LABEL.lower()}",
        "value": fmt_ratio(higher.iloc[0]),
        "delta": f"{higher.index[0]}, au-dessus de la France",
        "tone": "high",
    })

deficits = overseas_by_cat.sort_values()
if len(deficits):
    facts.append({
        "label": f"Plus fort déficit, {OVERSEAS_LABEL.lower()}",
        "value": fmt_ratio(deficits.iloc[0]),
        "delta": f"{deficits.index[0]}, en dessous de la France",
        "tone": "low",
    })

if pd.notna(raw_pooled) and pd.notna(std_pooled):
    facts.append({
        "label": "Effet de la correction par l'âge",
        "value": fmt_signed(std_pooled - raw_pooled),
        "delta": f"de {fmt_ratio(raw_pooled)} brut à {fmt_ratio(std_pooled)} standardisé",
        "help": "Sur la catégorie sélectionnée, outre-mer groupé.",
        "tone": tone_of(std_pooled),
    })

overseas_dots = shown[shown["area"] == OVERSEAS_LABEL]
if not overseas_dots.empty:
    strongest = overseas_dots.sort_values("ratio", ascending=False).iloc[0]
    facts.append({
        "label": "Sous-catégorie la plus marquée",
        "value": fmt_ratio(strongest["ratio"]),
        "delta": f"{strongest['label']}, contre x1 pour la France",
        "help": f"Niveau 2, parmi les {len(level2_codes)} sous-catégories retenues.",
        "tone": tone_of(strongest["ratio"]),
    })

if moved:
    facts.append({
        "label": f"Écart {filters.focus_name.lower()}, {int(moved['first']['year'])} à {int(moved['last']['year'])}",
        "value": fmt_ratio(moved["last"]["ratio"]),
        "delta": f"contre {fmt_ratio(moved['first']['ratio'])} au début : l'écart {moved['direction']}",
        "help": "Distance à x1 comparée entre la première et la dernière année.",
        "tone": tone_of(moved["last"]["ratio"]),
    })

if len(no_care) == 2:
    facts.append({
        "label": "Aucun soin repéré",
        "value": fmt_pct(no_care[OVERSEAS_LABEL]),
        "delta": f"contre {fmt_pct(no_care[MAINLAND_LABEL])} en métropole",
        "help": "Part de la population consommante sans pathologie, traitement, maternité ni hospitalisation repérés.",
    })

if facts:
    fact_cards(facts)
else:
    st.info("Aucun chiffre comparable pour cette sélection.")