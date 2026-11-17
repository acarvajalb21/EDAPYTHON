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
                if re.match(r"(Figura|Tabla) \d+\.\d+:", oracion):
                    continue  # Un pie de figura no responde preguntas por sí solo.
                if len(trozo) + len(oracion) > 900 and trozo:
                    partes.append(trozo)
                    trozo = ""
                trozo = f"{trozo} {oracion}".strip()
            partes.append(trozo)
            fuente = f"Informe, {s['capitulo']}" + (f", sección {s['titulo']}" if s["titulo"] != s["capitulo"] else "")
            salida.extend({**pasaje(s["titulo"], fuente, p, "informe"), "pagina": pagina.name} for p in partes)
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


def buscar_tabla(bloques, titulo: str) -> dict | None:
    """Primera tabla con ese título en un árbol de bloques de contenido.json."""
    for b in bloques if isinstance(bloques, list) else []:
        if b.get("tipo") == "tabla" and b.get("titulo") == titulo:
            return b
        hijos = b.get("bloques") or [x for p in b.get("pestanas", []) for x in p["bloques"]]
        hallada = buscar_tabla(hijos, titulo)
        if hallada:
            return hallada
    return None


def lista_natural(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


def numero(texto: str) -> int:
    return int(str(texto).replace(".", ""))


def respuestas_del_modelo(modelo: dict, contenido: dict) -> list[tuple[str, str, str, str]]:
    """Preguntas frecuentes de una revisión académica: elección, partición y lectura de las métricas."""
    modelos = modelo["models"]
    nombres = {"baseline": "la referencia sin modelo (predecir siempre la prevalencia)", "logistica": "la regresión logística regularizada",
               "random_forest": "el bosque aleatorio (Random Forest)", "hist_gradient_boosting": "el boosting de histogramas (Hist Gradient Boosting)"}
    reales = [k for k in ("logistica", "random_forest", "hist_gradient_boosting")]
    elegido = modelo["metadata"]["selected_model"]
    t = modelos[elegido]["test"]
    base = modelos["baseline"]["test"]
    c = t["confusion"]
    n = modelo["metadata"]["test_n"]
    positivos = modelo["metadata"]["test_positive"]
    prevalencia = positivos / n
    cero5 = min(modelo["thresholds"], key=lambda r: abs(r["threshold"] - 0.5))
    exactitud = (c["tn"] + c["tp"]) / n
    exactitud_05 = (cero5["tn"] + cero5["tp"]) / n
    sens_05 = cero5["tp"] / max(cero5["tp"] + cero5["fn"], 1)
    exactitud_balanceada = (t["recall"] + t["specificity"]) / 2
    ic = modelo["uncertainty"]["intervals_95"]
    rival = modelo["uncertainty"]["competitor"]
    top10 = next(r for r in modelo["prioritization"] if abs(r["fraction"] - 0.10) < 1e-9)
    por_val = sorted(reales, key=lambda k: -modelos[k]["validation_ap"])
    peor = por_val[-1]
    pct = lambda v, d=1: coma(100 * v, d) + " %"
    lista_ap = "; ".join(f"{nombres[k].split(' (')[0]}: {coma(modelos[k]['validation_ap'])} en validación y {coma(modelos[k]['test']['pr_auc'])} en prueba"
                         for k in ("baseline", "logistica", "random_forest", "hist_gradient_boosting"))
    sep = buscar_tabla(contenido["paginas"]["creacion"]["bloques"], "Separación por vivienda")
    col = {nombre: k for k, nombre in enumerate(sep["columnas"])}
    filas = {f[0]: (numero(f[col["Personas"]]), numero(f[col["Viviendas"]])) for f in sep["filas"]}
    total = sum(p for p, _ in filas.values())
    reparto = ", ".join(f"{nombre.lower()} {entero(p)} personas ({pct(p / total)}) de {entero(v)} viviendas" for nombre, (p, v) in filas.items())
    hip = buscar_tabla(contenido["paginas"]["creacion"]["bloques"], "Hiperparámetros elegidos")
    hip_texto = ", ".join(f"{f[0]} = {f[1]}" for f in hip["filas"])
    importancia = modelo["importance"][:3]
    nombres_var = {"U_MPIO": "municipio", "HOGAR_OTROS_ENFERMOS": "otras personas del hogar con problema de salud", "P_EDADR": "edad",
                   "SECCION_PCT_ENFERMOS": "proporción con problema de salud en la sección censal"}
    top = [f"{nombres_var.get(r['feature'], r['feature'])} ({coma(r['mean_ap_drop'])})" for r in importancia]
    mejora = next(b for b in contenido["modelo"]["despues"] if b.get("titulo") == "¿Se puede mejorar? Lo que probamos")
    return [
        ("modelo", "Modelo", "¿Se puede mejorar el modelo?",
         " ".join(f"{i['rotulo']}: {i['texto']}" for i in mejora["items"])),
        ("creacion", "Modelado", "¿Cuál es el mejor modelo?",
         f"El mejor de los candidatos evaluados fue {nombres[elegido]}. Tuvo la mayor precisión promedio (AP) en validación cruzada, en validación y en prueba, además del mayor ROC-AUC y el menor Brier. Precisión promedio por modelo: {lista_ap}. «Mejor» significa mejor entre estos cuatro bajo el mismo protocolo, no el mejor modelo posible."),
        ("creacion", "Modelado", "¿Por qué se escogió ese modelo?",
         f"Por cuatro razones. 1) La regla de selección, fijada antes de mirar la prueba, era la mayor precisión promedio (AP) en validación, y el boosting ganó con {coma(modelos[elegido]['validation_ap'])}, frente a {coma(modelos[por_val[1]]['validation_ap'])} del segundo. 2) También ganó en las demás métricas: ROC-AUC {coma(t['roc_auc'])} y Brier {coma(t['brier'])}. 3) La diferencia de AP en prueba, boosting menos {nombres[rival].split(' (')[0]}, fue {coma(t['pr_auc'] - modelos[rival]['test']['pr_auc'])}, con intervalo pareado del 95 % de {coma(ic['delta_ap_vs_competitor'][0])} a {coma(ic['delta_ap_vs_competitor'][1])} (bootstrap de 250 remuestreos por vivienda): no incluye cero, pero es una ventaja pequeña y el intervalo no cubre la variabilidad del entrenamiento ni de la selección. 4) Trata municipio, sexo y materiales como categorías y capta combinaciones entre variables sin especificarlas a mano."),
        ("creacion", "Modelado", "¿Qué modelos se compararon?",
         f"Cuatro, bajo los mismos datos y particiones: {nombres['baseline']}, {nombres['logistica']}, {nombres['random_forest']} y {nombres['hist_gradient_boosting']}. Precisión promedio: {lista_ap}."),
        ("creacion", "Modelado", "¿Cuál fue el peor modelo?",
         f"Sin contar la referencia, el de menor precisión promedio en validación fue {nombres[peor]}, con {coma(modelos[peor]['validation_ap'])}. La referencia sin modelo obtuvo {coma(modelos['baseline']['validation_ap'])}: todos los modelos la superan, pero las diferencias entre ellos son pequeñas."),
        ("creacion", "Modelado", "¿Cómo se dividieron los datos de entrenamiento y prueba?",
         f"Se separaron en tres partes, con proporciones 5/7, 1/7 y 1/7: {reparto}. La división es estratificada, para que cada parte tenga la misma proporción fuera de la ruta, y agrupada por vivienda: las personas de una misma vivienda quedan en una sola parte, para no evaluar con hogares que el modelo ya vio. Con entrenamiento se ajustan los modelos y se buscan hiperparámetros con validación cruzada de 3 pliegues; con validación se elige el modelo y el umbral; la prueba se usa una sola vez al final."),
        ("creacion", "Modelado", "¿Qué hiperparámetros usa el modelo?",
         f"El boosting de histogramas elegido usa {hip_texto}. Se escogieron con validación cruzada de 3 pliegues dentro del entrenamiento, buscando la mayor precisión promedio. La parada temprana se desactivó para no crear otra partición."),
        ("modelo", "Modelo", "¿Por qué las métricas del modelo son bajas?",
         f"Porque el censo no registra lo que más decide la acción: la gravedad del problema, el tiempo de espera, la distancia o la preferencia de la persona. Con solo datos de persona, hogar y vivienda, el modelo ordena mejor que el azar, pero con discriminación moderada: ROC-AUC {coma(t['roc_auc'])} y precisión promedio {coma(t['pr_auc'])}, frente a {coma(base['pr_auc'])} sin modelo. Sí aporta: entre el 10 % con mayor puntuación, {pct(top10['precision'])} está fuera de la ruta, {coma(top10['lift'], 1)} veces la prevalencia de {pct(prevalencia)}. Antes se probaron {modelo['audit_2026']['alternatives']} variantes de preparación y ajuste sin ganancia; la mejora solo llegó con información nueva."),
        ("modelo", "Modelo", "¿El modelo predice?",
         f"Sí, pero hay que usar el umbral validado. Con el corte convencional de 0,5 casi no marca a nadie: detecta solo {pct(sens_05)} de los casos, porque sus probabilidades rara vez pasan de 0,5 cuando la clase es de {pct(prevalencia)}. Con el umbral elegido en validación, {coma(modelo['metadata']['chosen_threshold'], 4)}, detecta {entero(c['tp'])} de {entero(positivos)} personas fuera de la ruta ({pct(t['recall'])}), con precisión de {pct(t['precision'])}."),
        ("modelo", "Modelo", "¿Por qué no se usa el umbral de 0,5?",
         f"Porque solo una de cada cinco personas está fuera de la ruta y el modelo está calibrado: sus probabilidades rara vez superan 0,5. Con ese corte la sensibilidad es {pct(sens_05)}. Por eso el umbral se eligió en validación maximizando F1: {coma(modelo['metadata']['chosen_threshold'], 4)}."),
        ("modelo", "Modelo", "¿Cuál es la exactitud del modelo?",
         f"Con el umbral validado, la exactitud (accuracy) en prueba es {pct(exactitud)} y la exactitud balanceada, {pct(exactitud_balanceada)}. No se usa como métrica principal porque engaña con clases desiguales: decir siempre «dentro de la ruta» acierta {pct(1 - prevalencia)} sin encontrar ningún caso, y con el corte de 0,5 el modelo llega a {pct(exactitud_05)} detectando apenas {pct(sens_05)}. Por eso se usa la precisión promedio."),
        ("modelo", "Modelo", "¿Qué es la matriz de confusión?",
         f"Es la tabla que cruza lo observado con lo predicho. En la prueba, con el umbral validado: {entero(c['tp'])} detectados, {entero(c['fn'])} no detectados, {entero(c['fp'])} falsas alarmas y {entero(c['tn'])} verdaderos negativos. Está en la sección Modelo, donde se puede mover el umbral."),
        ("modelo", "Modelo", "¿Cuál es la variable más importante?",
         f"Por importancia por permutación (cuánto cae la precisión promedio al desordenar la variable), las primeras son {lista_natural(top)}. Mide cuánto depende el modelo de cada variable, no su efecto causal."),
        ("creacion", "Modelado", "¿Qué es la referencia o baseline?",
         f"Es el punto de comparación mínimo: asigna a todas las personas la misma probabilidad, la proporción fuera de la ruta del entrenamiento. Su precisión promedio es {coma(base['pr_auc'])} y su ROC-AUC, 0,500. Un modelo solo aporta si supera esa referencia."),
        ("creacion", "Modelado", "¿Qué es el boosting de histogramas?",
         "Es un método que construye muchos árboles de decisión pequeños en secuencia: cada árbol corrige los errores de los anteriores. «De histogramas» indica que agrupa los valores en intervalos para entrenar rápido con muchas personas. Es la implementación HistGradientBoostingClassifier de scikit-learn."),
        ("creacion", "Modelado", "¿Cómo se evitó la fuga de información?",
         "Se excluyeron los campos que construyen la respuesta o son posteriores a la atención, se separó por vivienda y la imputación y la codificación se aprendieron solo con entrenamiento, dentro del pipeline. El modelo y el umbral se eligieron en validación, y la prueba se consultó al final."),
        ("problema", "Problema", "¿Cuál es la variable objetivo?",
         "Es SIN_ACCESO: vale 1 si la acción principal declarada no fue acudir a la EPS con atención ni a un médico particular (fuera de la ruta formal) y 0 si sí lo fue. Equivale a ACCESO_FORMAL_SALUD = 0. Es la clase positiva de las métricas."),
    ]


def respuestas_de_referencia(modelo: dict, relato: dict, contenido: dict) -> list[dict]:
    """Respuestas a las preguntas más comunes, con cifras leídas de los resultados validados."""
    t = modelo["models"]["hist_gradient_boosting"]["test"]
    base = modelo["models"]["baseline"]["test"]
    c = t["confusion"]
    eq = modelo["equity"]
    cambio = modelo["version_change"]
    cohorte, fuera = relato["cohorte"], relato["fuera"]
    sin_atencion = relato["rutas"]["eps_no_atendido"]
    a = relato["acciones"]
    modelos = modelo["models"]
    meta = modelo["metadata"]
    municipios = next(v for v in contenido["explorar"]["variables"] if v["id"] == "municipio")["categorias"]
    pct = lambda v, d=1: coma(100 * v, d) + " %"
    filas = [
        ("problema", "Problema", "¿Qué porcentaje de personas quedó dentro de la ruta formal?",
         f"Quedaron dentro {entero(cohorte - fuera)} personas, el {pct(1 - fuera / cohorte, 2)} de las {entero(cohorte)} estudiadas. Acudieron a su EPS con atención o consultaron a un médico particular."),
        ("conclusiones", "Conclusiones", "¿Qué conclusiones no se pueden sacar?",
         f"Los datos no permiten decir que al {pct(fuera / cohorte, 2)} le negaran la atención, que esa sea la situación actual ni que una variable cause las diferencias. Tampoco permiten predecir qué hará una persona ni aplicar el modelo a otro año o territorio."),
        ("modelo", "Modelo", "¿Qué significa discriminación moderada?",
         f"Que el modelo separa a las personas fuera y dentro de la ruta mejor que el azar, pero con muchos errores. Su ROC-AUC fue {coma(t['roc_auc'])}, donde 0,500 sería azar y 1 una separación perfecta."),
        ("modelo", "Modelo", "¿Qué es la especificidad?",
         f"De quienes están dentro de la ruta, es la parte que el modelo no marca. Con el umbral validado fue {pct(t['specificity'])}."),
        ("creacion", "Modelado", "¿Qué es la validación cruzada?",
         "Es repetir el ajuste varias veces, reservando cada vez una parte distinta del entrenamiento para medir el resultado. Aquí se usó dentro del entrenamiento para comparar parámetros sin tocar la prueba."),
        ("problema", "Problema", "¿Qué es la cohorte?",
         f"Es el grupo que analiza el proyecto: {entero(cohorte)} personas del Atlántico que declararon un problema de salud reciente sin hospitalización y cuya respuesta se pudo clasificar."),
        ("problema", "Problema", "¿Qué es la autorreceta?",
         f"Es una de las acciones principales que registra el censo: la persona declaró que se autorrecetó. Fue la respuesta más frecuente fuera de la ruta formal, con {entero(a['autorreceta'])} personas, el {pct(a['autorreceta'] / cohorte)} de las estudiadas."),
        ("problema", "Problema", "¿Les negaron la atención?",
         f"El censo no permite afirmarlo. De {entero(fuera)} personas fuera de la ruta formal, {entero(sin_atencion)} acudieron a su EPS y no fueron atendidas, y el censo no registra el motivo. Las demás declararon otra acción."),
        ("conclusiones", "Conclusiones", "¿Cuál es la causa de las diferencias?",
         "El proyecto no lo determina. El censo es una foto de un momento y las comparaciones no están ajustadas: muestran dónde hay diferencias, no por qué ocurren."),
        ("conclusiones", "Conclusiones", "¿Los resultados se pueden generalizar?",
         "No. Son respuestas de 2018 de personas del Atlántico que declararon un problema de salud reciente. No se extrapolan a otros años, a otros departamentos, a Colombia ni a toda la población."),
        ("panorama", "Introducción", "¿De qué año son los datos?",
         "Son del Censo Nacional de Población y Vivienda 2018. No describen la situación actual."),
        ("panorama", "Introducción", "¿Dónde están los microdatos?",
         "Los microdatos del censo no se publican aquí: las aplicaciones y este asistente solo contienen datos agregados. El DANE los distribuye en su catálogo."),
        ("explorar", "EDA multivariado", "¿Cuántos municipios se comparan?",
         f"Se comparan {len(municipios)} municipios del Atlántico. Piojó no aparece porque no alcanza el mínimo de 100 personas y 10 dentro y fuera de la ruta formal."),
        ("creacion", "Modelado", "¿Qué algoritmo usa el modelo?",
         f"Usa boosting de histogramas (Hist Gradient Boosting). Se eligió porque tuvo la mayor precisión promedio, el mayor ROC-AUC y el menor Brier entre los candidatos: precisión promedio de {coma(t['pr_auc'])}, frente a {coma(modelos['logistica']['test']['pr_auc'])} de la regresión logística y {coma(modelos['random_forest']['test']['pr_auc'])} del bosque aleatorio."),
        ("creacion", "Modelado", "¿Cómo se dividieron los datos?",
         f"En entrenamiento, validación y prueba, separados por vivienda: las personas de una misma vivienda quedan en una sola partición. La prueba tiene {entero(meta['test_n'])} personas."),
        ("modelo", "Modelo", "¿Cuántos casos detecta el modelo?",
         f"En la prueba había {entero(meta['test_positive'])} personas fuera de la ruta. Con el umbral validado, el modelo detectó a {entero(c['tp'])} y dejó sin detectar a {entero(c['fn'])}. También marcó a {entero(c['fp'])} personas que estaban dentro de la ruta."),
        ("modelo", "Modelo", "¿Qué es un falso positivo?",
         f"Es una falsa alarma: una persona que el modelo marca como fuera de la ruta y que en realidad estaba dentro. En la prueba hubo {entero(c['fp'])}."),
        ("modelo", "Modelo", "¿Qué es un falso negativo?",
         f"Es una persona que está fuera de la ruta y que el modelo no marca. En la prueba hubo {entero(c['fn'])}."),
        ("modelo", "Modelo", "¿Qué es F1?",
         f"Es una medida que resume en un número la precisión y la sensibilidad. Se usó en validación para elegir el umbral. En la prueba, el modelo obtuvo {coma(t['f1'])}."),
        ("problema", "Problema", "¿Qué significa estar fuera de la ruta formal?",
         f"Significa que la acción principal declarada no fue acudir a la EPS con atención ni a un médico particular. Incluye a quienes acudieron a la EPS sin ser atendidos, a quienes eligieron otra acción y a quienes no hicieron nada. No significa que les negaran la atención: solo {entero(sin_atencion)} de {entero(fuera)} personas acudieron a su EPS y no fueron atendidas."),
        ("problema", "Problema", "¿Qué es la ruta formal?",
         "Es acudir a la EPS y ser atendido, o consultar a un médico particular, como acción principal declarada ante un problema de salud. Es una regla del proyecto para clasificar respuestas del censo, no una medida completa de acceso."),
        ("panorama", "Introducción", "¿De qué trata este proyecto?",
         "Analiza qué hicieron las personas del Atlántico ante un problema de salud reciente, según el censo de 2018. Compara quién quedó dentro o fuera de la ruta formal y evalúa si un modelo puede ordenar esos casos."),
        ("problema", "Problema", "¿Cuál es el resultado principal?",
         f"De {entero(cohorte)} personas estudiadas, {entero(fuera)} ({pct(fuera / cohorte, 2)}) quedaron fuera de la ruta formal y {entero(cohorte - fuera)} ({pct(1 - fuera / cohorte, 2)}) dentro. La mayoría de quienes quedaron fuera declaró otra acción: {entero(a['autorreceta'])} se autorrecetaron. Solo {entero(sin_atencion)} acudieron a su EPS y no fueron atendidas."),
        ("problema", "Problema", "¿Qué hicieron las personas fuera de la ruta formal?",
         f"Declararon como acción principal: autorrecetarse ({entero(a['autorreceta'])}), remedios caseros ({entero(a['remedios'])}), no hacer nada ({entero(a['nada'])}), ir a un boticario o droguista ({entero(a['boticario'])}), otras alternativas ({entero(a['otras'])}) o acudir a su EPS sin ser atendidas ({entero(sin_atencion)})."),
        ("problema", "Problema", "¿Cuántas personas se estudiaron?",
         f"Se estudiaron {entero(cohorte)} personas. El archivo del censo del Atlántico tiene {entero(relato['flujo']['people'])} registros; {entero(relato['flujo']['recent_health_problem'])} declararon un problema de salud sin hospitalización y {entero(relato['flujo']['unclassifiable'])} no se pudieron clasificar."),
        ("modelo", "Modelo", "¿Qué tan bueno es el modelo?",
         f"Ordena mejor que el azar, con discriminación moderada. Su precisión promedio (AP) fue {coma(t['pr_auc'])}, frente a {coma(base['pr_auc'])} sin modelo, y su ROC-AUC fue {coma(t['roc_auc'])}. Deja errores importantes y solo se evaluó con viviendas del mismo censo: no hay validación en otro año, en otro territorio ni clínica."),
        ("modelo", "Modelo", "¿En qué falla el modelo?",
         f"Con el umbral validado, en la prueba de {entero(modelo['metadata']['test_n'])} personas dio {entero(c['fp'])} falsas alarmas y dejó sin detectar a {entero(c['fn'])} personas fuera de la ruta. De cada tres personas que marca, cerca de una está realmente fuera. Además encuentra menos casos entre personas con dificultad funcional y muy pocos entre personas de 60 años o más."),
        ("modelo", "Modelo", "¿Qué significa la precisión promedio?",
         f"La precisión promedio (AP) mide qué tan arriba quedan las personas fuera de la ruta cuando el modelo ordena a todos por puntuación. El modelo obtuvo {coma(t['pr_auc'])}; sin modelo se obtendría {coma(base['pr_auc'])}, que es la proporción de personas fuera de la ruta. Por eso se compara con esa referencia y no con cero."),
        ("modelo", "Modelo", "¿Qué significa ROC-AUC?",
         f"Es la probabilidad de que el modelo puntúe más alto a una persona fuera de la ruta que a una dentro. El azar daría 0,500 y el modelo obtuvo {coma(t['roc_auc'])}."),
        ("modelo", "Modelo", "¿Qué significa Brier?",
         f"Mide el error entre la probabilidad estimada y lo que ocurrió. Menor es mejor: el modelo obtuvo {coma(t['brier'])} y sin modelo se obtiene {coma(base['brier'])}."),
        ("modelo", "Modelo", "¿Qué es la sensibilidad?",
         f"De quienes están fuera de la ruta, es la parte que el modelo marca. Con el umbral validado fue {pct(t['recall'])}."),
        ("modelo", "Modelo", "¿Qué es la precisión?",
         f"De las personas que el modelo marca, es la parte que realmente está fuera de la ruta. Con el umbral validado fue {pct(t['precision'])}."),
        ("modelo", "Modelo", "¿Qué variables pesan más en el modelo?",
         "Las que más ayudaron a ordenar fueron el municipio y otras personas del hogar con problema de salud, seguidas por la edad y la proporción con problema de salud en la sección censal. Esto mide dependencia del modelo, no efecto causal."),
        ("modelo", "Modelo", "¿Por qué hay dos versiones del modelo?",
         f"La primera usaba 26 variables. La versión vigente añade dos de contexto: otras personas del hogar con problema de salud y la proporción que lo declaró en la sección censal. La precisión promedio en validación pasó de {coma(cambio['previous_validation_ap'])} a {coma(cambio['new_validation_ap'])}."),
        ("modelo", "Modelo", "¿El modelo funciona igual para todos los grupos?",
         f"No. Con el umbral validado, la sensibilidad fue {pct(eq['recall_difficulty'])} entre quienes declararon dificultad funcional y {pct(eq['recall_no_difficulty'])} entre quienes no. Entre personas de 60 años o más fue {pct(eq['recall_60_plus'])}. Ajustar por edad reduce la brecha, pero no la borra."),
        ("modelo", "Modelo", "¿Se puede usar el modelo para decidir a quién atender?",
         "No. Es retrospectivo, se evaluó dentro del mismo censo y deja errores importantes. Antes de cualquier uso práctico haría falta validarlo en otro año y territorio, y definir el costo de cada error."),
        ("univariado", "EDA univariado", "¿Qué variables usa el modelo?",
         "Usa 28 variables: diez de la persona, cinco del hogar, once de la vivienda y dos de contexto de salud, una del hogar y otra de la sección censal. No usa los campos que construyen la respuesta ni la calidad del servicio, porque revelarían el resultado o son posteriores a la atención."),
        ("modelo", "Modelo", "¿Cómo se eligió el umbral?",
         f"Se eligió en el conjunto de validación con la métrica F1, antes de evaluar la prueba, y su valor es {coma(modelo['metadata']['chosen_threshold'], 4)}. Otros valores en la aplicación son escenarios de exploración, no recomendaciones."),
        ("conclusiones", "Conclusiones", "¿Qué limitaciones tiene el análisis?",
         "Solo incluye personas del Atlántico que declararon un problema de salud en 2018, sin hospitalización. Registra la acción principal, no todas las acciones, ni gravedad, tiempo de espera o motivo. El censo es transversal, así que las diferencias no prueban causas. El modelo no se validó en otro año ni territorio."),
        ("conclusiones", "Conclusiones", "¿Qué concluye el proyecto?",
         f"El {pct(fuera / cohorte, 2)} quedó fuera de la ruta formal, sobre todo por otras acciones declaradas y no por falta de atención de la EPS. Las diferencias más marcadas son por edad y municipio, y son modestas. El modelo ordena mejor que el azar, pero con discriminación moderada y diferencias entre grupos."),
        ("explorar", "EDA multivariado", "¿Por qué quienes tienen dificultad funcional quedan menos fuera de la ruta?",
         "En parte por la edad: quienes declaran dificultad suelen tener más edad, y la diferencia baja de 7,30 a 4,25 puntos al ajustar. Los puntos restantes no se pueden atribuir a la dificultad funcional, porque pueden intervenir otros factores."),
        ("conclusiones", "Conclusiones", "¿Las personas fuera de la ruta no tienen EPS?",
         "El análisis no mide afiliación. Estar fuera de la ruta formal significa que la acción principal declarada no fue acudir a la EPS con atención ni a un médico particular. No indica si la persona estaba afiliada."),
        ("panorama", "Introducción", "¿Qué datos usa el proyecto?",
         "Usa los microdatos anonimizados del Censo Nacional de Población y Vivienda 2018 del DANE para el Atlántico: personas, hogares y viviendas, más el Marco Geoestadístico Nacional. Las aplicaciones y este asistente solo contienen datos agregados."),
        ("conclusiones", "Conclusiones", "¿Cómo se protegen los datos?",
         "Las aplicaciones solo contienen datos agregados. Un grupo se publica con al menos 30 personas y 5 dentro y fuera de la ruta, y los recuentos se redondean. Un porcentaje se oculta si su base aproximada es menor de 200 personas o la cobertura es menor de 80 %."),
        ("explorar", "EDA multivariado", "¿Cómo uso los filtros?",
         "En EDA multivariado, elige municipio, sexo, edad, zona o dificultad funcional. Cada filtro reduce el grupo, y la frase, la cobertura y las gráficas se recalculan con quienes cumplen todos los filtros. Si el grupo es muy pequeño, el porcentaje se oculta."),
        ("marco", "Marco teórico", "¿Qué es una EPS?",
         "En el proyecto, la EPS es la entidad a la que la Ley 100 de 1993 asigna la afiliación y la tarea de organizar y garantizar la prestación del plan de salud a sus afiliados. El censo pregunta si la persona acudió a su entidad de seguridad social."),
    ]
    # Las respuestas nuevas reemplazan a las anteriores con el mismo título.
    nuevas = respuestas_del_modelo(modelo, contenido)
    titulos_nuevos = {f[2] for f in nuevas}
    filas = [f for f in filas if f[2] not in titulos_nuevos and f[2] != "¿Cómo se dividieron los datos?"] + nuevas
    salida = []
    for seccion, nombre, titulo, texto in filas:
        p = pasaje(titulo, f"Aplicación, sección {nombre}", texto, "respuesta")
        p["seccion"] = seccion
        salida.append(p)
    salida.append({**pasaje("¿Quién hizo este proyecto?", "Informe, portada", "Es un trabajo de Alejandro Carvajal y Mateo Chang.", "respuesta"), "pagina": "index.html"})
    return salida


def main() -> None:
    contenido = json.loads((RAIZ / "data" / "contenido.json").read_text(encoding="utf-8"))
    modelo = json.loads((RAIZ / "data" / "modelo.json").read_text(encoding="utf-8"))
    relato = json.loads((RAIZ / "assets" / "relato_datos.json").read_text(encoding="utf-8"))
    pasajes: list[dict] = respuestas_de_referencia(modelo, relato, contenido)
    for clave, pagina in contenido["paginas"].items():
        seccion = NOMBRES_SECCION[clave]
        nuevos = [pasaje(pagina["titulo"], f"Aplicación, sección {seccion}", pagina["entrada"], "aplicacion")] if "titulo" in pagina else []
        nuevos.extend(bloques_a_pasajes(pagina["bloques"], seccion))
        pasajes.extend({**p, "seccion": clave} for p in nuevos)
    pasajes.extend({**p, "seccion": "explorar"} for p in explorar_a_pasajes(contenido))
    pasajes.extend({**p, "seccion": "modelo"} for p in modelo_a_pasajes(contenido))
    pasajes.extend(informe_a_pasajes(RAIZ / "informe"))
    for i, p in enumerate(pasajes, 1):
        p["id"] = i
    destino = RAIZ / "data" / "conocimiento.json"
    destino.write_text(json.dumps(pasajes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"conocimiento.json: {len(pasajes)} pasajes, {destino.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
