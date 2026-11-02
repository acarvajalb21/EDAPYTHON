# Acceso a atención formal en salud en el Atlántico

## Análisis exploratorio del CNPV 2018

Autores: Alejandro Carvajal y Mateo Chang

Este libro describe el acceso observado a atención formal entre las personas censadas en el Atlántico que reportaron un problema de salud durante los 30 días previos y cuya respuesta puede clasificarse. La medida se construye con el tratamiento principal declarado y la atención recibida en la entidad de seguridad social. No equivale a afiliación ni a cobertura de toda la población. Los tableros y el informe llaman «dentro de la ruta formal» a quienes este análisis clasifica con acceso formal, y «fuera de la ruta formal» a los demás.

```{admonition} Pregunta de investigación
¿Cómo varía el acceso a atención formal entre estas personas según sus características funcionales, sociodemográficas, habitacionales y territoriales?
```

El capítulo de análisis presenta el diccionario de variables, la preparación de los microdatos, tablas con conteos y porcentajes, descriptivos cuantitativos, comparaciones por grupo, una estandarización descriptiva por edad y un mapa municipal. La primera gráfica de acceso aparece allí, en su sección de análisis univariado.

El segundo capítulo es el cuaderno del modelo predictivo. Construye la clase, describe las variables y las particiones, compara los candidatos y evalúa el modelo vigente en la prueba interna, con su calibración, su umbral y sus diferencias entre grupos.

Las gráficas de los dos capítulos son interactivas: al pasar el cursor muestran el valor y la base de cada grupo, y en las que tienen leyenda se puede ocultar una serie con un clic. Solo usan datos agregados.

```{note}
Los CSV censales originales no se publican en este repositorio. Los resultados y tablas del cuaderno exploratorio se recalcularon con los archivos departamentales del DANE el 1 de octubre de 2026. El 2 de noviembre de 2026 los dos cuadernos se ejecutaron de nuevo para generar las gráficas interactivas, sin cambios en las cifras. Para repetir la ejecución en otro equipo se necesitan los archivos enumerados en `datos/README.md`.
```

Seleccione un capítulo en el menú para consultar el procedimiento y los resultados.

Para explorar los resultados con filtros por municipio y características de las personas, abra el [tablero interactivo en Dash](https://dataviz-salud-atlantico-409319239507.us-east1.run.app/).
