"""Verificaciones focalizadas del paquete público y sus agregados."""

from __future__ import annotations

from dash import dcc

from dash_salud.app import (
    ATLANTICO_MUNICIPIOS, CONTENIDO, COVERAGE, EDA, EXACT, FEATURE_NAMES, MODEL, NOMBRE, app, composition_figure, coverage_for,
    curve_figure, empty_figure, filter_cube, fmt_int, fmt_pct, reference_aggregate, safe_to_rate,
    threshold_metrics, threshold_row, update_comparar, update_explore, update_threshold,
)


def client_assets_ok() -> bool:
    client = app.server.test_client()
    return all(client.get(f"/assets/{name}").status_code == 200 for name in
               ("relato.js", "relato.css", "relato_datos.json", "tema.css", "tema_dash.css",
                "fonts/bricolage-grotesque-latin-wght-normal.woff2", "fonts/atkinson-next-latin-wght-normal.woff2"))


def run() -> None:
    meta = EDA["metadata"]
    assert meta["population_flow"] == {
        "people": 2342265, "recent_health_problem": 136114,
        "unclassifiable": 80, "analytic": 136034,
    }
    assert meta["total_labeled_exact"] == 136034
    assert meta["no_access_exact"] == 28650
    assert EXACT["sin_formal"] == 28650
    assert 90 <= meta["coverage_pct"] < 100
    assert all(row["n"] >= 30 and row["sin_formal"] >= 5
               and row["n"] - row["sin_formal"] >= 5 for row in EDA["cube"])
    assert all(row["n"] >= 100 and row["sin_formal"] >= 10
               and row["n"] - row["sin_formal"] >= 10 for row in EDA["municipal_overview"])
    zone_sex = EDA["zone_sex_summary"]
    assert {(row["zona"], row["sexo"]) for row in zone_sex} == {
        (zone, sex) for zone in ("Cabecera", "Centros poblados y rural disperso")
        for sex in ("Mujer", "Hombre")
    }
    assert abs(sum(row["n"] for row in zone_sex) - EXACT["n"]) <= 20
    assert "Piojó" not in {row["municipio"] for row in EDA["municipal_overview"]}
    assert all(value is None or value % 5 == 0 for value in COVERAGE.values())
    assert coverage_for(["Piojó"]) is None or coverage_for(["Piojó"]) < 80
    assert not safe_to_rate(100, 100)

    all_rows = filter_cube([], "Todos", "Todos", "Todos", "Todos")
    assert len(all_rows) == meta["publishable_cells"]
    composition, note = composition_figure(all_rows, [], "Todos", "Todos", "Todos", "Todos")
    assert len(composition.data) == 2
    assert all(len(trace.y) == 2 and all(value is not None for value in trace.y)
               for trace in composition.data)
    assert "todas las personas estudiadas" in note
    _, filtered_note = composition_figure(all_rows, ["Baranoa"], "Todos", "Todos", "Todos", "Todos")
    assert "dentro del filtro" in filtered_note
    assert update_explore([], "Todos", "Todos", "Todos", "Todos", "tasa")[3] is not None
    assert update_explore(["Piojó"], "Todos", "Todos", "Todos", "Todos", "tasa")[3] is not None
    assert len(ATLANTICO_MUNICIPIOS) == 23
    assert {row["municipio"] for row in EDA["cube"] + EDA["municipal_overview"]} <= set(ATLANTICO_MUNICIPIOS)
    # Sin celdas publicables no se muestra «≈ 0» como si no hubiera personas.
    empty = update_explore([], "Mujer", "0–19", "Centros poblados y rural disperso", "Con dificultad funcional", "tasa")
    assert "sin-datos" in empty[1][0].className and "Ningún grupo" in empty[0].children[1].children
    # Una tasa oculta remite al agregado publicado aparte, con su propio denominador.
    usiacuri = next(row for row in EDA["municipal_overview"] if row["municipio"] == "Usiacurí")
    hidden = update_explore(["Usiacurí"], "Todos", "Todos", "Todos", "Todos", "tasa")
    assert "oculta" in hidden[1][0].className and "no permite mostrar un porcentaje" in str(hidden[0].children[0])
    assert fmt_int(usiacuri["n"]) in hidden[2].children
    assert fmt_pct(usiacuri["sin_formal"] / usiacuri["n"]) in hidden[2].children
    rural = [row for row in EDA["zone_sex_summary"] if row["zona"] == "Centros poblados y rural disperso"]
    rural_note = update_explore([], "Todos", "Todos", "Centros poblados y rural disperso", "Todos", "tasa")[2]
    assert fmt_int(sum(row["n"] for row in rural)) in rural_note.children
    general = update_explore([], "Todos", "Todos", "Todos", "Todos", "tasa")
    assert general[2] is None and "21,5" in str(general[0].children[0])
    assert reference_aggregate(["Usiacurí"], "Hombre", "Todos", "Todos", "Todos") is None
    assert reference_aggregate([], "Todos", "65+", "Todos", "Todos") is None
    assert "<br>" in empty_figure("Cobertura o tamaño insuficiente para comparar municipios").layout.annotations[0].text
    assert all("recall" not in trace.name.lower() for trace in curve_figure("pr").data)
    threshold = MODEL["metadata"]["chosen_threshold"]
    row = threshold_row(threshold)
    assert {key: row[key] for key in ("tn", "fp", "fn", "tp")} == MODEL["models"]["hist_gradient_boosting"]["test"]["confusion"]
    assert round(threshold_metrics(row)["f1"], 6) == round(MODEL["models"]["hist_gradient_boosting"]["test"]["f1"], 6)
    assert update_threshold(threshold)[2] is not None
    audit = MODEL["audit_2026"]
    assert audit["selected"] == "referencia" and audit["alternatives"] == 9
    assert audit["best_cv_delta_ap_interval_95"][0] < 0 < audit["best_cv_delta_ap_interval_95"][1]
    assert MODEL["metadata"]["model_version"] == 2
    change = MODEL["version_change"]
    assert change["delta_ap_interval_95"][0] > 0
    assert change["new_validation_ap"] - change["previous_validation_ap"] >= 0.010
    assert change["new_unseen_sections_ap"] - change["previous_unseen_sections_ap"] >= 0.010
    assert [row["fraction"] for row in MODEL["prioritization"]] == [0.05, 0.10, 0.20]
    assert all(FEATURE_NAMES.get(row["feature"]) for row in MODEL["importance"][:8])

    def walk(component):
        if isinstance(component, (list, tuple)):
            for child in component:
                yield from walk(child)
        elif component is not None:
            yield component
            if hasattr(component, "children"):
                yield from walk(component.children)

    components = list(walk(app.layout))
    nav = next(item for item in components if getattr(item, "id", None) == "nav")
    assert [tab.label for tab in nav.children] == [seccion["etiqueta"] for seccion in CONTENIDO["secciones"]]
    assert len(nav.children) == 9
    text = " ".join(item.children for item in components if isinstance(getattr(item, "children", None), str))
    for phrase in ("Pregunta de investigación", "Objetivos específicos", "2. Qué significa acceso",
                   "Referencias", "Las 28 variables del modelo", "Por qué algunos resultados no aparecen"):
        assert phrase in text
    assert "DATAVIZ" not in text and app.title == NOMBRE
    for variable in CONTENIDO["explorar"]["variables"]:
        assert all(c["n"] >= 100 and c["sin_formal"] >= 10 and c["n"] - c["sin_formal"] >= 10
                   and c["n"] % 10 == 0 and c["sin_formal"] % 10 == 0 for c in variable["categorias"])
    # La asociación del informe se reproduce con las tablas publicadas.
    valores = {v["id"]: v["v"] for v in CONTENIDO["explorar"]["variables"]}
    assert (valores["edad"], valores["municipio"]) == ("0,163", "0,085")
    comparado = update_comparar("municipio")
    assert comparado[2]["height"] == f"{int(comparado[1].layout.height)}px"
    # El contenido de las secciones no presenta la clase como atención negada ni pruebas de significancia.
    plano = str(CONTENIDO).lower()
    assert "p-valor" not in plano and "barrera causal" not in plano and "significativ" not in plano
    assert any(getattr(item, "id", None) == "relato" for item in components)
    assert client_assets_ok()
    slider = next(item for item in components if getattr(item, "id", None) == "threshold")
    assert all(not label for value, label in slider.marks.items() if value != threshold and abs(value - threshold) < 0.03)
    municipio_filter = next(item for item in components if getattr(item, "id", None) == "f-municipio")
    assert municipio_filter.labels["select_all"] == "Seleccionar todos"
    graphs = [item for item in components if isinstance(item, dcc.Graph)]
    assert len(graphs) >= 9
    assert all(item.style["height"].endswith("px") for item in graphs)
    assert all(item.style["width"] == "100%" for item in graphs)
    assert all("Atkinson Hyperlegible Next" in item.figure.layout.font.family for item in graphs if item.figure is not None)
    dynamic = update_explore([], "Todos", "Todos", "Todos", "Todos", "tasa")
    assert dynamic[4]["height"] == f"{int(dynamic[3].layout.height)}px"
    assert "Atkinson Hyperlegible Next" in dynamic[3].layout.font.family

    client = app.server.test_client()
    assert client.get("/").status_code == 200
    assert b"atkinson-next-latin-wght-normal.woff2" in client.get("/").data
    assert client.get("/health").json["status"] == "ok"
    assert client.get("/_dash-layout").status_code == 200
    assert client.get("/informe/").status_code == 200
    assert client.get("/informe/modelo.html").status_code == 200
    assert b'id="modelo-contexto-2026"' in client.get("/informe/modelo.html").data
    assert client.get("/informe/figures/curvas_modelo.png").status_code == 200
    assert client.get("/informe/figures/brecha_dificultad_2026.png").status_code == 200
    print("Dash y datos publicables: verificaciones satisfactorias")


if __name__ == "__main__":
    run()
