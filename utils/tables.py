"""Reading the cleaned csv and building the aggregated tables.

This module has no streamlit import on purpose so the cleaning script can use it
without starting a streamlit runtime. The dashboard side lives in utils/io.py.
"""

import os
from pathlib import Path

import pandas as pd

from utils.config import CSV_PATH, TABLES_PATH
from utils.prep import make_tables

# the cleaned csv has 5.8 million rows so text columns read as category use about 5 times less memory
COLUMNS = [
    "year", "patho_l1", "patho_l2", "patho_l3", "patho_code",
    "age_gp", "sex", "region", "dep", "nb_patients", "pop", "prev",
    "is_masked", "is_patho", "geo_level", "patho_label",
]
DTYPES = {
    "year":"int16",
    "sex": "int8",
    "region": "float32",
    "pop": "int32",
    "patho_l1": "category",
    "patho_l2": "category",
    "patho_l3": "category",
    "patho_code": "category",
    "patho_label": "category",
    "age_gp": "category",
    "dep": "category",
    "geo_level": "category",
}


def load_raw(path=CSV_PATH):
    """Read the cleaned csv produced by cleaning_analysis/clean.py"""
    return pd.read_csv(path, usecols=COLUMNS, dtype=DTYPES)


def build_tables(csv_path=CSV_PATH, out_path=TABLES_PATH):
    """Build the aggregated tables from the csv and save them next to the project.

    The file is written under a temporary name then renamed so a failure never leaves a
    half written pickle that the dashboard would try to read.
    """
    tables = make_tables(load_raw(csv_path))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_suffix(out_path.suffix + ".tmp")
    pd.to_pickle(tables, temporary)
    os.replace(temporary, out_path)
    return tables


def load_tables(path=TABLES_PATH):
    """Prepared tables read from disk or built from the csv the first time"""
    if Path(path).exists():
        return pd.read_pickle(path)
    return build_tables(out_path=path)
