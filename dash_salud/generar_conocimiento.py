"""Genera la base de conocimiento del asistente.

Reúne solo fuentes autorizadas: los textos y tablas agregadas de contenido.json, las
métricas de modelo.json y la prosa del informe. Las tablas del informe se omiten porque
sus recuentos no siempre pasan por el redondeo de las aplicaciones.

Ejecutar desde la raíz: python -m dash_salud.generar_conocimiento
"""

from __future__ import annotations

import html as html_std
import json
import re
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOMBRES_SECCION = {"panorama": "Introducción", "objetivos": "Objetivos", "problema": "Problema", "marco": "Marco teórico",
                   "univariado": "EDA univariado", "creacion": "Modelado", "conclusiones": "Conclusiones"}


def pasaje(titulo: str, fuente: str, texto: str, tipo: str) -> dict:
    return {"titulo": titulo, "fuente": fuente, "texto": re.sub(r"\s+", " ", texto).strip(), "tipo": tipo}


def bloques_a_pasajes(bloques: list[dict], seccion: str) -> list[dict]:
    fuente = f"Aplicación, sección {seccion}"
    salida = []
    for b in bloques:
        tipo = b["tipo"]
        titulo = b.get("titulo") or seccion
        if tipo == "parrafos":
            salida.append(pasaje(titulo, fuente, " ".join(b["parrafos"]), "aplicacion"))
        elif tipo == "destacado":
            salida.append(pasaje(b["rotulo"], fuente, b["texto"], "aplicacion"))
        elif tipo == "fichas":
            salida.append(pasaje(f"Cifras de {seccion}", fuente, " ".join(f"{i['etiqueta']}: {i['valor']}. {i['nota']}." for i in b["items"]), "aplicacion"))
        elif tipo == "lista":
            salida.extend(pasaje(f"{titulo}: {i['rotulo']}", fuente, i["texto"], "aplicacion") for i in b["items"])
        elif tipo == "etapas":
            salida.append(pasaje(titulo, fuente, " ".join(f"{i['titulo']}: {i['texto']}" for i in b["items"]), "aplicacion"))
        elif tipo == "tabla":
            filas = " ".join("; ".join(f"{c}: {v}" for c, v in zip(b["columnas"], f)) + "." for f in b["filas"])
            salida.append(pasaje(titulo, f"{fuente}, tabla «{titulo}»", " ".join(x for x in (b.get("meta"), filas, b.get("nota")) if x), "tabla"))
        elif tipo == "barras":
            unidad = " %" if b["unidad"] == "%" else " personas"
            valores = "; ".join(f"{c}: {str(v).replace('.', ',')}{unidad}" for c, v in zip(b["categorias"], b["valores"]))
            salida.append(pasaje(titulo, f"{fuente}, gráfica «{titulo}»", f"{b['meta']}. {valores}. {b['nota']}", "tabla"))
        elif tipo == "ruta":
            salida.append(pasaje(titulo, fuente, " ".join(f"{i['nombre']}: {i['valor']}." for i in b["lista"]) + " " + b["nota"], "tabla"))
        elif tipo == "permite":
            salida.append(pasaje(b["si_titulo"], fuente, " ".join(b["si"]), "aplicacion"))
            salida.append(pasaje(b["no_titulo"], fuente, " ".join(b["no"]), "aplicacion"))
        elif tipo == "glosario":
            salida.extend(pasaje(f"Término: {i['termino']}", f"{fuente}, términos usados", i["definicion"], "glosario") for i in b["items"])
        elif tipo == "preguntas":
            salida.extend(pasaje(i["pregunta"], f"{fuente}, preguntas frecuentes", i["respuesta"], "aplicacion") for i in b["items"])
        elif tipo in ("columnas", "pila"):
            salida.extend(bloques_a_pasajes(b["bloques"], seccion))
        elif tipo == "pestanas":
            for p in b["pestanas"]:
                salida.extend(bloques_a_pasajes(p["bloques"], seccion))
    return salida


