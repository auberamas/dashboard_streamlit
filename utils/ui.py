"""Streamlit pieces shared by the three pages: style, header, footer, sidebar filters and small blocks"""

from dataclasses import dataclass, field
from html import escape
from itertools import count

import streamlit as st

from utils.compute import comparable_codes, national_ranking, period_label
from utils.config import (
    ALL_CATEGORIES, ALL_REGIONS, BASIS, FACT_TONES, FILTER_LABELS, NOTE_BACKGROUND, OVERSEAS,
    OVERSEAS_LABEL, PROJECT_ROOT, SEX_VIEWS, TYPE_ORDER,
)

SOURCE = (
    "Source : [Assurance Maladie (Cnam)]"
    "(https://www.data.gouv.fr/datasets/pathologies-effectif-de-patients-par-pathologie-sexe-classe-dage-et-territoire-departement-region)\n\n"
    "Licence [ODbL](https://opendatacommons.org/licenses/odbl/summary/)"
)

AUTHOR = "RAMASSAMY Aube"
AUTHOR_EMAIL = "aube.ramassamy@efrei.net"
# left empty until the repository is public
GITHUB_URL = "https://github.com/auberamas"
LOGO = PROJECT_ROOT / "image" / "logo_efrei.png"

ALL_FILTERS = ("period", "region", "category", "basis", "sex")


# ** STYLE **

