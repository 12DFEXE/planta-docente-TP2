"""Punto de entrada de la API de Planta Docente.

Por ahora solo expone /health para verificar que el contenedor levanta.
Los endpoints reales se agregan en el Paso 3.
"""
from fastapi import FastAPI

app = FastAPI(
    title="API Planta Docente",
    description="Gestión de planta docente con IA y automatizaciones n8n",
    version="0.1.0",
)


@app.get("/health")
def health():
    """Chequeo simple de estado: lo usan Streamlit y n8n para saber si la API está viva."""
    return {"status": "ok"}
