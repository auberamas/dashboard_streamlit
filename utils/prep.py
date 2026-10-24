"""Build every table used by the dashboard and the notebook, from the cleaned csv.

One person can appear in several categories, so a category total is never the sum of its
sub-categories. Every table below therefore keeps the total rows of one level only and
never adds categories together.
"""

import json
import re

import numpy as np
import pandas as pd

from utils.config import GEOJSON_PATH, MAINLAND, MAINLAND_LABEL, MIN_COVERAGE, OVERSEAS_LABEL, REFERENCE_CODES

# ** SMALL HELPERS **

def age_key(value):
    """Sort key of an age group: 05-09 -> 5, 95et+ -> 95, All -> 999"""
    found = re.search(r"\d+", str(value))
    return int(found.group()) if found else 999


def age_midpoint(value):
    """Middle of an age group: 00-04 -> 2, 95et+ -> 97"""
    digits = re.findall(r"\d+", str(value))
    if not digits:
        return np.nan
    return 97.0 if "et+" in str(value) else (int(digits[0]) + int(digits[1])) / 2


def area_of(region_code):
    """Mainland or overseas, from the region code"""
    return MAINLAND_LABEL if int(region_code) in MAINLAND else OVERSEAS_LABEL


# ** DIMENSION TABLES **

def make_dim_region(path=GEOJSON_PATH):
    """One row per region: code, name and area. The names are not in the dataset"""
    with open(path, encoding="utf-8") as f:
        geo = json.load(f)
    rows = [{"region": int(ft["properties"]["code"]), "region_name": ft["properties"]["nom"]}
            for ft in geo["features"]]
    dim = pd.DataFrame(rows).sort_values("region").reset_index(drop=True)
    dim["area"] = dim["region"].map(area_of)
    return dim


def make_dim_patho(df):
    """Identity card of each pathology code: labels, level (1 to 3) and type of care.

    Level 1 is the total of a family, level 2 the total of a sub-group, level 3 the detail.
    A code has no level below it when the lower column is "full" or repeats the upper one.
    """
    dim = df[df["is_patho"]].drop_duplicates("patho_code")
    dim = dim[["patho_code", "patho_l1", "patho_l2", "patho_l3", "patho_label"]].astype(str)
    dim = dim.reset_index(drop=True)

    no_level2 = (dim["patho_l2"] == "full") | (dim["patho_l1"] == dim["patho_l2"])
    no_level3 = (dim["patho_l3"] == "full") | (dim["patho_l3"] == dim["patho_l2"])
    dim["level"] = 3
    dim.loc[no_level3, "level"] = 2
    dim.loc[no_level2, "level"] = 1  # last, so it wins over level 2

    # separate identified diseases, treatments recorded without a disease and other care episodes
    dim["motif_type"] = "Maladie identifiée"
    dim.loc[dim["patho_code"].str.startswith(("TFC_", "TPS_", "TAA_")), "motif_type"] = "Traitement hors pathologie"
    dim.loc[dim["patho_code"].str.startswith(("MAT_", "INF_", "ALD_")), "motif_type"] = "Autre motif"
    return dim


# ** FILTERS ON THE RAW TABLE **

DIM_COLS = ["patho_code", "patho_label", "patho_l1", "patho_l2", "level", "motif_type"]
KEEP_COLS = ["year", "patho_code", "age_gp", "sex", "region", "nb_patients", "pop", "prev", "is_masked"]


def _slice(df, geo_level, all_ages, sex=None, codes=None, patho_only=True):
    """Common filter: one geographic level, ages totalled or detailed, one sex, some codes.

    Returns the useful columns with patho_code as plain text, ready to merge with the dimension.
    """
    mask = df["geo_level"] == geo_level
    mask &= (df["age_gp"] == "All") if all_ages else (df["age_gp"] != "All")
    if sex is not None:
        mask &= df["sex"].isin(sex) if isinstance(sex, (list, set, tuple)) else (df["sex"] == sex)
    if patho_only:
        mask &= df["is_patho"]
    out = df[mask]
    if codes is not None:
        out = out[out["patho_code"].astype(str).isin(list(codes))]
    # pop is read as int32 to save memory, but a sum over several regions times 100 overflows it
    return out[KEEP_COLS].astype({"patho_code": str, "age_gp": str, "pop": "int64"})


def _add_region(frame, dim_region):
    """Add the region name and the area (mainland or overseas)"""
    frame = frame.copy()
    frame["region"] = frame["region"].astype(int)
    return frame.merge(dim_region, on="region", how="left")


# ** AGE STANDARDIZATION (indirect method) **

