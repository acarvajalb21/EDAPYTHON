"""Panel interactivo público: acceso formal a salud en Atlántico, CNPV 2018."""

from __future__ import annotations

import csv
import io
import json
import os
import textwrap
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
from flask import abort, jsonify, request, send_from_directory

from dash_salud.asistente import LARGO_MAXIMO, Asistente


DATA_DIR = Path(__file__).resolve().parent / "data"
EDA = json.loads((DATA_DIR / "eda.json").read_text(encoding="utf-8"))
MODEL = json.loads((DATA_DIR / "modelo.json").read_text(encoding="utf-8"))
SOURCE = MODEL["models"]["hist_gradient_boosting"]["test"]
EXACT = {"n": EDA["metadata"]["total_labeled_exact"], "sin_formal": EDA["metadata"]["no_access_exact"]}
COVERAGE = {tuple(row["key"]): row["coverage_floor_5pct"] for row in EDA.get("coverage_index", [])}
# Textos y tablas de las secciones, comunes con Shiny; ver generar_contenido.py.
CONTENIDO = json.loads((DATA_DIR / "contenido.json").read_text(encoding="utf-8"))
NOMBRE = CONTENIDO["nombre"]
SECCIONES = [seccion["id"] for seccion in CONTENIDO["secciones"]]

# Tokens de color (ver DISENO.md). FUERA y DENTRO significan siempre lo mismo.
TINTA = "#14233A"
TINTA_MEDIA = "#3B4A60"
TINTA_SUAVE = "#556378"
HILO = "rgba(20, 35, 58, .13)"
SUELO = "#E9EDF2"
DENTRO = "#2454D6"
FUERA = "#D93F4C"
GRUPO_A = "#00908A"
GRUPO_B = "#A86C00"
REFERENCIA = "#7C8799"
BASE = "#A9B4C2"
FUENTE = "Atkinson Hyperlegible Next, Segoe UI, Arial, sans-serif"
AGE_ORDER = EDA["metadata"]["age_bands"]
MODEL_NAMES = {
    "baseline": "Referencia (prevalencia)",
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
    "VF_INTERNET": "Internet en la vivienda", "V_MAT_PARED": "Material de las paredes",
    "HOGAR_OTROS_ENFERMOS": "Otros enfermos en el hogar",
    "SECCION_PCT_ENFERMOS": "Enfermos en la sección censal",
}
NUEVAS = {"HOGAR_OTROS_ENFERMOS", "SECCION_PCT_ENFERMOS"}
# Los 23 municipios DIVIPOLA del Atlántico; mismos nombres que generar_datos.MUNICIPIOS.
ATLANTICO_MUNICIPIOS = (
    "Barranquilla", "Baranoa", "Campo de la Cruz", "Candelaria", "Galapa", "Juan de Acosta",
    "Luruaco", "Malambo", "Manatí", "Palmar de Varela", "Piojó", "Polonuevo", "Ponedera",
    "Puerto Colombia", "Repelón", "Sabanagrande", "Sabanalarga", "Santa Lucía", "Santo Tomás",
    "Soledad", "Suan", "Tubará", "Usiacurí",
)
DROPDOWN_LABELS = {
    "select_all": "Seleccionar todos", "deselect_all": "Quitar todos",
    "selected_count": "{num_selected} seleccionados", "search": "Buscar",
    "clear_search": "Borrar búsqueda", "clear_selection": "Quitar selección",
    "no_options_found": "Sin coincidencias",
}


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}".replace(",", ".")


def fmt_pct(value: float, digits: int = 1) -> str:
    # Espacio no separable: el signo % no queda solo en otra línea.
    return f"{100 * value:.{digits}f}".replace(".", ",") + " %"


def omitted_municipios_sentence(present, place: str, reason: str) -> str:
    missing = [name for name in sorted(ATLANTICO_MUNICIPIOS) if name not in set(present)]
    if not missing:
        return ""
    verb = "no aparece" if len(missing) == 1 else "no aparecen"
    return f" {', '.join(missing)} {verb} {place}: {reason}."


def figure_base(fig: go.Figure, height: int = 370, margin: dict | None = None, legend: bool = False) -> go.Figure:
    eje = dict(gridcolor=HILO, zeroline=False, linecolor=BASE, tickcolor=BASE, fixedrange=True, automargin=True,
               title_font=dict(color=TINTA_SUAVE, size=13))
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.", showlegend=legend,
        font=dict(family=FUENTE, color=TINTA_MEDIA, size=14),
        margin=margin or dict(l=52, r=18, t=10, b=46),
        hoverlabel=dict(bgcolor=TINTA, bordercolor=TINTA, align="left", font=dict(family=FUENTE, color="#FFFFFF", size=14)),
        xaxis=eje, yaxis=eje,
        legend=dict(orientation="h", x=0, y=1.1, xanchor="left", yanchor="bottom", font=dict(color=TINTA_MEDIA)),
    )
    return fig


def ficha(etiqueta: str, valor: str, nota: str, tono: str = "") -> html.Div:
    return html.Div([html.Div(etiqueta, className="c-ficha-etiqueta"), html.Div(valor, className="c-ficha-valor"),
                     html.Div(nota, className="c-ficha-nota")], className=f"c-ficha {tono}".strip())


def graph(id_: str | None = None, figure: go.Figure | None = None) -> dcc.Graph:
    # Plotly observa el tamaño del contenedor. Sin una altura explícita, ese
    # contenedor crece con el gráfico y dispara un ciclo de redimensionamiento.
    default_heights = {"municipio-chart": 360, "edad-chart": 320, "composicion-chart": 320}
    height = (int(figure.layout.height) if figure is not None and figure.layout.height
              else default_heights.get(id_, 350))
    props = {"figure": figure, "config": {"displayModeBar": False},
             "responsive": True, "style": {"height": f"{height}px", "width": "100%"},
             "className": "grafica"}
    if id_ is not None:
        props["id"] = id_
    return dcc.Graph(**props)


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


