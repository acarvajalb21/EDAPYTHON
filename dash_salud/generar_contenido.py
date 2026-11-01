"""Genera el contenido de las secciones, común a Dash y Shiny.

Usa las tablas agregadas del Bookdown; no necesita microdatos. Los grupos pasan por la
regla del panorama municipal: al menos 100 personas y 10 en cada clase, redondeo a 10.

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
         "Es la asociación más alta de las comparadas. Los grupos de edad avanzada tienen tamaños distintos de los jóvenes, así que cada tasa debe leerse con su base."),
        ("municipio", "Municipio", leer(t, "municipio"), lambda f: f["municipio"], True,
         "El municipio agrupa contextos sociales y de oferta distintos. Es un descriptor potente, no una explicación causal, y las diferencias no están ajustadas por edad. Piojó no aparece: no alcanza el mínimo de publicación."),
        ("dificultad", "Dificultad funcional", leer(t, "dificultad"), lambda f: f["dificultad"], False,
         "El contraste va en dirección contraria a la lectura intuitiva. La composición por edad contribuye a esa diferencia: por eso se revisa en «Ajuste por edad»."),
        ("estrato", "Estrato", leer(t, "estrato"), estrato, False,
         "Entre los estratos 1 a 3 la tasa es parecida y baja de forma visible en el 4. No se presume un cambio uniforme por nivel."),
        ("sexo", "Sexo", leer(t, "sexo"), lambda f: f["sexo"], False,
         "La diferencia no se estandarizó por edad ni por territorio."),
        ("zona", "Clase de área", leer(t, "clase_area"), lambda f: f["clase_area"], False,
         "La proporción es mayor en el área rural dispersa que en las cabeceras. Se refiere solo a quienes declararon el problema de salud; no mide cobertura territorial."),
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
    return barras(id_, titulo, "Porcentaje de la cohorte", nota, [g["categoria"] for g in grupos],
                  [round(100 * g["n"] / total, 2) for g in grupos], "%", "neutro")


def construir(t: Path, relato: dict) -> dict:
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
    nombres_accion = [("autorreceta", "Se autorrecetó"), ("remedios", "Remedios caseros"), ("nada", "No hizo nada"),
                      ("boticario", "Boticario o droguista"), ("otras", "Otras alternativas")]

    panorama = {"bloques": [
        {"tipo": "parrafos", "titulo": "Una respuesta del censo no cuenta toda la historia", "parrafos": [
            "Ante un problema de salud, una persona pudo acudir a su entidad de seguridad social, consultar a un médico particular, buscar otra alternativa o no hacer nada. El CNPV registra cuál fue su tratamiento principal.",
            "Comparar esas respuestas ayuda a detectar patrones que merecen estudiarse mejor. No permite reconstruir toda la trayectoria de atención."]},
        {"tipo": "fichas", "items": [
            {"etiqueta": "Cohorte analítica", "valor": entero(cohorte), "nota": "Personas con respuesta clasificable", "tono": "dentro"},
            {"etiqueta": "Fuera de la ruta formal", "valor": pct(tasa, 2), "nota": f"{entero(fuera)} personas. No equivale a atención negada", "tono": "fuera"},
            {"etiqueta": "Acudieron a su EPS sin atención", "valor": entero(eps_sin), "nota": f"{pct(100 * eps_sin / cohorte, 2)} de la cohorte"}]},
        {"tipo": "etapas", "titulo": "Estructura del proyecto", "items": [
            {"titulo": "Datos y calidad", "texto": "Unión de personas, hogares y viviendas, definición de la cohorte y revisión de faltantes."},
            {"titulo": "Análisis exploratorio", "texto": "Distribuciones y comparaciones por grupo, con el denominador visible."},
            {"titulo": "Tableros interactivos", "texto": "Dash y Shiny con filtros, publicando solo agregados protegidos."},
            {"titulo": "Modelo predictivo", "texto": "Comparación de modelos, umbral validado y revisión de errores por grupo."},
            {"titulo": "Informe reproducible", "texto": "Bookdown y notebook con las decisiones y las cifras exactas."}]},
        {"tipo": "columnas", "bloques": [
            {"tipo": "parrafos", "titulo": "Origen de los datos", "parrafos": [
                "Censo Nacional de Población y Vivienda 2018 del DANE. Se usan los microdatos anonimizados de personas, hogares y viviendas del Atlántico, y el Marco Geoestadístico Nacional para ubicar cada vivienda en su sección censal.",
                "Los microdatos no se publican con este proyecto: las aplicaciones solo leen agregados."],
             "enlace": {"texto": "Ver el catálogo del DANE", "url": URL_DANE}},
            {"tipo": "lista", "titulo": "Alcance", "items": [
                {"rotulo": "Unidad", "texto": "Una persona que declaró un problema de salud en los 30 días previos, sin hospitalización."},
                {"rotulo": "Periodo", "texto": "Respuestas del censo de 2018. No describen necesariamente la situación actual."},
                {"rotulo": "Lectura", "texto": "Las asociaciones no indican causas."}]}]},
        {"tipo": "pie", "texto": "Fuente: microdatos anonimizados del CNPV 2018, DANE. Nombres municipales: DIVIPOLA del DANE. Los cuadros del relato representan grupos, no personas reales."},
    ]}

    objetivos = {"titulo": "Lo que el proyecto *busca* responder", "entrada": "La pregunta, los objetivos y las etapas del trabajo.", "bloques": [
        {"tipo": "destacado", "rotulo": "Pregunta de investigación", "texto": "¿Cómo varía el acceso a atención formal entre las personas censadas en el Atlántico que reportaron un problema de salud, según sus características funcionales, sociodemográficas, habitacionales y territoriales?"},
        {"tipo": "destacado", "rotulo": "Objetivo general", "texto": "Describir el acceso a atención formal en esta población y su distribución según características funcionales, sociodemográficas, habitacionales y territoriales observadas en el CNPV 2018, y evaluar hasta qué punto esas variables permiten ordenar la clase menos frecuente."},
        {"tipo": "columnas", "bloques": [
            {"tipo": "lista", "titulo": "Objetivos específicos", "items": [
                {"rotulo": "OE 1 · Definir la medida", "texto": "Construir y documentar una medida binaria de acceso a partir del tratamiento principal y la atención recibida, y cuantificar los casos que no se pueden clasificar."},
                {"rotulo": "OE 2 · Revisar los datos", "texto": "Describir la distribución de la respuesta, la calidad de los datos y las características de las personas y los hogares incluidos."},
                {"rotulo": "OE 3 · Comparar grupos", "texto": "Comparar el acceso entre grupos de dificultad funcional, sexo, edad, estrato, personas por cuarto, clase territorial y municipio, indicando el tamaño y el denominador de cada grupo."},
                {"rotulo": "OE 4 · Ajustar por edad", "texto": "Examinar cuánto cambia la diferencia por dificultad funcional al estandarizar las tasas por edad."},
                {"rotulo": "OE 5 · Evaluar un modelo", "texto": "Medir, con una prueba interna separada, cuánto mejora un modelo frente a predecir siempre la prevalencia del grupo."}]},
            {"tipo": "etapas", "titulo": "Etapas del proyecto", "items": [
                {"titulo": "EDA", "texto": "Regla de la respuesta, calidad de los datos y comparaciones por grupo."},
                {"titulo": "Tableros", "texto": "Filtros, cobertura visible y reglas de protección de grupos pequeños."},
                {"titulo": "Modelo", "texto": "Boosting de histogramas, umbral validado y límites de uso."}]}]},
    ]}

    problema = {"titulo": "Qué ruta se *declaró* ante un problema de salud", "entrada": "Una clasificación de la acción principal reportada en el censo de 2018.", "bloques": [
        {"tipo": "fichas", "items": [
            {"etiqueta": "Cohorte analítica", "valor": entero(cohorte), "nota": "Personas con respuesta clasificable"},
            {"etiqueta": "Dentro de la ruta formal", "valor": entero(dentro), "nota": f"{pct(float(r['porcentaje_con_formal']), 2)} de la cohorte", "tono": "dentro"},
            {"etiqueta": "Fuera de la ruta formal", "valor": entero(fuera), "nota": f"{pct(tasa, 2)} de la cohorte", "tono": "fuera"},
            {"etiqueta": "EPS sin atención", "valor": entero(eps_sin), "nota": f"{pct(100 * eps_sin / fuera, 1)} de la clase «fuera»"}]},
        {"tipo": "parrafos", "titulo": "Descripción del problema", "parrafos": [
            "Cuando una persona tiene un problema de salud puede acudir a su EPS, consultar a un médico particular, recetarse por su cuenta, usar remedios caseros, ir a un boticario o no hacer nada. El censo de 2018 registró cuál fue su tratamiento principal.",
            f"En el Atlántico, {entero(cohorte)} personas declararon un problema de salud reciente sin hospitalización y tienen una respuesta clasificable. De ellas, {entero(fuera)} quedan fuera de la ruta formal que define el proyecto: acudir a la EPS con atención o a un médico particular.",
            "El problema no es medir una negativa de atención. Es entender cómo varía esa ruta declarada entre grupos y territorios, y si las variables del censo permiten ordenar esos casos."]},
        {"tipo": "ruta", "titulo": "Las cuatro rutas registradas", "nota": "Son acciones principales reportadas. «Otra acción o ninguna» incluye farmacia y otras formas de atención; no equivale a ausencia de toda atención."},
        {"tipo": "destacado", "rotulo": "Lo que esta cifra no significa", "tono": "fuera", "texto": f"El {pct(tasa, 2)} no es una tasa de rechazo de servicios. Solo {entero(eps_sin)} de esas {entero(fuera)} personas acudieron a su EPS y no recibieron atención; las demás declararon otra acción principal o ninguna."},
        {"tipo": "columnas", "bloques": [
            barras("b_acciones", "Qué declaró la clase «fuera»", "Personas", "Acción principal declarada. La pregunta no permite saber si además hubo otras acciones.",
                   [n for _, n in nombres_accion] + ["EPS sin atención"], [acciones[k] for k, _ in nombres_accion] + [eps_sin], "personas", "fuera"),
            {"tipo": "lista", "titulo": "Por qué es difícil de leer", "items": [
                {"rotulo": "Una sola respuesta", "texto": "La pregunta recoge una opción principal. Tampoco confirma que la consulta con médico particular se haya concretado."},
                {"rotulo": "Sin gravedad ni motivos", "texto": "El censo no ofrece gravedad, tiempo de espera, distancia ni el motivo de la decisión."},
                {"rotulo": "Clase menos frecuente", "texto": f"Una de cada cinco personas está en esa clase. Predecir siempre la prevalencia da AP {coma(prevalencia['ap_prueba'])}: esa es la referencia del modelo."}]}]},
    ]}

    marco = {"titulo": "Los conceptos detrás de las *cifras*", "entrada": "Las ideas y normas que sostienen la lectura de los datos. Los números entre corchetes remiten a las referencias de Conclusiones.", "bloques": [
        {"tipo": "parrafos", "titulo": "1. El censo como fuente", "parrafos": [
            "El CNPV 2018 es una operación censal del DANE, no una muestra aleatoria de personas enfermas [1]. Por eso las cifras describen los registros observados: no se aplican factores de expansión ni se corrigen posibles omisiones o errores de declaración.",
            "La pregunta de salud se refiere a un problema en los 30 días previos que no requirió hospitalización [2]. El tratamiento principal y la respuesta sobre la atención recibida se registran en campos separados [3][4]."]},
        {"tipo": "parrafos", "titulo": "2. Qué significa acceso", "parrafos": [
            "La literatura trata el acceso como un concepto con varias dimensiones. Aday y Andersen distinguen entre indicadores de proceso, ligados al sistema y a la población, e indicadores de resultado, como la utilización y la satisfacción [5]. Levesque, Harris y Russell describen cinco dimensiones de la accesibilidad y cinco capacidades de las personas: percibir, buscar, llegar, pagar y participar en la atención [6].",
            "El censo solo observa una parte de ese recorrido: la acción principal declarada. Por eso el proyecto usa una definición operativa, no una medida completa de acceso. No mide afiliación, oportunidad de la atención, calidad percibida ni barreras causales."]},
        {"tipo": "parrafos", "titulo": "3. El sistema de salud colombiano", "parrafos": [
            "La Ley 100 de 1993 creó el sistema de seguridad social integral y asignó a las EPS la afiliación y la tarea de organizar y garantizar la prestación del plan de salud a sus afiliados [7]. La Ley 1751 de 2015 regula la salud como derecho fundamental [8].",
            "Ese marco explica por qué acudir a la EPS es el primer componente de la ruta formal. El censo no permite evaluar cómo funcionó esa garantía en cada caso."]},
        {"tipo": "parrafos", "titulo": "4. Dificultad funcional", "parrafos": [
            "La variable del censo pregunta si existe alguna dificultad para la vida diaria [9]. Aquí se interpreta como dificultad funcional declarada, no como diagnóstico médico ni registro administrativo de discapacidad."]},
        {"tipo": "parrafos", "titulo": "5. Asociación, no causa", "parrafos": [
            "La V de Cramér resume la intensidad de la asociación en una tabla [10]. La estandarización directa por edad aplica las tasas de cada grupo a una misma estructura de edades. Ambas son descriptivas.",
            "No se interpretan pruebas de hipótesis ni valores p: los microdatos no son una muestra aleatoria y la respuesta se construye con una regla analítica. Además, el censo es transversal y no permite ordenar en el tiempo cada variable frente al episodio de salud."]},
        {"tipo": "parrafos", "titulo": "6. Evaluar un modelo con una clase menos frecuente", "parrafos": [
            "Con clases desiguales, la curva ROC puede dar una impresión engañosa y la curva de precisión y sensibilidad informa mejor [11]. Por eso la métrica principal del proyecto es la Average Precision, comparada con la prevalencia.",
            "El boosting de gradiente ajusta árboles en secuencia, cada uno sobre los errores que dejan los anteriores [12]. Los modelos de boosting pueden distorsionar las probabilidades, así que también se revisa la calibración [13]."]},
    ]}

    usos = [
        ("P_ENFERMO", "Problema de salud en los últimos 30 días, sin hospitalización", "Define la cohorte"),
        ("P_QUEHIZO_PPAL", "Tratamiento principal declarado", "Construye la respuesta"),
        ("PA_LO_ATENDIERON", "Si fue atendido en su entidad", "Construye la respuesta"),
        ("PA1_CALIDAD_SERV", "Calidad del servicio recibido", "Excluida: es posterior a la atención"),
        ("P_TRABAJO, PA_ASISTENCIA", "Actividad reciente y asistencia escolar", "Excluidas del modelo: ambigüedad temporal"),
        ("COD_ENCUESTAS, U_VIVIENDA, P_NROHOG, P_NRO_PER", "Claves de unión", "Control de duplicados, no entran al modelo"),
    ]
    tratamiento = [
        ("Códigos de no respuesta", "«No informa» y los recuentos centinela se convierten en faltantes de manera determinista."),
        ("Variables numéricas", "Se imputa la mediana aprendida solo en entrenamiento."),
        ("Variables categóricas", "Se usa una categoría explícita de ausencia y una codificación adecuada a cada familia de modelo."),
        ("Dentro de cada pliegue", "La codificación, la imputación y el escalado se ajustan dentro del pipeline, para no filtrar información de validación o prueba."),
        ("Preguntas que no aplican", "Los vacíos por edad no se leen como rechazo de respuesta ni se rellenan con una categoría inventada."),
    ]
    faltantes = calidad[:12]
    univariado = {"titulo": "Cada variable, *por separado*", "entrada": "Qué se usó, qué falta y cómo se distribuye la cohorte de 136.034 personas.".replace("136.034", entero(cohorte)), "bloques": [
        {"tipo": "pestanas", "id": "sub_univariado", "pestanas": [
            {"titulo": "Preparación de variables", "bloques": [
                {"tipo": "parrafos", "titulo": "Diccionario de variables", "parrafos": [
                    "La unidad es la persona. Hogar y vivienda se unen con claves exigidas y conservan una fila por persona: las " + entero(cohorte) + " personas enlazaron con su hogar y su vivienda, sin claves duplicadas.",
                    "Los códigos son categorías aunque se lean como números: municipio, sexo y materiales son códigos nominales."]},
                {"tipo": "tabla", "titulo": "Variables que no entran como predictores", "meta": "Reducen la fuga de información", "columnas": ["Variable", "Contenido", "Uso"], "texto_cols": 3,
                 "filas": [list(u) for u in usos]},
                {"tipo": "tabla", "titulo": "Variables construidas", "columnas": ["Variable", "Regla"], "texto_cols": 2, "filas": [
                    ["ACCESO_FORMAL_SALUD", "1 si acudió a su entidad y fue atendido, o a médico particular. 0 si acudió a su entidad y no fue atendido, o eligió otra opción."],
                    ["SIN_ACCESO", "Codificación inversa para evaluar la clase menos frecuente."],
                    ["PERS_POR_CUARTO", "Personas del hogar entre número de cuartos."],
                    ["HOGAR_OTROS_ENFERMOS", "Otras personas del hogar con problema de salud."],
                    ["SECCION_PCT_ENFERMOS", "Proporción que lo declaró en la sección censal, sin contar el hogar propio."]]},
                {"tipo": "tabla", "titulo": "Las 28 variables del modelo", "meta": "Diez de persona, cinco de hogar, once de vivienda y dos de contexto", "columnas": ["Código", "Contenido", "Nivel", "Tratamiento"], "texto_cols": 4,
                 "filas": [[f["variable"], f["descripcion"], f["nivel"], f["escala"]] for f in dic]}]},
            {"titulo": "Faltantes", "bloques": [
                {"tipo": "parrafos", "titulo": "Identificación de faltantes", "parrafos": [
                    "Se suman los valores vacíos y los códigos de «no informa» o «no aplica». Antes se comprobó la regla de la respuesta, la unicidad de las claves y el enlace entre tablas.",
                    f"Estado civil ({pct(float(calidad[0]['pct']))}), educación ({pct(float(calidad[1]['pct']))}) y alfabetismo ({pct(float(calidad[2]['pct']))}) concentran la ausencia. Parte de esos vacíos coincide con edades para las que el cuestionario no aplica."]},
                barras("b_faltantes", "Variables con mayor ausencia", "Porcentaje de la cohorte", "Combina vacíos y códigos especiales. Una ausencia pequeña no garantiza ausencia de sesgo.",
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
        {"tipo": "parrafos", "titulo": "Estandarización directa por edad", "parrafos": [
            "Las tasas de cada grupo de dificultad en cada tramo de edad se aplican a una misma estructura de edades: la de toda la cohorte. Así se ve cuánto de la diferencia se debe a que los grupos tienen edades distintas."]},
        {"tipo": "fichas", "items": [
            {"etiqueta": "Diferencia cruda", "valor": "7,30 puntos", "nota": "Entre personas con y sin dificultad funcional"},
            {"etiqueta": "Diferencia estandarizada", "valor": "4,25 puntos", "nota": "Con la misma estructura de edades", "tono": "dentro"},
            {"etiqueta": "60 años o más", "valor": "46,17 %", "nota": "De quienes declararon dificultad, frente a 18,00 %"}]},
        {"tipo": "parrafos", "titulo": "Cómo leerlo", "parrafos": [
            "La composición por edad explica parte de la diferencia. Los 4,25 puntos restantes no deben interpretarse como efecto causal de la dificultad funcional, porque pueden intervenir otros factores no controlados."]},
    ]

    filas_modelos = [[m["modelo"], coma(m["ap_cv"]) if m["ap_cv"] else "—", coma(m["ap_validacion"]), coma(m["ap_prueba"]), coma(m["roc_auc_prueba"]),
                      coma(m["brier_prueba"]), coma(m["f1_prueba"]), coma(m["precision_prueba"]), coma(m["recall_prueba"])] for m in modelos]
    nombres_ic = [("selected_ap", "Average Precision"), ("selected_roc_auc", "ROC-AUC"), ("selected_brier", "Brier"),
                  ("selected_f1", "F1"), ("selected_precision", "Precisión"), ("selected_recall", "Sensibilidad")]
    creacion = {"titulo": "Cómo se construyó el *modelo*", "entrada": "Del dato a la evaluación: variables, separación, preprocesamiento y elección. Las cifras son de viviendas reservadas del mismo censo.", "bloques": [
        {"tipo": "etapas", "titulo": "Etapas del modelo", "items": [
            {"titulo": "Variables", "texto": "28 entradas de persona, hogar, vivienda y contexto, sin los campos que revelan la respuesta."},
            {"titulo": "Separación", "texto": "Entrenamiento, validación y prueba, sin repartir una misma vivienda entre particiones."},
            {"titulo": "Preprocesamiento", "texto": "Imputación y codificación dentro de cada pliegue del pipeline."},
            {"titulo": "Elección", "texto": "Modelo y umbral elegidos en validación; la prueba se reserva para evaluarlos."}]},
        {"tipo": "columnas", "bloques": [
            {"tipo": "tabla", "titulo": "Separación por vivienda", "meta": "Estratificada por la respuesta", "columnas": ["Partición", "Personas", "Viviendas", "Prevalencia"], "texto_cols": 1,
             "filas": [[p["particion"], entero(p["n"]), entero(p["viviendas"]), pct(float(p["porcentaje_sin_formal"]), 2)] for p in part],
             "nota": "La búsqueda de parámetros usó validación cruzada de tres particiones, agrupada por vivienda. No se utilizó sobremuestreo sintético."},
            {"tipo": "tabla", "titulo": "Hiperparámetros elegidos", "meta": "Boosting de histogramas", "columnas": ["Parámetro", "Valor"], "texto_cols": 1,
             "filas": [[f["parametro"], coma(f["valor"], 2) if "." in f["valor"] else f["valor"]] for f in leer(t, "hiperparametros")],
             "nota": f"Umbral elegido en validación por F1: {coma(elegido['umbral'], 4)}."}]},
        {"tipo": "tabla", "titulo": "Comparación de modelos", "meta": "Métricas de la clase «fuera de la ruta formal»",
         "columnas": ["Modelo", "AP CV", "AP validación", "AP prueba", "ROC-AUC", "Brier", "F1", "Precisión", "Sensibilidad"], "texto_cols": 1, "filas": filas_modelos,
         "nota": "AP es Average Precision. La prevalencia es la referencia: predecir siempre la proporción de la clase."},
        {"tipo": "columnas", "bloques": [
            {"tipo": "tabla", "titulo": "Incertidumbre en la prueba", "meta": "Intervalo de 95 % por bootstrap pareado", "columnas": ["Métrica", "Inferior", "Superior"], "texto_cols": 1,
             "filas": [[e, coma(inc[k]["inferior"]), coma(inc[k]["superior"])] for k, e in nombres_ic],
             "nota": f"La ventaja en AP frente al segundo mejor modelo va de {coma(inc['delta_ap_vs_competitor']['inferior'])} a {coma(inc['delta_ap_vs_competitor']['superior'])}."},
            {"tipo": "tabla", "titulo": "Efecto de las dos variables de contexto", "meta": "De 26 a 28 variables", "columnas": ["Medida", "26 variables", "28 variables"], "texto_cols": 1,
             "filas": [[f["medida"], coma(f["modelo_26"]), coma(f["modelo_28"])] for f in ctx],
             "nota": f"Mejora del AP en validación: {coma(dec['delta_ap'])}, con intervalo de {coma(dec['inferior'])} a {coma(dec['superior'])}. Se comprobó también en secciones censales no vistas."}]},
        {"tipo": "destacado", "rotulo": "Evaluación interna", "texto": "La prueba usa viviendas distintas, pero del mismo censo y los mismos municipios. No hay validación temporal, geográfica externa ni clínica."},
    ]}

    limites = [
        ("Cobertura de la población", "Solo se estudian personas del Atlántico con un problema de salud en los 30 días previos, sin hospitalización y con etiqueta clasificable. El 21,06 % no es una tasa actual de todo el departamento."),
        ("Significado de la etiqueta", "Se registra el tratamiento principal, no todas las acciones. La categoría «fuera» agrupa situaciones muy distintas."),
        ("Asociación y temporalidad", "El censo es transversal. Las diferencias por vivienda, educación o municipio no prueban mecanismos causales."),
        ("Generalización", "La prueba se hizo en viviendas distintas, pero dentro del mismo censo. No hay validación temporal, geográfica externa ni clínica."),
        ("Equidad", "La sensibilidad es menor en el grupo con dificultad funcional y muy baja entre personas de 60 años o más."),
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
        ("¿El 21,06 % significa que se negó la atención?", f"No. Es una clasificación de la acción principal declarada. Solo {entero(eps_sin)} de esas {entero(fuera)} personas acudieron a su EPS y no recibieron atención; las demás declararon otra acción o ninguna."),
        ("¿Describe el Atlántico de hoy?", "No. Son respuestas del censo de 2018 de quienes declararon un problema de salud reciente. No se extrapolan a otros años ni a toda la población."),
        ("¿Por qué algunas tasas se ocultan?", "Para proteger grupos pequeños y evitar lecturas engañosas. Una tasa se oculta si su base aproximada es menor de 200 personas o si la cobertura del filtro es menor de 80 %."),
        ("¿Por qué las cifras filtradas no coinciden con el informe?", "Las celdas pequeñas se suprimen y los recuentos se redondean. Por eso las cifras de las aplicaciones son aproximadas; las exactas están en el informe."),
        ("¿Por qué no hay valores p?", "Los microdatos no son una muestra aleatoria de una población futura y la respuesta se construye con una regla analítica. Por eso se muestran tasas con su base y la V de Cramér como resumen descriptivo."),
        ("¿El modelo dice qué hará una persona?", "No. Ordena perfiles dentro del mismo censo, con discriminación moderada, y no debe usarse para decidir sobre personas. Esta aplicación no calcula predicciones individuales."),
    ]
    conclusiones = {"titulo": "Lo que *sí* muestran los datos", "entrada": "Hallazgos, límites y referencias del proyecto.", "bloques": [
        {"tipo": "lista", "titulo": "Hallazgos principales", "columnas": 2, "items": [
            {"rotulo": "Una clasificación, no una negativa", "texto": f"El {pct(tasa, 2)} queda fuera de la ruta formal, y la etiqueta se explica sobre todo por el tratamiento principal declarado. La mayoría declaró otra acción, no una falta de atención de la EPS."},
            {"rotulo": "La edad y el territorio pesan más", "texto": "Las asociaciones son modestas: 0,163 con la edad y 0,085 con el municipio, y menos de 0,07 con las demás variables comparadas."},
            {"rotulo": "La dificultad funcional sorprende", "texto": "Quienes la declararon quedan menos fuera de la ruta. La diferencia baja de 7,30 a 4,25 puntos al estandarizar por edad; no indica que la dificultad proteja frente a barreras."},
            {"rotulo": "Un modelo útil para explorar", "texto": f"El boosting de histogramas alcanzó AP {coma(elegido['ap_prueba'])} frente a {coma(prevalencia['ap_prueba'])} de la prevalencia. Ordena mejor que el azar, pero deja errores importantes y no sirve para decisiones individuales."},
            {"rotulo": "El contexto ayudó al modelo", "texto": "Las dos variables añadidas sobre otras personas con problemas de salud mejoraron el ordenamiento. Sugieren que parte de la clase podría reflejar problemas más leves o diferencias de declaración, aunque el censo no permite comprobarlo."},
            {"rotulo": "La equidad sigue pendiente", "texto": "Ajustar por edad reduce, pero no borra, la diferencia de sensibilidad entre personas con y sin dificultad funcional."}]},
        {"tipo": "lista", "titulo": "Límites que acompañan cada gráfico", "columnas": 2, "items": [{"rotulo": a, "texto": b} for a, b in limites]},
        {"tipo": "preguntas", "titulo": "Lo que conviene *preguntar*", "items": [{"pregunta": a, "respuesta": b} for a, b in preguntas]},
        {"tipo": "lista", "titulo": "Protección de grupos pequeños", "items": [
            {"rotulo": "Solo agregados", "texto": "La aplicación no contiene ningún registro individual ni el modelo serializado."},
            {"rotulo": "Cruces filtrables", "texto": "Se publican con al menos 30 personas y 5 en cada clase; los recuentos se redondean a 5."},
            {"rotulo": "Panorama por grupo", "texto": "Se publica con al menos 100 personas y 10 en cada clase; los recuentos se redondean a 10."},
            {"rotulo": "Tasas ocultas", "texto": "Una tasa se oculta si la base aproximada es menor de 200 o la cobertura del filtro es menor de 80 %."}]},
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
        "explorar": {
            "pestanas": ["Explorar grupos", "Comparar variables", "Ajuste por edad"],
            "comparar_entrada": "Tasa fuera de la ruta formal por categoría. La V de Cramér va de 0 a 1 y resume la intensidad de la asociación en la tabla observada; un valor pequeño puede coexistir con diferencias visibles en grupos concretos.",
            "comparar_nota": "Comparaciones descriptivas y sin ajuste. No se usan pruebas de hipótesis ni valores p: el censo no es una muestra aleatoria. Recuentos redondeados a 10.",
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
    contenido = construir(args.tablas, relato)
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    for carpeta in args.destino:
        (carpeta / "contenido.json").write_text(texto, encoding="utf-8")
    print(f"contenido.json: {len(texto):,} bytes")


if __name__ == "__main__":
    main()