def standardize(reg_age, nat_age, min_coverage=MIN_COVERAGE):
    """Compare each region with France at the same age structure.

    Expected patients = national prevalence of each age group applied to the regional population.
    Ratio = observed / expected (1 = the region behaves like France for its own age structure).
    Masked age groups are dropped from both sides and the ratio is kept only when the
    remaining age groups still cover `min_coverage` of the expected patients.
    """
    reference = nat_age[["year", "patho_code", "age_gp", "prev"]].rename(columns={"prev": "prev_nat_age"})
    std = reg_age.merge(reference, on=["year", "patho_code", "age_gp"], how="left")
    std["expected_all"] = std["prev_nat_age"] * std["pop"] / 100
    usable = std["nb_patients"].notna() & std["expected_all"].notna()
    std["observed"] = std["nb_patients"].where(usable)
    std["expected"] = std["expected_all"].where(usable)

    out = std.groupby(["year", "region", "patho_code"], as_index=False).agg(
        observed_std=("observed", "sum"),
        expected_std=("expected", "sum"),
        expected_all=("expected_all", "sum"),
    )
    out["coverage"] = out["expected_std"] / out["expected_all"]
    enough = out["coverage"] >= min_coverage
    out["std_ratio"] = (out["observed_std"] / out["expected_std"]).where(enough)
    # emptied below the limit, so a pooled sum over several regions never uses a partial value
    out.loc[~enough, ["observed_std", "expected_std"]] = np.nan
    return out.drop(columns="expected_all")


# ** MAIN BUILDER **

def make_tables(df, regions_path=GEOJSON_PATH):
    """Return the dictionary of tables used by the three pages and by the notebook.

    - nat_cat -> France, all ages, both sexes, every level: the national reference
    - nat_age -> France, one row per age group and sex: age and sex profiles
    - reg_cat -> regions, all ages, both sexes, levels 1 and 2, with the ratios to France
    - reg_age -> regions, one row per age group: regional age profiles
    - reg_pop -> regions, population by age group and its share: age structures
    - reference  indicators that are not pathologies (no recorded care, hospitalisations)
    - dim_patho / dim_region  ->  description of the codes and of the regions
    - quality -> data quality checks
    - meta -> figures describing the dataset itself
    """
    dim = make_dim_patho(df)
    dim_region = make_dim_region(regions_path)
    codes_l1 = dim.loc[dim["level"] == 1, "patho_code"].tolist()
    codes_l12 = dim.loc[dim["level"] <= 2, "patho_code"].tolist()

    # 1. NATIONAL REFERENCE: one row per year, category and sex (9 = both, the usual reading)
    nat_cat = _slice(df, "France", all_ages=True, sex=[1, 2, 9]).merge(dim[DIM_COLS], on="patho_code")
    both = nat_cat["sex"] == 9
    nat_cat.loc[both, "rank_prev"] = nat_cat[both].groupby("year")["prev"].rank(ascending=False, method="min")

    # 2. NATIONAL AGE AND SEX PROFILES
    nat_age = _slice(df, "France", all_ages=False, sex=[1, 2, 9]).merge(dim[DIM_COLS], on="patho_code")

    # 3. REGIONS, ALL AGES: prevalence and raw ratio to France
    reg_cat = _slice(df, "Region", all_ages=True, sex=9, codes=codes_l12)
    reg_cat = _add_region(reg_cat, dim_region).merge(dim[DIM_COLS], on="patho_code")
    france_ref = nat_cat.loc[both, ["year", "patho_code", "prev"]].rename(columns={"prev": "prev_france"})
    reg_cat = reg_cat.merge(france_ref, on=["year", "patho_code"], how="left")
    reg_cat["raw_ratio"] = (reg_cat["prev"] / reg_cat["prev_france"]).where(reg_cat["prev_france"] > 0)
    reg_cat["expected_raw"] = reg_cat["prev_france"] * reg_cat["pop"] / 100

    # 4. REGIONS BY AGE GROUP and the age-standardized ratio built from it
    reg_age = _add_region(_slice(df, "Region", all_ages=False, sex=9, codes=codes_l12), dim_region)
    reg_std = standardize(reg_age, nat_age[nat_age["patho_code"].isin(codes_l12) & (nat_age["sex"] == 9)])
    reg_cat = reg_cat.merge(reg_std, on=["year", "region", "patho_code"], how="left")

    # 5. AGE STRUCTURE: the population is the same for every category, so one code is enough
    pop_cols = ["year", "region", "region_name", "area", "age_gp", "pop"]
    reg_pop = reg_age[reg_age["patho_code"] == codes_l1[0]][pop_cols].copy()
    reg_pop["share"] = 100 * reg_pop["pop"] / reg_pop.groupby(["year", "region"])["pop"].transform("sum")
    reg_pop["mid"] = reg_pop["age_gp"].map(age_midpoint)

    # 6. REFERENCE INDICATORS: no recorded care, hospitalisations outside identified pathologies
    reference = _slice(df, "Region", all_ages=True, sex=9, codes=REFERENCE_CODES, patho_only=False)
    reference = _add_region(reference, dim_region)
    ref_france = _slice(df, "France", all_ages=True, sex=9, codes=REFERENCE_CODES, patho_only=False)
    ref_france = ref_france[["year", "patho_code", "prev"]].rename(columns={"prev": "prev_france"})
    reference = reference.merge(ref_france, on=["year", "patho_code"], how="left")
    reference["raw_ratio"] = (reference["prev"] / reference["prev_france"]).where(reference["prev_france"] > 0)

    # 7. QUALITY AND METADATA
    quality = _make_quality(df, reg_age, reg_cat, codes_l1)
    meta = _make_meta(df, dim, dim_region)

    return {
        "nat_cat": nat_cat, "nat_age": nat_age,
        "reg_cat": reg_cat, "reg_age": reg_age, "reg_pop": reg_pop,
        "reference": reference,
        "dim_patho": dim, "dim_region": dim_region,
        "quality": quality, "meta": meta,
    }


