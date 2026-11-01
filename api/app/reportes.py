"""Reporte de la planta docente: números calculados con reglas + texto redactado por IA.

La respuesta separa explícitamente las dos cosas:
  - "indicadores": calculados en Python (exactos).
  - "resumen_ia":  redactado por la IA a partir de esos números (hay que revisarlo).
"""
from datetime import datetime

from . import ia, indicadores


def generar_reporte() -> dict:
    datos = indicadores.calcular_indicadores()
    texto = ia.redactar_reporte(datos)
    return {
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "indicadores": datos,
        "resumen_ia": texto,
        "modelo_ia": ia.OLLAMA_MODEL,
        # Campo pensado para la decisión (IF) del workflow de n8n
        "hay_materias_sin_cobertura": len(datos["materias_sin_cobertura"]) > 0,
    }
