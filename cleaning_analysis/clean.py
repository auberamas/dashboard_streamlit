"""
Clean the cvs extracted from data.gouv and create the necessary files for the dashboard

Reads  data/effectifs.csv: the raw download from data.gouv.fr
Writes:
- data/effectifs_clean.csv: one row per observation with flags used on the dashboard
- processing/measures.csv: the level 2 sub-categories worth showing
- processing/tables.pkl: the aggregated tables the dashboard reads at startup

The cleaning steps come from part I of cleaning_analysis/analyse_effectifs.ipynb and the sub-category
selection from part II section 5

note: every output is written to a temporary file then renamed so a failure never leaves a truncated
file behind
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd

# the project folder is the parent of this file so the script runs from any directory
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_CSV = ROOT / "data" / "effectifs.csv"
CLEAN_CSV = ROOT / "data" / "effectifs_clean.csv"
MEASURES_CSV = ROOT / "processing" / "measures.csv"

# raw column names of the Cnam file on the left the names used everywhere else on the right
COLUMN_NAMES = {
    "annee": "year",
    "patho_niv1": "patho_l1",
    "patho_niv2": "patho_l2",
    "patho_niv3": "patho_l3",
    "top": "patho_code",
    "cla_age_5": "age_gp",
    "sexe": "sex",
    "dept": "dep",
    "Ntop": "nb_patients",
    "Npop": "pop",
    "Niveau prioritaire": "priority_level",
    "libelle_classe_age": "age_label",
    "libelle_sexe": "sex_label",
    "tri": "sort_order",
}

# codes that are references and not pathologies
NOT_PATHOLOGY_PREFIXES = ("POP_", "HHP_")

# thresholds of the level 2 selection explained in part II section 5 of the notebook
GEO_MAX = 0.3  # below this the sub-category ranks the regions its own way
SLOPE_MIN = 1.5  # above this it amplifies the gap of its category
SPREAD_MIN = 1.5  # highest region divided by lowest region
MIN_REGIONS = 14  # a measure computed on fewer regions is not reliable


# ** SMALL HELPERS **

def write_atomic(frame, path, **kwargs):
    """Write a csv next to its target then rename it so a crash never truncates the real file"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, **kwargs)
    os.replace(temporary, path)
    return path

def log(message):
    """Progress line printed in the terminal"""
    print(f"[clean] {message}", flush=True)

# ** STEP 1 CLEANING **

def read_raw(path=RAW_CSV):
    """Read the raw file. The separator is a semicolon and the file starts with a byte order mark"""
    if not Path(path).exists():
        raise FileNotFoundError(f"fichier source absent : {path}")
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


def clean(df):
    """Rename the columns and add the four flags the dashboard relies on"""
    df = df.rename(columns=COLUMN_NAMES)

    # a missing sub level means the row is a total so there is nothing to put below
    df["patho_l2"] = df["patho_l2"].fillna("full")
    df["patho_l3"] = df["patho_l3"].fillna("full")

    # a missing count is a small number hidden by the provider and never a zero
    df["is_masked"] = df["nb_patients"].isna()

    df["age_gp"] = df["age_gp"].replace({"tsage": "All"})
    df["dep"] = df["dep"].astype(str)

    # real pathologies against the reference rows
    df["is_patho"] = ~df["patho_code"].str.startswith(NOT_PATHOLOGY_PREFIXES)

    # readable label built from the deepest level that carries a name
    df["patho_label"] = df["patho_l3"]
    same_as_level2 = (df["patho_l3"] == "full") | (df["patho_l3"] == df["patho_l2"])
    df.loc[same_as_level2, "patho_label"] = df["patho_l2"]
    df.loc[df["patho_l2"] == "full", "patho_label"] = df["patho_l1"]

    # geographic level of each row so the totals are never summed with their parts
    df["geo_level"] = "Department"
    df.loc[df["dep"] == "999", "geo_level"] = "Region"
    df.loc[df["region"] == 99, "geo_level"] = "France"

    return df

# ** STEP 2 LEVEL 2 SELECTION **