def reference_aggregate(municipios, sexo, edad, zona, dificultad) -> tuple[str, dict, str] | None:
    """Agregado publicado aparte que describe la misma selección sin cruces adicionales."""
    if edad != "Todos" or dificultad != "Todos":
        return None
    if municipios and len(municipios) == 1 and sexo == "Todos" and zona == "Todos":
        row = next((r for r in EDA["municipal_overview"] if r["municipio"] == municipios[0]), None)
        return (municipios[0], row, "el panorama municipal de esta aplicación") if row else None
    if not municipios:
        rows = [r for r in EDA["zone_sex_summary"]
                if (sexo == "Todos" or r["sexo"] == sexo) and (zona == "Todos" or r["zona"] == zona)]
        group = " · ".join(value for value in (sexo, zona) if value != "Todos") or "Toda la cohorte"
        return (group, {"n": sum(r["n"] for r in rows), "sin_formal": sum(r["sin_formal"] for r in rows)},
                "la comparación por sexo y zona de esta página")
    return None


def empty_figure(message: str = "No hay cruces publicables con estos filtros") -> go.Figure:
    fig = go.Figure()
    # Se parte en líneas cortas para que el aviso no se recorte en pantallas estrechas.
    fig.add_annotation(text="<br>".join(textwrap.wrap(message, 34)), showarrow=False,
                       font=dict(color=TINTA_SUAVE, size=15))
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
                           marker_color=FUERA, customdata=[[r["n"]] for r in data],
                           hovertemplate=hover))
    fig.update_layout(xaxis_title=xlabel, yaxis_title="", bargap=0.34)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", ticks="")
    return figure_base(fig, height=max(170, 58 + 25 * len(data)), margin=dict(l=8, r=18, t=6, b=44))


def age_figure(rows: list[dict], municipios, sexo, zona, dificultad) -> go.Figure:
    data = aggregate(rows, ("edad", "dificultad"))
    data = [r for r in data if safe_to_rate(
        r["n"], coverage_for(municipios, sexo, r["edad"], zona, r["dificultad"])
    )]
    if not data:
        return empty_figure("Cobertura o tamaño insuficiente para comparar edades")
    fig = go.Figure()
    for label, color in [("Sin dificultad funcional", GRUPO_A), ("Con dificultad funcional", GRUPO_B)]:
        group = {r["edad"]: r for r in data if r["dificultad"] == label}
        keys = [age for age in AGE_ORDER if age in group]
        if keys:
            fig.add_scatter(x=keys, y=[100 * group[age]["sin_formal"] / group[age]["n"] for age in keys],
                            mode="lines+markers", name=label, line=dict(color=color, width=2.5), marker=dict(size=10, line=dict(color=SUELO, width=2)),
                            customdata=[[group[age]["n"]] for age in keys],
                            hovertemplate="%{x}<br>%{y:.1f} % aprox.<br>Base: %{customdata[0]:,}<extra>" + label + "</extra>")
    fig.update_layout(xaxis_title="Edad", yaxis_title="Fuera de la ruta formal (%)")
    return figure_base(fig, height=320, legend=True, margin=dict(l=52, r=18, t=34, b=46))


def composition_figure(rows: list[dict], municipios, sexo, edad, zona, dificultad) -> tuple[go.Figure, str]:
    broad_selection = not municipios and edad == "Todos" and dificultad == "Todos"
    if broad_selection:
        data = [r for r in EDA["zone_sex_summary"]
                if (sexo == "Todos" or r["sexo"] == sexo)
                and (zona == "Todos" or r["zona"] == zona)]
        note = ("Cada barra muestra, de cada 100 personas de ese sexo y zona, cuántas quedaron fuera de la ruta formal. "
                "Se usan todas las personas estudiadas y los recuentos se redondean a 10.")
    else:
        grouped = aggregate(rows, ("zona", "sexo"))
        data = [r for r in grouped if safe_to_rate(
            r["n"], coverage_for(municipios, r["sexo"], edad, r["zona"], dificultad)
        )]
        omitted = len(grouped) - len(data)
        note = ("Cada barra usa como base a las personas de ese sexo y zona dentro del filtro. "
                + (f"Se omiten {omitted} grupos por tamaño o cobertura insuficiente. " if omitted else "")
                + "Los porcentajes son aproximados y pueden no representar a todo el grupo filtrado.")
    if not data:
        return empty_figure("No hay grupos con cobertura suficiente para comparar"), note
    fig = go.Figure()
    zones = [z for z in ["Cabecera", "Centros poblados y rural disperso"]
             if any(r["zona"] == z for r in data)]
    for label, color in [("Mujer", GRUPO_B), ("Hombre", GRUPO_A)]:
        group = {r["zona"]: r for r in data if r["sexo"] == label}
        present = [z for z in zones if z in group]
        if not present:
            continue
        values = [100 * group[z]["sin_formal"] / group[z]["n"] for z in present]
        bases = [[fmt_int(group[z]["n"])] for z in present]
        fig.add_bar(x=present, y=values, name=label, marker_color=color, customdata=bases,
                    text=[fmt_pct(value / 100) for value in values], textposition="outside",
                    hovertemplate="%{x}<br>%{y:.1f} % aprox.<br>Base: %{customdata[0]} personas<extra>" + label + "</extra>")
    fig.update_layout(barmode="group", yaxis_title="Fuera de la ruta formal (%)", xaxis_title="", bargap=0.34,
                      uniformtext=dict(mode="show", minsize=11))
    fig.update_xaxes(tickmode="array", tickvals=zones,
                     ticktext=["Cabecera" if z == "Cabecera" else "Centros poblados<br>y rural disperso" for z in zones])
    fig.update_yaxes(range=[0, max(100 * r["sin_formal"] / r["n"] for r in data) * 1.18])
    return figure_base(fig, height=320, legend=True, margin=dict(l=52, r=18, t=34, b=50)), note


