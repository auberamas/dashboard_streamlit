"""Loading for the dashboard. The cleaned csv weighs about 1.4 GB so the tables are built once.

cleaning_analysis/clean.py runs the preparation and saves the result in processing/tables.pkl.
The dashboard then reads that small file instead of the csv, which makes the first page open in a second instead of a minute.
If the file is missing the dashboard rebuilds it by itself.

The file handling lives in utils/tables.py, which has no streamlit import, so the cleaning script can reuse it.
"""

import streamlit as st

from utils.config import CSV_PATH, TABLES_PATH
from utils.tables import build_tables, load_raw, load_tables

__all__ = ["CSV_PATH", "TABLES_PATH", "build_tables", "load_raw", "load_tables", "get_data"]


@st.cache_data(show_spinner="Chargement des données")
def get_data():
    """Tables shared by the three pages, kept in the session cache"""
    return load_tables()
