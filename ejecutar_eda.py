"""Reejecuta el cuaderno completo en un kernel limpio y guarda sus salidas.

Uso: python ejecutar_eda.py
Ejecutar con el Python que tenga pandas, numpy, matplotlib, seaborn, ipykernel,
nbclient y nbformat instalados. El cuaderno solo se reemplaza si todo termina bien.
"""

import json
import os
import sys
import tempfile
import asyncio
from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).parent
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
NOTEBOOK = ROOT / "EDA_acceso_salud_Atlantico_CNPV2018.ipynb"
REQUIRED = [
    "CNPV2018_5PER_A2_08.CSV",
    "CNPV2018_2HOG_A2_08.CSV",
    "CNPV2018_1VIV_A2_08.CSV",
]
missing = [name for name in REQUIRED if not (ROOT / "datos" / name).is_file()]
if missing:
    raise FileNotFoundError("Faltan en datos/: " + ", ".join(missing))

with tempfile.TemporaryDirectory(prefix="eda_atlantico_jupyter_") as temporary:
    temporary = Path(temporary)
    for key, relative in [
        ("JUPYTER_CONFIG_DIR", "config"),
        ("JUPYTER_DATA_DIR", "data"),
        ("JUPYTER_RUNTIME_DIR", "runtime"),
        ("IPYTHONDIR", "ipython"),
        ("MPLCONFIGDIR", "matplotlib"),
    ]:
        path = temporary / relative
        path.mkdir()
        os.environ[key] = str(path)
    kernel_dir = temporary / "data" / "kernels" / "eda_actual"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "EDA actual",
        "language": "python",
    }), encoding="utf-8")

    notebook = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=1800,
        kernel_name="eda_actual",
        resources={"metadata": {"path": str(ROOT)}},
        allow_errors=False,
    )
    client.execute()
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "code" and any(
            output.output_type == "error" for output in cell.get("outputs", [])
        ):
            raise RuntimeError(f"La celda {index} produjo un error.")
    candidate = ROOT / ".eda_ejecutado_temporal.ipynb"
    try:
        nbformat.write(notebook, candidate)
        candidate.replace(NOTEBOOK)
    finally:
        candidate.unlink(missing_ok=True)

print("Cuaderno ejecutado completo y salidas actualizadas.")
