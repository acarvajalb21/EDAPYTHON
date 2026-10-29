"""Genera agregados publicables para Dash desde los microdatos locales.

Ejecutar desde la raíz del proyecto con ``python -m dash_salud.generar_datos``.
Los CSV y las puntuaciones individuales nunca se copian al directorio web.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, roc_curve

from ml_salud.entrenar import group_ids, load_data, split_three
from ml_salud.esquema import FEATURES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = Path.home() / "OneDrive" / "Documents" / "PROYECTO_DISCAPACIDAD" / "data"
OUT = Path(__file__).resolve().parent / "data"
REPORT = ROOT / "ml_salud" / "resultados" / "resultados.json"
AUDIT_DIR = ROOT / "ml_salud" / "experimentos_2026_10" / "salidas"
MODEL = ROOT / "ml_salud" / "resultados" / "modelo_sin_acceso.joblib"

MUNICIPIOS = {
    1: "Barranquilla", 78: "Baranoa", 137: "Campo de la Cruz", 141: "Candelaria",
    296: "Galapa", 372: "Juan de Acosta", 421: "Luruaco", 433: "Malambo",
    436: "Manatí", 520: "Palmar de Varela", 549: "Piojó", 558: "Polonuevo",
    560: "Ponedera", 573: "Puerto Colombia", 606: "Repelón", 634: "Sabanagrande",
    638: "Sabanalarga", 675: "Santa Lucía", 685: "Santo Tomás", 758: "Soledad",
    770: "Suan", 832: "Tubará", 849: "Usiacurí",
}
AGE_LABELS = ["0–19", "20–39", "40–64", "65+"]
DIMENSIONS = ["municipio", "sexo", "edad", "zona", "dificultad"]


def rounded(value: int, base: int) -> int:
    return int(base * round(value / base))


def prepare_eda(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    result["municipio"] = df["U_MPIO"].map(MUNICIPIOS)
    result["sexo"] = df["P_SEXO"].map({1: "Hombre", 2: "Mujer"})
    result["edad"] = pd.cut(
        df["P_EDADR"], bins=[0, 4, 8, 13, 21], labels=AGE_LABELS,
        include_lowest=True,
    ).astype(str)
    result["zona"] = np.where(df["UA_CLASE"].eq(1), "Cabecera", "Centros poblados y rural disperso")
    result["dificultad"] = df["CONDICION_FISICA"].map({
        1: "Con dificultad funcional", 2: "Sin dificultad funcional",
    })
    result["sin_formal"] = df["SIN_ACCESO"].astype(int)
    if result[DIMENSIONS].isna().any().any() or result["municipio"].eq("nan").any():
        raise AssertionError("Hay códigos sin etiqueta en las dimensiones del panel")
    return result


def make_eda(df: pd.DataFrame, source: dict) -> dict:
    labeled = prepare_eda(df)
    by_cell = (
        labeled.groupby(DIMENSIONS, observed=True)
        .agg(n=("sin_formal", "size"), sin_formal=("sin_formal", "sum"))
        .reset_index()
    )
    by_cell["formal"] = by_cell["n"] - by_cell["sin_formal"]
    keep = (by_cell["n"] >= 30) & (by_cell["sin_formal"] >= 5) & (by_cell["formal"] >= 5)
    kept = by_cell.loc[keep].copy()
    coverage_n = int(kept["n"].sum())
    rows = []
    for row in kept.itertuples(index=False):
        formal = rounded(int(row.formal), 5)
        nonformal = rounded(int(row.sin_formal), 5)
        rows.append({
            "municipio": row.municipio, "sexo": row.sexo, "edad": row.edad,
            "zona": row.zona, "dificultad": row.dificultad,
            "n": formal + nonformal, "sin_formal": nonformal,
        })
    municipal = (
        labeled.groupby("municipio", observed=True)
        .agg(n=("sin_formal", "size"), sin_formal=("sin_formal", "sum"))
        .reset_index()
    )
    broad = []
    for row in municipal.itertuples(index=False):
        # El panorama también queda publicado: nunca mostrar clases minúsculas.
        if row.n < 100 or row.sin_formal < 10 or row.n - row.sin_formal < 10:
            continue
        formal = rounded(int(row.n - row.sin_formal), 10)
        nonformal = rounded(int(row.sin_formal), 10)
        broad.append({"municipio": row.municipio, "n": formal + nonformal, "sin_formal": nonformal})
    # Esta vista amplia evita que la supresión de cruces de cinco dimensiones
    # borre una zona completa al comparar únicamente sexo y residencia.
    by_zone_sex = (
        labeled.groupby(["zona", "sexo"], observed=True)
        .agg(n=("sin_formal", "size"), sin_formal=("sin_formal", "sum"))
        .reset_index()
    )
    zone_sex_summary = []
    for row in by_zone_sex.itertuples(index=False):
        if row.n < 100 or row.sin_formal < 10 or row.n - row.sin_formal < 10:
            continue
        formal = rounded(int(row.n - row.sin_formal), 10)
        nonformal = rounded(int(row.sin_formal), 10)
        zone_sex_summary.append({
            "zona": row.zona, "sexo": row.sexo,
            "n": formal + nonformal, "sin_formal": nonformal,
        })
    # Solo se publican bandas de cobertura. Esto permite avisar de sesgo por
    # supresión sin divulgar el denominador exacto de un cruce pequeño.
    coverage = []
    for size in range(len(DIMENSIONS) + 1):
        for dim_tuple in itertools.combinations(DIMENSIONS, size):
            if not dim_tuple:
                full_groups = [((), len(labeled))]
                kept_groups = {(): int(kept["n"].sum())}
            else:
                full_groups = list(labeled.groupby(list(dim_tuple), observed=True).size().items())
                kept_groups = kept.groupby(list(dim_tuple), observed=True)["n"].sum().to_dict()
            for key, total in full_groups:
                # Ni siquiera publicar la existencia de un cruce diminuto.
                if total < 100:
                    continue
                if not isinstance(key, tuple):
                    key = (key,)
                selected = dict(zip(dim_tuple, key))
                lookup_key = [selected.get(dim, "Todos") for dim in DIMENSIONS]
                group_key = key[0] if len(dim_tuple) == 1 else key
                kept_n = int(kept_groups.get(group_key, 0))
                pct = int(5 * np.floor(100 * kept_n / int(total) / 5))
                coverage.append({"key": lookup_key, "coverage_floor_5pct": pct})
    return {
        "metadata": {
            "title": "Atlántico · CNPV 2018 · consulta de salud en 30 días",
            "population": "Personas que reportaron un problema de salud en los 30 días previos, sin hospitalización y con etiqueta clasificable",
            "source_sha256": source["source_sha256"],
            "population_flow": {
                "people": int(source["people"]),
                "recent_health_problem": int(source["sick"]),
                "unclassifiable": int(source["unlabeled"]),
                "analytic": int(source["labeled"]),
            },
            "total_labeled_exact": int(source["labeled"]),
            "no_access_exact": int(source["no_access"]),
            "label_breakdown_exact": source["label_breakdown"],
            "all_cells": int(len(by_cell)), "publishable_cells": int(len(kept)),
            "coverage_pct": round(100 * coverage_n / int(source["labeled"]), 2),
            "rules": "Cruces publicados solo si n ≥ 30 y ambas clases ≥ 5; conteos del cubo redondeados a 5. Panorama municipal con n ≥ 100 y ambas clases ≥ 10, redondeado a 10.",
            "age_bands": AGE_LABELS,
            "municipality_source": "https://geoportal.dane.gov.co/descargas/descarga_divipola/pdf/Atlantico.pdf",
        },
        "cube": rows,
        "municipal_overview": broad,
        "zone_sex_summary": zone_sex_summary,
        "coverage_index": coverage,
    }


def sampled_curve(x: np.ndarray, y: np.ndarray, max_points: int = 320) -> list[dict]:
    ix = np.unique(np.linspace(0, len(x) - 1, min(max_points, len(x))).astype(int))
    return [{"x": round(float(x[i]), 6), "y": round(float(y[i]), 6)} for i in ix]


def make_model(df: pd.DataFrame, report: dict) -> dict:
    audit = json.loads((AUDIT_DIR / "auditoria.json").read_text(encoding="utf-8"))
    extended = json.loads((AUDIT_DIR / "ampliacion.json").read_text(encoding="utf-8"))
    breach = json.loads((AUDIT_DIR / "brecha_dificultad.json").read_text(encoding="utf-8"))
    if audit["source_sha256"] != report["source"]["source_sha256"] or extended["selected"] != "referencia":
        raise AssertionError("La revisión adicional no corresponde al modelo original")
    artifact = joblib.load(MODEL)
    if artifact["source_sha256"] != report["source"]["source_sha256"]:
        raise AssertionError("El modelo y el informe no proceden de los mismos microdatos")
    x = df[FEATURES]
    y = df["SIN_ACCESO"].to_numpy(dtype=int)
    groups = group_ids(df)
    _, _, test = split_three(x, y, groups)
    scores = artifact["pipeline"].predict_proba(x.iloc[test])[:, 1]
    yy = y[test]
    ap = average_precision_score(yy, scores)
    if abs(ap - report["test_metrics"]["hist_gradient_boosting"]["pr_auc"]) > 1e-9:
        raise AssertionError("La prueba reproducida no coincide con el informe")
    chosen_threshold = float(report["threshold_from_validation"])
    grid = sorted(set([round(i / 100, 2) for i in range(1, 100)] + [chosen_threshold]))
    threshold_rows = []
    for threshold in grid:
        tn, fp, fn, tp = confusion_matrix(yy, scores >= threshold, labels=[0, 1]).ravel()
        threshold_rows.append({"threshold": threshold, "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)})
    selected = next(row for row in threshold_rows if row["threshold"] == chosen_threshold)
    if {key: selected[key] for key in ("tn", "fp", "fn", "tp")} != report["test_metrics"]["hist_gradient_boosting"]["confusion"]:
        raise AssertionError("La matriz de confusión reproducida no coincide")
    fpr, tpr, _ = roc_curve(yy, scores)
    precision, recall, _ = precision_recall_curve(yy, scores)
    return {
        "metadata": {
            "target": report["target"],
            "selected_model": report["selected_model"],
            "chosen_threshold": chosen_threshold,
            "test_n": int(len(test)), "test_positive": int(yy.sum()),
            "note": "Los umbrales alternativos son exploratorios sobre la prueba de 2018; el umbral recomendado se eligió antes en validación.",
        },
        "models": {key: {
            "cv_ap": value["cv_pr_auc"], "validation_ap": value["validation"]["pr_auc"],
            "test": report["test_metrics"][key],
        } for key, value in report["models"].items()},
        "uncertainty": report["test_uncertainty"],
        "calibration": report["calibration_deciles_test"],
        "importance": report["permutation_importance_validation"],
        "audit_2026": {
            "alternatives": 9,
            "selected": extended["selected"],
            "original_validation_ap": extended["baseline_validation"]["ap"],
            "best_new_validation_ap": max(row["validation"]["ap"] for row in extended["candidates"]),
            "best_cv_delta_ap_interval_95": extended["paired_validation"]["delta_ap_interval_95"],
            "recall_difficulty": breach["raw_recall"]["1"],
            "recall_no_difficulty": breach["raw_recall"]["2"],
            "age_adjusted_recall_difficulty": breach["age_standardized_recall"]["1"],
            "age_adjusted_recall_no_difficulty": breach["age_standardized_recall"]["2"],
        },
        "thresholds": threshold_rows,
        "roc_curve": sampled_curve(fpr, tpr),
        "pr_curve": sampled_curve(recall, precision),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    df, source = load_data(args.data_dir)
    if source["source_sha256"] != report["source"]["source_sha256"]:
        raise AssertionError("Los CSV cambiaron desde la evaluación del modelo")
    eda = make_eda(df, source)
    model = make_model(df, report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (("eda.json", eda), ("modelo.json", model)):
        (args.output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    print(json.dumps({
        "labeled": source["labeled"],
        "publishable_cells": eda["metadata"]["publishable_cells"],
        "all_cells": eda["metadata"]["all_cells"],
        "coverage_pct": eda["metadata"]["coverage_pct"],
        "test_ap_reproduced": model["models"]["hist_gradient_boosting"]["test"]["pr_auc"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
