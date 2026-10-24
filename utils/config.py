"""Constants shared by the notebook, the data preparation and the three pages"""

from pathlib import Path

# the project folder, so the dashboard works whatever the current directory is
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSING_DIR = PROJECT_ROOT / "processing"

CSV_PATH = DATA_DIR / "effectifs_clean.csv"
TABLES_PATH = PROCESSING_DIR / "tables.pkl"
GEOJSON_PATH = DATA_DIR / "regions.geojson"
MEASURES_PATH = PROCESSING_DIR / "measures.csv"

# ** GEOGRAPHY **

# the 13 mainland regions and the 5 overseas ones (Insee region codes)
MAINLAND = {11, 24, 27, 28, 32, 44, 52, 53, 75, 76, 84, 93, 94}
OVERSEAS = {1, 2, 3, 4, 6}

MAINLAND_LABEL = "Métropole"
OVERSEAS_LABEL = "Outre-mer"

# region codes of each map: mainland France with Corsica, then one map per overseas region
ZONES = {
    "France métropolitaine": sorted(MAINLAND),
    "Guadeloupe": [1],
    "Martinique": [2],
    "Guyane": [3],
    "La Réunion": [4],
    "Mayotte": [6],
}

# ** PATHOLOGY CATEGORIES **

# three families of care categories, as built in make_dim_patho
TYPE_ORDER = ["Maladie identifiée", "Traitement hors pathologie", "Autre motif"]

# reference codes: not pathologies, but useful as context indicators
NO_CARE_CODE = "POP_TOT_ABS"  # insured people with no condition, treatment, maternity or hospitalisation
HOSPITAL_CODE = "HHP_CAT_INC"  # hospitalisations outside identified pathologies
REFERENCE_CODES = [NO_CARE_CODE, HOSPITAL_CODE]

# left out of "all categories": Covid-19 starts in 2020, maternity concerns another population
EXCLUDED_FROM_ALL = {"INF_COV_HOS", "MAT_CAT_INC"}

# pairs used for the treatment / disease comparison
CARE_PAIRS = {
    "Cardiovasculaire": ("MCV_CAT_CAT", "TFC_CAT_EXC"),
    "Psychiatrie": ("PSY_CAT_CAT", "TPS_CAT_EXC"),
}

MATERNITY_CODE = "MAT_CAT_INC"

# ** METHOD THRESHOLDS **

MIN_COVERAGE = 0.9  # share of expected patients that must be unmasked to keep a standardized ratio
MIN_REGION_SHARE = 0.8  # share of the regions of an area that must have a value to pool them

# ** LABELS OF THE FILTERS **

ALL_CATEGORIES = "Toutes les catégories"
ALL_REGIONS = "Outre-mer (5 régions groupées)"

# basis of the comparison with France: ratio column, patients column, expected patients column
BASIS = {
    "Standardisé sur l'âge": {"ratio": "std_ratio", "num": "observed_std", "den": "expected_std"},
    "Prévalence brute": {"ratio": "raw_ratio", "num": "nb_patients", "den": "expected_raw"},
}

# sex codes behind each option of the sex filter
SEX_VIEWS = {
    "Ensemble": {9: "Ensemble"},
    "Hommes": {1: "Hommes"},
    "Femmes": {2: "Femmes"},
    "Hommes vs femmes": {1: "Hommes", 2: "Femmes"},
}

# ** COLORS **

# colors taken from the default palette of the streamlit theme
COLORS = {
    "mainland": "#83c9ff",
    "overseas": "#ff8700",
    "focus": "#7defa1",
    "neutral": "#d5dae5",
    "high": "#ff4b4b",
    "low": "#1c83e1",
}

AREA_COLORS = {MAINLAND_LABEL: COLORS["mainland"], OVERSEAS_LABEL: COLORS["overseas"]}

TYPE_COLORS = {
    "Maladie identifiée": "#29b09d",
    "Traitement hors pathologie": "#ffabab",
    "Autre motif": "#d5dae5",
}

SEX_COLORS = {"Ensemble": "#7defa1", "Hommes": "#83c9ff", "Femmes": "#ffabab"}

# ratio to France: blue below and red above with a light middle at x1
RATIO_COLORS = [
    [0, "#004280"], [0.25, "#1c83e1"], [0.45, "#a6dcff"], [0.5, "#f0f2f6"],
    [0.55, "#ffc7c7"], [0.75, "#ff4b4b"], [1, "#7d353b"],
]

# reading notes and fact cards
NOTE_BACKGROUND = "#102731"

FACT_TONES = {
    "high": {"background": "rgba(255, 75, 75, 0.12)", "accent": COLORS["high"]},
    "low": {"background": "rgba(28, 131, 225, 0.16)", "accent": COLORS["low"]},
    "neutral": {"background": "rgba(213, 218, 229, 0.08)", "accent": COLORS["neutral"]},
}

# names of the sidebar filters used to say which ones drive a chart
FILTER_LABELS = {
    "period": "période",
    "region": "région",
    "category": "catégorie",
    "basis": "comparaison brute ou standardisée sur l'âge",
    "sex": "sexe",
}