def _make_quality(df, reg_age, reg_cat, codes_l1):
    """Checks shown on the data quality page"""
    real = df["is_patho"]
    keys = ["year", "patho_code", "age_gp", "sex", "region", "dep"]  # should identify one observation

    # men + women must give the "both sexes" row (France, level 1 totals)
    sexes = df[(df["geo_level"] == "France") & (df["age_gp"] == "All") & df["patho_code"].isin(codes_l1)]
    sexes = sexes.pivot_table(index=["year", "patho_code"], columns="sex", values="nb_patients", observed=True)

    # share of masked age cells by region, on level 1 categories only
    age_l1 = reg_age[reg_age["patho_code"].isin(codes_l1)]
    masked_age = (age_l1["nb_patients"].isna().groupby(age_l1["region_name"]).mean() * 100).round(1)

    # all regions pooled must give a standardized ratio of 1: this validates the method
    pooled = reg_cat[reg_cat["patho_code"].isin(codes_l1)]
    national_std = pooled["observed_std"].sum() / pooled["expected_std"].sum()

    masked_cat = reg_cat[reg_cat["level"] == 1].groupby("patho_label")["nb_patients"].apply(
        lambda s: 100 * s.isna().mean()
    )

    return {
        "missing_pct": (df[["nb_patients", "prev"]].isna().mean() * 100).round(1),
        "total_rows_pct": pd.Series({
            "patho_l2 = full (total de niveau 1)": (df["patho_l2"] == "full").mean() * 100,
            "patho_l3 = full (pas de niveau 3)": (df["patho_l3"] == "full").mean() * 100,
        }).round(1),
        "masked_pct_by_geo": (df["is_masked"][real].groupby(df["geo_level"][real], observed=True).mean() * 100).round(1),
        "masked_pct_age_by_region": masked_age.sort_values(ascending=False),
        "masked_pct_by_category": masked_cat.round(1).sort_values(ascending=False),
        "checks": pd.Series({
            "rows": float(len(df)),
            "duplicated_observations": float(df.duplicated(subset=keys).sum()),
            "max_gap_sex_9_vs_1_plus_2": float((sexes[1] + sexes[2] - sexes[9]).abs().max()),
            "national_std_ratio": float(national_std),
            "std_available_pct": float(100 * reg_cat["std_ratio"].notna().mean()),
        }),
    }


def _make_meta(df, dim, dim_region):
    """Figures describing the dataset, shown on the presentation page"""
    ages = [a for a in sorted(df["age_gp"].astype(str).unique(), key=age_key) if a != "All"]
    return {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "year_min": int(df["year"].min()),
        "year_max": int(df["year"].max()),
        "n_years": int(df["year"].nunique()),
        "n_regions": int(dim_region["region"].nunique()),
        "n_departments": int(df.loc[df["geo_level"] == "Department", "dep"].nunique()),
        "n_codes": int(dim["patho_code"].nunique()),
        "n_level1": int((dim["level"] == 1).sum()),
        "n_level2": int((dim["level"] == 2).sum()),
        "n_level3": int((dim["level"] == 3).sum()),
        "age_groups": ages,
        "n_age_groups": len(ages),
    }
