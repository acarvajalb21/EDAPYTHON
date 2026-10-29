"""Panel interactivo público: acceso formal a salud en Atlántico, CNPV 2018."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from flask import abort, send_from_directory


DATA_DIR = Path(__file__).resolve().parent / "data"
EDA = json.loads((DATA_DIR / "eda.json").read_text(encoding="utf-8"))
MODEL = json.loads((DATA_DIR / "modelo.json").read_text(encoding="utf-8"))
SOURCE = MODEL["models"]["hist_gradient_boosting"]["test"]
EXACT = {"n": EDA["metadata"]["total_labeled_exact"], "sin_formal": EDA["metadata"]["no_access_exact"]}
COVERAGE = {tuple(row["key"]): row["coverage_floor_5pct"] for row in EDA.get("coverage_index", [])}

NAVY = "#17324D"
TEAL = "#0A8D88"
CORAL = "#E88969"
INK = "#193047"
MUTED = "#667789"
GRID = "#E7ECEE"
CREAM = "#F7F8F5"
AGE_ORDER = EDA["metadata"]["age_bands"]
RULE_NOTE = "Cruces publicables del censo de 2018; recuentos redondeados a 5. Se omiten celdas pequeñas. Las gráficas basadas en esos cruces ocultan tasas con menos de 80 % de cobertura o base aproximada menor de 200."
MODEL_NAMES = {
    "baseline": "Referencia por prevalencia",
    "logistica": "Regresión logística",
    "random_forest": "Bosque aleatorio",
    "hist_gradient_boosting": "Boosting de histogramas",
}
FEATURE_NAMES = {
    "U_MPIO": "Municipio", "P_EDADR": "Edad agrupada", "H_DONDE_PREPALIM": "Lugar de preparación de alimentos",
    "P_NIVEL_ANOSR": "Nivel educativo", "VA1_ESTRATO": "Estrato reportado",
    "HA_TOT_PER": "Personas en el hogar", "CONDICION_FISICA": "Dificultad funcional",
    "UA_CLASE": "Clase de asentamiento", "P_SEXO": "Sexo reportado",
    "V_MAT_PISO": "Material del piso", "P_PARENTESCOR": "Parentesco",
    "VF_INTERNET": "Internet en la vivienda",
}


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}".replace(",", ".")


def fmt_pct(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}".replace(".", ",") + " %"


def figure_base(fig: go.Figure, height: int = 370, margin: dict | None = None) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, Arial, sans-serif", color=INK, size=13),
        margin=margin or dict(l=32, r=25, t=30, b=42),
        hoverlabel=dict(bgcolor=NAVY, font_color="white", font_family="IBM Plex Sans, Segoe UI, Arial, sans-serif"),
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        legend=dict(orientation="h", y=-0.22),
    )
    return fig


def card(label: str, value: str, note: str, tone: str = "teal") -> html.Div:
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value"),
        html.Div(note, className="kpi-note"),
    ], className=f"kpi-card {tone}")


def panel(title: str, child, eyebrow: str | None = None, note: str | None = None) -> html.Div:
    return html.Div([
        html.Div([
            html.H3(title),
            html.Span(eyebrow, className="panel-meta") if eyebrow else None,
        ], className="panel-heading"),
        child,
        html.P(note, className="panel-note") if note else None,
    ], className="panel")


def graph(id_: str | None = None, figure: go.Figure | None = None) -> dcc.Graph:
    # Plotly observa el tamaño del contenedor. Sin una altura explícita, ese
    # contenedor crece con el gráfico y dispara un ciclo de redimensionamiento.
    default_heights = {"municipio-chart": 360, "edad-chart": 350,
                       "composicion-chart": 360, "confusion-chart": 350}
    height = (int(figure.layout.height) if figure is not None and figure.layout.height
              else default_heights.get(id_, 350))
    props = {"figure": figure, "config": {"displaylogo": False,
                                        "toImageButtonOptions": {"format": "png", "scale": 2}},
             "responsive": True, "style": {"height": f"{height}px", "width": "100%"},
             "className": "chart"}
    if id_ is not None:
        props["id"] = id_
    return dcc.Graph(**props)


def action_breakdown() -> html.Div:
    labels = EDA["metadata"]["label_breakdown_exact"]
    routes = [
        ("EPS y recibió atención", labels["eps_atendido"], "route-teal"),
        ("Otra acción principal o ninguna", labels["otras_acciones_o_ninguna"], "route-navy"),
        ("Médico particular", labels["medico_particular"], "route-mint"),
        ("EPS sin atención", labels["eps_no_atendido"], "route-coral"),
    ]
    return html.Div([
        html.P(f"De {fmt_int(EXACT['n'])} personas con respuesta clasificable", className="route-denominator"),
        *[html.Div([
            html.Div([
                html.Span(name, className="route-name"),
                html.Strong([fmt_int(value), html.Span(" personas", className="route-unit"),
                             html.Span(fmt_pct(value / EXACT["n"]), className="route-share")],
                            className="route-value"),
            ], className="route-line"),
            html.Div(html.Div(className=f"route-fill {tone}",
                              style={"width": f"{100 * value / EXACT['n']:.3f}%"}),
                     className="route-track", **{"aria-hidden": "true"}),
        ], className="route-row") for name, value, tone in routes],
    ], className="route-breakdown")


def municipal_overview_figure() -> go.Figure:
    records = sorted(EDA["municipal_overview"], key=lambda row: row["sin_formal"] / row["n"])
    fig = go.Figure(go.Bar(
        x=[100 * r["sin_formal"] / r["n"] for r in records],
        y=[r["municipio"] for r in records], orientation="h",
        marker=dict(color=[r["sin_formal"] / r["n"] for r in records], colorscale=[[0, "#A8D8D3"], [1, TEAL]], showscale=False),
        customdata=[[r["n"], r["sin_formal"]] for r in records],
        hovertemplate="%{y}<br>%{x:.1f} % con acción principal fuera de ruta formal<br>Base aproximada: %{customdata[0]:,}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Porcentaje aproximado (%)", yaxis_title="")
    return figure_base(fig, height=610, margin=dict(l=138, r=25, t=15, b=42))


def filter_cube(municipios, sexo, edad, zona, dificultad) -> list[dict]:
    chosen = set(municipios or [])
    return [r for r in EDA["cube"]
            if (not chosen or r["municipio"] in chosen)
            and (sexo == "Todos" or r["sexo"] == sexo)
            and (edad == "Todos" or r["edad"] == edad)
            and (zona == "Todos" or r["zona"] == zona)
            and (dificultad == "Todos" or r["dificultad"] == dificultad)]


def aggregate(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    sums = defaultdict(lambda: [0, 0])
    for row in rows:
        key = tuple(row[k] for k in keys)
        sums[key][0] += row["n"]
        sums[key][1] += row["sin_formal"]
    return [dict(zip(keys, key), n=values[0], sin_formal=values[1])
            for key, values in sums.items() if values[0] > 0]


def coverage_for(municipios, sexo="Todos", edad="Todos", zona="Todos", dificultad="Todos") -> int | None:
    """Límite inferior redondeado; multi-municipio usa el menor de sus miembros."""
    selected = municipios or ["Todos"]
    values = [COVERAGE.get((muni, sexo, edad, zona, dificultad)) for muni in selected]
    if not values or any(value is None for value in values):
        return None
    return min(values)


def safe_to_rate(n: int, coverage: int | None) -> bool:
    return n >= 200 and coverage is not None and coverage >= 80


def empty_figure(message: str = "No hay cruces publicables con estos filtros") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=15))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return figure_base(fig)


def ranked_figure(rows: list[dict], metric: str, sexo, edad, zona, dificultad) -> go.Figure:
    data = aggregate(rows, ("municipio",))
    data = [r for r in data if safe_to_rate(
        r["n"], coverage_for([r["municipio"]], sexo, edad, zona, dificultad)
    )]
    if not data:
        return empty_figure("Cobertura o tamaño insuficiente para comparar municipios")
    if metric == "conteo":
        data.sort(key=lambda r: r["sin_formal"])
        x = [r["sin_formal"] for r in data]
        xlabel = "Personas aproximadas, acción principal fuera de ruta formal"
        hover = "%{y}<br>%{x:,} personas aprox.<br>Base: %{customdata[0]:,}<extra></extra>"
    else:
        data.sort(key=lambda r: r["sin_formal"] / r["n"])
        x = [100 * r["sin_formal"] / r["n"] for r in data]
        xlabel = "Porcentaje aproximado (%)"
        hover = "%{y}<br>%{x:.1f} % aprox.<br>Base: %{customdata[0]:,}<extra></extra>"
    fig = go.Figure(go.Bar(x=x, y=[r["municipio"] for r in data], orientation="h",
                           marker_color=TEAL, customdata=[[r["n"]] for r in data],
                           hovertemplate=hover))
    fig.update_layout(xaxis_title=xlabel, yaxis_title="")
    return figure_base(fig, height=max(360, 55 + 24 * len(data)), margin=dict(l=130, r=22, t=20, b=47))


def age_figure(rows: list[dict], municipios, sexo, zona, dificultad) -> go.Figure:
    data = aggregate(rows, ("edad", "dificultad"))
    data = [r for r in data if safe_to_rate(
        r["n"], coverage_for(municipios, sexo, r["edad"], zona, r["dificultad"])
    )]
    if not data:
        return empty_figure("Cobertura o tamaño insuficiente para comparar edades")
    fig = go.Figure()
    for label, color in [("Sin dificultad funcional", TEAL), ("Con dificultad funcional", CORAL)]:
        group = {r["edad"]: r for r in data if r["dificultad"] == label}
        keys = [age for age in AGE_ORDER if age in group]
        if keys:
            fig.add_scatter(x=keys, y=[100 * group[age]["sin_formal"] / group[age]["n"] for age in keys],
                            mode="lines+markers", name=label, line=dict(color=color, width=3), marker=dict(size=9),
                            customdata=[[group[age]["n"]] for age in keys],
                            hovertemplate="%{x}<br>%{y:.1f} % aprox.<br>Base: %{customdata[0]:,}<extra>" + label + "</extra>")
    fig.update_layout(xaxis_title="Edad", yaxis_title="Porcentaje aproximado (%)")
    return figure_base(fig, height=350)


def composition_figure(rows: list[dict], municipios, sexo, edad, zona, dificultad) -> tuple[go.Figure, str]:
    broad_selection = not municipios and edad == "Todos" and dificultad == "Todos"
    if broad_selection:
        data = [r for r in EDA["zone_sex_summary"]
                if (sexo == "Todos" or r["sexo"] == sexo)
                and (zona == "Todos" or r["zona"] == zona)]
        note = ("Cómo leerla: cada barra muestra, de cada 100 personas de ese sexo y zona, "
                "cuántas quedaron fuera de la ruta formal definida. Se usa toda la cohorte; "
                "los recuentos se redondean a 10 y los porcentajes son aproximados.")
    else:
        grouped = aggregate(rows, ("zona", "sexo"))
        data = [r for r in grouped if safe_to_rate(
            r["n"], coverage_for(municipios, r["sexo"], edad, r["zona"], dificultad)
        )]
        omitted = len(grouped) - len(data)
        note = ("Cada barra usa como base a las personas de ese sexo y zona dentro del filtro. "
                "Comparación basada en cruces publicables. "
                + (f"Se omiten {omitted} grupos por tamaño o cobertura insuficiente. " if omitted else "")
                + "Los porcentajes son aproximados y pueden no representar a toda la subpoblación filtrada.")
    if not data:
        return empty_figure("No hay grupos con cobertura suficiente para comparar"), note
    fig = go.Figure()
    zones = [z for z in ["Cabecera", "Centros poblados y rural disperso"]
             if any(r["zona"] == z for r in data)]
    for label, color in [("Mujer", CORAL), ("Hombre", TEAL)]:
        group = {r["zona"]: r for r in data if r["sexo"] == label}
        present = [z for z in zones if z in group]
        if not present:
            continue
        values = [100 * group[z]["sin_formal"] / group[z]["n"] for z in present]
        bases = [[fmt_int(group[z]["n"])] for z in present]
        fig.add_bar(x=present, y=values, name=label, marker_color=color, customdata=bases,
                    text=[fmt_pct(value / 100) for value in values], textposition="outside",
                    hovertemplate="%{x}<br>%{y:.1f} % aprox.<br>Base: %{customdata[0]} personas<extra>" + label + "</extra>")
    fig.update_layout(barmode="group", yaxis_title="Fuera de ruta formal (%)", xaxis_title="",
                      uniformtext=dict(mode="show", minsize=11))
    fig.update_xaxes(tickmode="array", tickvals=zones,
                     ticktext=["Cabecera" if z == "Cabecera" else "Centros poblados<br>y rural disperso" for z in zones])
    fig.update_yaxes(range=[0, max(100 * r["sin_formal"] / r["n"] for r in data) * 1.18])
    return figure_base(fig, height=360, margin=dict(l=62, r=25, t=30, b=95)), note


def comparison_figure() -> go.Figure:
    keys = ["baseline", "logistica", "random_forest", "hist_gradient_boosting"]
    fig = go.Figure(go.Bar(
        x=[MODEL_NAMES[k] for k in keys],
        y=[MODEL["models"][k]["test"]["pr_auc"] for k in keys],
        marker_color=["#B7C4CE", "#6BAEAA", "#317C84", TEAL],
        text=[f"{MODEL['models'][k]['test']['pr_auc']:.3f}" for k in keys],
        textposition="outside", hovertemplate="%{x}<br>Average Precision: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(yaxis_title="Average Precision (AP)", xaxis_title="", yaxis_range=[0, 0.42])
    return figure_base(fig, height=350, margin=dict(l=45, r=25, t=25, b=80))


def curve_figure() -> go.Figure:
    fig = go.Figure()
    roc = MODEL["roc_curve"]
    pr = MODEL["pr_curve"]
    fig.add_scatter(x=[r["x"] for r in roc], y=[r["y"] for r in roc], mode="lines",
                    name="ROC", line=dict(color=TEAL, width=3), visible=True)
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Azar", line=dict(color="#A7B2BC", dash="dash"), visible=True)
    fig.add_scatter(x=[r["x"] for r in pr], y=[r["y"] for r in pr], mode="lines",
                    name="Precisión–recall", line=dict(color=CORAL, width=3), visible=False)
    base = MODEL["metadata"]["test_positive"] / MODEL["metadata"]["test_n"]
    fig.add_scatter(x=[0, 1], y=[base, base], mode="lines", name="Prevalencia",
                    line=dict(color="#A7B2BC", dash="dash"), visible=False)
    fig.update_layout(
        updatemenus=[dict(type="buttons", direction="right", x=0, y=1.16,
                          buttons=[dict(label="ROC", method="update", args=[{"visible": [True, True, False, False]}, {"xaxis.title": "1 − especificidad", "yaxis.title": "Sensibilidad"}]),
                                   dict(label="Precisión–sensibilidad", method="update", args=[{"visible": [False, False, True, True]}, {"xaxis.title": "Sensibilidad", "yaxis.title": "Precisión"}])])],
        xaxis_title="1 − especificidad", yaxis_title="Sensibilidad", xaxis_range=[0, 1], yaxis_range=[0, 1.02],
    )
    return figure_base(fig, height=390, margin=dict(l=50, r=30, t=65, b=50))


def calibration_figure() -> go.Figure:
    bins = MODEL["calibration"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 0.6], y=[0, 0.6], name="Calibración perfecta", mode="lines",
                    line=dict(color="#A7B2BC", dash="dash"))
    fig.add_scatter(x=[r["mean_predicted"] for r in bins], y=[r["observed"] for r in bins],
                    mode="lines+markers", name="Modelo", line=dict(color=TEAL, width=3),
                    marker=dict(size=8), customdata=[[r["n"]] for r in bins],
                    hovertemplate="Predicho: %{x:.1%}<br>Observado: %{y:.1%}<br>Base: %{customdata[0]:,}<extra></extra>")
    fig.update_layout(xaxis_title="Probabilidad predicha media", yaxis_title="Proporción observada",
                      xaxis_tickformat=".0%", yaxis_tickformat=".0%", xaxis_range=[0, 0.6], yaxis_range=[0, 0.6])
    return figure_base(fig, height=380)


def importance_figure() -> go.Figure:
    data = sorted(MODEL["importance"][:8], key=lambda x: x["mean_ap_drop"])
    fig = go.Figure(go.Bar(x=[r["mean_ap_drop"] for r in data],
                           y=[FEATURE_NAMES.get(r["feature"], r["feature"]) for r in data],
                           orientation="h", marker_color=TEAL,
                           hovertemplate="%{y}<br>Caída de AP al permutar: %{x:.3f}<extra></extra>"))
    fig.update_layout(xaxis_title="Caída media de AP", yaxis_title="")
    return figure_base(fig, height=355, margin=dict(l=170, r=25, t=15, b=45))


def threshold_row(value: float) -> dict:
    return min(MODEL["thresholds"], key=lambda r: abs(r["threshold"] - value))


def threshold_metrics(row: dict) -> dict:
    tp, fp, tn, fn = [row[k] for k in ("tp", "fp", "tn", "fn")]
    return {
        "precision": tp / (tp + fp) if tp + fp else 0,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "flagged": tp + fp,
    }


def confusion_figure(row: dict) -> go.Figure:
    z = [[row["tn"], row["fp"]], [row["fn"], row["tp"]]]
    fig = go.Figure(go.Heatmap(z=z, x=["Ruta formal", "Fuera de ruta formal"],
                               y=["Ruta formal", "Fuera de ruta formal"],
                               text=[[fmt_int(v) for v in line] for line in z], texttemplate="%{text}",
                               textfont=dict(size=18), colorscale=[[0, "#EDF5F3"], [1, TEAL]], showscale=False,
                               hovertemplate="Real: %{y}<br>Predicho: %{x}<br>%{text} personas<extra></extra>"))
    fig.update_layout(xaxis_title="Predicción", yaxis_title="Dato censal")
    fig.update_yaxes(autorange="reversed")
    return figure_base(fig, height=350, margin=dict(l=138, r=25, t=22, b=70))


def layout_panorama() -> html.Div:
    source = EDA["metadata"]
    labels = source["label_breakdown_exact"]
    flow = source["population_flow"]
    return html.Div([
        html.Div([
            html.Div([
                html.H1("¿Qué ruta de atención se declaró ante un problema de salud?"),
                html.P("Analizamos respuestas del CNPV 2018 en el Atlántico y las características relacionadas con la acción principal declarada.", className="hero-sub"),
                html.Div([
                    html.Span("CNPV 2018 · Atlántico · DANE"),
                    html.Button("Explorar los datos", id="go-eda", className="hero-action"),
                ], className="hero-actions"),
            ], className="hero-copy"),
            html.Div([
                html.Div(fmt_pct(EXACT["sin_formal"] / EXACT["n"], 2), className="hero-stat"),
                html.H2("Fuera de la ruta formal definida"),
                html.P(f"{fmt_int(EXACT['sin_formal'])} de {fmt_int(EXACT['n'])} personas en la cohorte.", className="hero-base"),
                html.P("Es una clasificación del tratamiento principal reportado. No equivale a atención denegada ni a ausencia de toda atención.", className="hero-caveat"),
            ], className="hero-side"),
        ], className="hero"),
        html.Section([
            html.H2("Una respuesta del censo no cuenta toda la historia"),
            html.P("Ante un problema de salud, una persona pudo acudir a su entidad de seguridad social, consultar a un médico particular, buscar otra alternativa o no hacer nada. El CNPV registra cuál fue su tratamiento principal. Comparar esas respuestas ayuda a detectar patrones que merecen estudiarse mejor; no permite reconstruir toda la trayectoria de atención."),
            html.Div([
                html.Div([html.Span("FUENTE", className="context-label"), html.Strong("CNPV 2018 · DANE"),
                          html.P("Microdatos anonimizados de personas, hogares y viviendas del Atlántico.")]),
                html.Div([html.Span("UNIDAD", className="context-label"), html.Strong("Una persona"),
                          html.P("Que declaró un problema de salud en los 30 días previos, sin hospitalización.")]),
                html.Div([html.Span("ALCANCE", className="context-label"), html.Strong("Descripción de 2018"),
                          html.P("Las asociaciones no indican causas ni describen necesariamente la situación actual.")]),
            ], className="context-facts"),
        ], className="story-section"),
        html.Section([
            html.Div([
                html.H2("Entender cómo varía la ruta declarada de atención"),
                html.P("Analizar las diferencias en la clasificación de acceso formal según características funcionales, sociodemográficas, territoriales, del hogar y de la vivienda. Después, evaluar hasta qué punto esas variables permiten ordenar la clase menos frecuente sin usar información que revele la respuesta."),
            ], className="objective-lead"),
            html.Div([
                html.H3("Tres objetivos concretos"),
                html.Ol([
                    html.Li([html.Strong("Definir bien la población y la respuesta."), " Mostrar quiénes entran al análisis, cómo se construye la etiqueta y qué queda fuera."]),
                    html.Li([html.Strong("Explorar las diferencias."), " Comparar edad, sexo, dificultad funcional, zona y municipio con filtros y denominadores visibles."]),
                    html.Li([html.Strong("Evaluar el modelo con prudencia."), " Contrastar enfoques, revisar errores y reconocer dónde la predicción es menos fiable."]),
                ]),
            ], className="objective-list"),
        ], className="objective-grid"),
        html.Section([
            html.Div([
                html.H2("¿A quién representan estas cifras?"),
                html.P("La cohorte no es toda la población del Atlántico. Solo incluye respuestas para las que pudo aplicarse la regla del proyecto."),
            ], className="section-heading"),
            html.Div([
                html.Div([html.Span("01", className="flow-step"), html.Strong(fmt_int(flow["people"])),
                          html.Span("personas en el archivo censal", className="flow-note")]),
                html.Div([html.Span("02", className="flow-step"), html.Strong(fmt_int(flow["recent_health_problem"])),
                          html.Span("declararon el problema de salud definido", className="flow-note")]),
                html.Div([html.Span("03", className="flow-step"), html.Strong(fmt_int(flow["analytic"])),
                          html.Span(f"con etiqueta clasificable; {fmt_int(flow['unclassifiable'])} excluidas", className="flow-note")]),
            ], className="flow-grid"),
            html.P("La unidad es la persona. Hogar y vivienda aportan características adicionales; las uniones conservan una fila por persona. No se extrapolan estos resultados a otros años.", className="flow-caption"),
        ], className="story-section"),
        html.Div([
            panel("Las cuatro rutas registradas", action_breakdown(), "CÓMO SE DEFINIÓ LA RESPUESTA",
                  "Son acciones principales reportadas. ‘Otra acción o ninguna’ incluye farmacia y otras formas de atención; no equivale a ausencia de toda atención."),
            html.Div([
                html.H3("La mayoría de la clase ‘fuera de la ruta formal’ no reportó una negativa de la EPS."),
                html.P(f"De {fmt_int(EXACT['sin_formal'])} personas en esa clase, {fmt_int(labels['eps_no_atendido'])} dijeron haber acudido a su EPS sin recibir atención. Las otras {fmt_int(labels['otras_acciones_o_ninguna'])} registraron una acción principal distinta o ninguna. Por eso, el panel evita llamar a toda esa clase ‘atención denegada’."),
                html.Div("Definición operativa · no permite afirmar causas.", className="insight-foot"),
            ], className="insight-card"),
        ], className="two-col uneven"),
        panel("Una vista por municipio", graph(figure=municipal_overview_figure()), "PATRÓN TERRITORIAL",
              "Se muestran municipios con al menos 100 personas y 10 en cada clase; conteos redondeados a 10 antes de publicarse. Las diferencias pueden reflejar composición demográfica y otras características."),
        html.P("Para consultar las definiciones, las tablas exactas y las decisiones metodológicas, abre el informe Bookdown desde el enlace superior.", className="source-line"),
        html.P(f"Fuente: microdatos anonimizados del CNPV 2018, DANE. Universo: quienes reportaron problema de salud en los últimos 30 días sin hospitalización. Se excluyeron {fmt_int(flow['unclassifiable'])} respuestas no clasificables. Nombres municipales: DIVIPOLA del DANE.", className="source-line"),
    ], className="page")


def dropdown(id_: str, label: str, options: list[str], multi: bool = False):
    return html.Label([
        html.Span(label, className="filter-label"),
        dcc.Dropdown(id=id_, options=[{"label": v, "value": v} for v in options],
                     value=[] if multi else "Todos", multi=multi, clearable=multi,
                     placeholder="Todos los municipios" if multi else None,
                     className="filter-control"),
    ], className="filter")


def layout_explorar() -> html.Div:
    municip = sorted({r["municipio"] for r in EDA["cube"]})
    return html.Div([
        html.Div([
            html.H2("Explora los datos"),
            html.P("Compara las respuestas de 2018 por municipio, edad, sexo, zona y dificultad funcional. Los filtros usan cruces publicables; la comparación general por sexo y zona se calcula aparte con grupos amplios."),
        ], className="page-intro"),
        html.P([html.Strong("Qué se compara: "), "la proporción cuya acción principal quedó fuera de EPS con atención o médico particular. Al filtrar cambian el grupo, su denominador y la cobertura publicable."], className="eda-definition"),
        html.Div([
            dropdown("f-municipio", "Municipio", municip, multi=True),
            dropdown("f-sexo", "Sexo reportado", ["Todos", "Hombre", "Mujer"]),
            dropdown("f-edad", "Edad", ["Todos"] + AGE_ORDER),
            dropdown("f-zona", "Zona", ["Todos", "Cabecera", "Centros poblados y rural disperso"]),
            dropdown("f-dificultad", "Dificultad funcional diaria", ["Todos", "Con dificultad funcional", "Sin dificultad funcional"]),
        ], className="filter-grid"),
        html.Div([
            html.Div(id="explore-kpis", className="kpi-grid two"),
            html.Div(id="coverage-note", className="coverage-note"),
        ]),
        html.Div([
            panel("Municipios en la selección", html.Div([
                dcc.RadioItems(id="metric-toggle", options=[{"label": "Porcentaje", "value": "tasa"},
                                                            {"label": "Personas", "value": "conteo"}],
                               value="tasa", inline=True, className="segmented"),
                graph("municipio-chart"),
            ]), "COMPARAR TERRITORIOS", RULE_NOTE),
            panel("Cómo cambia por edad", graph("edad-chart"), "PERFIL POR DIFICULTAD",
                  "Porcentajes dentro de cada grupo publicado; los cruces omitidos no entran en la línea."),
        ], className="two-col"),
        panel("Sexo y zona de residencia", html.Div([graph("composicion-chart"),
                                                    html.P(id="composition-note", className="chart-explanation")]), "OTRA MIRADA",
              "La comparación es descriptiva; los grupos pueden diferir en edad, municipio y otras condiciones."),
        html.Div([
            html.Button("Descargar selección agregada", id="download-button", className="download-button"),
            dcc.Download(id="download-data"),
            html.Span("El archivo contiene solo celdas publicables y recuentos redondeados.", className="download-note"),
        ], className="download-row"),
        html.P(f"Protección de grupos pequeños: {EDA['metadata']['rules']} El cubo publicado cubre {str(EDA['metadata']['coverage_pct']).replace('.', ',')} % del universo clasificable antes de aplicar filtros.", className="source-line"),
    ], className="page")


def layout_modelo() -> html.Div:
    chosen = MODEL["metadata"]["chosen_threshold"]
    audit = MODEL["audit_2026"]
    uncertainty = MODEL["uncertainty"]["intervals_95"]
    marks = {i / 20: (f"{i / 20:.2f}".replace(".", ",") if i % 2 == 0 else "") for i in range(1, 17)}
    marks[chosen] = "Validado"
    return html.Div([
        html.Div([
            html.H2("Un modelo para ordenar perfiles, con límites claros"),
            html.P("Comparamos cuatro enfoques. El mejor entre los probados fue boosting de histogramas. Sus resultados corresponden a viviendas reservadas del mismo censo de 2018."),
        ], className="page-intro"),
        html.Div([
            card("Average Precision", f"{SOURCE['pr_auc']:.3f}".replace(".", ","), "Referencia por prevalencia: 0,211 · prueba interna"),
            card("ROC-AUC", f"{SOURCE['roc_auc']:.3f}".replace(".", ","), "Capacidad de ordenar casos · prueba interna", "navy"),
            card("Brier", f"{SOURCE['brier']:.3f}".replace(".", ","), "Menor es mejor · prueba interna", "coral"),
        ], className="kpi-grid model-metrics"),
        html.Section([
            html.Div([
                html.H3("El modelo se mantiene después de nuevas pruebas"),
                html.P(f"Probamos {audit['alternatives']} alternativas de preparación de datos y ajuste. La mayor AP nueva en validación fue " +
                       f"{audit['best_new_validation_ap']:.4f}".replace(".", ",") +
                       ", frente a " + f"{audit['original_validation_ap']:.4f}".replace(".", ",") +
                       " del modelo original. La diferencia fue demasiado pequeña e incierta para justificar un cambio."),
            ]),
            html.Div([
                html.Strong("Una diferencia que merece atención"),
                html.P(f"Con el umbral elegido, la sensibilidad fue {fmt_pct(audit['recall_difficulty'])} entre quienes declararon dificultad funcional y {fmt_pct(audit['recall_no_difficulty'])} entre quienes no la declararon. Al ajustar descriptivamente por edad, la brecha se reduce, pero persiste."),
                html.A("Ver la revisión completa en el Bookdown", href="/informe/modelo.html#revision-modelo-2026", target="_blank", rel="noopener noreferrer"),
            ]),
        ], className="audit-strip"),
        html.Div([
            panel("Comparación en prueba", graph(figure=comparison_figure()), "MÉTRICA PRINCIPAL",
                  "Average Precision resume el ordenamiento de la clase minoritaria. Es AP no interpolada; no es el área trapezoidal de la curva PR."),
            panel("Curvas de discriminación", graph(figure=curve_figure()), "ROC Y PRECISIÓN–RECALL",
                  "Curvas visuales resumidas; las cifras de AP y ROC-AUC provienen de todas las puntuaciones de prueba."),
        ], className="two-col"),
        html.Div([
            html.Div([
                html.H3("¿Qué cambia al marcar a más personas?"),
                html.P("Mueve el umbral para comparar alcance y falsos avisos en la prueba de 2018. El punto ‘Validado’ se eligió con el conjunto de validación; los demás son escenarios exploratorios."),
                dcc.Slider(id="threshold", min=0.05, max=0.8, step=None, marks=marks, value=chosen,
                           tooltip={"placement": "bottom", "always_visible": False}),
                html.Div(id="threshold-title", className="threshold-title"),
                html.Div(id="threshold-kpis", className="threshold-grid"),
            ], className="threshold-controls"),
            panel("Aciertos y errores", graph("confusion-chart"), "MATRIZ DE CONFUSIÓN",
                  "La clase positiva es la acción principal fuera de la ruta formal. Las cifras son del conjunto de prueba reservado."),
        ], className="two-col"),
        html.Div([
            panel("Probabilidad y frecuencia observada", graph(figure=calibration_figure()), "CALIBRACIÓN",
                  "Cada punto agrupa aproximadamente una décima parte de la prueba. La cercanía a la diagonal no valida el modelo para otro año."),
            panel("Variables que más contribuyeron al ordenamiento", graph(figure=importance_figure()), "IMPORTANCIA POR PERMUTACIÓN",
                  "La caída de AP al alterar una variable mide dependencia predictiva. No representa efecto causal ni justifica una decisión individual."),
        ], className="two-col"),
        html.Div([
            html.H3("Cómo leer este modelo"),
            html.Div([
                html.Div([html.H4("Separación cuidadosa"), html.P("Entrenamiento, validación y prueba se separaron por vivienda. Preprocesamiento y ajustes se hicieron dentro de entrenamiento; el umbral se eligió en validación.")]),
                html.Div([html.H4("Una mejora acotada"), html.P(
                    "El AP del modelo fue 0,339; su intervalo interno de 95 % fue "
                    f"{uncertainty['selected_ap'][0]:.3f}".replace(".", ",") + "–" +
                    f"{uncertainty['selected_ap'][1]:.3f}".replace(".", ",") +
                    ". La discriminación es moderada.")]),
                html.Div([html.H4("Uso responsable"), html.P("Los datos son transversales de 2018. Falta validación temporal y geográfica antes de aplicarlo a personas actuales o decisiones de atención.")]),
            ], className="method-grid"),
            html.P("La clase modelada depende de una sola acción principal reportada. No mide afiliación, necesidad clínica, barreras causales ni ausencia de toda atención. ‘Dificultad funcional’ no equivale a diagnóstico de discapacidad.", className="method-warning"),
        ], className="method-panel"),
    ], className="page")


app = Dash(__name__, title="Salud Atlántico · DataViz", suppress_callback_exceptions=True)
app.index_string = app.index_string.replace(
    "{%css%}",
    '<link rel="preload" href="/assets/fonts/ibm-plex-sans-latin-variable.woff2" as="font" type="font/woff2" crossorigin>{%css%}',
)
server = app.server


@server.get("/health")
def health():
    return {"status": "ok", "data_loaded": True}


@server.get("/informe/")
@server.get("/informe/<path:filename>")
def informe(filename="index.html"):
    path = Path(__file__).resolve().parent / "informe"
    if not (path / "index.html").is_file():
        abort(404)
    return send_from_directory(path, filename)


app.layout = html.Div([
    html.Div([
        html.Div([html.Span(className="brand-dot"), html.Span("DATAVIZ", className="brand-main"), html.Span("/ SALUD ATLÁNTICO", className="brand-sub")], className="brand"),
        html.Div("CNPV 2018 · DANE", className="header-source"),
    ], className="site-header"),
    dcc.Tabs(id="nav", value="panorama", className="nav-tabs", children=[
        dcc.Tab(label="Proyecto", value="panorama", className="nav-tab", selected_className="nav-tab-active"),
        dcc.Tab(label="EDA", value="explorar", className="nav-tab", selected_className="nav-tab-active"),
        dcc.Tab(label="Modelo y método", value="modelo", className="nav-tab", selected_className="nav-tab-active"),
    ]),
    html.Div(html.A("Leer informe completo", href="/informe/", target="_blank", rel="noopener noreferrer", className="book-link"), className="book-link-wrap"),
    html.Main([
        html.Div(layout_panorama(), id="page-panorama"),
        html.Div(layout_explorar(), id="page-explorar", style={"display": "none"}),
        html.Div(layout_modelo(), id="page-modelo", style={"display": "none"}),
    ]),
    html.Footer([
        html.Span("DATAVIZ · Análisis reproducible del Atlántico"),
        html.Span([html.A("Microdatos CNPV 2018 · DANE", href="https://microdatos.dane.gov.co/catalog/643",
                          target="_blank", rel="noopener noreferrer"), " · Cifras históricas"]),
    ], className="site-footer"),
], className="app-shell")


@app.callback(Output("page-panorama", "style"), Output("page-explorar", "style"), Output("page-modelo", "style"), Input("nav", "value"))
def switch_page(tab):
    return tuple({"display": "block" if tab == name else "none"} for name in ("panorama", "explorar", "modelo"))


@app.callback(Output("nav", "value"), Input("go-eda", "n_clicks"), prevent_initial_call=True)
def go_to_eda(_clicks):
    return "explorar"


@app.callback(
    Output("explore-kpis", "children"), Output("coverage-note", "children"),
    Output("municipio-chart", "figure"), Output("municipio-chart", "style"),
    Output("edad-chart", "figure"), Output("composicion-chart", "figure"),
    Output("composition-note", "children"),
    Input("f-municipio", "value"), Input("f-sexo", "value"), Input("f-edad", "value"),
    Input("f-zona", "value"), Input("f-dificultad", "value"), Input("metric-toggle", "value"),
)
def update_explore(municipios, sexo, edad, zona, dificultad, metric):
    rows = filter_cube(municipios, sexo, edad, zona, dificultad)
    n = sum(r["n"] for r in rows)
    positive = sum(r["sin_formal"] for r in rows)
    coverage_pct = coverage_for(municipios, sexo, edad, zona, dificultad)
    trusted_rate = safe_to_rate(n, coverage_pct)
    kpis = [
        card("Personas representadas", "≈ " + fmt_int(n), "Suma de celdas publicables redondeadas"),
        card("Acción principal fuera de ruta formal", fmt_pct(positive / n) if trusted_rate else "Cobertura insuficiente",
             "Proporción aproximada en celdas publicables" if trusted_rate else "Se oculta para evitar una lectura engañosa", "coral"),
    ]
    coverage_text = "sin estimación publicable" if coverage_pct is None else f"al menos {coverage_pct} %"
    interpretation = (
        "La tasa mostrada describe los cruces publicados y puede diferir de la tasa de toda la subpoblación."
        if trusted_rate else
        "La tasa se oculta porque esta selección no tiene cobertura o tamaño suficientes para interpretarla."
    )
    coverage = f"{len(rows)} cruces publicables en esta selección. Cobertura del filtro: {coverage_text}" + (" (límite conservador por municipio)." if municipios and len(municipios) > 1 else ".") + f" {RULE_NOTE} {interpretation}"
    ranked = ranked_figure(rows, metric, sexo, edad, zona, dificultad)
    ranked_style = {"height": f"{int(ranked.layout.height)}px", "width": "100%"}
    composition, composition_note = composition_figure(rows, municipios, sexo, edad, zona, dificultad)
    return (kpis, coverage, ranked, ranked_style,
            age_figure(rows, municipios, sexo, zona, dificultad),
            composition, composition_note)


@app.callback(Output("threshold-title", "children"), Output("threshold-kpis", "children"),
              Output("confusion-chart", "figure"), Input("threshold", "value"))
def update_threshold(value):
    row = threshold_row(float(value))
    met = threshold_metrics(row)
    label = "Umbral validado" if abs(row["threshold"] - MODEL["metadata"]["chosen_threshold"]) < 1e-8 else "Escenario exploratorio"
    title = f"{label}: {row['threshold']:.3f}".replace(".", ",")
    values = [
        card("Sensibilidad", fmt_pct(met["recall"]), "De los casos de la clase, cuántos marca"),
        card("Precisión", fmt_pct(met["precision"]), "De los marcados, cuántos pertenecen a la clase", "coral"),
        card("Personas marcadas", fmt_int(met["flagged"]), f"De {fmt_int(MODEL['metadata']['test_n'])} en prueba", "navy"),
    ]
    return title, values, confusion_figure(row)


@app.callback(Output("download-data", "data"), Input("download-button", "n_clicks"),
              State("f-municipio", "value"), State("f-sexo", "value"), State("f-edad", "value"),
              State("f-zona", "value"), State("f-dificultad", "value"), prevent_initial_call=True)
def download_selection(_clicks, municipios, sexo, edad, zona, dificultad):
    rows = filter_cube(municipios, sexo, edad, zona, dificultad)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["municipio", "sexo", "edad", "zona", "dificultad", "n", "sin_formal"])
    writer.writeheader()
    writer.writerows(rows)
    return dict(content=stream.getvalue(), filename="dataviz_salud_agregados.csv", type="text/csv")


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8050")), debug=False)
