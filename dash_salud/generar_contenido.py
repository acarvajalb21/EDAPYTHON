"""Genera el contenido de las secciones, común a Dash y Shiny.

Usa las tablas agregadas del Bookdown y modelo.json; no necesita microdatos. Los grupos
pasan por la regla del panorama municipal: al menos 100 personas y 10 dentro y fuera de
la ruta formal, con recuentos redondeados a 10.

Ejecutar desde la raíz: python -m dash_salud.generar_contenido --tablas ../EDAR-main/data
    --destino dash_salud/data ../EDAR-main/shiny_salud/data
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

# Cuando el equipo defina el nombre del proyecto, se cambia aquí y se regenera.
NOMBRE = "Salud Atlántico"

URL_BOOKDOWN = "https://acarvajalb21.github.io/EDAR/"
URL_DASH = "https://dataviz-salud-atlantico-409319239507.us-east1.run.app/"
URL_SHINY = "https://shiny-salud-atlantico-409319239507.us-east1.run.app/"
URL_NOTEBOOK = "https://github.com/acarvajalb21/EDAPYTHON/blob/main/Modelo_acceso_salud_Atlantico_CNPV2018.ipynb"
URL_DANE = "https://microdatos.dane.gov.co/catalog/643"

SECCIONES = [
    ("panorama", "Introducción"), ("objetivos", "Objetivos"), ("problema", "Problema"),
    ("marco", "Marco teórico"), ("univariado", "EDA univariado"), ("explorar", "EDA multivariado"),
    ("creacion", "Modelado"), ("modelo", "Modelo"), ("conclusiones", "Conclusiones"),
]


def entero(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def coma(valor: float, decimales: int = 3) -> str:
    return f"{float(valor):.{decimales}f}".replace(".", ",")


def pct(valor: float, decimales: int = 1) -> str:
    return coma(valor, decimales) + " %"


def leer(carpeta: Path, nombre: str) -> list[dict]:
    with (carpeta / f"{nombre}.csv").open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def redondeado(valor: int, base: int = 10) -> int:
    return int(base * round(valor / base))


def publicable(filas: list[dict], etiqueta) -> tuple[list[dict], int]:
    """Aplica la regla del panorama a una tabla de grupos y cuenta los omitidos."""
    salida, omitidos = [], 0
    for fila in filas:
        n, fuera = int(fila["n"]), int(fila["sin_formal"])
        if n < 100 or fuera < 10 or n - fuera < 10:
            omitidos += 1
            continue
        dentro_r, fuera_r = redondeado(n - fuera), redondeado(fuera)
        salida.append({"categoria": etiqueta(fila), "n": dentro_r + fuera_r, "sin_formal": fuera_r})
    return salida, omitidos


def v_cramer(filas: list[dict]) -> float:
    """V de Cramér de una tabla de grupos por dos clases, con los recuentos exactos."""
    pares = [(int(f["sin_formal"]), int(f["n"]) - int(f["sin_formal"])) for f in filas]
    total = sum(a + b for a, b in pares)
    fuera = sum(a for a, _ in pares)
    dentro = total - fuera
    chi2 = 0.0
    for a, b in pares:
        fila = a + b
        chi2 += (a - fila * fuera / total) ** 2 / (fila * fuera / total)
        chi2 += (b - fila * dentro / total) ** 2 / (fila * dentro / total)
    return math.sqrt(chi2 / total)


ESTRATOS = {"0": "Sin estrato", "9": "No sabe", "": "Sin dato"}


def estrato(fila: dict) -> str:
    codigo = fila["VA1_ESTRATO"].split(".")[0]
    return ESTRATOS.get(codigo, f"Estrato {codigo}")


def comparaciones(t: Path) -> list[dict]:
    fuentes = [
        ("edad", "Edad", leer(t, "edad"), lambda f: f["grupo_edad"], False,
         "Es la asociación más alta de las comparadas. Los grupos de edad avanzada son más pequeños que los jóvenes: cada porcentaje debe leerse con su base."),
        ("municipio", "Municipio", leer(t, "municipio"), lambda f: f["municipio"], True,
         "Cada municipio reúne contextos sociales y de oferta distintos. Describe dónde hay diferencias, no por qué ocurren, y no está ajustado por edad. Piojó no aparece porque no alcanza el mínimo de publicación."),
        ("dificultad", "Dificultad funcional", leer(t, "dificultad"), lambda f: f["dificultad"], False,
         "Va en dirección contraria a lo que se podría esperar. Quienes declaran dificultad suelen tener más edad, y eso explica parte de la diferencia: revísalo en «Ajuste por edad»."),
        ("estrato", "Estrato", leer(t, "estrato"), estrato, False,
         "Entre los estratos 1 a 3 el porcentaje es parecido y baja de forma visible en el 4. No se presume un cambio uniforme por nivel."),
        ("sexo", "Sexo", leer(t, "sexo"), lambda f: f["sexo"], False,
         "La diferencia no se ajustó por edad ni por territorio."),
        ("zona", "Clase de área", leer(t, "clase_area"), lambda f: f["clase_area"], False,
         "El porcentaje es mayor en el área rural dispersa que en las cabeceras. Se refiere solo a quienes declararon el problema de salud; no mide cobertura territorial."),
    ]
    salida = []
    for clave, etiqueta, filas, nombre, ordenar, lectura in fuentes:
        categorias, omitidos = publicable(filas, nombre)
        if ordenar:
            categorias.sort(key=lambda c: -c["sin_formal"] / c["n"])
        tasas = [c["sin_formal"] / c["n"] for c in categorias]
        alta, baja = categorias[tasas.index(max(tasas))], categorias[tasas.index(min(tasas))]
        rango = (f"Va de {pct(100 * min(tasas))} en {baja['categoria']} a {pct(100 * max(tasas))} en {alta['categoria']}."
                 if len(categorias) > 2 else
                 f"{categorias[0]['categoria']}: {pct(100 * tasas[0])}. {categorias[1]['categoria']}: {pct(100 * tasas[1])}.")
        salida.append({"id": clave, "etiqueta": etiqueta, "v": coma(v_cramer(filas)), "rango": rango, "lectura": lectura,
                       "omitidos": omitidos, "categorias": categorias})
    return salida


def barras(id_: str, titulo: str, meta: str, nota: str, categorias: list, valores: list, unidad: str, color: str) -> dict:
    return {"tipo": "barras", "id": id_, "titulo": titulo, "meta": meta, "nota": nota, "categorias": categorias,
            "valores": valores, "unidad": unidad, "color": color}


def distribucion(id_: str, titulo: str, filas: list[dict], etiqueta, total: int) -> dict:
    grupos, omitidos = publicable(filas, etiqueta)
    nota = "Recuentos redondeados a 10." + (f" Se omite {omitidos} grupo con menos de 100 personas." if omitidos == 1 else
                                            f" Se omiten {omitidos} grupos con menos de 100 personas." if omitidos else "")
    return barras(id_, titulo, "Porcentaje de las personas estudiadas", nota, [g["categoria"] for g in grupos],
                  [round(100 * g["n"] / total, 2) for g in grupos], "%", "neutro")


def banda(x1, a1, b1, x2, a2, b2, clase) -> str:
    m = (x1 + x2) / 2
    return (f'<path class="ruta-banda {clase}" d="M{x1:.1f},{a1:.1f} C{m:.1f},{a1:.1f} {m:.1f},{a2:.1f} {x2:.1f},{a2:.1f} '
            f'L{x2:.1f},{b2:.1f} C{m:.1f},{b2:.1f} {m:.1f},{b1:.1f} {x1:.1f},{b1:.1f} Z"/>')


def nodo(x, y, alto, clase) -> str:
    return f'<rect class="ruta-nodo {clase}" x="{x:.1f}" y="{y:.1f}" width="9" height="{alto:.1f}" rx="2"/>'


def rotulo(x, y, titulo, cifra, fuerte=False) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="ruta-nombre{" fuerte" if fuerte else ""}">{titulo}</text>'
            f'<text x="{x:.1f}" y="{y + 19:.1f}" class="ruta-cifra">{cifra}</text>')


def diagrama_ruta(comp: dict, total: int, fuera: int) -> dict:
    """Diagrama de ruta: el ancho de cada banda es proporcional a las personas que la siguen."""
    atendido, medico = comp["EPS/entidad, atendido"], comp["Médico particular"]
    sin_atencion, otras = comp["EPS/entidad, no atendido"], comp["Otras acciones o ninguna"]
    dentro = atendido + medico
    k = 250 / total
    xa, xb, xc = 196, 548, 800
    a0 = 50
    yd, hd = 34, dentro * k
    yf, hf = yd + hd + 28, fuera * k
    he, hp, ho = atendido * k, medico * k, otras * k
    hn = max(sin_atencion * k, 3)
    ye = 18
    yp = ye + he + 20
    yo = yp + hp + 26
    yn = yo + ho + 16

    def etiqueta(v):
        return f"{entero(v)} personas, {pct(100 * v / total)}"

    partes = [
        banda(xa + 9, a0, a0 + hd, xb, yd, yd + hd, "dentro"),
        banda(xa + 9, a0 + hd, a0 + 250, xb, yf, yf + hf, "fuera"),
        banda(xb + 9, yd, yd + he, xc, ye, ye + he, "dentro"),
        banda(xb + 9, yd + he, yd + hd, xc, yp, yp + hp, "dentro"),
        banda(xb + 9, yf, yf + ho, xc, yo, yo + ho, "fuera"),
        banda(xb + 9, yf + ho, yf + hf, xc, yn, yn + hn, "fuera"),
        nodo(xa, a0, 250, "total"), nodo(xb, yd, hd, "dentro"), nodo(xb, yf, hf, "fuera"),
        nodo(xc, ye, he, "dentro"), nodo(xc, yp, hp, "dentro"), nodo(xc, yo, ho, "fuera"), nodo(xc, yn, hn, "fuera"),
        f'<text x="0" y="168" class="ruta-total">{entero(total)}</text><text x="0" y="192" class="ruta-nombre">personas estudiadas</text>',
        rotulo(xb - 210, yd + hd / 2 - 8, "Dentro de la ruta formal", etiqueta(dentro), True),
        rotulo(xb - 210, yf + hf / 2 - 2, "Fuera de la ruta formal", etiqueta(fuera), True),
        rotulo(xc + 20, ye + he / 2 - 8, "Acudió a su EPS y fue atendida", etiqueta(atendido)),
        rotulo(xc + 20, yp + 2, "Consultó a médico particular", etiqueta(medico)),
        rotulo(xc + 20, yo + ho / 2 - 8, "Otra acción principal o ninguna", etiqueta(otras)),
        rotulo(xc + 20, yn + 8, "Acudió a su EPS y no fue atendida", etiqueta(sin_atencion)),
    ]
    descripcion = (f"De {entero(total)} personas, {entero(dentro)} quedaron dentro de la ruta formal y {entero(fuera)} fuera. "
                   f"Solo {entero(sin_atencion)} acudieron a su EPS y no fueron atendidas.")
    svg = f'<svg class="ruta-svg" viewBox="0 0 1130 360" role="img" aria-label="{descripcion}">{"".join(partes)}</svg>'
    lista = [{"nombre": n, "valor": etiqueta(v), "clase": c, "ancho": round(100 * v / total, 2)} for n, v, c in [
        ("Acudió a su EPS y fue atendida", atendido, "dentro"), ("Consultó a médico particular", medico, "dentro"),
        ("Otra acción principal o ninguna", otras, "fuera"), ("Acudió a su EPS y no fue atendida", sin_atencion, "fuera")]]
    return {"tipo": "ruta", "titulo": "Las cuatro respuestas posibles",
            "meta": "El ancho de cada banda es proporcional a las personas que dieron esa respuesta",
            "nota": "Son acciones principales declaradas. «Otra acción principal o ninguna» incluye automedicación, remedios caseros y boticario; no significa que la persona no recibiera ninguna atención.",
            "svg": svg, "lista": lista}


def pagina_modelo(modelo: dict) -> dict:
    prueba = modelo["models"]["hist_gradient_boosting"]["test"]
    base = modelo["models"]["baseline"]["test"]
    cambio = modelo["version_change"]
    auditoria = modelo["audit_2026"]
    equidad = modelo["equity"]
    ic = modelo["uncertainty"]["intervals_95"]["selected_ap"]
    escenarios = {"v1_umbral_validado": "Versión 1, su umbral", "v2_mismas_personas_marcadas": "Versión 2, mismas personas marcadas",
                  "v2_umbral_validado": "Versión 2, su umbral"}
    grupos = [[e, entero(modelo["same_flagged"][k]["flagged"]), pct(100 * modelo["same_flagged"][k]["recall"]),
               pct(100 * modelo["same_flagged"][k]["recall_difficulty"]), pct(100 * modelo["same_flagged"][k]["recall_no_difficulty"]),
               pct(100 * modelo["same_flagged"][k]["recall_60_plus"])] for k, e in escenarios.items()]
    priorizacion = [[f"{pct(100 * r['fraction'], 0)} con mayor puntuación", entero(r["reviewed"]), entero(r["positives_found"]),
                     pct(100 * r["precision"]), pct(100 * r["recall"])] for r in modelo["prioritization"]]
    return {
        "titulo": "Qué tan bien ordena el modelo",
        "entrada": "El modelo intenta ordenar a las personas según qué tan probable es que estén fuera de la ruta formal, usando solo datos del censo. Se evaluó con viviendas del mismo censo que no vio al entrenar. Esta aplicación no calcula predicciones sobre personas.",
        "fichas": {"tipo": "fichas", "items": [
            {"etiqueta": "Precisión promedio (AP)", "valor": coma(prueba["pr_auc"]), "tono": "dentro",
             "nota": f"Qué tan arriba quedan las personas fuera de la ruta. Sin modelo, {coma(base['pr_auc'])}"},
            {"etiqueta": "ROC-AUC", "valor": coma(prueba["roc_auc"]),
             "nota": "Probabilidad de puntuar más alto a alguien fuera que a alguien dentro. El azar da 0,500"},
            {"etiqueta": "Brier", "valor": coma(prueba["brier"]),
             "nota": f"Error de las probabilidades: menor es mejor. Sin modelo, {coma(base['brier'])}"}]},
        "cambio": {
            "titulo": "Qué cambió en esta versión",
            "parrafos": [
                f"Las {auditoria['alternatives']} alternativas de preparación de datos y ajuste que se probaron primero no mejoraron el modelo de 26 variables. La mejora llegó con dos variables de contexto: cuántas personas más del hogar declararon un problema de salud y qué proporción lo declaró en la sección censal.",
                f"La precisión promedio en validación pasó de {coma(cambio['previous_validation_ap'])} a {coma(cambio['new_validation_ap'])}, y en secciones censales que el modelo no vio, de {coma(cambio['previous_unseen_sections_ap'])} a {coma(cambio['new_unseen_sections_ap'])}."],
            "aviso_titulo": "Cómo leerlo",
            "aviso": ["Estas variables no revelan la acción de la persona, pero se miden en el mismo censo. Pueden reflejar problemas más leves o la forma de responder. No indican una causa."],
        },
        "laboratorio": {
            "titulo": "Qué cambia al marcar a más personas",
            "texto": "El umbral es el punto de corte: quien supera esa puntuación queda marcado. Muévelo para ver el balance entre encontrar más casos y dar más falsas alarmas en la prueba. La posición validada se eligió antes de mirar la prueba; las demás son escenarios de exploración.",
            "etiqueta": "Umbral de clasificación",
            "matriz_titulo": "Aciertos y errores con este umbral",
            "matriz_nota": "Personas de la prueba reservada. Se considera positivo estar fuera de la ruta formal.",
        },
        "graficas": {
            "comparacion": {"titulo": "Comparación de los cuatro enfoques", "meta": "Precisión promedio (AP) en la prueba", "nota": "La referencia predice siempre la prevalencia: es lo que se obtendría sin modelo."},
            "curvas": {"titulo": "Curvas de desempeño", "meta": "Cómo cambia el balance de errores en todos los umbrales", "nota": "Curvas resumidas para la gráfica; AP y ROC-AUC se calculan con todas las puntuaciones de la prueba."},
            "calibracion": {"titulo": "Probabilidad estimada y frecuencia observada", "meta": "Calibración", "nota": "Cada punto agrupa cerca de una décima parte de la prueba. Estar cerca de la diagonal no valida el modelo para otro año."},
            "importancia": {"titulo": "Variables que más ayudaron a ordenar", "meta": "Cuánto cae la precisión promedio si se desordena la variable", "nota": "En azul, las dos variables añadidas. Mide dependencia del modelo, no efecto causal."},
        },
        "despues": [
            {"tipo": "columnas", "bloques": [
                {"tipo": "tabla", "titulo": "Si solo se revisara una parte", "meta": "Personas de la prueba ordenadas por puntuación", "texto_cols": 1,
                 "columnas": ["Se revisa", "Personas", "Fuera de la ruta", "Precisión", "Sensibilidad"], "filas": priorizacion,
                 "nota": "No es una recomendación: no hay costos ni capacidad definidos, y el modelo no debe usarse para decidir sobre personas."},
                {"tipo": "tabla", "titulo": "Diferencias entre grupos", "meta": "Sensibilidad: de quienes están fuera de la ruta, cuántos marca el modelo", "texto_cols": 1,
                 "columnas": ["Escenario", "Marcadas", "Todas", "Con dificultad", "Sin dificultad", "60 años o más"], "filas": grupos,
                 "nota": f"Con las mismas personas marcadas, la versión 2 mejora en todos los grupos. Ajustada por edad, la sensibilidad es {pct(100 * equidad['age_adjusted_recall_difficulty'])} con dificultad funcional y {pct(100 * equidad['age_adjusted_recall_no_difficulty'])} sin ella: la brecha persiste, y en personas de 60 años o más sigue baja."}]},
            {"tipo": "lista", "titulo": "Cómo leer este modelo", "columnas": 2, "items": [
                {"rotulo": "Una mejora acotada", "texto": f"La precisión promedio fue {coma(prueba['pr_auc'])}, con intervalo interno de 95 % de {coma(ic[0])} a {coma(ic[1])}. La discriminación es moderada."},
                {"rotulo": "Separación cuidadosa", "texto": "Entrenamiento, validación y prueba se separaron por vivienda. Los ajustes se hicieron en entrenamiento y el umbral se eligió en validación."},
                {"rotulo": "Uso responsable", "texto": "Los datos son de 2018. Falta validación en otro año y otro territorio antes de aplicarlo a personas o a decisiones de atención."},
                {"rotulo": "Qué no mide", "texto": "No mide afiliación, necesidad clínica, barreras ni ausencia de toda atención. Dificultad funcional no equivale a un diagnóstico de discapacidad."}]},
        ],
    }


def construir(t: Path, relato: dict, modelo: dict, eda: dict) -> dict:
    r = leer(t, "resumen_general")[0]
    cohorte, fuera, dentro = int(r["cohorte"]), int(r["sin_formal"]), int(r["con_formal"])
    comp = {f["tratamiento_principal"]: int(f["n"]) for f in leer(t, "composicion_etiqueta")}
    eps_sin = comp["EPS/entidad, no atendido"]
    tasa = float(r["porcentaje_sin_formal"])
    modelos = leer(t, "comparacion_modelos")
    prevalencia = next(m for m in modelos if m["codigo"] == "baseline")
    elegido = next(m for m in modelos if m["codigo"] == "hist_gradient_boosting")
    part = leer(t, "particiones")
    inc = {f["metrica"]: f for f in leer(t, "incertidumbre")}
    ctx = leer(t, "contexto_comparacion")
    dec = leer(t, "contexto_decision")[0]
    calidad = leer(t, "calidad_variables")
    dic = leer(t, "diccionario_modelo")
    acciones = relato["acciones"]
    nombres_accion = [("autorreceta", "Se automedicó"), ("remedios", "Remedios caseros"), ("nada", "No hizo nada"),
                      ("boticario", "Boticario o droguista"), ("otras", "Otras alternativas")]
    tasa_cubo = 100 * sum(c["sin_formal"] for c in eda["cube"]) / sum(c["n"] for c in eda["cube"])

    panorama = {"bloques": [
        {"tipo": "parrafos", "titulo": "Qué es este proyecto", "parrafos": [
            "En 2018, el censo preguntó a las personas si habían tenido un problema de salud en los últimos 30 días y qué hicieron principalmente para atenderlo. Este proyecto analiza esas respuestas en el departamento del Atlántico.",
            "Llamamos ruta formal a acudir a la EPS y ser atendido, o consultar a un médico particular. Comparar quién quedó dentro o fuera de esa ruta ayuda a encontrar patrones que merecen estudiarse. No permite reconstruir toda la historia de atención de cada persona."]},
        {"tipo": "fichas", "items": [
            {"etiqueta": "Personas estudiadas", "valor": entero(cohorte), "nota": "Declararon un problema de salud sin hospitalización y tienen respuesta clasificable"},
            {"etiqueta": "Fuera de la ruta formal", "valor": pct(tasa, 2), "nota": f"{entero(fuera)} personas. No significa que les negaran la atención", "tono": "fuera"},
            {"etiqueta": "Acudieron a su EPS y no fueron atendidas", "valor": entero(eps_sin), "nota": f"{pct(100 * eps_sin / cohorte, 2)} de las personas estudiadas"}]},
        {"tipo": "etapas", "titulo": "Cómo se hizo", "horizontal": True, "items": [
            {"titulo": "Datos y calidad", "texto": "Se unieron personas, hogares y viviendas, y se revisó qué información falta."},
            {"titulo": "Análisis exploratorio", "texto": "Se compararon grupos, siempre con su número de personas."},
            {"titulo": "Tableros", "texto": "Dash y Shiny permiten filtrar, publicando solo datos agregados."},
            {"titulo": "Modelo", "texto": "Se compararon modelos y se revisaron sus errores por grupo."},
            {"titulo": "Informe", "texto": "Bookdown y notebook guardan las decisiones y las cifras exactas."}]},
        {"tipo": "columnas", "bloques": [
            {"tipo": "parrafos", "titulo": "De dónde salen los datos", "parrafos": [
                "Del Censo Nacional de Población y Vivienda 2018 del DANE. Se usan los microdatos anonimizados de personas, hogares y viviendas del Atlántico, y el Marco Geoestadístico Nacional para ubicar cada vivienda en su sección censal.",
                "Esos microdatos no se publican aquí: las aplicaciones solo contienen datos agregados."],
             "enlace": {"texto": "Ver el catálogo del DANE", "url": URL_DANE}},
            {"tipo": "lista", "titulo": "Cómo recorrer la aplicación", "items": [
                {"rotulo": "Para entender el tema", "texto": "Problema explica la cifra principal y qué no significa."},
                {"rotulo": "Para explorar", "texto": "EDA multivariado deja elegir un grupo y compararlo."},
                {"rotulo": "Para ver el modelo", "texto": "Modelo muestra qué tan bien ordena y dónde falla."},
                {"rotulo": "Para cerrar", "texto": "Conclusiones reúne lo que los datos permiten y no permiten decir."}]}]},
        {"tipo": "pie", "texto": "Fuente: microdatos anonimizados del CNPV 2018, DANE. Nombres municipales: DIVIPOLA del DANE. Los cuadros del relato representan grupos, no personas reales."},
    ]}

    objetivos = {"titulo": "Qué busca responder el proyecto", "entrada": "La pregunta de partida, lo que se quiso lograr y cómo se organizó el trabajo.", "bloques": [
        {"tipo": "destacado", "rotulo": "Pregunta de investigación", "texto": "¿Cómo varía el acceso a atención formal entre las personas censadas en el Atlántico que reportaron un problema de salud, según sus características funcionales, sociodemográficas, habitacionales y territoriales?"},
        {"tipo": "parrafos", "titulo": "Objetivo general", "parrafos": [
            "Describir el acceso a atención formal en esta población y su distribución según características funcionales, sociodemográficas, habitacionales y territoriales observadas en el CNPV 2018, y evaluar hasta qué punto esas variables permiten ordenar a las personas que quedaron fuera de la ruta formal."]},
        {"tipo": "columnas", "bloques": [
            {"tipo": "lista", "titulo": "Objetivos específicos", "items": [
                {"rotulo": "1. Definir la medida", "texto": "Construir y documentar una medida binaria de acceso a partir del tratamiento principal y la atención recibida, y cuantificar los casos que no se pueden clasificar."},
                {"rotulo": "2. Revisar los datos", "texto": "Describir la distribución de la respuesta, la calidad de los datos y las características de las personas y los hogares incluidos."},
                {"rotulo": "3. Comparar grupos", "texto": "Comparar el acceso entre grupos de dificultad funcional, sexo, edad, estrato, personas por cuarto, clase de área y municipio, indicando el tamaño y el denominador de cada grupo."},
                {"rotulo": "4. Ajustar por edad", "texto": "Examinar cuánto cambia la diferencia por dificultad funcional al estandarizar los porcentajes por edad."},
                {"rotulo": "5. Evaluar un modelo", "texto": "Medir, con una prueba interna separada, cuánto mejora un modelo frente a predecir siempre la prevalencia del grupo."}]},
            {"tipo": "etapas", "titulo": "Etapas del proyecto", "items": [
                {"titulo": "Análisis exploratorio", "texto": "Regla de la respuesta, calidad de los datos y comparaciones por grupo."},
                {"titulo": "Tableros", "texto": "Filtros, cobertura visible y protección de grupos pequeños."},
                {"titulo": "Modelo", "texto": "Boosting de histogramas, umbral validado y límites de uso."}]}]},
    ]}

    problema = {"titulo": "Qué ruta se declaró ante un problema de salud", "entrada": "Una clasificación de la acción principal reportada en el censo de 2018, no una medida de atención negada.", "bloques": [
        {"tipo": "fichas", "items": [
            {"etiqueta": "Personas estudiadas", "valor": entero(cohorte), "nota": "Con respuesta clasificable"},
            {"etiqueta": "Dentro de la ruta formal", "valor": entero(dentro), "nota": f"{pct(float(r['porcentaje_con_formal']), 2)} de las personas estudiadas", "tono": "dentro"},
            {"etiqueta": "Fuera de la ruta formal", "valor": entero(fuera), "nota": f"{pct(tasa, 2)} de las personas estudiadas", "tono": "fuera"},
            {"etiqueta": "EPS sin atención", "valor": entero(eps_sin), "nota": f"{pct(100 * eps_sin / fuera, 1)} de quienes están fuera"}]},
        {"tipo": "parrafos", "titulo": "Descripción del problema", "parrafos": [
            "Cuando alguien tiene un problema de salud puede acudir a su EPS, consultar a un médico particular, automedicarse, usar remedios caseros, ir a un boticario o no hacer nada. El censo de 2018 registró cuál fue su acción principal.",
            f"En el Atlántico, {entero(cohorte)} personas declararon un problema de salud reciente sin hospitalización y tienen una respuesta clasificable. De ellas, {entero(fuera)} quedan fuera de la ruta formal: su acción principal no fue acudir a la EPS con atención ni a un médico particular.",
            "El propósito no es medir una negativa de atención. Es entender cómo varía esa ruta declarada entre grupos y territorios, y si las variables del censo permiten ordenar esos casos."]},
        diagrama_ruta(comp, cohorte, fuera),
        {"tipo": "destacado", "rotulo": "Lo que esta cifra no significa", "tono": "fuera", "texto": f"El {pct(tasa, 2)} no es un porcentaje de rechazo de servicios. Solo {entero(eps_sin)} de esas {entero(fuera)} personas acudieron a su EPS y no fueron atendidas. Las demás declararon otra acción principal o ninguna."},
        {"tipo": "columnas", "bloques": [
            barras("b_acciones", "Qué declararon quienes están fuera de la ruta", "Personas", "Acción principal declarada. La pregunta no permite saber si además hubo otras acciones.",
                   [n for _, n in nombres_accion] + ["EPS sin atención"], [acciones[k] for k, _ in nombres_accion] + [eps_sin], "personas", "fuera"),
            {"tipo": "lista", "titulo": "Por qué hay que leerla con cuidado", "items": [
                {"rotulo": "Una sola respuesta", "texto": "La pregunta recoge la opción principal. Tampoco confirma que la consulta con médico particular se haya concretado."},
                {"rotulo": "Sin gravedad ni motivos", "texto": "El censo no registra gravedad, tiempo de espera, distancia ni el motivo de la decisión."},
                {"rotulo": "Un grupo menos frecuente", "texto": f"Una de cada cinco personas está fuera de la ruta. Por eso, sin modelo, la precisión promedio ya da {coma(prevalencia['ap_prueba'])}: esa es la referencia."}]}]},
    ]}

    marco = {"titulo": "Conceptos para leer las cifras", "entrada": "Las ideas y normas que sostienen la lectura de los datos. Los números entre corchetes remiten a las referencias de Conclusiones.", "bloques": [
        {"tipo": "parrafos", "titulo": "1. El censo como fuente", "parrafos": [
            "El CNPV 2018 es una operación censal del DANE, no una muestra aleatoria de personas enfermas [1]. Por eso las cifras describen los registros observados: no se aplican factores de expansión ni se corrigen posibles omisiones o errores de declaración.",
            "La pregunta de salud se refiere a un problema en los 30 días previos que no requirió hospitalización [2]. El tratamiento principal y la respuesta sobre la atención recibida se registran en campos separados [3][4]."]},
        {"tipo": "parrafos", "titulo": "2. Qué significa acceso", "parrafos": [
            "La literatura trata el acceso como un concepto con varias dimensiones. Aday y Andersen distinguen entre indicadores de proceso, ligados al sistema y a la población, e indicadores de resultado, como la utilización y la satisfacción [5]. Levesque, Harris y Russell describen cinco dimensiones de la accesibilidad y cinco capacidades de las personas: percibir, buscar, llegar, pagar y participar en la atención [6].",
            "El censo solo observa una parte de ese recorrido: la acción principal declarada. Por eso el proyecto habla de una ruta formal definida por una regla, no de una medida completa de acceso. No mide afiliación, oportunidad de la atención, calidad percibida ni barreras."]},
        {"tipo": "parrafos", "titulo": "3. El sistema de salud colombiano", "parrafos": [
            "La Ley 100 de 1993 creó el sistema de seguridad social integral y asignó a las EPS la afiliación y la tarea de organizar y garantizar la prestación del plan de salud a sus afiliados [7]. La Ley 1751 de 2015 regula la salud como derecho fundamental [8].",
            "Ese marco explica por qué acudir a la EPS es el primer componente de la ruta formal. El censo no permite evaluar cómo funcionó esa garantía en cada caso."]},
        {"tipo": "parrafos", "titulo": "4. Dificultad funcional", "parrafos": [
            "La variable del censo pregunta si existe alguna dificultad para la vida diaria [9]. Aquí se interpreta como dificultad funcional declarada, no como diagnóstico médico ni registro administrativo de discapacidad."]},
        {"tipo": "parrafos", "titulo": "5. Asociación, no causa", "parrafos": [
            "La V de Cramér resume la intensidad de la asociación en una tabla [10]. La estandarización directa por edad aplica los porcentajes de cada grupo a una misma estructura de edades. Ambas son herramientas descriptivas.",
            "No se interpretan pruebas de hipótesis ni valores p: los microdatos no son una muestra aleatoria y la respuesta se construye con una regla. Además, el censo es transversal y no permite ordenar en el tiempo cada variable frente al episodio de salud."]},
        {"tipo": "parrafos", "titulo": "6. Evaluar un modelo cuando un grupo es menos frecuente", "parrafos": [
            "Con grupos desiguales, la curva ROC puede dar una impresión engañosa y la curva de precisión y sensibilidad informa mejor [11]. Por eso la métrica principal del proyecto es la precisión promedio (AP), comparada con la prevalencia.",
            "El boosting de gradiente ajusta árboles en secuencia, cada uno sobre los errores que dejan los anteriores [12]. Los modelos de boosting pueden distorsionar las probabilidades, así que también se revisa la calibración [13]."]},
    ]}

    usos = [
        ("P_ENFERMO", "Problema de salud en los últimos 30 días, sin hospitalización", "Define a las personas estudiadas"),
        ("P_QUEHIZO_PPAL", "Tratamiento principal declarado", "Construye la respuesta"),
        ("PA_LO_ATENDIERON", "Si fue atendido en su entidad", "Construye la respuesta"),
        ("PA1_CALIDAD_SERV", "Calidad del servicio recibido", "Excluida: es posterior a la atención"),
        ("P_TRABAJO, PA_ASISTENCIA", "Actividad reciente y asistencia escolar", "Excluidas del modelo: ambigüedad temporal"),
        ("COD_ENCUESTAS, U_VIVIENDA, P_NROHOG, P_NRO_PER", "Claves de unión", "Control de duplicados, no entran al modelo"),
    ]
    tratamiento = [
        ("Códigos de no respuesta", "«No informa» y los códigos especiales de recuento se convierten en faltantes siempre de la misma manera."),
        ("Variables numéricas", "Se imputa la mediana aprendida solo en entrenamiento."),
        ("Variables categóricas", "Se usa una categoría explícita de ausencia y una codificación adecuada a cada familia de modelo."),
        ("Dentro de cada partición", "La codificación, la imputación y el escalado se ajustan dentro del pipeline, para no filtrar información de validación o prueba."),
        ("Preguntas que no aplican", "Los vacíos por edad no se leen como rechazo de respuesta ni se rellenan con una categoría inventada."),
    ]
    faltantes = calidad[:12]
    univariado = {"titulo": "Cómo es la población estudiada", "entrada": f"Cada variable por separado: qué se usó, qué información falta y cómo se distribuyen las {entero(cohorte)} personas.", "bloques": [
        {"tipo": "pestanas", "id": "sub_univariado", "pestanas": [
            {"titulo": "Preparación de variables", "bloques": [
                {"tipo": "parrafos", "titulo": "Diccionario de variables", "parrafos": [
                    "La unidad de análisis es la persona. Hogar y vivienda se unen con claves exigidas y conservan una fila por persona: las " + entero(cohorte) + " personas enlazaron con su hogar y su vivienda, sin claves duplicadas.",
                    "Los códigos son categorías aunque se lean como números: municipio, sexo y materiales son códigos nominales."]},
                {"tipo": "tabla", "titulo": "Variables que no entran como predictores", "meta": "Se excluyen para que el modelo no lea la respuesta directamente", "columnas": ["Variable", "Contenido", "Uso"], "texto_cols": 3,
                 "filas": [list(u) for u in usos]},
                {"tipo": "tabla", "titulo": "Variables construidas", "columnas": ["Variable", "Regla"], "texto_cols": 2, "filas": [
                    ["ACCESO_FORMAL_SALUD", "1 si acudió a su entidad y fue atendido, o a médico particular. 0 si acudió a su entidad y no fue atendido, o eligió otra opción."],
                    ["SIN_ACCESO", "Codificación inversa: 1 equivale a estar fuera de la ruta formal."],
                    ["PERS_POR_CUARTO", "Personas del hogar entre número de cuartos."],
                    ["HOGAR_OTROS_ENFERMOS", "Otras personas del hogar con problema de salud."],
                    ["SECCION_PCT_ENFERMOS", "Proporción que lo declaró en la sección censal, sin contar el hogar propio."]]},
                {"tipo": "tabla", "titulo": "Las 28 variables del modelo", "meta": "Diez de persona, cinco de hogar, once de vivienda y dos de contexto", "columnas": ["Código", "Contenido", "Nivel", "Tratamiento"], "texto_cols": 4,
                 "filas": [[f["variable"], f["descripcion"], f["nivel"], f["escala"]] for f in dic]}]},
            {"titulo": "Faltantes", "bloques": [
                {"tipo": "parrafos", "titulo": "Qué información falta", "parrafos": [
                    "Se suman los valores vacíos y los códigos de «no informa» o «no aplica». Antes se comprobó la regla de la respuesta, la unicidad de las claves y el enlace entre tablas.",
                    f"Estado civil ({pct(float(calidad[0]['pct']))}), educación ({pct(float(calidad[1]['pct']))}) y alfabetismo ({pct(float(calidad[2]['pct']))}) concentran la ausencia. Parte de esos vacíos coincide con edades para las que el cuestionario no aplica."]},
                barras("b_faltantes", "Variables con mayor ausencia", "Porcentaje de las personas estudiadas", "Combina vacíos y códigos especiales. Una ausencia pequeña no garantiza ausencia de sesgo.",
                       [f["descripcion"] for f in faltantes], [round(float(f["pct"]), 2) for f in faltantes], "%", "neutro")]},
            {"titulo": "Distribuciones", "bloques": [
                {"tipo": "columnas", "bloques": [
                    distribucion("b_edad", "Grupo de edad", leer(t, "edad"), lambda f: f["grupo_edad"], cohorte),
                    {"tipo": "pila", "bloques": [
                        distribucion("b_dificultad", "Dificultad funcional", leer(t, "dificultad"), lambda f: f["dificultad"], cohorte),
                        distribucion("b_sexo", "Sexo", leer(t, "sexo"), lambda f: f["sexo"], cohorte),
                        distribucion("b_zona", "Clase de área", leer(t, "clase_area"), lambda f: f["clase_area"], cohorte),
                        distribucion("b_estrato", "Estrato", leer(t, "estrato"), estrato, cohorte)]}]}]},
            {"titulo": "Tratamiento de faltantes", "bloques": [
                {"tipo": "lista", "titulo": "Cómo se trató la ausencia", "items": [{"rotulo": a, "texto": b} for a, b in tratamiento]}]},
        ]},
    ]}

    ajuste = [
        {"tipo": "parrafos", "titulo": "Por qué ajustar por edad", "parrafos": [
            "Quienes declaran dificultad funcional suelen tener más edad, y la edad también se relaciona con la ruta declarada. Para separar ese efecto, los porcentajes de cada grupo se aplican a una misma estructura de edades: la de todas las personas estudiadas."]},
        {"tipo": "fichas", "items": [
            {"etiqueta": "Diferencia sin ajustar", "valor": "7,30 puntos", "nota": "Entre personas con y sin dificultad funcional"},
            {"etiqueta": "Diferencia ajustada por edad", "valor": "4,25 puntos", "nota": "Con la misma estructura de edades", "tono": "dentro"},
            {"etiqueta": "60 años o más", "valor": "46,17 %", "nota": "De quienes declararon dificultad, frente a 18,00 %"}]},
        {"tipo": "parrafos", "titulo": "Cómo leerlo", "parrafos": [
            "La edad explica parte de la diferencia. Los 4,25 puntos restantes no deben interpretarse como efecto causal de la dificultad funcional, porque pueden intervenir otros factores no controlados."]},
    ]

    filas_modelos = [[m["modelo"], coma(m["ap_cv"]) if m["ap_cv"] else "—", coma(m["ap_validacion"]), coma(m["ap_prueba"]), coma(m["roc_auc_prueba"]),
                      coma(m["brier_prueba"]), coma(m["f1_prueba"]), coma(m["precision_prueba"]), coma(m["recall_prueba"])] for m in modelos]
    nombres_ic = [("selected_ap", "Precisión promedio (AP)"), ("selected_roc_auc", "ROC-AUC"), ("selected_brier", "Brier"),
                  ("selected_f1", "F1"), ("selected_precision", "Precisión"), ("selected_recall", "Sensibilidad")]
    creacion = {"titulo": "Cómo se construyó el modelo", "entrada": "Del dato a la evaluación: qué entra, cómo se separan los datos y cómo se elige. Las cifras son de viviendas reservadas del mismo censo.", "bloques": [
        {"tipo": "etapas", "titulo": "Etapas del modelo", "horizontal": True, "items": [
            {"titulo": "Variables", "texto": "28 entradas de persona, hogar, vivienda y contexto, sin los campos que revelan la respuesta."},
            {"titulo": "Separación", "texto": "Entrenamiento, validación y prueba, sin repartir una misma vivienda entre particiones."},
            {"titulo": "Preparación", "texto": "Imputación y codificación dentro de cada partición del pipeline."},
            {"titulo": "Elección", "texto": "Modelo y umbral se eligen en validación; la prueba se reserva para evaluarlos."}]},
        {"tipo": "columnas", "bloques": [
            {"tipo": "tabla", "titulo": "Separación por vivienda", "meta": "Cada partición conserva la misma proporción fuera de la ruta", "columnas": ["Partición", "Personas", "Viviendas", "Prevalencia"], "texto_cols": 1,
             "filas": [[p["particion"], entero(p["n"]), entero(p["viviendas"]), pct(float(p["porcentaje_sin_formal"]), 2)] for p in part],
             "nota": "La búsqueda de parámetros usó validación cruzada de tres particiones, agrupada por vivienda. No se usó sobremuestreo sintético."},
            {"tipo": "tabla", "titulo": "Hiperparámetros elegidos", "meta": "Boosting de histogramas", "columnas": ["Parámetro", "Valor"], "texto_cols": 1,
             "filas": [[f["parametro"], coma(f["valor"], 2) if "." in f["valor"] else f["valor"]] for f in leer(t, "hiperparametros")],
             "nota": f"Umbral elegido en validación con la métrica F1: {coma(elegido['umbral'], 4)}."}]},
        {"tipo": "tabla", "titulo": "Comparación de modelos", "meta": "Evaluación para detectar a quienes están fuera de la ruta formal",
         "columnas": ["Modelo", "AP validación cruzada", "AP validación", "AP prueba", "ROC-AUC", "Brier", "F1", "Precisión", "Sensibilidad"], "texto_cols": 1, "filas": filas_modelos, "destacar": 3,
         "nota": "AP es la precisión promedio, la métrica principal. La prevalencia es la referencia: predecir siempre la proporción de personas fuera de la ruta."},
        {"tipo": "columnas", "bloques": [
            {"tipo": "tabla", "titulo": "Incertidumbre en la prueba", "meta": "Intervalo de 95 % por bootstrap pareado", "columnas": ["Métrica", "Inferior", "Superior"], "texto_cols": 1,
             "filas": [[e, coma(inc[k]["inferior"]), coma(inc[k]["superior"])] for k, e in nombres_ic],
             "nota": f"La ventaja en AP frente al segundo mejor modelo va de {coma(inc['delta_ap_vs_competitor']['inferior'])} a {coma(inc['delta_ap_vs_competitor']['superior'])}."},
            {"tipo": "tabla", "titulo": "Efecto de las dos variables de contexto", "meta": "De 26 a 28 variables", "columnas": ["Medida", "26 variables", "28 variables"], "texto_cols": 1,
             "filas": [[f["medida"].replace("AP en CV,", "AP en validación cruzada,"), coma(f["modelo_26"]), coma(f["modelo_28"])] for f in ctx],
             "nota": f"Mejora de la AP en validación: {coma(dec['delta_ap'])}, con intervalo de {coma(dec['inferior'])} a {coma(dec['superior'])}."}]},
        {"tipo": "destacado", "rotulo": "Alcance de la evaluación", "texto": "La prueba usa viviendas distintas, pero del mismo censo y los mismos municipios. No hay validación en otro año, en otro territorio ni clínica."},
    ]}

    limites = [
        ("Quiénes están", f"Solo personas del Atlántico con un problema de salud en los 30 días previos, sin hospitalización y con respuesta clasificable. El {pct(tasa, 2)} no es un porcentaje actual de todo el departamento."),
        ("Qué mide la etiqueta", "Registra la acción principal, no todas las acciones. «Fuera de la ruta» agrupa situaciones muy distintas."),
        ("Asociación y tiempo", "El censo es una foto de un momento. Las diferencias por vivienda, educación o municipio no prueban causas."),
        ("Generalización", "La prueba se hizo en viviendas distintas, pero dentro del mismo censo. No hay validación en otro año, en otro territorio ni clínica."),
        ("Equidad", "El modelo encuentra menos casos entre personas con dificultad funcional y muy pocos entre personas de 60 años o más."),
        ("Calidad censal", "Son respuestas observadas. No se corrigen omisiones censales, errores de declaración ni sesgos de no respuesta."),
    ]
    referencias = [
        {"texto": "DANE. Censo Nacional de Población y Vivienda 2018: ficha y catálogo.", "url": URL_DANE},
        {"texto": "DANE. P_ENFERMO: problema de salud en los últimos 30 días sin hospitalización.", "url": "https://microdatos.dane.gov.co/index.php/catalog/643/variable/F11/V581?name=P_ENFERMO"},
        {"texto": "DANE. P_QUEHIZO_PPAL: tratamiento principal declarado.", "url": "https://microdatos.dane.gov.co/index.php/catalog/643/variable/F11/V582?name=P_QUEHIZO_PPAL"},
        {"texto": "DANE. PA_LO_ATENDIERON: respuesta sobre atención en la entidad.", "url": "https://microdatos.dane.gov.co/index.php/catalog/643/variable/F11/V583?name=PA_LO_ATENDIERON"},
        {"texto": "Aday, L. A., y Andersen, R. (1974). A framework for the study of access to medical care. Health Services Research, 9(3), 208–220.", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1071804/"},
        {"texto": "Levesque, J.-F., Harris, M. F., y Russell, G. (2013). Patient-centred access to health care: conceptualising access at the interface of health systems and populations. International Journal for Equity in Health, 12, 18.", "url": "https://doi.org/10.1186/1475-9276-12-18"},
        {"texto": "Congreso de Colombia. Ley 100 de 1993, por la cual se crea el sistema de seguridad social integral. Diario Oficial 41.148."},
        {"texto": "Congreso de Colombia. Ley 1751 de 2015, por medio de la cual se regula el derecho fundamental a la salud.", "url": "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=60733"},
        {"texto": "DANE. CONDICION_FISICA: dificultad para actividades diarias.", "url": "https://microdatos.dane.gov.co/index.php/catalog/643/variable/F11/V585?name=CONDICION_FISICA"},
        {"texto": "Cramér, H. (1946). Mathematical Methods of Statistics. Princeton University Press."},
        {"texto": "Saito, T., y Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLoS ONE, 10(3), e0118432.", "url": "https://doi.org/10.1371/journal.pone.0118432"},
        {"texto": "Friedman, J. H. (2001). Greedy function approximation: a gradient boosting machine. Annals of Statistics, 29(5), 1189–1232.", "url": "https://doi.org/10.1214/aos/1013203451"},
        {"texto": "Niculescu-Mizil, A., y Caruana, R. (2005). Predicting good probabilities with supervised learning. Proceedings of ICML 2005, 625–632.", "url": "https://doi.org/10.1145/1102351.1102430"},
    ]
    preguntas = [
        (f"¿El {pct(tasa, 2)} significa que se negó la atención?", f"No. Es una clasificación de la acción principal declarada. Solo {entero(eps_sin)} de esas {entero(fuera)} personas acudieron a su EPS y no fueron atendidas; las demás declararon otra acción o ninguna."),
        ("¿Describe el Atlántico de hoy?", "No. Son respuestas del censo de 2018 de quienes declararon un problema de salud reciente. No se extrapolan a otros años ni a toda la población."),
        (f"¿Por qué sin filtros aparece ≈ {pct(tasa_cubo)} y no {pct(tasa, 2)}?", f"La vista con filtros suma solo los grupos publicados, con recuentos redondeados. El {pct(tasa, 2)} es la cifra exacta de todas las personas estudiadas."),
        ("¿Por qué algunos porcentajes se ocultan?", "Para proteger grupos pequeños y evitar lecturas engañosas. Un porcentaje se oculta si su base aproximada es menor de 200 personas o si la cobertura de la selección es menor de 80 %."),
        ("¿Por qué no hay valores p?", "Los microdatos no son una muestra aleatoria de una población futura y la respuesta se construye con una regla. Por eso se muestran porcentajes con su base y la V de Cramér como resumen descriptivo."),
        ("¿El modelo dice qué hará una persona?", "No. Ordena perfiles dentro del mismo censo, con discriminación moderada, y no debe usarse para decidir sobre personas. Esta aplicación no calcula predicciones individuales."),
    ]
    glosario = [
        ("Ruta formal", "Acudir a la EPS y ser atendido, o consultar a un médico particular, como acción principal declarada."),
        ("Fuera de la ruta formal", "Acudir a la EPS sin ser atendido, otra acción principal o ninguna. El informe la codifica como SIN_ACCESO = 1."),
        ("Personas estudiadas", f"Las {entero(cohorte)} personas de la cohorte analítica: declararon un problema de salud sin hospitalización y tienen respuesta clasificable."),
        ("Dificultad funcional", "Dificultad para actividades diarias declarada en el censo. No es un diagnóstico."),
        ("Base aproximada", "Número de personas detrás de un porcentaje, con recuentos redondeados para proteger grupos pequeños."),
        ("Grupo publicado", "Combinación de municipio, sexo, edad, zona y dificultad con suficientes personas para mostrarse."),
        ("Cobertura", "Parte de las personas de una selección que está en grupos publicados."),
        ("Prevalencia", "Proporción de personas fuera de la ruta formal. Es lo que se obtiene sin modelo."),
        ("Precisión promedio (AP)", "Resume qué tan arriba quedan las personas fuera de la ruta al ordenar por puntuación. Va de la prevalencia a 1."),
        ("Sensibilidad", "De quienes están fuera de la ruta, qué parte marca el modelo."),
        ("Precisión", "De quienes marca el modelo, qué parte está fuera de la ruta."),
        ("Umbral", "Puntuación a partir de la cual el modelo marca a una persona."),
        ("V de Cramér", "Resume de 0 a 1 la intensidad de la asociación en una tabla. No mide causa."),
    ]
    conclusiones = {"titulo": "Qué permiten concluir los datos", "entrada": "Hallazgos, límites, términos y referencias del proyecto.", "bloques": [
        {"tipo": "lista", "titulo": "Hallazgos principales", "columnas": 2, "items": [
            {"rotulo": "Una clasificación, no una negativa", "texto": f"El {pct(tasa, 2)} queda fuera de la ruta formal, sobre todo por el tratamiento principal declarado. La mayoría declaró otra acción, no una falta de atención de la EPS."},
            {"rotulo": "La edad y el territorio pesan más", "texto": "Las asociaciones son modestas: V de Cramér de 0,163 con la edad, 0,085 con el municipio y menos de 0,07 con las demás variables comparadas."},
            {"rotulo": "La dificultad funcional sorprende", "texto": "Quienes la declararon quedan menos fuera de la ruta. La diferencia baja de 7,30 a 4,25 puntos al ajustar por edad y no indica que la dificultad proteja frente a barreras."},
            {"rotulo": "Un modelo útil para explorar", "texto": f"El boosting de histogramas alcanzó una precisión promedio de {coma(elegido['ap_prueba'])}, frente a {coma(prevalencia['ap_prueba'])} sin modelo. Ordena mejor que el azar, pero deja errores importantes."},
            {"rotulo": "El contexto ayudó al modelo", "texto": "Las dos variables sobre otras personas con problemas de salud mejoraron el ordenamiento. Sugieren que parte del grupo podría reflejar problemas más leves o diferencias de declaración, aunque el censo no permite comprobarlo."},
            {"rotulo": "La equidad sigue pendiente", "texto": "Ajustar por edad reduce, pero no borra, la diferencia de sensibilidad entre personas con y sin dificultad funcional."}]},
        {"tipo": "permite", "si_titulo": "Lo que los datos permiten decir", "si": [
            "Qué acción principal declararon las personas estudiadas en 2018.",
            "En qué grupos y municipios el porcentaje fuera de la ruta fue mayor o menor.",
            "Que un modelo con datos del censo ordena mejor que el azar dentro del mismo censo."],
         "no_titulo": "Lo que no permiten decir", "no": [
            "Que a esas personas se les negó la atención.",
            "Por qué ocurren las diferencias entre grupos o territorios.",
            "Cómo está hoy el Atlántico, ni qué pasa con quienes no declararon un problema de salud.",
            "Qué hará una persona concreta, ni a quién atender primero."]},
        {"tipo": "lista", "titulo": "Límites que acompañan cada gráfica", "columnas": 2, "items": [{"rotulo": a, "texto": b} for a, b in limites]},
        {"tipo": "glosario", "titulo": "Términos usados", "items": [{"termino": a, "definicion": b} for a, b in glosario]},
        {"tipo": "preguntas", "titulo": "Preguntas frecuentes", "items": [{"pregunta": a, "respuesta": b} for a, b in preguntas]},
        {"tipo": "lista", "titulo": "Protección de grupos pequeños", "columnas": 2, "items": [
            {"rotulo": "Solo datos agregados", "texto": "La aplicación no contiene ningún registro individual ni el modelo serializado."},
            {"rotulo": "Grupos filtrables", "texto": "Se publican con al menos 30 personas y 5 dentro y fuera de la ruta; los recuentos se redondean a 5."},
            {"rotulo": "Panorama por grupo", "texto": "Se publica con al menos 100 personas y 10 dentro y fuera de la ruta; los recuentos se redondean a 10."},
            {"rotulo": "Porcentajes ocultos", "texto": "Un porcentaje se oculta si la base aproximada es menor de 200 o la cobertura de la selección es menor de 80 %."}]},
        {"tipo": "referencias", "titulo": "Referencias", "items": referencias},
        {"tipo": "enlaces", "titulo": "Otros materiales", "items": [
            {"texto": "Informe completo en Bookdown", "url": URL_BOOKDOWN},
            {"texto": "Tablero en Dash", "url": URL_DASH},
            {"texto": "Aplicación en Shiny", "url": URL_SHINY},
            {"texto": "Notebook del modelo", "url": URL_NOTEBOOK},
            {"texto": "Microdatos CNPV 2018 del DANE", "url": URL_DANE}]},
        {"tipo": "pie", "texto": "Alejandro Carvajal y Mateo Chang"},
    ]}

    return {
        "nombre": NOMBRE,
        "secciones": [{"id": a, "etiqueta": b} for a, b in SECCIONES],
        "paginas": {"panorama": panorama, "objetivos": objetivos, "problema": problema, "marco": marco,
                    "univariado": univariado, "creacion": creacion, "conclusiones": conclusiones},
        "modelo": pagina_modelo(modelo),
        "explorar": {
            "titulo": "Comparar grupos",
            "entrada": "Elige un grupo de personas y mira qué proporción quedó fuera de la ruta formal: su acción principal no fue acudir a la EPS con atención ni a un médico particular.",
            "pestanas": ["Explorar grupos", "Comparar variables", "Ajuste por edad"],
            "ayuda": "Cada filtro reduce el grupo. La frase, la cobertura y las gráficas se recalculan con quienes cumplen todos los filtros.",
            "total_nota": f"Sin filtros da ≈ {pct(tasa_cubo)} y no {pct(tasa, 2)} porque aquí solo se suman los grupos publicados.",
            "mapa_nota": "Se suman solo los grupos publicados, por eso puede diferir de la cifra del mapa.",
            "por_que_titulo": "Por qué algunos resultados no aparecen",
            "por_que": [
                "Grupos pequeños: una combinación se publica solo si tiene al menos 30 personas y 5 dentro y fuera de la ruta, para que nadie pueda identificarse.",
                "Porcentaje oculto: si la base aproximada es menor de 200 personas, o los grupos publicados cubren menos del 80 % de la selección, se muestra el tamaño del grupo pero no el porcentaje.",
                "Cifras aproximadas: los recuentos se redondean a 5, así que los totales filtrados no coinciden exactamente con el informe."],
            "graficas": {
                "municipios": {"titulo": "Por municipio", "meta": "Solo municipios con cobertura y tamaño suficientes"},
                "edad": {"titulo": "Por edad y dificultad funcional", "meta": "Porcentaje fuera de la ruta formal dentro de cada grupo", "nota": "Los grupos no publicados no entran en la línea."},
                "composicion": {"titulo": "Por sexo y zona", "meta": "Porcentaje fuera de la ruta formal dentro de cada grupo"},
            },
            "descarga_nota": "El archivo contiene solo grupos publicados y recuentos redondeados.",
            "comparar_entrada": "Porcentaje fuera de la ruta formal en cada categoría de una variable. La V de Cramér va de 0 a 1 y resume la intensidad de la asociación; un valor pequeño puede coexistir con diferencias visibles en grupos concretos.",
            "comparar_nota": "Comparaciones descriptivas y sin ajuste. No se usan pruebas de hipótesis ni valores p porque el censo no es una muestra aleatoria. Recuentos redondeados a 10.",
            "variables": comparaciones(t),
            "ajuste": ajuste,
        },
    }


def main() -> None:
    raiz = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tablas", type=Path, required=True)
    parser.add_argument("--destino", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    relato = json.loads((raiz / "assets" / "relato_datos.json").read_text(encoding="utf-8"))
    modelo = json.loads((raiz / "data" / "modelo.json").read_text(encoding="utf-8"))
    eda = json.loads((raiz / "data" / "eda.json").read_text(encoding="utf-8"))
    contenido = construir(args.tablas, relato, modelo, eda)
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    for carpeta in args.destino:
        (carpeta / "contenido.json").write_text(texto, encoding="utf-8")
    print(f"contenido.json: {len(texto):,} bytes")


if __name__ == "__main__":
    main()
