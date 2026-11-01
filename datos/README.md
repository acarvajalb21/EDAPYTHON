# Datos para reejecutar el análisis

Coloque aquí los siguientes microdatos departamentales del CNPV 2018 del DANE:

- `CNPV2018_5PER_A2_08.CSV`: personas; contiene salud, edad, sexo y municipio.
- `CNPV2018_2HOG_A2_08.CSV`: hogares; contiene cuartos y personas del hogar.
- `CNPV2018_1VIV_A2_08.CSV`: viviendas; contiene estrato.

Estos microdatos **no se incluyen** en el repositorio: `.gitignore` los excluye. Se descargan del [catálogo del CNPV 2018 del DANE](https://microdatos.dane.gov.co/catalog/643) (departamento 08). El cuaderno se reejecutó con ellos el 1 de octubre de 2026; sin los CSV, `ejecutar_eda.py` se detiene indicando los archivos que faltan. `CNPV2018_MGN_A2_08.CSV` es opcional para este cuaderno y `CNPV2018_3FALL_A2_08.CSV` no se utiliza.

`mgn2018_municipios_atlantico.geojson` se obtuvo de la [capa Municipios del MGN integrado 2018 del DANE](https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2018/Serv_CapaMunicipiosInt_2018/MapServer/0), filtrando `DPTO_CCDGO='08'` y solicitando los campos `DPTO_CCDGO`, `MPIO_CCDGO` y `MPIO_CNMBR` con geometría GeoJSON en EPSG:4326. Contiene 23 polígonos con códigos únicos que coinciden con el diccionario municipal del cuaderno. La unión con los microdatos se valida al ejecutar la celda del mapa.
