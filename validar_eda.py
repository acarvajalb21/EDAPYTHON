"""Comprueba la estructura del proyecto antes de reejecutar el cuaderno."""

import json
import re
import csv
from pathlib import Path

ROOT = Path(__file__).parent
NOTEBOOK = ROOT / "EDA_acceso_salud_Atlantico_CNPV2018.ipynb"
nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
code_cells = [(i, "".join(c["source"])) for i, c in enumerate(nb["cells"])
              if c["cell_type"] == "code"]
for i, source in code_cells:
    compile(source, f"cell {i}", "exec")

markdown = "\n".join("".join(c["source"]) for c in nb["cells"]
                     if c["cell_type"] == "markdown")
assert "**" not in markdown, "Queda negrilla Markdown."
assert not re.search(r"\bmoda\b", markdown, flags=re.I), "Queda una referencia a la moda."

geo = json.loads((ROOT / "datos" / "mgn2018_municipios_atlantico.geojson").read_text(encoding="utf-8"))
codes = [str(f["properties"]["MPIO_CCDGO"]).zfill(3) for f in geo["features"]]
assert len(codes) == 23 and len(set(codes)) == 23
assert all(str(f["properties"]["DPTO_CCDGO"]).zfill(2) == "08" for f in geo["features"])

for name in ("01_distribucion_acceso", "02_histogramas_cuantitativas",
             "03_mediana_hogar_acceso", "04_acceso_por_dificultad",
             "05_acceso_edad_dificultad", "06_acceso_sexo_dificultad",
             "07_acceso_por_estrato", "08_acceso_por_municipio",
             "09_mapa_acceso_municipal"):
    assert (ROOT / "figuras" / f"{name}.png").is_file(), f"Falta figura {name}."

required = ["CNPV2018_5PER_A2_08.CSV", "CNPV2018_2HOG_A2_08.CSV",
            "CNPV2018_1VIV_A2_08.CSV"]
missing = [name for name in required if not (ROOT / "datos" / name).is_file()]
print(f"OK: {len(code_cells)} celdas de código compilan; 23 códigos MGN únicos; 9 figuras presentes.")
if missing:
    print("Reejecución completa pendiente: faltan " + ", ".join(missing))
else:
    incomplete = [i for i, cell in enumerate(nb["cells"])
                  if cell["cell_type"] == "code" and (cell.get("execution_count") is None
                  or any(o["output_type"] == "error" for o in cell.get("outputs", [])))]
    assert not incomplete, f"Hay celdas sin ejecución correcta: {incomplete}"
    assert [nb["cells"][i]["execution_count"] for i, _ in code_cells] == list(range(1, len(code_cells) + 1))
    with (ROOT / "salidas" / "resumen_municipal_acceso.csv").open(encoding="utf-8-sig", newline="") as file:
        municipalities = list(csv.DictReader(file))
    assert len(municipalities) == 23
    assert {row["código"] for row in municipalities} == set(codes)
    assert sum(int(row["n"]) for row in municipalities) == 136034
    assert sum(int(row["accedieron"]) for row in municipalities) == 107384
    assert (ROOT / "salidas" / "base_analitica_acceso_salud.csv").is_file()
    print("Ejecución completa: 38 celdas en orden, sin errores; 136.034 personas y 23 municipios verificados.")