class TextoInforme(HTMLParser):
    """Extrae secciones de una página del informe; omite tablas, figuras y código."""

    OMITIR = {"table", "figure", "script", "style", "pre", "nav"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dentro = False
        self.omitiendo = 0
        self.encabezado = None
        self.capitulo = ""
        self.secciones: list[dict] = []
        self.actual = None

    def handle_starttag(self, tag, attrs):
        clases = dict(attrs).get("class") or ""
        if tag == "section" and "normal" in clases.split():
            self.dentro = True
        if not self.dentro:
            return
        if tag in self.OMITIR:
            self.omitiendo += 1
        elif tag in ("h1", "h2", "h3") and not self.omitiendo:
            self.encabezado = {"nivel": tag, "texto": ""}

    def handle_endtag(self, tag):
        if not self.dentro:
            return
        if tag in self.OMITIR and self.omitiendo:
            self.omitiendo -= 1
        elif tag in ("h1", "h2", "h3") and self.encabezado and self.encabezado["nivel"] == tag:
            texto = re.sub(r"\s+", " ", self.encabezado["texto"]).strip()
            if tag == "h1":
                self.capitulo = texto
            self.actual = {"titulo": texto, "capitulo": self.capitulo, "texto": ""}
            self.secciones.append(self.actual)
            self.encabezado = None

    def handle_data(self, data):
        if not self.dentro or self.omitiendo:
            return
        if self.encabezado is not None:
            self.encabezado["texto"] += data
        elif self.actual is not None:
            self.actual["texto"] += data


def informe_a_pasajes(carpeta: Path) -> list[dict]:
    salida = []
    for pagina in sorted(carpeta.glob("*.html")):
        if pagina.name in ("404.html",):
            continue
        lector = TextoInforme()
        lector.feed(pagina.read_text(encoding="utf-8"))
        for s in lector.secciones:
            texto = html_std.unescape(s["texto"])
            texto = re.sub(r"\s+", " ", texto).strip()
            if len(texto) < 80:
                continue
            # Las secciones largas se parten para que cada pasaje trate un solo tema.
            partes, trozo = [], ""
            for oracion in re.split(r"(?<=[.!?])\s+", texto):
                if len(trozo) + len(oracion) > 900 and trozo:
                    partes.append(trozo)
                    trozo = ""
                trozo = f"{trozo} {oracion}".strip()
            partes.append(trozo)
            fuente = f"Informe, {s['capitulo']}" + (f", sección {s['titulo']}" if s["titulo"] != s["capitulo"] else "")
            salida.extend(pasaje(s["titulo"], fuente, p, "informe") for p in partes)
    return salida


def modelo_a_pasajes(contenido: dict) -> list[dict]:
    m = contenido["modelo"]
    fuente = "Aplicación, sección Modelo"
    salida = [pasaje(m["titulo"], fuente, m["entrada"], "aplicacion"),
              pasaje("Métricas del modelo validado", fuente, " ".join(f"{i['etiqueta']}: {i['valor']}. {i['nota']}." for i in m["fichas"]["items"]), "tabla"),
              pasaje(m["cambio"]["titulo"], fuente, " ".join(m["cambio"]["parrafos"] + m["cambio"]["aviso"]), "aplicacion"),
              pasaje(m["laboratorio"]["titulo"], fuente, m["laboratorio"]["texto"], "aplicacion")]
    salida.extend(bloques_a_pasajes(m["despues"], "Modelo"))
    return salida


def explorar_a_pasajes(contenido: dict) -> list[dict]:
    e = contenido["explorar"]
    fuente = "Aplicación, sección EDA multivariado"
    salida = [pasaje(e["titulo"], fuente, f"{e['entrada']} {e['ayuda']}", "aplicacion"),
              pasaje(e["por_que_titulo"], fuente, " ".join(e["por_que"]) + " " + e["total_nota"], "aplicacion"),
              pasaje("V de Cramér", fuente, e["comparar_entrada"] + " " + e["comparar_nota"], "aplicacion")]
    for v in e["variables"]:
        salida.append(pasaje(f"Comparación por {v['etiqueta'].lower()}", f"{fuente}, Comparar variables",
                             f"V de Cramér con {v['etiqueta'].lower()}: {v['v']}. {v['rango']} {v['lectura']}", "tabla"))
    salida.extend(bloques_a_pasajes(e["ajuste"], "EDA multivariado"))
    return salida


def coma(valor: float, decimales: int = 3) -> str:
    return f"{float(valor):.{decimales}f}".replace(".", ",")


def entero(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def respuestas_de_referencia(modelo: dict, relato: dict) -> list[dict]:
    """Respuestas a las preguntas más comunes, con cifras leídas de los resultados validados."""
    prueba = modelo["models"]["hist_gradient_boosting"]["test"]
    base = modelo["models"]["baseline"]["test"]
    mod = "Aplicación, sección Modelo"
    con = "Aplicación, sección Conclusiones"
    return [pasaje(t, f, x, "respuesta") for t, f, x in [
        ("¿Qué significa estar fuera de la ruta formal?", "Aplicación, sección Problema",
         f"Significa que la acción principal declarada no fue acudir a la EPS con atención ni a un médico particular. Incluye a quienes acudieron a la EPS sin ser atendidos, a quienes eligieron otra acción y a quienes no hicieron nada. No significa que les negaran la atención: solo {entero(relato['rutas']['eps_no_atendido'])} de {entero(relato['fuera'])} personas acudieron a su EPS y no fueron atendidas."),
        ("¿Qué tan bueno es el modelo?", mod,
         f"Ordena mejor que el azar, con discriminación moderada. Su precisión promedio (AP) fue {coma(prueba['pr_auc'])}, frente a {coma(base['pr_auc'])} sin modelo, y su ROC-AUC fue {coma(prueba['roc_auc'])}. Deja errores importantes y solo se evaluó con viviendas del mismo censo: no hay validación en otro año, en otro territorio ni clínica."),
        ("¿Qué limitaciones tiene el análisis?", con,
         "Solo incluye personas del Atlántico que declararon un problema de salud en 2018, sin hospitalización. Registra la acción principal, no todas las acciones, ni gravedad, tiempo de espera o motivo. El censo es transversal, así que las diferencias no prueban causas. El modelo no se validó en otro año ni territorio."),
        ("¿Qué variables usa el modelo?", "Aplicación, sección EDA univariado, tabla «Las 28 variables del modelo»",
         "Usa 28 variables: diez de la persona, cinco del hogar, once de la vivienda y dos de contexto de salud, una del hogar y otra de la sección censal. No usa los campos que construyen la respuesta ni la calidad del servicio, porque revelarían el resultado o son posteriores a la atención."),
        ("¿Cómo se eligió el umbral?", mod,
         f"Se eligió en el conjunto de validación con la métrica F1, antes de evaluar la prueba, y su valor es {coma(modelo['metadata']['chosen_threshold'], 4)}. Otros valores en la aplicación son escenarios de exploración, no recomendaciones."),
        ("¿Las personas fuera de la ruta no tienen EPS?", con,
         "El análisis no mide afiliación. Estar fuera de la ruta formal significa que la acción principal declarada no fue acudir a la EPS con atención ni a un médico particular. No indica si la persona estaba afiliada."),
        ("¿Qué datos usa el proyecto?", "Aplicación, sección Introducción",
         "Usa los microdatos anonimizados del Censo Nacional de Población y Vivienda 2018 del DANE para el Atlántico: personas, hogares y viviendas, más el Marco Geoestadístico Nacional. Las aplicaciones y este asistente solo contienen datos agregados."),
    ]]


def main() -> None:
    contenido = json.loads((RAIZ / "data" / "contenido.json").read_text(encoding="utf-8"))
    modelo = json.loads((RAIZ / "data" / "modelo.json").read_text(encoding="utf-8"))
    relato = json.loads((RAIZ / "assets" / "relato_datos.json").read_text(encoding="utf-8"))
    pasajes: list[dict] = respuestas_de_referencia(modelo, relato)
    for clave, pagina in contenido["paginas"].items():
        seccion = NOMBRES_SECCION[clave]
        if "titulo" in pagina:
            pasajes.append(pasaje(pagina["titulo"], f"Aplicación, sección {seccion}", pagina["entrada"], "aplicacion"))
        pasajes.extend(bloques_a_pasajes(pagina["bloques"], seccion))
    pasajes.extend(explorar_a_pasajes(contenido))
    pasajes.extend(modelo_a_pasajes(contenido))
    pasajes.extend(informe_a_pasajes(RAIZ / "informe"))
    for i, p in enumerate(pasajes, 1):
        p["id"] = i
    destino = RAIZ / "data" / "conocimiento.json"
    destino.write_text(json.dumps(pasajes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"conocimiento.json: {len(pasajes)} pasajes, {destino.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