def apply_style():
    """Saira for the titles and Inter for the rest of the text"""
    st.markdown(
        f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Saira:wght@400;500;600;700&display=swap');

    /* Inter by default for every text of the page and of the sidebar including the charts */
    html, body,
    [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] *,
    [data-testid="stSidebar"], [data-testid="stSidebar"] * {{
        font-family: "Inter", sans-serif !important;
    }}

    /* Saira for the titles and everything inside them since streamlit wraps the text in a span */
    [data-testid="stAppViewContainer"] h1, [data-testid="stAppViewContainer"] h1 *,
    [data-testid="stAppViewContainer"] h2, [data-testid="stAppViewContainer"] h2 *,
    [data-testid="stAppViewContainer"] h3, [data-testid="stAppViewContainer"] h3 *,
    [data-testid="stAppViewContainer"] h4, [data-testid="stAppViewContainer"] h4 *,
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h1 *,
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h2 *,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h3 * {{
        font-family: "Saira", sans-serif !important;
        font-stretch: normal !important;
        letter-spacing: normal !important;
        line-height: 1.3 !important;
    }}

    h1 {{
        font-weight: 600 !important;
    }}

    h2, h3, h4, h5, h6 {{
        font-weight: 500 !important;
    }}

    [data-testid="stMetricValue"] {{
        font-weight: 300 !important;
    }}

    /* space between the sections and around the charts */
    [data-testid="stAppViewContainer"] h2 {{
        margin-top: 2.4rem;
        margin-bottom: 0.2rem;
    }}

    [data-testid="stAppViewContainer"] h3 {{
        margin-top: 1.4rem;
    }}

    [data-testid="stPlotlyChart"] {{
        margin: 0.8rem 0 1.2rem 0;
    }}

    /* keep the icon font or the icon names show up as text */
    [data-testid] span[data-testid="stIconMaterial"],
    [data-testid] .material-symbols-rounded {{
        font-family: "Material Symbols Rounded" !important;
    }}

    [data-testid="stHeader"] {{
        background-color: transparent;
    }}

    /* reading notes */
    [class*="st-key-note_"] {{
        background-color: {NOTE_BACKGROUND};
        border-radius: 6px;
        padding: 0.2rem 0.4rem;
    }}

    /* fact cards */
    [class*="st-key-fact_"] {{
        border-radius: 8px;
        padding: 0.9rem 1rem 0.8rem 1rem;
        min-height: 128px;
    }}

    .fact-label {{
        font-size: 0.85rem;
        opacity: 0.8;
    }}

    .fact-value {{
        font-size: 2rem;
        font-weight: 300;
        line-height: 1.2;
        margin: 0.2rem 0;
    }}

    .fact-delta {{
        font-size: 0.85rem;
        opacity: 0.85;
    }}

    [class*="st-key-fact_"][class*="_high"] {{
        background-color: {FACT_TONES["high"]["background"]};
    }}

    [class*="st-key-fact_"][class*="_low"] {{
        background-color: {FACT_TONES["low"]["background"]};
    }}

    [class*="st-key-fact_"][class*="_neutral"] {{
        background-color: {FACT_TONES["neutral"]["background"]};
    }}

    /* header and footer */
    .app-header {{
        font-size: 0.85rem;
        opacity: 0.85;
        line-height: 1.5;
    }}

    .app-footer {{
        text-align: center;
        font-size: 0.8rem;
        opacity: 0.7;
        line-height: 1.6;
        padding-bottom: 1rem;
    }}

    .app-header a, .app-footer a {{
        color: inherit;
    }}

    /* center the content of the metric cards */
    [data-testid="stMetric"] {{
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        text-align: center !important;
    }}

    [data-testid="stMetric"] > div {{
        width: 100% !important;
    }}

    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] {{
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        text-align: center !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


# ** HEADER AND FOOTER **

def page_header():
    """School logo and author shown at the top of every page"""
    logo, text = st.columns([1, 6], vertical_alignment="center")
    if LOGO.exists():
        logo.image(str(LOGO), width=130)
    links = [f'<a href="mailto:{AUTHOR_EMAIL}">{AUTHOR_EMAIL}</a>']
    if GITHUB_URL:
        links.append(f'<a href="{GITHUB_URL}">GitHub</a>')
    text.markdown(
        f'<div class="app-header"><b>{AUTHOR}</b>, Data et IA, EFREI Paris<br>{" - ".join(links)}</div>',
        unsafe_allow_html=True,
    )


def page_footer():
    """Course and tools shown at the bottom of every page"""
    st.divider()
    st.markdown(
        '<div class="app-footer">'
        "Projet de <b>data visualisation</b> encadré par <b>MATHEW Mano Joseph</b> "
        '(<a href="mailto:mano.mathew@efrei.fr">mano.mathew@efrei.fr</a>)<br>'
        "Données Assurance Maladie (Cnam), licence ODbL - réalisé avec Streamlit et Plotly"
        "</div>",
        unsafe_allow_html=True,
    )


# ** SMALL BLOCKS **

# each note gets its own key so the css can find it
_note_ids = count()


def lecture(text):
    """Boxed sentence under a chart: what it says and what comes next"""
    with st.container(border=True, key=f"note_{next(_note_ids)}"):
        st.write(text)


def kpi(column, label, value, delta=None, help=None, delta_arrow="auto"):
    """Metric card without the green or red color since a high ratio is neither good nor bad"""
    column.metric(label, value, delta, delta_color="off", border=True, help=help, delta_arrow=delta_arrow)


def fact_cards(facts, per_row=3, name="fact"):
    """Takeaways as tinted cards: a short label then one key figure then the comparison

    Each fact can carry a tone: high when above France and low when below France
    name keeps the keys unique when a page shows several groups of cards
    """
    for start in range(0, len(facts), per_row):
        columns = st.columns(per_row)
        for offset, (column, fact) in enumerate(zip(columns, facts[start:start + per_row])):
            tone = fact.get("tone", "neutral")
            tooltip = f' title="{escape(fact["help"])}"' if fact.get("help") else ""
            with column.container(key=f"fact_{name}_{start + offset}_{tone}"):
                st.markdown(
                    f'<div class="fact-label">{escape(fact["label"])}</div>'
                    f'<div class="fact-value"{tooltip}>{escape(fact["value"])}</div>'
                    f'<div class="fact-delta">{escape(fact.get("delta") or "")}</div>',
                    unsafe_allow_html=True,
                )


def tone_of(ratio):
    """high above France and low below France"""
    if ratio is None or ratio != ratio:
        return "neutral"
    return "high" if ratio > 1 else "low"


def params(*parts):
    """Caption listing the fixed parameters behind a chart"""
    st.caption(", ".join(str(part) for part in parts if part))


def varies(*keys):
    """Caption saying which sidebar filters change the chart above"""
    names = [FILTER_LABELS[key] for key in keys if key in FILTER_LABELS]
    if not names:
        st.caption("Ne dépend d'aucun filtre")
    elif len(names) == 1:
        st.caption(f"Varie avec le filtre : {names[0]}")
    else:
        st.caption("Varie avec les filtres : " + ", ".join(names))


def section(number, title, varies_with=None, text=None):
    """Section header with the filters that drive it and its introduction

    varies_with=None hides the caption about the filters
    """
    st.divider()
    st.header(f"{number}. {title}")
    if varies_with is not None:
        varies(*varies_with)
    if text:
        st.write(text)


# ** FILTERS **

@dataclass
class Filters:
    """The sidebar choices and everything the pages derive from them"""
    years: tuple
    region_label: str
    category_label: str
    basis: str
    sex_view: str
    ranking: object = None
    category_order: list = field(default_factory=list)
    codes_all: list = field(default_factory=list)

    @property
    def period(self):
        return period_label(self.years)

    @property
    def all_regions(self):
        return self.region_label == ALL_REGIONS

    @property
    def all_categories(self):
        return self.category_label == ALL_CATEGORIES

    @property
    def ratio_col(self):
        return BASIS[self.basis]["ratio"]

    @property
    def focus_name(self):
        return OVERSEAS_LABEL if self.all_regions else self.region_label

    @property
    def basis_text(self):
        """Comparison basis written out for the captions"""
        if self.ratio_col == "std_ratio":
            return "comparaison standardisée sur l'âge"
        return "comparaison brute, sans correction de l'âge"


def build_filters(tables, show=ALL_FILTERS):
    """Draw the sidebar with only the filters that act on the current page and return the choices

    Streamlit forgets the value of a widget that is not drawn on a page so each key is written
    back to the session at every run. A choice survives a visit to a page where it is hidden
    """
    nat_cat, dim, dim_region = tables["nat_cat"], tables["dim_patho"], tables["dim_region"]
    years_available = sorted(nat_cat["year"].unique())
    first, last = min(years_available), max(years_available)

    defaults = {
        "f_years": (first, last),
        "f_region": ALL_REGIONS,
        "f_category": ALL_CATEGORIES,
        "f_basis": list(BASIS)[0],
        "f_sex": "Hommes vs femmes",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
        st.session_state[key] = st.session_state[key]

    # the national ranking of the period orders the categories in the selector
    ranking = national_ranking(nat_cat, st.session_state["f_years"])
    category_order = ranking["patho_label"].tolist()
    # a choice that disappears with the period falls back on diabetes
    if st.session_state["f_category"] not in [ALL_CATEGORIES] + category_order:
        st.session_state["f_category"] = "Diabète" if "Diabète" in category_order else category_order[0]

    with st.sidebar:
        if show:
            st.header("Filtres")
        if "period" in show:
            st.slider("Période", first, last, key="f_years")
        if "region" in show:
            st.selectbox("Région observée", [ALL_REGIONS] + dim_region["region_name"].tolist(), key="f_region")
        if "category" in show:
            st.selectbox("Catégorie de soins", [ALL_CATEGORIES] + category_order, key="f_category")
        if "basis" in show:
            st.radio("Comparaison à la France", list(BASIS), key="f_basis")
            st.caption(
                "Standardisée : chaque région est comparée à la France à structure d'âge identique. "
                "Brute : les prévalences sont comparées telles quelles."
            )
        if "sex" in show:
            st.radio("Sexe", list(SEX_VIEWS), key="f_sex")
        if show:
            st.divider()
        st.caption(SOURCE)

    return Filters(
        years=tuple(st.session_state["f_years"]),
        region_label=st.session_state["f_region"],
        category_label=st.session_state["f_category"],
        basis=st.session_state["f_basis"],
        sex_view=st.session_state["f_sex"],
        ranking=ranking,
        category_order=category_order,
        codes_all=comparable_codes(dim),
    )


def focus_regions(filters, dim_region):
    """Region codes behind the current choice: one region or the five overseas ones"""
    if filters.all_regions:
        return OVERSEAS
    code = dim_region.loc[dim_region["region_name"] == filters.region_label, "region"]
    return {int(code.iloc[0])} if len(code) else set()


def selected_codes(filters, dim):
    """Category codes behind the current choice: every comparable one or the chosen one"""
    if filters.all_categories:
        return filters.codes_all
    code = dim.loc[(dim["level"] == 1) & (dim["patho_label"] == filters.category_label), "patho_code"]
    return code.tolist()


def type_groups(ranking):
    """(type of care, number of categories) in the order used by the charts"""
    return [(name, int((ranking["motif_type"] == name).sum())) for name in TYPE_ORDER]