def comparison_figure() -> go.Figure:
    keys = ["baseline", "logistica", "random_forest", "hist_gradient_boosting"]
    top = max(MODEL["models"][k]["test"]["pr_auc"] for k in keys)
    fig = go.Figure(go.Bar(
        x=[MODEL_NAMES[k] for k in keys],
        y=[MODEL["models"][k]["test"]["pr_auc"] for k in keys],
        marker_color=[REFERENCIA, BASE, BASE, DENTRO],
        text=[f"{MODEL['models'][k]['test']['pr_auc']:.3f}".replace(".", ",") for k in keys],
        textposition="outside", hovertemplate="%{x}<br>Precisión promedio: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="", yaxis_title="Precisión promedio (AP)", yaxis_range=[0, top * 1.2], bargap=0.34)
    fig.update_xaxes(gridcolor="rgba(0,0,0,0)", ticks="")
    return figure_base(fig, height=340)


def curve_figure(kind: str = "roc") -> go.Figure:
    fig = go.Figure()
    if kind == "roc":
        roc = MODEL["roc_curve"]
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Azar", line=dict(color=REFERENCIA, width=1.5, dash="dash"))
        fig.add_scatter(x=[r["x"] for r in roc], y=[r["y"] for r in roc], mode="lines", name="Modelo", line=dict(color=DENTRO, width=2.5))
        fig.update_layout(xaxis_title="1 − especificidad", yaxis_title="Sensibilidad")
    else:
        pr = MODEL["pr_curve"]
        base = MODEL["metadata"]["test_positive"] / MODEL["metadata"]["test_n"]
        fig.add_scatter(x=[0, 1], y=[base, base], mode="lines", name="Prevalencia", line=dict(color=REFERENCIA, width=1.5, dash="dash"))
        fig.add_scatter(x=[r["x"] for r in pr], y=[r["y"] for r in pr], mode="lines", name="Modelo", line=dict(color=DENTRO, width=2.5))
        fig.update_layout(xaxis_title="Sensibilidad", yaxis_title="Precisión")
    fig.update_layout(xaxis_range=[0, 1], yaxis_range=[0, 1.02])
    return figure_base(fig, height=340, legend=True, margin=dict(l=52, r=18, t=34, b=46))


def calibration_figure() -> go.Figure:
    bins = MODEL["calibration"]
    fig = go.Figure()
    fig.add_scatter(x=[0, 0.6], y=[0, 0.6], name="Calibración perfecta", mode="lines",
                    line=dict(color=REFERENCIA, width=1.5, dash="dash"))
    fig.add_scatter(x=[r["mean_predicted"] for r in bins], y=[r["observed"] for r in bins],
                    mode="lines+markers", name="Modelo", line=dict(color=DENTRO, width=2.5),
                    marker=dict(size=9, line=dict(color=SUELO, width=2)), customdata=[[r["n"]] for r in bins],
                    hovertemplate="Predicho: %{x:.1%}<br>Observado: %{y:.1%}<br>Base: %{customdata[0]:,}<extra></extra>")
    fig.update_layout(xaxis_title="Probabilidad estimada", yaxis_title="Proporción observada",
                      xaxis_tickformat=".0%", yaxis_tickformat=".0%", xaxis_range=[0, 0.6], yaxis_range=[0, 0.6])
    return figure_base(fig, height=340, legend=True, margin=dict(l=52, r=18, t=34, b=46))


def importance_figure() -> go.Figure:
    data = sorted(MODEL["importance"][:8], key=lambda x: x["mean_ap_drop"])
    fig = go.Figure(go.Bar(x=[r["mean_ap_drop"] for r in data],
                           y=[FEATURE_NAMES.get(r["feature"], r["feature"]) for r in data],
                           orientation="h", marker_color=[DENTRO if r["feature"] in NUEVAS else BASE for r in data],
                           hovertemplate="%{y}<br>Caída de la precisión promedio: %{x:.3f}<extra></extra>"))
    fig.update_layout(xaxis_title="Caída de la precisión promedio", yaxis_title="", bargap=0.34)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", ticks="")
    return figure_base(fig, height=340, margin=dict(l=8, r=18, t=6, b=44))


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


def matriz(row: dict) -> html.Div:
    celda = lambda valor, etiqueta, clase: html.Div([html.Strong(fmt_int(valor)), html.Span(etiqueta)], className=f"matriz-celda {clase}")
    eje = lambda texto, clase="": html.Div(texto, className=f"matriz-eje {clase}".strip())
    return html.Div([
        html.Div(), eje("El modelo dice: dentro"), eje("El modelo dice: fuera"),
        eje("En el censo: dentro", "lado"), celda(row["tn"], "Aciertos", "acierto"), celda(row["fp"], "Falsas alarmas", "error"),
        eje("En el censo: fuera", "lado"), celda(row["fn"], "No detectados", "error"), celda(row["tp"], "Aciertos", "acierto"),
    ], className="matriz", role="group", **{"aria-label": "Matriz de confusión en la prueba"})


def barras_figure(b: dict) -> go.Figure:
    valores = b["valores"][::-1]
    bases = b.get("bases", [None] * len(valores))[::-1]
    textos = [fmt_pct(v / 100) if b["unidad"] == "%" else fmt_int(v) for v in valores]
    detalle = [texto if base is None else f"{texto} · base aproximada {fmt_int(base)}" for texto, base in zip(textos, bases)]
    fig = go.Figure(go.Bar(x=valores, y=b["categorias"][::-1], orientation="h", text=textos, textposition="outside", cliponaxis=False,
                           marker_color={"fuera": FUERA, "dentro": DENTRO}.get(b["color"], TINTA_SUAVE),
                           customdata=detalle, hovertemplate="%{y}<br>%{customdata}<extra></extra>"))
    fig.update_layout(bargap=0.34)
    fig.update_xaxes(visible=False, range=[0, max(valores) * 1.2])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", ticks="")
    return figure_base(fig, height=max(170, 58 + 25 * len(valores)), margin=dict(l=8, r=18, t=6, b=6))


def caja(contenido: list, titulo: str | None = None, meta: str | None = None, nota: str | None = None) -> html.Div:
    return html.Div([
        html.H3(titulo) if titulo else None,
        html.Span(meta, className="c-meta") if meta else None,
        *contenido,
        html.P(nota, className="c-nota") if nota else None,
    ], className="c-bloque")


def enlace(texto: str, url: str, clase: str | None = None) -> html.A:
    return html.A(texto, href=url, target="_blank", rel="noopener noreferrer", className=clase)


def tabla(b: dict) -> html.Div:
    clase = lambda j: "izq" if j < b["texto_cols"] else None
    return html.Div(html.Table([
        html.Thead(html.Tr([html.Th(texto, scope="col", className=clase(j)) for j, texto in enumerate(b["columnas"])])),
        html.Tbody([html.Tr([html.Td(valor, className=clase(j)) for j, valor in enumerate(fila)],
                            className="destacada" if i == b.get("destacar") else None) for i, fila in enumerate(b["filas"])]),
    ], className="c-tabla"), className="c-tabla-marco")


GRUPOS_PESTANAS: list[tuple[str, int]] = []


def pestanas(id_: str, titulos: list[str], contenidos: list) -> html.Div:
    GRUPOS_PESTANAS.append((id_, len(titulos)))
    return html.Div([
        dcc.Tabs(id=id_, value="0", className="c-pestanas", children=[
            dcc.Tab(label=titulo, value=str(i), className="c-pestana", selected_className="c-pestana-activa")
            for i, titulo in enumerate(titulos)]),
        *[html.Div(contenido, id=f"{id_}-{i}", style={"display": "block" if i == 0 else "none"})
          for i, contenido in enumerate(contenidos)],
    ])


def bloque(b: dict):
    tipo = b["tipo"]
    if tipo == "parrafos":
        vinculo = b.get("enlace")
        return caja([html.Div([html.P(texto) for texto in b["parrafos"]], className="c-texto"),
                     enlace(vinculo["texto"], vinculo["url"], "c-enlace") if vinculo else None], b["titulo"])
    if tipo == "destacado":
        return html.Div([html.Span(b["rotulo"], className="c-rotulo"), html.P(b["texto"])],
                        className=f"c-destacado {b.get('tono', '')}".strip())
    if tipo == "fichas":
        return html.Div([ficha(item["etiqueta"], item["valor"], item["nota"], item.get("tono", "")) for item in b["items"]], className="c-fichas")
    if tipo == "lista":
        items = [html.Div([html.Strong(item["rotulo"]), html.P(item["texto"])], className="c-item") for item in b["items"]]
        return caja([html.Div(items, className="c-lista dos" if b.get("columnas") == 2 else "c-lista")], b["titulo"])
    if tipo == "etapas":
        lista = caja([html.Ol([html.Li([html.Strong(item["titulo"]), html.P(item["texto"])]) for item in b["items"]],
                              className="c-etapas")], b["titulo"])
        return html.Div(lista, className="c-horizontal") if b.get("horizontal") else lista
    if tipo == "tabla":
        return caja([tabla(b)], b["titulo"], b.get("meta"), b.get("nota"))
    if tipo == "barras":
        return caja([graph(figure=barras_figure(b))], b["titulo"], b["meta"], b["nota"])
    if tipo == "ruta":
        lista = html.Div([html.Div([
            html.Div([html.Span(i["nombre"]), html.Strong(i["valor"])], className="ruta-linea"),
            html.Div(html.Div(className=f"ruta-relleno {i['clase']}", style={"width": f"{i['ancho']}%"}), className="ruta-pista"),
        ], className="ruta-fila") for i in b["lista"]], className="ruta-lista")
        return caja([html.Div(className="ruta-diagrama", **{"data-svg": b["svg"]}), lista], b["titulo"], b["meta"], b["nota"])
    if tipo == "permite":
        return html.Div([html.Div([html.H3(b["si_titulo"]), html.Ul([html.Li(t) for t in b["si"]])]),
                         html.Div([html.H3(b["no_titulo"]), html.Ul([html.Li(t) for t in b["no"]])])], className="c-permite")
    if tipo == "glosario":
        return caja([html.Dl([html.Div([html.Dt(i["termino"]), html.Dd(i["definicion"])]) for i in b["items"]], className="c-glosario")], b["titulo"])
    if tipo == "columnas":
        return html.Div([bloque(hijo) for hijo in b["bloques"]], className="c-columnas")
    if tipo == "pila":
        return html.Div([bloque(hijo) for hijo in b["bloques"]], className="c-pila")
    if tipo == "pestanas":
        return pestanas(b["id"], [p["titulo"] for p in b["pestanas"]],
                        [html.Div([bloque(hijo) for hijo in p["bloques"]], className="c-pila") for p in b["pestanas"]])
    if tipo == "preguntas":
        return html.Section([html.H3(b["titulo"]),
                             *[html.Details([html.Summary(item["pregunta"]), html.P(item["respuesta"])], className="pregunta")
                               for item in b["items"]]], className="preguntas")
    if tipo == "referencias":
        return caja([html.Ol([html.Li([item["texto"], " ", enlace("Ver fuente", item["url"]) if item.get("url") else None])
                              for item in b["items"]], className="c-referencias")], b["titulo"])
    if tipo == "enlaces":
        return caja([html.Ul([html.Li(enlace(item["texto"], item["url"])) for item in b["items"]], className="c-enlaces")], b["titulo"])
    if tipo == "pie":
        return html.P(b["texto"], className="c-pie")
    raise ValueError(f"Bloque desconocido: {tipo}")


def layout_contenido(clave: str) -> html.Div:
    pagina = CONTENIDO["paginas"][clave]
    cabecera = html.Div([html.H1(pagina["titulo"]), html.P(pagina["entrada"], className="c-entrada")],
                        className="c-cabecera") if "titulo" in pagina else None
    return html.Div([cabecera, *[bloque(b) for b in pagina["bloques"]]], className="c-pagina")


def dropdown(id_: str, label: str, options: list[str], multi: bool = False):
    return html.Div([
        html.Span(label, className="filtro-etiqueta"),
        dcc.Dropdown(id=id_, options=[{"label": v, "value": v} for v in options],
                     value=[] if multi else "Todos", multi=multi, clearable=multi,
                     placeholder="Todos los municipios" if multi else None,
                     labels=DROPDOWN_LABELS),
    ], className="filtro")


def selection_sentence(municipios, sexo, edad, zona, dificultad, n, positive, cells, trusted_rate) -> html.Div:
    """Resume la selección; solo enuncia un porcentaje cuando las reglas lo permiten."""
    explorar = CONTENIDO["explorar"]
    place = "En el Atlántico" if not municipios else f"En {municipios[0]}" if len(municipios) == 1 else f"En {len(municipios)} municipios"
    details = []
    if edad != "Todos":
        details.append("de 65 años o más" if edad == "65+" else f"de {edad} años")
    if zona != "Todos":
        details.append("de cabecera" if zona == "Cabecera" else "de centros poblados y rural disperso")
    if dificultad != "Todos":
        details.append(dificultad.lower())
    who = {"Mujer": "entre mujeres", "Hombre": "entre hombres"}.get(sexo, "entre personas" if details else None)
    group = f", {' '.join([who, *details])}" if who else ""
    if trusted_rate:
        base = f"Base aproximada: {fmt_int(n)} personas en {cells} {'grupo publicado' if cells == 1 else 'grupos publicados'}."
        if len(municipios or []) == 1 and not who:
            base += " " + explorar["mapa_nota"]
        elif not municipios and not who:
            base += " " + explorar["total_nota"]
        return html.Div([html.P([f"{place}{group}, ", html.Strong(f"\u2248 {fmt_pct(positive / n)}"), " quedó fuera de la ruta formal."]),
                         html.Span(base, className="frase-base")], className="frase")
    note = ("Ningún grupo cumple las reglas de publicación. Prueba a quitar un filtro." if not cells
            else f"\u2248 {fmt_int(n)} personas en grupos publicados. La protección de grupos pequeños oculta el porcentaje.")
    return html.Div([html.P([f"{place}{group}, esta selección ", html.Em("no permite mostrar un porcentaje"), "."]),
                     html.Span(note, className="frase-base")], className="frase")


def layout_comparar() -> html.Div:
    explorar = CONTENIDO["explorar"]
    return html.Div([
        html.P(explorar["comparar_entrada"], className="c-entrada"),
        dcc.RadioItems(id="comp-variable", options=[{"label": v["etiqueta"], "value": v["id"]} for v in explorar["variables"]],
                       value=explorar["variables"][0]["id"], inline=True, className="opciones"),
        html.Div(id="comp-lectura"),
        caja([graph("comp-chart")], "Porcentaje fuera de la ruta formal", "En cada categoría de la variable elegida"),
        html.P(explorar["comparar_nota"], className="c-pie"),
    ], className="c-pila")


def layout_grupos() -> html.Div:
    municip = sorted({r["municipio"] for r in EDA["cube"]})
    explorar = CONTENIDO["explorar"]
    g = explorar["graficas"]
    omitidos = omitted_municipios_sentence(municip, "en el selector", "ninguno de sus grupos cumple las reglas de publicación")
    return html.Div([
        html.Section([
            html.Div([
                dropdown("f-municipio", "Municipio", municip, multi=True),
                dropdown("f-sexo", "Sexo", ["Todos", "Hombre", "Mujer"]),
                dropdown("f-edad", "Edad", ["Todos"] + AGE_ORDER),
                dropdown("f-zona", "Zona", ["Todos", "Cabecera", "Centros poblados y rural disperso"]),
                dropdown("f-dificultad", "Dificultad funcional", ["Todos", "Con dificultad funcional", "Sin dificultad funcional"]),
            ], className="seleccion-filtros"),
            html.Div([html.P(explorar["ayuda"], className="seleccion-ayuda"),
                      html.Button("Quitar filtros", id="limpiar", className="boton discreto", n_clicks=0)], className="seleccion-pie"),
            html.Div([html.Div(id="frase"), html.Div(id="coverage-note")], className="seleccion-resultado"),
        ], className="seleccion", **{"aria-label": "Filtros y resultado"}),
        html.Div(id="nota-referencia"),
        html.Div([
            caja([dcc.RadioItems(id="metric-toggle", options=[{"label": "Porcentaje", "value": "tasa"}, {"label": "Personas", "value": "conteo"}],
                                 value="tasa", inline=True, className="opciones"), graph("municipio-chart")],
                 g["municipios"]["titulo"], g["municipios"]["meta"]),
            html.Div([
                caja([graph("edad-chart")], g["edad"]["titulo"], g["edad"]["meta"], g["edad"]["nota"]),
                caja([graph("composicion-chart"), html.P(id="composition-note", className="c-nota")], g["composicion"]["titulo"], g["composicion"]["meta"]),
            ], className="lecturas-lado"),
        ], className="lecturas"),
        html.Details([html.Summary(explorar["por_que_titulo"]), html.Ul([html.Li(t) for t in explorar["por_que"]]),
                      html.P(omitidos.strip(), className="c-nota") if omitidos else None], className="por-que-faltan"),
        html.Div([
            html.Button("Descargar selección agregada", id="download-button", className="boton secundario"),
            dcc.Download(id="download-data"),
            html.Span(explorar["descarga_nota"], className="descarga-nota"),
        ], className="descarga"),
    ], className="c-pila")


def layout_explorar() -> html.Div:
    explorar = CONTENIDO["explorar"]
    return html.Div([
        html.Div([html.H1(explorar["titulo"]), html.P(explorar["entrada"], className="c-entrada")], className="c-cabecera"),
        pestanas("sub-explorar", explorar["pestanas"], [layout_grupos(), layout_comparar(), html.Div([bloque(b) for b in explorar["ajuste"]], className="c-pila")]),
    ], className="pagina")


def layout_modelo() -> html.Div:
    m = CONTENIDO["modelo"]
    g = m["graficas"]
    lab = m["laboratorio"]
    cambio = m["cambio"]
    chosen = MODEL["metadata"]["chosen_threshold"]
    # La marca numérica pegada al umbral validado pierde su texto para no superponerse.
    marks = {i / 20: (f"{i / 20:.2f}".replace(".", ",") if i % 2 == 0 and abs(i / 20 - chosen) >= 0.03 else "")
             for i in range(1, 17)}
    marks[chosen] = {"label": "Validado", "style": {"color": DENTRO, "fontWeight": 700}}
    return html.Div([
        html.Div([html.H1(m["titulo"]), html.P(m["entrada"], className="c-entrada")], className="c-cabecera"),
        bloque(m["fichas"]),
        html.Section([
            html.Div([html.H2(cambio["titulo"]), *[html.P(t) for t in cambio["parrafos"]],
                      html.A("Ver la revisión completa en el informe", href="/informe/modelo.html#modelo-contexto-2026", target="_blank", rel="noopener noreferrer")]),
            html.Div([html.H3(cambio["aviso_titulo"]), *[html.P(t) for t in cambio["aviso"]]]),
        ], className="cambio"),
        html.Div([
            html.Div([
                html.H2(lab["titulo"]), html.P(lab["texto"]),
                html.Span(lab["etiqueta"], className="c-rotulo"),
                dcc.Slider(id="threshold", min=0.05, max=0.8, step=None, marks=marks, value=chosen,
                           tooltip={"placement": "bottom", "always_visible": False}),
                html.Div(id="threshold-title"),
                html.Div(id="threshold-kpis", className="c-fichas"),
            ]),
            html.Div([html.H3(lab["matriz_titulo"]), html.Div(id="confusion"), html.P(lab["matriz_nota"], className="c-nota")]),
        ], className="laboratorio"),
        html.Div([
            caja([graph(figure=comparison_figure())], g["comparacion"]["titulo"], g["comparacion"]["meta"], g["comparacion"]["nota"]),
            caja([dcc.RadioItems(id="curva", options=[{"label": "ROC", "value": "roc"}, {"label": "Precisión y sensibilidad", "value": "pr"}],
                                 value="roc", inline=True, className="opciones"), graph("curve-chart")],
                 g["curvas"]["titulo"], g["curvas"]["meta"], g["curvas"]["nota"]),
        ], className="c-columnas"),
        html.Div([
            caja([graph(figure=calibration_figure())], g["calibracion"]["titulo"], g["calibracion"]["meta"], g["calibracion"]["nota"]),
            caja([graph(figure=importance_figure())], g["importancia"]["titulo"], g["importancia"]["meta"], g["importancia"]["nota"]),
        ], className="c-columnas"),
        *[bloque(b) for b in m["despues"]],
    ], className="pagina")


app = Dash(__name__, title=NOMBRE, suppress_callback_exceptions=True)
app.index_string = app.index_string.replace(
    "{%css%}",
    '<link rel="preload" href="/assets/fonts/atkinson-next-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>{%css%}',
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


def layout_pagina(clave: str) -> html.Div:
    if clave == "panorama":
        return html.Div([html.Div(id="relato"), layout_contenido(clave)])
    if clave == "explorar":
        return layout_explorar()
    if clave == "modelo":
        return layout_modelo()
    return layout_contenido(clave)


app.layout = html.Div([
    html.Header([
        html.Div([html.Span(className="marca-punto"), NOMBRE], className="marca"),
        dcc.Tabs(id="nav", value=SECCIONES[0], className="nav-tabs", children=[
            dcc.Tab(label=seccion["etiqueta"], value=seccion["id"], className="nav-tab", selected_className="nav-tab-active")
            for seccion in CONTENIDO["secciones"]]),
    ], className="site-header"),
    html.Main([html.Div(layout_pagina(clave), id=f"page-{clave}", style={"display": "block" if clave == SECCIONES[0] else "none"})
               for clave in SECCIONES]),
    html.Footer([
        html.Span([f"{NOMBRE}. Datos del censo de 2018. ", html.A("Informe completo", href="/informe/", target="_blank", rel="noopener noreferrer"), ". ",
                   html.A("Aplicación Shiny", href="https://shiny-salud-atlantico-409319239507.us-east1.run.app/", target="_blank", rel="noopener noreferrer"), ". ",
                   html.A("Microdatos del DANE", href="https://microdatos.dane.gov.co/catalog/643", target="_blank", rel="noopener noreferrer"), "."]),
    ], className="pie-sitio"),
    dcc.Store(id="filtros-activos"),
], className="app-shell")


# Cada sección empieza arriba y cambia sin esperar al servidor.
app.clientside_callback(
    "function (vista) { window.scrollTo({ top: 0, behavior: 'instant' }); "
    # En pantallas angostas el menú se desplaza: la sección elegida queda a la vista.
    "setTimeout(function () { var t = document.querySelector('.nav-tab-active'); if (t) t.scrollIntoView({ inline: 'center', block: 'nearest' }); }, 0); "
    "return " + json.dumps(SECCIONES)
    + ".map(function (id) { return { display: id === vista ? 'block' : 'none' }; }); }",
    [Output(f"page-{clave}", "style") for clave in SECCIONES], Input("nav", "value"))

for grupo, total in GRUPOS_PESTANAS:
    app.clientside_callback(
        "function (v) { var s = []; for (var i = 0; i < " + str(total) + "; i++) s.push({ display: String(i) === v ? 'block' : 'none' }); return s; }",
        [Output(f"{grupo}-{i}", "style") for i in range(total)], Input(grupo, "value"))


@app.callback(
    Output("frase", "children"), Output("coverage-note", "children"), Output("nota-referencia", "children"),
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
    reference = None if trusted_rate else reference_aggregate(municipios, sexo, edad, zona, dificultad)
    sentence = selection_sentence(municipios, sexo, edad, zona, dificultad, n, positive, len(rows), trusted_rate)
    state = "sin-datos" if not rows else ("visible" if trusted_rate else "oculta")
    state_label = {"visible": "Porcentaje visible", "oculta": "Porcentaje oculto", "sin-datos": "Sin grupos publicados"}[state]
    if not rows:
        motive = "Ninguno de sus grupos cumple las reglas de publicación."
    elif trusted_rate:
        motive = "Tiene personas suficientes y buena cobertura."
    elif coverage_pct is None or coverage_pct < 80:
        motive = "Los grupos publicados cubren menos del 80 % de esta selección."
    else:
        motive = "La base aproximada es menor de 200 personas."
    coverage_label = ("Cobertura sin estimación publicable" if coverage_pct is None else f"Cobertura: al menos {coverage_pct} %") \
        + (" (se usa el municipio con menor valor)" if municipios and len(municipios) > 1 else "")
    coverage = [html.Div([
        html.Div([html.Strong(state_label), html.Span(motive)], className="cinta-texto"),
        html.Div([
            html.Div(coverage_label, className="cinta-rotulo"),
            html.Div([html.Div(className="cinta-relleno", style={"width": f"{coverage_pct or 0}%"}),
                      html.Div(className="cinta-umbral", title="Mínimo de 80 %")],
                     className="cinta-pista", role="img", **{"aria-label": f"{coverage_label}; mínimo para publicar 80 %"}),
        ]),
    ], className=f"cinta {state}")]
    note = None
    if reference:
        label, ref, source = reference
        note = html.P(
            f"Como referencia, «{label}» registra ≈ {fmt_pct(ref['sin_formal'] / ref['n'])} sobre una base aproximada de "
            f"{fmt_int(ref['n'])} personas en {source}. Esa cifra se publica aparte, con recuentos redondeados a 10, y no sale de los grupos filtrables.",
            className="referencia")
    ranked = ranked_figure(rows, metric, sexo, edad, zona, dificultad)
    ranked_style = {"height": f"{int(ranked.layout.height)}px", "width": "100%"}
    composition, composition_note = composition_figure(rows, municipios, sexo, edad, zona, dificultad)
    return (sentence, coverage, note, ranked, ranked_style,
            age_figure(rows, municipios, sexo, zona, dificultad),
            composition, composition_note)


@app.callback(Output("comp-lectura", "children"), Output("comp-chart", "figure"), Output("comp-chart", "style"),
              Input("comp-variable", "value"))
def update_comparar(clave):
    variable = next(v for v in CONTENIDO["explorar"]["variables"] if v["id"] == clave)
    categorias = variable["categorias"]
    figura = barras_figure({"categorias": [c["categoria"] for c in categorias], "unidad": "%", "color": "fuera",
                            "valores": [round(100 * c["sin_formal"] / c["n"], 1) for c in categorias],
                            "bases": [c["n"] for c in categorias]})
    lectura = html.Div([
        html.Div([html.Span("V de Cramér", className="c-rotulo"), html.Strong(variable["v"], className="c-v")]),
        html.Div([html.P(variable["rango"], className="c-rango"), html.P(variable["lectura"], className="c-lectura-texto")]),
    ], className="c-lectura")
    return lectura, figura, {"height": f"{int(figura.layout.height)}px", "width": "100%"}


@app.callback(Output("f-municipio", "value"), Output("f-sexo", "value"), Output("f-edad", "value"),
              Output("f-zona", "value"), Output("f-dificultad", "value"), Input("limpiar", "n_clicks"), prevent_initial_call=True)
def clear_filters(_clicks):
    return [], "Todos", "Todos", "Todos", "Todos"


@app.callback(Output("curve-chart", "figure"), Input("curva", "value"))
def update_curve(kind):
    return curve_figure(kind)


@app.callback(Output("threshold-title", "children"), Output("threshold-kpis", "children"),
              Output("confusion", "children"), Input("threshold", "value"))
def update_threshold(value):
    row = threshold_row(float(value))
    met = threshold_metrics(row)
    validated = abs(row["threshold"] - MODEL["metadata"]["chosen_threshold"]) < 1e-8
    label = "Umbral validado" if validated else "Escenario de exploración"
    title = html.Div(f"{label}: {row['threshold']:.3f}".replace(".", ","), className="umbral-titulo validado" if validated else "umbral-titulo")
    values = [
        ficha("Sensibilidad", fmt_pct(met["recall"]), "De quienes están fuera de la ruta, cuántos marca"),
        ficha("Precisión", fmt_pct(met["precision"]), "De los marcados, cuántos están fuera de la ruta"),
        ficha("Personas marcadas", fmt_int(met["flagged"]), f"De {fmt_int(MODEL['metadata']['test_n'])} en la prueba"),
    ]
    return title, values, matriz(row)


# El asistente lee aquí la selección; las cifras las recalcula el servidor.
app.clientside_callback(
    "function (m, s, e, z, d) { window.__filtrosActivos = { municipios: m || [], sexo: s, edad: e, zona: z, dificultad: d }; return true; }",
    Output("filtros-activos", "data"), Input("f-municipio", "value"), Input("f-sexo", "value"), Input("f-edad", "value"),
    Input("f-zona", "value"), Input("f-dificultad", "value"))


def texto_de(componente) -> str:
    if isinstance(componente, (list, tuple)):
        return "".join(texto_de(c) for c in componente)
    if hasattr(componente, "children"):
        return texto_de(componente.children)
    return "" if componente is None else str(componente)


def resumen_asistente(filtros: dict) -> dict:
    """Resultado de la selección con las mismas funciones y reglas de la vista de grupos."""
    permitidos = {"sexo": ("Hombre", "Mujer"), "edad": tuple(AGE_ORDER), "zona": ("Cabecera", "Centros poblados y rural disperso"),
                  "dificultad": ("Con dificultad funcional", "Sin dificultad funcional")}
    limpios = {k: (filtros.get(k) if filtros.get(k) in v else "Todos") for k, v in permitidos.items()}
    municipios = [m for m in (filtros.get("municipios") or []) if m in ATLANTICO_MUNICIPIOS]
    activo = bool(municipios) or any(v != "Todos" for v in limpios.values())
    rows = filter_cube(municipios, limpios["sexo"], limpios["edad"], limpios["zona"], limpios["dificultad"])
    n, positive = sum(r["n"] for r in rows), sum(r["sin_formal"] for r in rows)
    coverage = coverage_for(municipios, limpios["sexo"], limpios["edad"], limpios["zona"], limpios["dificultad"])
    trusted = safe_to_rate(n, coverage)
    frase = selection_sentence(municipios, limpios["sexo"], limpios["edad"], limpios["zona"], limpios["dificultad"], n, positive, len(rows), trusted)
    partes = frase.children
    texto = f"{texto_de(partes[0])} {texto_de(partes[1])}"
    return {"activo": activo, "visible": trusted, "texto": texto}


def consulta_municipio(municipio: str) -> str:
    fila = next((r for r in EDA["municipal_overview"] if r["municipio"] == municipio), None)
    if fila is None:
        return f"El porcentaje de {municipio} no se publica porque no alcanza el mínimo de 100 personas y 10 dentro y fuera de la ruta formal."
    return (f"En {municipio}, ≈ {fmt_pct(fila['sin_formal'] / fila['n'])} de las personas estudiadas quedó fuera de la ruta formal, "
            f"sobre una base aproximada de {fmt_int(fila['n'])} personas. Es una respuesta del censo de 2018, no indica atención negada ni explica la causa.")


asistente = Asistente(resumen_asistente, consulta_municipio, list(ATLANTICO_MUNICIPIOS))
ORIGENES = set(filter(None, os.environ.get("ASISTENTE_ORIGENES", "http://localhost:8060,http://127.0.0.1:8060,https://shiny-salud-atlantico-409319239507.us-east1.run.app").split(",")))


def con_cors(respuesta):
    origen = request.headers.get("Origin")
    if origen in ORIGENES:
        respuesta.headers["Access-Control-Allow-Origin"] = origen
        respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        respuesta.headers["Vary"] = "Origin"
    return respuesta


@server.get("/api/asistente/estado")
def asistente_estado():
    return con_cors(jsonify(modo=asistente.modo()))


@server.route("/api/asistente", methods=["POST", "OPTIONS"])
def asistente_preguntar():
    if request.method == "OPTIONS":
        return con_cors(app.server.response_class(status=204))
    datos = request.get_json(silent=True) or {}
    pregunta = str(datos.get("pregunta") or "").strip()
    if not pregunta or len(pregunta) > LARGO_MAXIMO:
        return con_cors(jsonify(error=f"Escribe una pregunta de hasta {LARGO_MAXIMO} caracteres.")), 400
    if not asistente.limite.permitir(request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0]):
        return con_cors(jsonify(error="Se alcanzó el límite de preguntas. Intenta de nuevo en unos minutos.")), 429
    filtros = datos.get("filtros") if isinstance(datos.get("filtros"), dict) else {}
    return con_cors(jsonify(asistente.responder(pregunta, filtros)))


@app.callback(Output("download-data", "data"), Input("download-button", "n_clicks"),
              State("f-municipio", "value"), State("f-sexo", "value"), State("f-edad", "value"),
              State("f-zona", "value"), State("f-dificultad", "value"), prevent_initial_call=True)
def download_selection(_clicks, municipios, sexo, edad, zona, dificultad):
    rows = filter_cube(municipios, sexo, edad, zona, dificultad)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["municipio", "sexo", "edad", "zona", "dificultad", "n", "sin_formal"])
    writer.writeheader()
    writer.writerows(rows)
    return dict(content=stream.getvalue(), filename="salud_atlantico_agregados.csv", type="text/csv")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8050")), debug=False)
