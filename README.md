# EDA de acceso a atención formal en salud en el Atlántico

Autores: Alejandro Carvajal y Mateo Chang

Este proyecto describe el acceso a atención formal entre las personas registradas en los microdatos anonimizados del CNPV 2018 para el Atlántico que reportaron un problema de salud en los 30 días previos y cuyo acceso pudo clasificarse. La respuesta se construye a partir del tratamiento principal y, para quienes acudieron a su entidad de seguridad social, la confirmación de atención. El análisis es descriptivo y no establece causas ni diferencias inferenciales.

El procedimiento y los resultados están en [el cuaderno](EDA_acceso_salud_Atlantico_CNPV2018.ipynb). Para la entrega al profesor:

- **Jupyter Book:** <https://acarvajalb21.github.io/EDAPYTHON/>
- **Dash Python:** <https://eda-salud-atlantico-python-409319239507.us-east1.run.app/>

El [dashboard interactivo](dashboard/README.md) en Plotly Dash permite seleccionar cada municipio, comparar acceso y no acceso, revisar desgloses por grupo y descargar datos agregados. Se publica en Google Cloud Run y se actualiza desde `main` mediante Cloud Build.

## Estructura

- `EDA_acceso_salud_Atlantico_CNPV2018.ipynb`: metodología, diccionario, análisis, figuras y conclusión.
- `datos/README.md`: archivos censales necesarios para reejecutar y procedencia de la capa geográfica.
- `datos/mgn2018_municipios_atlantico.geojson`: 23 polígonos municipales del MGN integrado 2018 del DANE.
- `figuras/`: nueve imágenes regeneradas con los microdatos departamentales. `09_mapa_acceso_municipal.png` usa la geometría oficial del DANE y las tasas municipales recalculadas.
- `salidas/`: descripción de la base analítica exportada; el CSV por persona no se distribuye.
- `dashboard/`: aplicación Plotly Dash y tablas agregadas calculadas desde el cuaderno Python.
- `docs/`: Jupyter Book estático listo para GitHub Pages.
- `ejecutar_eda.py`: ejecución completa del cuaderno en un kernel limpio y guardado de las salidas.
- `validar_ejecucion_sintetica.py`: prueba de ejecución con datos ficticios, sin modificar las salidas reales.

## Reejecución

Los tres CSV indicados en `datos/README.md` están disponibles en la carpeta local original del EDA y se excluyen de este repositorio. El cuaderno se reejecutó de principio a fin con esos archivos el 1 de octubre de 2026. La configuración del libro conserva las salidas y no reejecuta el cuaderno durante la publicación.

Para repetir el cálculo desde un kernel limpio, active el entorno Python del proyecto (`ml_venv` en VS Code) o instale `requirements.txt` y ejecute:

```powershell
python ejecutar_eda.py
```

`python validar_eda.py` comprueba estructura, ejecución y archivos generados. `python validar_ejecucion_sintetica.py` prueba el flujo con datos ficticios.

Para construir el libro localmente:

```bash
python -m pip install -r requirements.txt
jupyter-book build .
```

## Cifras de control de la ejecución verificada

- Personas en archivo departamental: 2.342.265.
- Reportaron problema de salud: 136.114.
- Respuesta clasificable: 136.034.
- Accedió a atención formal: 107.384 (78,94 %).
- No accedió: 28.650 (21,06 %).
- Diferencia por dificultad funcional estandarizada por edad: 4,25 puntos porcentuales.

Fuentes: [diccionario del CNPV 2018](https://microdatos.dane.gov.co/index.php/catalog/643/data-dictionary) y [capa municipal del MGN integrado 2018](https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2018/Serv_CapaMunicipiosInt_2018/MapServer/0).
