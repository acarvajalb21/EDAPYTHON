"""Ejecuta todas las celdas de código con microdatos ficticios y aislados.

Esta prueba detecta errores de ejecución; no valida las cifras censales.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.show = lambda *args, **kwargs: None


ROOT = Path(__file__).parent
NOTEBOOK = ROOT / "EDA_acceso_salud_Atlantico_CNPV2018.ipynb"
GEO = ROOT / "datos" / "mgn2018_municipios_atlantico.geojson"
codes = [str(f["properties"]["MPIO_CCDGO"]).zfill(3)
         for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]]

people, households, dwellings = [], [], []
for code in codes:
    for age in range(1, 22):
        for difficulty in (1, 2):
            for access in (0, 1):
                key = f"{len(people) + 1:08d}"
                base = {"COD_ENCUESTAS": key, "U_VIVIENDA": "1"}
                people.append({
                    **base, "U_DPTO": "08", "U_MPIO": code, "UA_CLASE": (age % 3) + 1,
                    "P_NROHOG": 1, "P_NRO_PER": 1, "P_SEXO": (age % 2) + 1,
                    "P_EDADR": age, "P_PARENTESCOR": 1, "PA1_GRP_ETNIC": 6,
                    "P_ENFERMO": 1, "P_QUEHIZO_PPAL": 1 if access else 3,
                    "PA_LO_ATENDIERON": 1 if access else None,
                    "PA1_CALIDAD_SERV": 2 if access else None,
                    "CONDICION_FISICA": difficulty, "P_ALFABETA": 1,
                    "PA_ASISTENCIA": 2, "P_NIVEL_ANOSR": 2,
                    "P_TRABAJO": 1, "P_EST_CIVIL": 7,
                })
                households.append({
                    **base, "H_NROHOG": 1, "H_NRO_CUARTOS": (age % 4) + 1,
                    "H_NRO_DORMIT": (age % 2) + 1, "HA_TOT_PER": (age % 5) + 1,
                })
                dwellings.append({**base, "VA1_ESTRATO": age % 7})

notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
with tempfile.TemporaryDirectory(prefix="eda_atlantico_smoke_") as temporary:
    workdir = Path(temporary)
    (workdir / "datos").mkdir()
    shutil.copy2(GEO, workdir / "datos" / GEO.name)
    pd.DataFrame(people).to_csv(workdir / "datos" / "CNPV2018_5PER_A2_08.CSV", index=False)
    pd.DataFrame(households).to_csv(workdir / "datos" / "CNPV2018_2HOG_A2_08.CSV", index=False)
    pd.DataFrame(dwellings).to_csv(workdir / "datos" / "CNPV2018_1VIV_A2_08.CSV", index=False)
    previous = Path.cwd()
    try:
        os.chdir(workdir)
        namespace = {"__name__": "__main__"}
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            try:
                exec(compile(source, f"celda {index}", "exec"), namespace)
                namespace["display"] = lambda *args, **kwargs: None
                plt.close("all")
            except Exception as error:
                raise RuntimeError(f"Falló la celda {index}: {error}") from error
        figures = list((workdir / "figuras").glob("*.png"))
        assert len(figures) == 9, f"Se generaron {len(figures)} figuras; se esperaban 9."
        assert (workdir / "salidas" / "base_analitica_acceso_salud.csv").is_file()
        print(f"OK: {len(people)} registros ficticios, {len(figures)} figuras y CSV analítico generado.")
    finally:
        os.chdir(previous)
