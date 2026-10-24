"""Reusable measures
Every page calls these instead of recomputing ratios by hand"""

import math

import numpy as np
import pandas as pd

from utils.config import BASIS, EXCLUDED_FROM_ALL, MEASURES_PATH, MIN_REGION_SHARE, TYPE_ORDER

# ratios are read on a log2 scale (x0.5 and x2 are the same distance from x1), capped at x3
LOG_LIMIT = float(np.log2(3))
RATIO_TICKS = dict(tickvals=[-LOG_LIMIT, -1, 0, 1, LOG_LIMIT],
                   ticktext=["x0,33", "x0,5", "x1", "x2", "x3"])


def log_ratio(ratio):
    """log2 of a ratio, capped at +/- log2(3): beyond x3 or under x0.33 the color saturates"""
    values = np.asarray(ratio, dtype=float)
    return np.log2(np.where(values > 0, values, np.nan)).clip(-LOG_LIMIT, LOG_LIMIT)


def geo_mean(values):
    """Geometric mean of ratios: x2 and x0.5 cancel each other, an arithmetic mean would not"""
    values = pd.Series(values).dropna()
    values = values[values > 0]
    return float(np.exp(np.log(values).mean())) if len(values) else float("nan")


def min_regions(n_regions):
    """Number of regions that must have a value before pooling an area"""
    return int(math.ceil(MIN_REGION_SHARE * n_regions - 1e-9))


def pooled_prevalence(data, keys, n_regions):
    """Prevalence of a group of regions: patients added, then divided by the population added"""
    usable = data.dropna(subset=["nb_patients", "pop"])
    out = usable.groupby(keys, as_index=False).agg(
        patients=("nb_patients", "sum"), population=("pop", "sum"), regions=("region", "nunique"),
    )
    out["prev"] = 100 * out["patients"] / out["population"]
    incomplete = (out["regions"] < min_regions(n_regions)) | (out["population"] <= 0)
    out.loc[incomplete, "prev"] = np.nan
    return out


def pooled_ratio(data, keys, n_regions, basis):
    """Ratio to France of a group of regions: patients added / expected patients added.

    Summing is not the same as averaging the regional ratios: here the large regions weigh more,
    which is what a national reading needs.
    """
    num, den = BASIS[basis]["num"], BASIS[basis]["den"]
    usable = data.dropna(subset=[num, den])
    out = usable.groupby(keys, as_index=False).agg(
        patients=(num, "sum"), expected=(den, "sum"), regions=("region", "nunique"),
    )
    out["ratio"] = out["patients"] / out["expected"]
    incomplete = (out["regions"] < min_regions(n_regions)) | (out["expected"] <= 0)
    out.loc[incomplete, "ratio"] = np.nan
    return out


def annual_ratio(reg_cat, regions, codes, basis):
    """One ratio per year for a group of regions. Several categories are combined with a
    geometric mean, so that a category at x2 and another at x0.5 give x1"""
    rows = reg_cat[reg_cat["region"].isin(regions) & reg_cat["patho_code"].isin(codes)]
    per_code = pooled_ratio(rows, ["year", "patho_code"], len(regions), basis)
    out = per_code.groupby("year")["ratio"].agg(geo_mean).dropna().reset_index()
    return out.sort_values("year")


def category_ratio(reg_cat, regions, codes, basis):
    """Mean ratio to France of each category, for a group of regions"""
    rows = reg_cat[reg_cat["region"].isin(regions) & reg_cat["patho_code"].isin(codes)]
    per_year = pooled_ratio(rows, ["year", "patho_code", "patho_label"], len(regions), basis)
    return per_year.dropna(subset=["ratio"])


def national_ranking(nat_cat, years, level=1):
    """Mean annual prevalence of each category over the period, ordered by type then prevalence"""
    rows = nat_cat[nat_cat["year"].between(*years) & (nat_cat["level"] == level) & (nat_cat["sex"] == 9)]
    out = rows.groupby(["patho_code", "patho_label", "motif_type"], as_index=False).agg(
        prev=("prev", "mean"), patients=("nb_patients", "mean"),
    ).dropna(subset=["prev"])
    out["type_rank"] = out["motif_type"].map({name: i for i, name in enumerate(TYPE_ORDER)})
    return out.sort_values(["type_rank", "prev"], ascending=[True, False]).reset_index(drop=True)


def comparable_codes(dim):
    """Level 1 codes usable over the whole period (Covid-19 and maternity left out)"""
    level1 = dim[dim["level"] == 1]
    return [code for code in level1["patho_code"] if code not in EXCLUDED_FROM_ALL]


def informative_level2(path=MEASURES_PATH):
    """Level 2 sub-categories the notebook kept: they rank the regions differently from their
    sisters, or they amplify the gap of their family. None when the file is missing"""
    try:
        measures = pd.read_csv(path)
    except (FileNotFoundError, KeyError):
        return None
    return measures.loc[measures["adds_information"].astype(bool), "patho_code"].tolist()


def ratio_list(series, count=3):
    """Short readable list: name (x1,42), name (x1,20)"""
    return ", ".join(f"{name} ({fmt_ratio(value)})" for name, value in series.head(count).items())


def fmt_ratio(value):
    """x1,42 with a comma, as French figures are written"""
    return "n/a" if pd.isna(value) else f"x{value:.2f}".replace(".", ",")


def fmt_pct(value, digits=1):
    """2,4 % with a comma"""
    return "n/a" if pd.isna(value) else f"{value:.{digits}f} %".replace(".", ",")


def fmt_num(value, digits=1):
    """1,4 with a comma"""
    return "n/a" if pd.isna(value) else f"{value:.{digits}f}".replace(".", ",")


def fmt_signed(value, digits=2):
    """+0,12 with a comma, for a change"""
    return "n/a" if pd.isna(value) else f"{value:+.{digits}f}".replace(".", ",")


def fmt_int(value):
    """1 234 567 with thin spaces"""
    return "n/a" if pd.isna(value) else f"{int(value):,}".replace(",", " ")


def period_label(years):
    """2015-2024, or 2024 when the period is a single year"""
    start, end = years
    return str(start) if start == end else f"{start}-{end}"


def gap_trend(series):
    """Describe how the distance to France moves between the first and the last year"""
    series = series.dropna(subset=["ratio"]).sort_values("year")
    if len(series) < 2:
        return None
    first, last = series.iloc[0], series.iloc[-1]
    gap_first, gap_last = abs(first["ratio"] - 1), abs(last["ratio"] - 1)
    if gap_last > gap_first + 0.02:
        direction = "se creuse"
    elif gap_last < gap_first - 0.02:
        direction = "se resserre lentement, sans se fermer"
    else:
        direction = "reste stable"
    return {"first": first, "last": last, "direction": direction}
