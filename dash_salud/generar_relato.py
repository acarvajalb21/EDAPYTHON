"""Genera relato_datos.json: los agregados y el mapa del relato de apertura.

Ejecutar desde la raíz: python -m dash_salud.generar_relato --data-dir RUTA_CSV --geojson RUTA_MGN
Solo produce recuentos de grupos amplios, geometría pública del DANE y las tasas ya publicadas en eda.json.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from dash_salud.generar_datos import MUNICIPIOS, OUT

ANCHO = 560


def simplificar(puntos: list, tolerancia: float) -> list:
    """Douglas-Peucker iterativo sobre una línea cerrada."""
    if len(puntos) < 4:
        return puntos
    # El anillo empieza y termina en el mismo punto: se parte en el vértice más lejano.
    x0, y0 = puntos[0]
    lejano = max(range(len(puntos)), key=lambda i: math.hypot(puntos[i][0] - x0, puntos[i][1] - y0))
    conservar = {0, lejano, len(puntos) - 1}
    pila = [(0, lejano), (lejano, len(puntos) - 1)]
    while pila:
        a, b = pila.pop()
        ax, ay = puntos[a]
        bx, by = puntos[b]
        largo = math.hypot(bx - ax, by - ay) or 1e-12
        mayor, indice = 0.0, None
        for i in range(a + 1, b):
            px, py = puntos[i]
            distancia = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / largo
            if distancia > mayor:
                mayor, indice = distancia, i
        if indice is not None and mayor > tolerancia:
            conservar.add(indice)
            pila += [(a, indice), (indice, b)]
    return [puntos[i] for i in sorted(conservar)]


def mapa(ruta: Path) -> tuple[list, int]:
    geo = json.loads(ruta.read_text(encoding="utf-8"))
    def anillos(geometria):
        if geometria["type"] == "Polygon":
            return [geometria["coordinates"][0]]
        return [poligono[0] for poligono in geometria["coordinates"]]

    todos = [p for f in geo["features"] for anillo in anillos(f["geometry"]) for p in anillo]
    xmin, xmax = min(p[0] for p in todos), max(p[0] for p in todos)
    ymin, ymax = min(p[1] for p in todos), max(p[1] for p in todos)
    coseno = math.cos(math.radians((ymin + ymax) / 2))
    escala = ANCHO / ((xmax - xmin) * coseno)
    alto = round((ymax - ymin) * escala)
    salida = []
    for feature in geo["features"]:
        codigo = int(feature["properties"]["MPIO_CCDGO"])
        trazos = []
        for anillo in anillos(feature["geometry"]):
            proyectado = [((x - xmin) * coseno * escala, (ymax - y) * escala) for x, y in anillo]
            reducido = simplificar(proyectado, 0.9)
            if len(reducido) > 2:
                trazos.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in reducido) + "Z")
        salida.append({"municipio": MUNICIPIOS[codigo], "trazo": "".join(trazos)})
    return salida, alto


def acciones(data_dir: Path) -> dict:
    personas = pd.read_csv(data_dir / "CNPV2018_5PER_A2_08.CSV", usecols=["P_ENFERMO", "P_QUEHIZO_PPAL"], low_memory=False)
    conteo = personas.loc[personas["P_ENFERMO"].eq(1), "P_QUEHIZO_PPAL"].value_counts()
    # Las categorías 4, 5 y 6 se agrupan porque dos de ellas son muy pequeñas.
    return {"autorreceta": int(conteo[8]), "remedios": int(conteo[7]), "nada": int(conteo[9]),
            "boticario": int(conteo[3]), "otras": int(conteo[[4, 5, 6]].sum())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--geojson", type=Path, required=True)
    parser.add_argument("--destino", type=Path, nargs="+", default=[OUT.parent / "assets"])
    args = parser.parse_args()
    eda = json.loads((OUT / "eda.json").read_text(encoding="utf-8"))
    meta = eda["metadata"]
    tasas = {r["municipio"]: {"n": r["n"], "sin_formal": r["sin_formal"]} for r in eda["municipal_overview"]}
    trazos, alto = mapa(args.geojson)
    for fila in trazos:
        fila.update(tasas.get(fila["municipio"], {}))
    resultado = {
        "flujo": meta["population_flow"], "rutas": meta["label_breakdown_exact"],
        "fuera": meta["no_access_exact"], "cohorte": meta["total_labeled_exact"],
        "acciones": acciones(args.data_dir),
        "mapa": {"ancho": ANCHO, "alto": alto, "municipios": trazos},
    }
    texto = json.dumps(resultado, ensure_ascii=False, separators=(",", ":"))
    for destino in args.destino:
        (destino / "relato_datos.json").write_text(texto, encoding="utf-8")
    print(len(texto), "bytes", resultado["acciones"])


if __name__ == "__main__":
    main()
