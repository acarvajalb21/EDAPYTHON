"""Verifica el asistente sin red: fuentes, protección, límites y modo conectado simulado."""

from __future__ import annotations

import os
from types import SimpleNamespace

from dash_salud import asistente as modulo
from dash_salud.app import EDA, app, asistente, consulta_municipio, resumen_asistente

CON_RESPUESTA = [
    ("¿Qué significa estar fuera de la ruta formal?", "no significa que les negaran la atención"),
    ("¿Por qué algunos porcentajes se ocultan?", "oculta"),
    ("¿Qué es la V de Cramér?", "asociación"),
    ("¿Qué mide la precisión promedio?", "qué tan arriba"),
    ("¿Cuántas personas se estudiaron?", "136.034"),
    ("¿Por qué no hay valores p?", "muestra aleatoria"),
    ("¿Qué es la dificultad funcional?", "dificultad"),
    ("¿Qué variables usa el modelo?", "variables"),
    ("¿Qué tan bueno es el modelo?", "moderada"),
    ("¿Cuáles son las limitaciones del análisis?", "2018"),
]
SIN_RESPUESTA = ["¿Quién ganó el mundial de fútbol?", "¿Cuál es la capital de Francia?", "Recomiéndame una receta de arroz",
                 "¿Cuánto costó el censo?"]


class ClienteFalso:
    """Imita la forma de la respuesta del SDK."""

    def __init__(self, texto, stop_reason="end_turn"):
        self.llamadas = []
        self.texto, self.stop_reason = texto, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.llamadas.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=self.texto)])


def run() -> None:
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert asistente.modo() == "demostracion"
    for pregunta, esperado in CON_RESPUESTA:
        r = asistente.responder(pregunta)
        assert not r["sin_respuesta"], pregunta
        assert r["modo"] == "demostracion" and r["fuentes"], pregunta
        assert esperado.lower() in r["respuesta"].lower(), (pregunta, r["respuesta"][:200])
    for pregunta in SIN_RESPUESTA:
        r = asistente.responder(pregunta)
        assert r["sin_respuesta"] and not r["fuentes"], (pregunta, r["respuesta"][:120])

    # Una persona concreta nunca recibe una predicción.
    for pregunta in ("¿Qué hará una persona de 70 años?", "Predice para mi mamá si la van a atender", "¿Cuál es mi riesgo?"):
        r = asistente.responder(pregunta)
        assert "No puedo hacer predicciones" in r["respuesta"], pregunta

    # Los municipios usan solo el panorama publicado.
    malambo = next(m for m in EDA["municipal_overview"] if m["municipio"] == "Malambo")
    assert "28,8" in asistente.responder("¿Cuál es el porcentaje en Malambo?")["respuesta"]
    assert malambo["n"] == 8320
    assert "no se publica" in asistente.responder("¿Cuál es el porcentaje en Piojó?")["respuesta"]

    # Filtros: la cifra sale de las reglas y una selección oculta no enuncia porcentaje.
    assert "No tienes filtros activos" in asistente.responder("¿Qué dicen mis filtros?")["respuesta"]
    visible = asistente.responder("¿Qué muestra esta selección?", {"municipios": ["Malambo"]})
    assert visible["filtros"] and "29,1" in visible["filtros"]["texto"]
    oculta = asistente.responder("¿Qué muestra esta selección?", {"municipios": ["Usiacurí"]})
    assert "%" not in oculta["filtros"]["texto"] and "oculta" in oculta["filtros"]["texto"]
    vacia = resumen_asistente({"sexo": "Mujer", "edad": "0–19", "zona": "Centros poblados y rural disperso", "dificultad": "Con dificultad funcional"})
    assert "%" not in vacia["texto"]
    # Un filtro manipulado se ignora.
    assert not resumen_asistente({"sexo": "<script>", "edad": "x", "municipios": ["Inventado"]})["activo"]

    # Modo conectado simulado.
    falso = ClienteFalso("Es una clasificación de la acción principal, con 21,06 % [1].")
    conectado = modulo.Asistente(resumen_asistente, consulta_municipio, ["Malambo"], cliente=falso)
    r = conectado.responder("¿Qué significa estar fuera de la ruta formal?")
    assert r["modo"] == "conectado" and "[1]" in r["respuesta"]
    llamada = falso.llamadas[0]
    assert llamada["model"] == "claude-opus-5-5" and llamada["fallbacks"] == "default"
    assert "<fuentes>" in llamada["messages"][0]["content"] and "No uses conocimiento externo" in llamada["system"]

    inventada = modulo.Asistente(resumen_asistente, consulta_municipio, ["Malambo"], cliente=ClienteFalso("Son 47.123 personas [1]."))
    r = inventada.responder("¿Qué significa estar fuera de la ruta formal?")
    assert r["modo"] == "demostracion" and "47.123" not in r["respuesta"] and "sin fuente" in r["aviso"]

    rechazo = modulo.Asistente(resumen_asistente, consulta_municipio, ["Malambo"], cliente=ClienteFalso("", "refusal"))
    assert rechazo.responder("¿Qué significa estar fuera de la ruta formal?")["modo"] == "demostracion"

    # Límites del servicio.
    cliente = app.server.test_client()
    assert cliente.get("/api/asistente/estado").json["modo"] == "demostracion"
    assert cliente.post("/api/asistente", json={"pregunta": ""}).status_code == 400
    assert cliente.post("/api/asistente", json={"pregunta": "x" * 501}).status_code == 400
    ok = cliente.post("/api/asistente", json={"pregunta": "¿Qué es la ruta formal?", "filtros": {}}, headers={"Origin": "http://localhost:8060"})
    assert ok.status_code == 200 and ok.headers["Access-Control-Allow-Origin"] == "http://localhost:8060"
    ajeno = cliente.post("/api/asistente", json={"pregunta": "¿Qué es la ruta formal?"}, headers={"Origin": "https://ajeno.example"})
    assert "Access-Control-Allow-Origin" not in ajeno.headers
    print("Asistente: verificaciones satisfactorias")


if __name__ == "__main__":
    run()
