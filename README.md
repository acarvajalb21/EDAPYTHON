# DATAVIZ · Salud en el Atlántico — Dash y modelo

Proyecto de Alejandro Carvajal y Mateo Chang sobre respuestas de salud del CNPV 2018 en el Atlántico. **Las carpetas vigentes son [`dash_salud/`](dash_salud/README.md) y [`ml_salud/`](ml_salud/README.md).** El [informe Bookdown actual](https://github.com/acarvajalb21/EDAR) y su [versión HTML](https://acarvajalb21.github.io/EDAR/) están en el repositorio EDAR.

## Qué se entrega

- [`dash_salud/`](dash_salud/README.md): tablero Dash de tres vistas: Proyecto, EDA y Modelo y método. `data/` contiene solo agregados preparados para publicación; `informe/` es una copia HTML del Bookdown integrada en la app. Incluye Dockerfile, scripts de despliegue y pruebas.
- [`ml_salud/`](ml_salud/README.md): pipeline reproducible, modelo seleccionado, métricas y auditoría. El [informe técnico principal](ml_salud/resultados/INFORME_MODELO.md) y la [auditoría de octubre de 2026](ml_salud/experimentos_2026_10/INFORME_AUDITORIA.md) documentan la evaluación y sus límites.
- [`PRODUCT.md`](PRODUCT.md): contexto de producto y principios de comunicación del tablero.

El [tablero en Cloud Run](https://dataviz-salud-atlantico-409319239507.us-east1.run.app/) usa el proyecto `eda-salud-atlantico-2018`, región `us-east1` y servicio `dataviz-salud-atlantico`. **Un push a este repositorio no actualiza automáticamente ese servicio.** Para publicar una revisión deliberada use `dash_salud/deploy_cloud_run.ps1` o `dash_salud/deploy_cloud_shell.sh` tras verificar la app. El `Dockerfile` de la raíz pertenece al dashboard anterior; el despliegue vigente usa `dash_salud/Dockerfile`.

## Interpretación correcta

La cohorte analítica tiene **136.034 personas**. La regla `ACCESO_FORMAL_SALUD = 0` marca **28.650 (21,06 %)** como fuera de la ruta formal definida: 1.907 reportaron acudir a su EPS sin recibir atención y 26.743 reportaron otra acción principal o ninguna. **No es una medida de necesidad médica insatisfecha ni de barreras causales.** El modelo histórico de boosting alcanzó AP **0,339** frente a **0,211** por prevalencia en la prueba interna; su discriminación es moderada y no se validó en otra época. La auditoría de variantes no encontró evidencia suficiente para reemplazarlo.

## Continuar el trabajo

1. Ejecute las pruebas desde la raíz: `python -m ml_salud.pruebas` y `python -m dash_salud.pruebas` con las dependencias de sus respectivos `requirements.txt`.
2. Para levantar el tablero local, ejecute `python -m dash_salud.app` y abra `http://127.0.0.1:8050/`. El tablero puede funcionar con los JSON agregados incluidos, sin CSV individuales.
3. Si desea regenerar el entrenamiento o los agregados, descargue los tres CSV del CNPV 2018 para el departamento 08 desde el [DANE](https://microdatos.dane.gov.co/catalog/643) y pase su carpeta con `--data-dir`, siguiendo cada README. Las huellas SHA-256 del experimento impiden mezclar fuentes diferentes.
4. La **decisión pendiente** es encontrar una pregunta predictiva con utilidad real. Antes de cambiar la etiqueta o rehacer el Dash, compruebe si una fuente que observe razones de no atención y barreras ofrece suficiente muestra en Atlántico; la [ECV 2025 del DANE](https://microdatos.dane.gov.co/index.php/catalog/905) es una candidata para esa auditoría. No se ha probado aquí su viabilidad ni comparabilidad con el censo. Evite presentar la etiqueta actual como denegación de atención o usar el modelo para decisiones sobre personas actuales.

Los microdatos originales, entornos virtuales y cachés no están incluidos. Los archivos `*.joblib` son artefactos de modelos entrenados; cárguelos solo desde una fuente confiable y con versiones compatibles de Python y scikit-learn.

## Material anterior

`EDA_acceso_salud_Atlantico_CNPV2018.ipynb`, `dashboard/`, `docs/` y el `Dockerfile` de la raíz conservan la entrega previa de Jupyter Book y Dash Python. No son el punto de entrada del tablero actual. El servicio anterior `eda-salud-atlantico-python` y el servicio `dash` no se modifican desde los scripts del tablero vigente.
