# Panel interactivo DATAVIZ · Salud Atlántico

Panel Dash de tres vistas: **Proyecto**, con contexto, pregunta, objetivos y
cohorte; **EDA**, con filtros y cruces censales; y **Modelo y método**, con
evaluación del clasificador. El universo es la población del Atlántico que reportó un problema
de salud en los 30 días previos al CNPV 2018 sin hospitalización y con acción
principal clasificable. La clase «fuera de la ruta formal» significa que la
acción principal **no** fue EPS con atención o médico particular bajo la regla
del EDA. No implica necesariamente denegación, falta total de atención ni
una barrera causal.

## Origen y privacidad

Los CSV originales del DANE se leen localmente con
`python -m dash_salud.generar_datos --data-dir RUTA_A_LOS_CSV`, desde la raíz de
`DATAVIZ`. El generador valida sus SHA-256 frente al informe de entrenamiento,
reproduce la prueba reservada y escribe dos JSON:

- `data/eda.json`: cubo real de municipio × sexo × edad amplia × zona ×
  dificultad funcional. Solo se publican celdas con al menos 30 personas y
  al menos 5 en cada clase. Los conteos se redondean a múltiplos de 5. El
  panorama municipal usa al menos 100 personas y 10 en cada clase, y redondea
  a múltiplos de 10. El índice de cobertura contiene porcentajes en escalones
  de 5, nunca conteos originales de cruces pequeños.
- `data/modelo.json`: métricas, curvas visuales muestreadas, calibración,
  importancias y matrices para umbrales del conjunto de prueba. No contiene
  registros ni puntuaciones individuales. Se omiten métricas de subgrupos
  pequeños.

La cobertura de la exploración puede cambiar según los filtros. Cuando cae
por debajo de 80 % o la base publicada es menor de 200, el panel oculta la
tasa. El panorama municipal procede de un agregado independiente y su
denominador se explica por separado.

Las [denominaciones municipales](https://geoportal.dane.gov.co/descargas/descarga_divipola/pdf/Atlantico.pdf)
se verificaron con el mapa DIVIPOLA oficial del DANE. Las demás definiciones
y métricas están documentadas en `ml_salud/resultados/INFORME_MODELO.md`.

## Probar localmente

Instale `requirements.txt` en un entorno de Python compatible y ejecute,
desde la raíz del proyecto:

```powershell
python -m dash_salud.generar_datos --data-dir 'C:\Users\Alejandro Carvajal\OneDrive\Documents\PROYECTO_DISCAPACIDAD\data'
python -m dash_salud.app
```

Abra `http://localhost:8050`. El generador usa el entorno de entrenamiento
de `ml_salud` (pandas, scikit-learn y joblib compatibles con el modelo).
La aplicación publicada requiere únicamente Dash, Plotly y Gunicorn.
La interfaz y las gráficas usan IBM Plex Sans. El archivo variable latino se
sirve desde `assets/fonts/`; su licencia OFL está en ese mismo directorio.

El Bookdown renderizado se copia a `dash_salud/informe/` con `index.html` y
sus recursos. El enlace «Leer informe completo» abre `/informe/`.

## Publicar en Google Cloud Run

El `Dockerfile` escucha en `0.0.0.0:$PORT`. `data/` contiene exclusivamente
agregados publicables, y `.gcloudignore`/`.dockerignore` excluyen microdatos,
notebooks, artefactos de inferencia y el generador. El servicio propuesto
`dataviz-salud-atlantico` es distinto del servicio académico existente `dash`.
El despliegue desde código fuente y el uso de `PORT` siguen la
[documentación de Cloud Run](https://docs.cloud.google.com/run/docs/deployment-options-for-services)
y su [contrato de contenedor](https://docs.cloud.google.com/run/docs/container-contract).

Con Google Cloud CLI instalado, sesión iniciada, permisos de Cloud Run/Cloud
Build/Artifact Registry y facturación habilitada en el proyecto:

```powershell
.\dash_salud\deploy_cloud_run.ps1 -ProjectId eda-salud-atlantico-2018 -Region us-east1
```

El script verifica los dos JSON y el Bookdown, usa `gcloud run deploy
--source .` y publica un enlace accesible sin autenticación. El servicio está
disponible en [Google Cloud Run](https://dataviz-salud-atlantico-409319239507.us-east1.run.app/).
Tras actualizarlo, compruebe `/health`, `/informe/` y los tres paneles. Cloud
Run reserva algunas rutas terminadas en `z`, por lo que se usa `/health`.

Si se usa **Cloud Shell**, suba `entregables/dash_salud_cloud_run.zip` desde este
equipo y ejecute:

```bash
unzip dash_salud_cloud_run.zip
cd dash_salud
bash deploy_cloud_shell.sh
```

El script usa el mismo
proyecto, región y nombre de servicio; se pueden cambiar con las variables
`PROJECT_ID`, `REGION` y `SERVICE_NAME`. Cloud Shell debe estar autenticado y
la cuenta necesita permisos para habilitar API, construir y publicar Cloud Run.

## Límites de interpretación

El modelo procede del mismo censo y los mismos municipios en entrenamiento y prueba,
aunque las viviendas no se repiten. La elección del umbral se hizo en
validación; moverlo en el panel ilustra escenarios posteriores en la prueba,
sin convertirlos en recomendaciones. No usar sus probabilidades para
decisiones individuales o datos actuales sin validación externa.
