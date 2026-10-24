"""Chart builders. Each one returns a plotly figure and the pages only display it.

The colors come from the default palette of the streamlit theme (see utils/config.py) so every
chart matches the native look of the dashboard.
"""

import json

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.compute import LOG_LIMIT, RATIO_TICKS, log_ratio
from utils.config import AREA_COLORS, COLORS, GEOJSON_PATH, RATIO_COLORS, TYPE_COLORS, ZONES

GUIDE = COLORS["neutral"]
LOG_TICKS = dict(tickvals=[0.25, 0.5, 1, 2, 4], ticktext=["x0,25", "x0,5", "x1", "x2", "x4"])


def _finish(fig, height=400, legend=True):
    """Same frame for every chart: no outer margin and a flat legend above the plot"""
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom"),
        showlegend=legend,
    )
    return fig


def show(fig):
    """Display a figure or a short message when there is nothing to draw

    The page css writes chart text in Inter so plotly must measure legends with the same font
    """
    if fig is None:
        st.info("Aucune valeur comparable pour cette sélection.")
    else:
        fig.update_layout(font_family="Inter, sans-serif")
        st.plotly_chart(fig, width="stretch")


# ** BARS **

def ranking_bar(ranking, highlight=None):
    """Mean prevalence of each category colored by type of care with the highest on top"""
    order = ranking.sort_values("prev")["patho_label"].tolist()
    fig = px.bar(
        ranking, x="prev", y="patho_label", color="motif_type", orientation="h",
        category_orders={"patho_label": order}, color_discrete_map=TYPE_COLORS,
        labels={"prev": "Prévalence annuelle moyenne (%)", "patho_label": "", "motif_type": ""},
        hover_data={"prev": ":.2f"},
    )
    if highlight:
        # the chosen category keeps its color and the others are dimmed
        fig.for_each_trace(lambda trace: trace.update(
            marker_line_color="#ffffff",
            marker_line_width=[2 if label == highlight else 0 for label in trace.y],
            marker_opacity=[1 if label == highlight else 0.35 for label in trace.y],
        ))
    return _finish(fig, max(520, 32 * len(ranking) + 120))


def diverging_bar(frame, value, label, order=None, names=("Au-dessus", "En dessous"), hover=None):
    """One bar per category: red when the value is positive and blue when it is negative"""
    frame = frame.copy()
    positive, negative = names
    frame["sens"] = np.where(frame[value] >= 0, positive, negative)
    fig = px.bar(
        frame, x=value, y="patho_label", orientation="h", color="sens",
        color_discrete_map={positive: COLORS["high"], negative: COLORS["low"]},
        category_orders={"patho_label": order or frame["patho_label"].tolist()},
        labels={value: label, "patho_label": "", "sens": ""},
        hover_data=hover,
    )
    return _finish(fig, max(400, 28 * len(frame) + 110))


def plain_bar(frame, x, y, orientation="v", height=400, text=None):
    """One color bar chart used by the data quality page"""
    extra = {"text_auto": text} if text else {}
    fig = px.bar(frame, x=x, y=y, orientation=orientation, **extra)
    if orientation == "h":
        fig.update_yaxes(dtick=1, automargin=True)
    return _finish(fig, height, legend=False)


def area_bar(frame, x, y, labels, height=380):
    """Horizontal bars comparing the mainland and the overseas regions"""
    fig = px.bar(frame, x=x, y=y, color="area", orientation="h", barmode="group",
                 color_discrete_map=AREA_COLORS, labels=labels)
    return _finish(fig, height)


def ranked_bar(frame, value, name, labels, reference=None, height=None):
    """One bar per region colored by zone and sorted. A dotted line marks a reference value"""
    frame = frame.sort_values(value)
    fig = px.bar(frame, x=value, y=name, color="area", orientation="h",
                 color_discrete_map=AREA_COLORS, labels=labels,
                 category_orders={name: frame[name].tolist()})
    if reference is not None:
        fig.add_vline(x=reference, line_dash="dot", line_color=GUIDE)
    return _finish(fig, height or max(360, 24 * len(frame) + 120))


# ** LINES **

def line(frame, x, y, color, labels, colors=None, hline=None, height=390, highlight=None):
    """One line per value of `color`. Years get one tick per year

    highlight thickens that line and dims the others
    """
    fig = px.line(frame.sort_values([color, x]), x=x, y=y, color=color, markers=True,
                  color_discrete_map=colors or {}, labels=labels)
    if x == "year":
        fig.update_xaxes(dtick=1, tickformat="d")
    if hline is not None:
        fig.add_hline(y=hline, line_dash="dot", line_color=GUIDE)
    if highlight:
        fig.for_each_trace(lambda trace: trace.update(line_width=4, opacity=1) if trace.name == highlight
                           else trace.update(line_width=1.5, opacity=0.35))
    return _finish(fig, height)


