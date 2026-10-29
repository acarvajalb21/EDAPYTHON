"""Verificaciones focalizadas del paquete público y sus agregados."""

from __future__ import annotations

from dash import dcc

from dash_salud.app import (
    COVERAGE, EDA, EXACT, MODEL, app, composition_figure, coverage_for, filter_cube, safe_to_rate,
    threshold_metrics, threshold_row, update_explore, update_threshold,
)


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
    assert "toda la cohorte" in note
    _, filtered_note = composition_figure(all_rows, ["Baranoa"], "Todos", "Todos", "Todos", "Todos")
    assert "cruces publicables" in filtered_note
    assert update_explore([], "Todos", "Todos", "Todos", "Todos", "tasa")[2] is not None
    assert update_explore(["Piojó"], "Todos", "Todos", "Todos", "Todos", "tasa")[2] is not None
    threshold = MODEL["metadata"]["chosen_threshold"]
    row = threshold_row(threshold)
    assert {key: row[key] for key in ("tn", "fp", "fn", "tp")} == MODEL["models"]["hist_gradient_boosting"]["test"]["confusion"]
    assert round(threshold_metrics(row)["f1"], 6) == round(MODEL["models"]["hist_gradient_boosting"]["test"]["f1"], 6)
    assert update_threshold(threshold)[2] is not None
    audit = MODEL["audit_2026"]
    assert audit["selected"] == "referencia" and audit["alternatives"] == 9
    assert audit["best_cv_delta_ap_interval_95"][0] < 0 < audit["best_cv_delta_ap_interval_95"][1]

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
    assert [tab.label for tab in nav.children] == ["Proyecto", "EDA", "Modelo y método"]
    text = " ".join(item.children for item in components if isinstance(getattr(item, "children", None), str))
    for phrase in ("¿Qué ruta de atención se declaró", "Entender cómo varía la ruta declarada de atención",
                   "Tres objetivos concretos", "¿A quién representan estas cifras?", "Explora los datos"):
        assert phrase in text
    assert any(getattr(item, "id", None) == "go-eda" for item in components)
    graphs = [item for item in components if isinstance(item, dcc.Graph)]
    assert len(graphs) >= 9
    assert all(item.style["height"].endswith("px") for item in graphs)
    assert all(item.style["width"] == "100%" for item in graphs)
    assert all("IBM Plex Sans" in item.figure.layout.font.family for item in graphs if item.figure is not None)
    dynamic = update_explore([], "Todos", "Todos", "Todos", "Todos", "tasa")
    assert dynamic[3]["height"] == f"{int(dynamic[2].layout.height)}px"
    assert "IBM Plex Sans" in dynamic[2].layout.font.family

    client = app.server.test_client()
    assert client.get("/").status_code == 200
    assert b'ibm-plex-sans-latin-variable.woff2' in client.get("/").data
    assert client.get("/assets/fonts/ibm-plex-sans-latin-variable.woff2").status_code == 200
    assert client.get("/health").json["status"] == "ok"
    assert client.get("/_dash-layout").status_code == 200
    assert client.get("/informe/").status_code == 200
    assert client.get("/informe/modelo.html").status_code == 200
    assert client.get("/informe/figures/curvas_modelo.png").status_code == 200
    assert client.get("/informe/figures/brecha_dificultad_2026.png").status_code == 200
    print("Dash y datos publicables: verificaciones satisfactorias")


if __name__ == "__main__":
    run()