def code_levels(df):
    """One row per care code with its level of detail. Same rule as the notebook"""
    codes = df[df["is_patho"]].drop_duplicates("patho_code").copy()
    codes = codes[["patho_code", "patho_l1", "patho_l2", "patho_l3", "patho_label"]]

    no_level_2 = (codes["patho_l2"] == "full") | (codes["patho_l2"] == codes["patho_l1"])
    no_level_3 = (codes["patho_l3"] == "full") | (codes["patho_l3"] == codes["patho_l2"])
    codes["level"] = 3
    codes.loc[no_level_3, "level"] = 2
    codes.loc[no_level_2, "level"] = 1 # last so it wins over level 2
    return codes


def measure(ratios, codes):
    """One row per level 2 sub-category with its own geography and its amplification.

    ratios holds one row per region and one column per code so a sub-category can be compared
    with the other sub-categories of its category without being part of its own reference.
    """
    rows = []
    for category in codes[codes["level"] == 1].itertuples():
        children = codes.loc[(codes["level"] == 2) & (codes["patho_l1"] == category.patho_l1),
                             "patho_code"]
        children = [code for code in children if code in ratios.columns]
        if len(children) < 2 or category.patho_code not in ratios.columns:
            continue
        ranks = ratios[children].rank()  # ranks so one extreme region cannot drive the result
        for child in children:
            sisters = [code for code in children if code != child]
            pair = ratios[[child, category.patho_code]].dropna()
            rows.append({
                "category": category.patho_l1,
                "patho_code": child,
                "sub_category": codes.loc[codes["patho_code"] == child, "patho_label"].iloc[0],
                "geo_sisters": ranks[child].corr(ranks[sisters].mean(axis=1)),
                "slope": pair[child].cov(pair[category.patho_code]) / pair[category.patho_code].var(),
                "spread": ratios[child].max() / ratios[child].min(),
                "n_regions": int(ratios[child].notna().sum()),
            })
    return pd.DataFrame(rows)


def adds_information(frame):
    """Keep a sub-category when it says something new and when it can be measured"""
    own_geography = frame["geo_sisters"] < GEO_MAX
    amplifies = frame["slope"] > SLOPE_MIN
    measurable = (frame["spread"] >= SPREAD_MIN) & (frame["n_regions"] >= MIN_REGIONS)
    return (own_geography | amplifies) & measurable

def build_measures(tables):
    """Run the selection on the standardized ratios of the latest year"""
    reg_cat = tables["reg_cat"]
    codes = tables["dim_patho"]
    last_year = int(reg_cat["year"].max())

    ratios = reg_cat[reg_cat["year"] == last_year].pivot_table(
        index="region", columns="patho_code", values="std_ratio")

    measures = measure(ratios, codes)
    measures["adds_information"] = adds_information(measures)
    return measures, last_year

# ** MAIN **

def run(raw_csv=RAW_CSV, clean_csv=CLEAN_CSV, measures_csv=MEASURES_CSV):
    """Full pipeline. Returns a small summary of what was written"""
    started = time.time()

    log(f"lecture de {raw_csv}")
    df = clean(read_raw(raw_csv))
    log(f"{len(df):,} lignes nettoyees".replace(",", " "))

    log(f"ecriture de {clean_csv}")
    write_atomic(df, clean_csv)
    del df # the raw frame is heavy and the tables are rebuilt from the file

    # the aggregated tables use the same preparation layer as the dashboard
    from utils.tables import build_tables
    log("construction des tables agregees")
    tables = build_tables(csv_path=clean_csv)

    log("selection des sous-categories de niveau 2")
    measures, last_year = build_measures(tables)
    write_atomic(measures, measures_csv, index=False)

    summary = {
        "rows": int(tables["meta"]["rows"]),
        "years": f"{tables['meta']['year_min']}-{tables['meta']['year_max']}",
        "level2_kept": int(measures["adds_information"].sum()),
        "level2_total": int(len(measures)),
        "measures_year": last_year,
        "clean_csv": str(clean_csv),
        "measures_csv": str(measures_csv),
        "duration_sec": round(time.time() - started, 1),
    }
    log(f"termine en {summary['duration_sec']} s")
    return summary

if __name__ == "__main__":
    result = run()
    for key, value in result.items():
        print(f"{key:>14} : {value}")