def age_gap(order, values, height=370):
    """Overseas minus mainland in points of population share for each age group"""
    fig = go.Figure(go.Scatter(
        x=order, y=values, mode="lines+markers", fill="tozeroy",
        line=dict(color=COLORS["overseas"], width=3), fillcolor="rgba(255, 135, 0, 0.2)",
        hovertemplate="%{x}<br>%{y:+.1f} points<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=GUIDE)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=order, title="Classe d'âge")
    fig.update_yaxes(title="Outre-mer moins métropole (points)", zeroline=False)
    return _finish(fig, height, legend=False)


def observed_expected(frame, order, height=360):
    """Observed and expected patients of each age group side by side"""
    long = frame.melt(id_vars="age_gp", value_vars=["Observés", "Attendus"], var_name="serie", value_name="patients")
    fig = px.bar(long, x="age_gp", y="patients", color="serie", barmode="group",
                 category_orders={"age_gp": order},
                 color_discrete_map={"Observés": COLORS["overseas"], "Attendus": GUIDE},
                 labels={"age_gp": "Classe d'âge", "patients": "Patients", "serie": ""})
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=order)
    return _finish(fig, height)


def category_line(frame, x, y, color, labels, colors=None, order=None, height=390):
    """Line chart over age groups which are text and must keep their own order"""
    fig = px.line(frame, x=x, y=y, color=color, markers=True,
                  category_orders={x: order} if order else None,
                  color_discrete_map=colors or {}, labels=labels)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=order)
    return _finish(fig, height)


# ** COMPOSITION OF THE DATASET **

def _shade(color, level):
    """Same hue for a whole family and lighter for each deeper level"""
    red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    opacity = {3: 1.0, 2: 0.7, 1: 0.45}.get(level, 0.45)
    return f"rgba({red}, {green}, {blue}, {opacity})"


def treemap(frame, height=520):
    """Level 1 boxes holding their level 2 boxes holding their level 3 boxes

    frame has one row per code with id parent label value real motif_type and level. value is
    the size drawn and real is the true number of patients shown on hover
    """
    colors = [_shade(TYPE_COLORS.get(motif, GUIDE), level)
              for motif, level in zip(frame["motif_type"], frame["level"])]
    fig = go.Figure(go.Treemap(
        ids=frame["id"], parents=frame["parent"], labels=frame["label"], values=frame["value"],
        branchvalues="total", customdata=frame["real"], maxdepth=-1,
        marker=dict(colors=colors, line=dict(color="#09171f", width=1)), textfont=dict(color="#000000"),
        textinfo="label", tiling=dict(pad=2),
        hovertemplate="%{label}<br>%{customdata:,.0f} patients<extra></extra>",
    ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_traces(textposition="middle center")
    return fig


def donut(frame, names, values, center_text, height=420):
    """Ring of the share of each type of care with the total written in the hole"""
    fig = go.Figure(go.Pie(
        labels=frame[names], values=frame[values], hole=0.58, sort=False,
        marker=dict(colors=[TYPE_COLORS.get(name, GUIDE) for name in frame[names]],
                    line=dict(color="#09171f", width=2)),
        textinfo="percent", hovertemplate="%{label}<br>%{value:,.0f} prises en charge<extra></extra>",
    ))
    fig.add_annotation(text=center_text, showarrow=False, font=dict(size=15))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=80),
                      legend=dict(orientation="v", x=0, y=0, yanchor="top"))
    return fig


# ** AREA COMPARISONS **

def area_box(frame, value, labels, height=320):
    """One box per zone: how far its region and category pairs sit from France"""
    fig = px.box(frame, x=value, y="area", color="area", orientation="h",
                 color_discrete_map=AREA_COLORS, labels=labels, points="outliers")
    fig.add_vline(x=1, line_dash="dot", line_color=GUIDE)
    fig.update_xaxes(type="log", **LOG_TICKS)
    fig.update_yaxes(title="")
    return _finish(fig, height, legend=False)


