"""Cambia en el Jupyter Book compilado las imágenes de respaldo por las figuras interactivas.

Uso, después de compilar el libro:
    python libro_interactivo.py CARPETA_HTML

myst-nb nombra cada imagen con su huella SHA-256. Este script busca esa huella en las salidas
de los cuadernos, pone en su lugar la figura de Plotly y conserva la imagen dentro de
<noscript> para quien lea sin JavaScript. Plotly se sirve desde el propio libro.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import plotly

RAIZ = Path(__file__).parent
CUADERNOS = ["EDA_acceso_salud_Atlantico_CNPV2018", "Modelo_acceso_salud_Atlantico_CNPV2018"]
TIPO = "application/vnd.plotly.v1+json"
# En el tema oscuro del libro, las tintas pasan a tonos claros y la etiqueta emergente se invierte.
DIBUJAR = """<script src="_static/plotly.min.js"></script>
<script>
(function () {
  var OSCURO = {"#10293B": "#F2F6F9", "#3A4F60": "#DCE5EC", "#54697A": "#A9B8C4", "#D9E1E7": "rgba(255,255,255,0.14)"};
  function dibujar() {
    var oscuro = document.documentElement.dataset.theme === "dark";
    document.querySelectorAll(".figura-interactiva").forEach(function (div) {
      var texto = document.getElementById(div.dataset.datos).textContent;
      if (oscuro) Object.keys(OSCURO).forEach(function (c) { texto = texto.split(c).join(OSCURO[c]); });
      var f = JSON.parse(texto);
      if (oscuro) f.layout.hoverlabel = {bgcolor: "#F2F6F9", bordercolor: "#F2F6F9", font: {color: "#10293B"}};
      Plotly.react(div, f.data, f.layout, f.config);
    });
  }
  dibujar();
  new MutationObserver(dibujar).observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
})();
</script>
"""


def texto_de(valor) -> str:
    return "".join(valor) if isinstance(valor, list) else valor


def main(destino: Path) -> None:
    shutil.copyfile(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", destino / "_static" / "plotly.min.js")
    for nombre in CUADERNOS:
        pagina = destino / f"{nombre}.html"
        html = pagina.read_text(encoding="utf-8")
        cuaderno = json.loads((RAIZ / f"{nombre}.ipynb").read_text(encoding="utf-8"))
        cambios = 0
        for celda in cuaderno["cells"]:
            for salida in celda.get("outputs", []):
                datos = salida.get("data", {})
                if TIPO not in datos or "image/png" not in datos:
                    continue
                huella = hashlib.sha256(base64.b64decode(texto_de(datos["image/png"]))).hexdigest()
                imagen = re.search(r'<img[^>]*src="_images/' + huella + r'\.png"[^>]*>', html)
                if not imagen:
                    raise SystemExit(f"No se encontró la imagen {huella[:12]} en {pagina.name}")
                figura = json.dumps(datos[TIPO], ensure_ascii=False).replace("</", "<\\/")
                nuevo = (f'<div class="figura-interactiva" data-datos="datos-{huella[:12]}"></div>'
                         f'<script type="application/json" id="datos-{huella[:12]}">{figura}</script>'
                         f'<noscript>{imagen.group(0)}</noscript>')
                html = html[:imagen.start()] + nuevo + html[imagen.end():]
                cambios += 1
        if cambios:
            html = html.replace("</body>", DIBUJAR + "</body>", 1)
        pagina.write_text(html, encoding="utf-8")
        print(f"{pagina.name}: {cambios} figuras interactivas")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs"))
