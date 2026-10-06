# Datos para reejecutar el análisis

Coloque aquí los siguientes microdatos departamentales del CNPV 2018 del DANE:

- `CNPV2018_5PER_A2_08.CSV`: personas; contiene salud, edad, sexo y municipio.
- `CNPV2018_2HOG_A2_08.CSV`: hogares; contiene cuartos y personas del hogar.
- `CNPV2018_1VIV_A2_08.CSV`: viviendas; contiene estrato.

Los tres CSV requeridos están presentes localmente y permitieron reejecutar el cuaderno el 1 de octubre de 2026. `.gitignore` excluye estos microdatos del repositorio. `CNPV2018_MGN_A2_08.CSV` también está disponible, pero es opcional para este cuaderno; `CNPV2018_3FALL_A2_08.CSV` no se utiliza.

`mgn2018_municipios_atlantico.geojson` se obtuvo de la [capa Municipios del MGN integrado 2018 del DANE](https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2018/Serv_CapaMunicipiosInt_2018/MapServer/0), filtrando `DPTO_CCDGO='08'` y solicitando los campos `DPTO_CCDGO`, `MPIO_CCDGO` y `MPIO_CNMBR` con geometría GeoJSON en EPSG:4326. Contiene 23 polígonos con códigos únicos que coinciden con el diccionario municipal del cuaderno. La unión con los microdatos se valida al ejecutar la celda del mapa.