def dumbbell(frame, name_col, left, right, left_label, right_label, height=380):
    """One line per region between two ratios on a log axis where x0.5 and x2 are symmetric"""
    frame = frame.dropna(subset=[left, right], how="all").sort_values(left)
    if frame.empty:
        return None
    names = frame[name_col].tolist()
    fig = go.Figure()
    for _, row in frame.dropna(subset=[left, right]).iterrows():
        fig.add_trace(go.Scatter(
            x=[row[left], row[right]], y=[row[name_col]] * 2, mode="lines",
            line=dict(color=GUIDE, width=2), showlegend=False, hoverinfo="skip",
        ))
    for column, label, color in ((left, left_label, GUIDE), (right, right_label, COLORS["overseas"])):
        fig.add_trace(go.Scatter(
            x=frame[column], y=names, mode="markers", name=label, marker=dict(size=13, color=color),
            hovertemplate="%{y}<br>" + label + ": x%{x:.2f}<extra></extra>",
        ))
    fig.add_vline(x=1, line_dash="dot", line_color=GUIDE)
    fig.update_xaxes(type="log", title="Rapport à la France (échelle log)", **LOG_TICKS)
    fig.update_yaxes(categoryorder="array", categoryarray=names, automargin=True)
    return _finish(fig, height)


def level2_dots(frame, height=None):
    """Mainland and overseas ratio of each level 2 sub-category grouped under its family

    frame has the columns family label area and ratio. The y axis has two levels so each
    family name sits next to its own sub-categories
    """
    families = frame["family"].str.split(" (", regex=False).str[0]
    frame = frame.assign(family=families).sort_values(["family", "label"])
    rows = frame[["family", "label"]].drop_duplicates()
    fig = go.Figure()
    # a grey link between the two zones shows the size of the gap
    wide = frame.pivot_table(index=["family", "label"], columns="area", values="ratio").reset_index()
    for _, row in wide.dropna().iterrows():
        fig.add_trace(go.Scatter(
            x=[row[area] for area in AREA_COLORS], y=[[row["family"]] * 2, [row["label"]] * 2],
            mode="lines", line=dict(color=GUIDE, width=2), showlegend=False, hoverinfo="skip",
        ))
    for area, color in AREA_COLORS.items():
        part = frame[frame["area"] == area]
        fig.add_trace(go.Scatter(
            x=part["ratio"], y=[part["family"], part["label"]], mode="markers", name=area,
            marker=dict(size=12, color=color),
            hovertemplate="%{y}<br>" + area + " : x%{x:.2f}<extra></extra>",
        ))
    fig.add_vline(x=1, line_dash="dot", line_color=GUIDE)
    fig.update_xaxes(type="log", title="Rapport à la France (échelle log)", **LOG_TICKS)
    fig.update_yaxes(autorange="reversed", automargin=True)
    return _finish(fig, height or max(420, 34 * len(rows) + 120))


# ** HEATMAP **

def ratio_heatmap(matrix, split_after=None, column_groups=None, highlight=None, height=760):
    """Region x category ratios to France on the log scale so x0.5 and x2 are symmetric

    split_after is the number of rows above the line between the two zones
    column_groups is a list of (type of care, number of columns) drawn above the chart
    """
    values = matrix.to_numpy()
    fig = go.Figure(go.Heatmap(
        z=log_ratio(values), customdata=values,
        x=[name.split(" (")[0] for name in matrix.columns], y=matrix.index.tolist(),
        zmin=-LOG_LIMIT, zmax=LOG_LIMIT, zmid=0, colorscale=RATIO_COLORS,
        colorbar=dict(title="Région / France", **RATIO_TICKS),
        hovertemplate="%{y}<br>%{x}<br>Rapport : x%{customdata:.2f}<extra></extra>",
        hoverongaps=False, xgap=1, ygap=1,
    ))
    columns = list(matrix.columns)
    if highlight in columns:
        index = columns.index(highlight)
        fig.add_shape(type="rect", x0=index - 0.5, x1=index + 0.5, y0=0, y1=1,
                      xref="x", yref="paper", line=dict(color="#ffffff", width=3))
    if split_after and 0 < split_after < len(matrix.index):
        fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=split_after - 0.5, y1=split_after - 0.5,
                      yref="y", line=dict(color="#ffffff", width=2, dash="dot"))
        fig.add_annotation(x=1.0, y=split_after - 0.5, xref="paper", yref="y", xanchor="left",
                           yanchor="bottom", textangle=-90, showarrow=False, font=dict(size=10),
                           text="métropole au-dessus, outre-mer en dessous")
    # a wide gap between two types of care and the name of each type in its color on top
    offset = 0
    for label, count in column_groups or []:
        if count == 0:
            continue
        color = TYPE_COLORS.get(label, GUIDE)
        # a narrow group gets its name on two lines so it does not run into the next one
        text = label.replace(" ", "<br>", 1) if count <= 4 else label
        fig.add_annotation(x=offset + (count - 1) / 2, y=1.05, xref="x", yref="paper", yanchor="bottom",
                           text=f"<b>{text}</b>", showarrow=False, font=dict(size=13, color=color))
        fig.add_shape(type="line", x0=offset - 0.4, x1=offset + count - 0.6, y0=1.03, y1=1.03,
                      xref="x", yref="paper", line=dict(color=color, width=4))
        offset += count
        if offset < len(columns):
            fig.add_shape(type="line", x0=offset - 0.5, x1=offset - 0.5, y0=0, y1=1,
                          xref="x", yref="paper", line=dict(color="#09171f", width=8))
    fig.update_layout(
        height=height,
        margin=dict(l=190, r=0, t=90, b=10),
        xaxis=dict(tickangle=-40, side="bottom", automargin=True, showgrid=False),
        yaxis=dict(autorange="reversed", dtick=1, showgrid=False),
    )
    return fig


