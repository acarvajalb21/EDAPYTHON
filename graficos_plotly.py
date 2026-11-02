"""Figuras de los cuadernos con Plotly y la gama Petróleo (ver DISENO.md).

Cada figura sale de dos formas: interactiva y como imagen de respaldo. GitHub y otros visores
sin JavaScript muestran la imagen; el Jupyter Book la cambia por la figura interactiva al
compilarse (ver libro_interactivo.py). Las figuras reciben solo agregados, nunca registros
individuales.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

DENTRO, FUERA = "#1B6CA8", "#DD6B20"
GRUPO_A, GRUPO_B = "#5B6FB5", "#A86C00"
TINTA, TINTA2, TINTA3 = "#10293B", "#3A4F60", "#54697A"
HILO, BASE, REFERENCIA, SUELO = "#D9E1E7", "#A9B6C1", "#7D8A96", "#EEF2F5"
LETRA = "Atkinson Hyperlegible Next, Segoe UI, Arial, sans-serif"
CONFIG = {"displayModeBar": False, "responsive": True}
TIPO_INTERACTIVO = "application/vnd.plotly.v1+json"

_EJE = dict(gridcolor=HILO, zeroline=False, linecolor=BASE, tickcolor=BASE, automargin=True,
            title=dict(font=dict(color=TINTA3, size=13)))
pio.templates["petroleo"] = go.layout.Template(layout=go.Layout(
    font=dict(family=LETRA, color=TINTA2, size=13), separators=",.",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=[DENTRO, FUERA, GRUPO_A, GRUPO_B],
    margin=dict(l=10, r=24, t=84, b=56),
    hoverlabel=dict(bgcolor=TINTA, bordercolor=TINTA, align="left", font=dict(family=LETRA, color="#FFFFFF", size=13)),
    legend=dict(orientation="h", x=0, y=1.0, xanchor="left", yanchor="bottom", font=dict(color=TINTA2)),
    xaxis=_EJE, yaxis=_EJE,
))


def dec_es(valor: float, decimales: int = 2) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def pct_es(valor: float, decimales: int = 1) -> str:
    return dec_es(valor, decimales) + " %"


def entero_es(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def rotular(fig: go.Figure, titulo: str, subtitulo: str | None = None, nota: str | None = None,
            espacio: int | None = None) -> go.Figure:
    """Título y subtítulo a la izquierda; la nota de fuente va debajo del eje horizontal."""
    fig.update_layout(title=dict(text=titulo, x=0, xanchor="left", xref="paper", y=1, yref="container", yanchor="top",
                                 pad=dict(t=12), font=dict(color=TINTA, size=17),
                                 subtitle=dict(text=subtitulo or "", font=dict(color=TINTA3, size=13))))
    if subtitulo:
        fig.update_layout(margin=dict(t=108))  # Título, subtítulo y leyenda sin encimarse.
    if espacio is None:
        # Con título en el eje horizontal la nota baja un poco más.
        espacio = 66 if any(eje.title.text for eje in fig.select_xaxes()) else 40
    if nota:
        fig.add_annotation(text=nota, x=0, y=0, xref="paper", yref="paper", xanchor="left", yanchor="top",
                           yshift=-espacio, showarrow=False, align="left", font=dict(size=11, color=TINTA3))
        fig.update_layout(margin=dict(b=espacio + 16 * (nota.count("<br>") + 1) + 8))
    return fig


def mostrar_figura(fig: go.Figure, nombre: str | None = None, carpeta: Path | None = None,
                   alto: int = 420, ancho: int = 860) -> None:
    """Muestra la figura interactiva con su imagen de respaldo y, si se indica, guarda la imagen."""
    fig.update_layout(template="petroleo", height=alto)
    respaldo = go.Figure(fig)
    respaldo.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    png = respaldo.to_image(format="png", width=ancho, height=alto, scale=2)
    if nombre and carpeta is not None:
        Path(carpeta, f"{nombre}.png").write_bytes(png)
    from IPython import get_ipython
    if get_ipython() is None:
        return
    from IPython.display import display
    interactiva = json.loads(fig.to_json())
    interactiva["config"] = CONFIG
    titulo = re.sub(r"<[^>]+>.*", "", fig.layout.title.text or "Figura").strip()
    display({TIPO_INTERACTIVO: interactiva, "image/png": base64.b64encode(png).decode("ascii"),
             "text/plain": f"Figura interactiva: {titulo}"}, raw=True)
