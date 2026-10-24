"""Entry point of the dashboard: style, header, the three pages and the footer.

    python run.py
"""

import streamlit as st

from utils.ui import apply_style, page_footer, page_header

st.set_page_config(page_title="Soins enregistrés en France", layout="wide")
apply_style()

pages = [
    st.Page("views/presentation.py", title="Les données", icon=":material/dataset:", default=True),
    st.Page("views/analyse.py", title="Analyse territoriale", icon=":material/insights:"),
    st.Page("views/qualite.py", title="Qualité et limites", icon=":material/rule:"),
]
page = st.navigation(pages)

page_header()
page.run()
page_footer()
