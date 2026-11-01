# Asistente del proyecto

Responde preguntas sobre los datos, los indicadores, la metodología, los resultados y los límites del análisis. Vive en el servidor del Dash (`/api/asistente`) y Shiny usa el mismo servicio, con el mismo widget (`assets/asistente.js`).

## Fuentes

`data/conocimiento.json` reúne 188 pasajes, generados con `python -m dash_salud.generar_conocimiento`:

- Textos y tablas agregadas de `contenido.json`.
- Métricas del modelo validado en `modelo.json`.
- Prosa del informe en `informe/`. Sus tablas se omiten porque no siempre pasan por el redondeo de las aplicaciones.
- Respuestas de referencia a las preguntas más comunes, con cifras leídas de esos mismos archivos.

Si cambia el informe o el contenido, hay que regenerarlo.

## Modos

| Modo | Cuándo | Qué hace |
|:--|:--|:--|
| Demostración | Sin clave | Extrae frases de los pasajes recuperados. No usa ningún modelo de lenguaje. La interfaz lo indica |
| Conectado | Con `ANTHROPIC_API_KEY` | Claude redacta solo con esos pasajes y cita cada afirmación |

Si la llamada falla, llega al tope diario o la redacción trae una cifra que no está en las fuentes, se descarta y se vuelve al modo de demostración con un aviso.

## Reglas

- Las cifras de filtros y municipios las calcula el servidor con las funciones de la aplicación. Una cifra oculta no llega al modelo.
- Los filtros recibidos se validan contra los valores permitidos.
- No hace predicciones ni da orientación sobre personas concretas.
- Si no hay evidencia en una misma frase, responde que no encuentra la información.

## Activar el modo conectado

Hace falta una clave de la API de Anthropic. En Cloud Run conviene guardarla en Secret Manager:

```bash
printf "%s" "LA_CLAVE" | gcloud secrets create anthropic-api-key --data-file=-
gcloud run services update dataviz-salud-atlantico --region us-east1 --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest
```

Variables opcionales: `ASISTENTE_MODELO` (por defecto `claude-opus-5-5`), `ASISTENTE_TOPE_DIARIO` (200 por proceso) y `ASISTENTE_ORIGENES`. Con el modelo por defecto, cada respuesta usa unos pocos miles de tokens de entrada y unos cientos de salida.

## Pruebas

`python -m dash_salud.pruebas_asistente` no usa red ni clave. Comprueba fuentes, preguntas sin respuesta, protección, límites y el modo conectado con un cliente simulado.
