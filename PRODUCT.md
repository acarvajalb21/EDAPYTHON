# Producto

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

El público general es la audiencia principal. Su tarea es entender los resultados del análisis de salud del Atlántico sin necesitar conocimientos de modelado estadístico. Esta prioridad fue confirmada por el usuario.

## Product Purpose

El proyecto publicado permite explorar y comprender patrones observados en el CNPV 2018 entre personas del Atlántico que declararon un problema de salud en los 30 días previos al censo, sin hospitalización y con una acción principal clasificable. Reúne un tablero interactivo, un informe reproducible y una evaluación interna de modelos de clasificación. La documentación del proyecto define su uso como exploración retrospectiva y educativa.

## Positioning

El análisis aplica una regla operativa explícita a respuestas censales de una cohorte concreta del Atlántico y publica resultados agregados con supresión de celdas pequeñas. Acompaña la exploración con el método, las métricas de prueba y los límites de interpretación del modelo, de modo que cada cifra pueda leerse en su contexto.

## Operating Context

- El tablero público está en Google Cloud Run y se usa en un navegador, sin inicio de sesión. Su contenido está en español.
- Las vistas del tablero son **Proyecto**, **EDA** y **Modelo y método**. El informe Bookdown amplía definiciones, calidad de datos, resultados y reproducibilidad.
- El EDA permite combinar filtros por municipio, sexo reportado, grupo de edad, zona y dificultad funcional. También presenta comparaciones descriptivas y una exploración ilustrativa del umbral del modelo.
- Los CSV individuales del DANE se procesan localmente. La web sirve agregados publicables y no expone registros individuales ni predicciones personales.

## Capabilities and Constraints

- La cohorte analítica documentada contiene 136.034 personas. La regla original clasifica 28.650 (21,06 %) como `ACCESO_FORMAL_SALUD = 0` o `SIN_ACCESO = 1` para la evaluación del modelo.
- Esa categoría significa que la acción principal declarada no fue EPS con atención ni médico particular según la regla del proyecto. No equivale a una tasa de atención denegada, ausencia total de atención o una barrera causal.
- Los cruces publicables suprimen celdas pequeñas y redondean recuentos. El tablero oculta tasas cuando la cobertura es menor del 80 % o la base publicada es menor de 200; sus porcentajes filtrados son aproximados.
- El modelo es retrospectivo, entrenado y evaluado con viviendas separadas del mismo censo y los mismos municipios. No cuenta con validación temporal ni geográfica externa. Sus probabilidades no deben usarse para decisiones sobre personas actuales.
- La documentación y los datos originales se atribuyen al DANE. Los microdatos no se copian al sitio publicado.

## Brand Commitments

- Nombre usado en la interfaz: **DATAVIZ · Salud Atlántico**.
- El lenguaje público debe explicar las etiquetas, los denominadores, la cobertura y la incertidumbre sin convertir asociaciones en causas ni resultados del modelo en recomendaciones individuales.

## Evidence on Hand

- `README.md` describe el alcance, cifras principales, publicación y límites.
- `dash_salud/README.md`, `dash_salud/app.py` y `dash_salud/data/` documentan la interfaz y sus agregados publicables.
- `bookdown_salud/index.Rmd` y los capítulos del libro contienen la explicación extensa del análisis.
- `ml_salud/resultados/INFORME_MODELO.md` registra la metodología, métricas y límites del modelo.
- `entregables/tablero_publicado.png` muestra el tablero publicado.

## Product Principles

1. Hacer comprensibles los resultados para el público general mediante definiciones claras y contexto junto a las cifras.
2. Mantener visible la diferencia entre la etiqueta operativa y la experiencia real de atención de las personas.
3. Mostrar solo agregados que respeten las reglas de publicación y explicar cuándo una selección no permite una tasa fiable.
4. Presentar el modelo como evidencia interna e histórica, con sus límites de generalización.