# ** SCATTER **

def scatter(frame, x, y, labels, color="area", hover="region_name", height=440, diagonal=False, highlight=None):
    """One point per region or per category with the two zones in two colors

    highlight is the value of the hover column to single out with a bigger marker and its name
    """
    fig = px.scatter(frame, x=x, y=y, color=color, hover_name=hover,
                     color_discrete_map=AREA_COLORS, labels=labels)
    fig.update_traces(marker_size=12)
    if highlight is not None and hover in frame.columns:
        picked = frame[frame[hover] == highlight]
        if not picked.empty:
            fig.add_trace(go.Scatter(
                x=picked[x], y=picked[y], mode="markers+text", text=[str(highlight)],
                textposition="top center", showlegend=False,
                marker=dict(size=18, color="#ffffff", line=dict(width=2, color="#09171f")),
                hovertemplate=str(highlight) + "<extra></extra>",
            ))
    if diagonal:
        top = float(np.nanmax([frame[x].max(), frame[y].max()]))
        fig.add_shape(type="line", x0=0, y0=0, x1=top, y1=top, line=dict(color=GUIDE, dash="dash"))
    return _finish(fig, height)


# ** MAPS **

@st.cache_data
def load_geojson(path=GEOJSON_PATH):
    """Region shapes. The id is the region code that plotly uses to match the data"""
    with open(path, encoding="utf-8") as f:
        geo = json.load(f)
    for feature in geo["features"]:
        feature["id"] = int(feature["properties"]["code"])
    return geo


def _zone_map(frame, geo, codes, title, value, label, height, show_scale):
    """Choropleth of one zone or None when the zone has no value"""
    data = frame[frame["region"].isin(codes)]
    if data.empty:
        return None
    shapes = {"type": "FeatureCollection", "features": [f for f in geo["features"] if f["id"] in codes]}
    # colored on the log scale while the hover shows the ratio itself
    fig = px.choropleth(
        data, geojson=shapes, locations="region", color="_log", hover_name="region_name",
        range_color=(-LOG_LIMIT, LOG_LIMIT), hover_data={value: ":.2f", "_log": False},
        color_continuous_scale=RATIO_COLORS, labels={value: label, "_log": label},
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0, 0, 0, 0)")
    fig.update_traces(marker_line_color="#09171f", marker_line_width=0.6)
    if show_scale:
        # one shared legend for the six maps laid flat so it does not eat the width
        fig.update_coloraxes(colorbar=dict(title=label, orientation="h", y=-0.08, thickness=12, len=0.8, **RATIO_TICKS))
    fig.update_layout(title=dict(text=title, font=dict(size=14), x=0.5, xanchor="center"),
                      margin=dict(l=4, r=4, t=36, b=4), height=height, coloraxis_showscale=show_scale)
    return fig


def maps(frame, value, label, fmt=None):
    """Six maps on one color scale: mainland on the left and the five overseas regions on the right

    Each overseas tile carries its own value in the title because the shapes are small
    """
    geo = load_geojson()
    frame = frame.assign(region=frame["region"].astype(int)).dropna(subset=[value])
    if frame.empty:
        st.info("Aucune valeur comparable à cartographier pour cette sélection.")
        return
    frame = frame.assign(_log=log_ratio(frame[value]))

    def title_of(zone):
        codes = ZONES[zone]
        row = frame[frame["region"] == codes[0]]
        if len(codes) != 1 or fmt is None or row.empty:
            return zone
        return f"{zone}   {fmt(row[value].iloc[0])}"

    def draw(zone, height, show_scale):
        fig = _zone_map(frame, geo, ZONES[zone], title_of(zone), value, label, height, show_scale)
        if fig is None:
            st.caption(f"{zone} : pas de valeur pour cette sélection")
        else:
            show(fig)

    left, right = st.columns([2, 3])
    with left:
        draw("France métropolitaine", 520, True)
    with right:
        for names in (["Guadeloupe", "Martinique", "Guyane"], ["La Réunion", "Mayotte"]):
            for column, zone in zip(st.columns(3), names):
                with column:
                    draw(zone, 250, False)
