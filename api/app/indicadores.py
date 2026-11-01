"""Indicadores y alertas de la planta docente.

Este módulo NO guarda nada: solo LEE los datos y los ANALIZA.
Todos los cálculos son reglas de programación en Python (sumas, promedios,
porcentajes, comparación de fechas). No interviene la IA.

Lo usan:
  - La pantalla (Streamlit) para mostrar el tablero.
  - n8n para el reporte semanal y las alertas de vencimiento.
"""
from datetime import date, timedelta

from . import materias
from .database import get_connection

# Títulos que cuentan como posgrado
TITULOS_POSGRADO = {"especializacion", "maestria", "doctorado"}


def _porcentaje(parte: float, total: float) -> float:
    """Calcula un porcentaje con 1 decimal, evitando dividir por cero."""
    return round(parte * 100 / total, 1) if total else 0.0


def calcular_indicadores() -> dict:
    """Arma todos los indicadores de la planta docente."""
    with get_connection() as conn:
        docentes = [dict(f) for f in conn.execute("SELECT id, estado, titulo_maximo FROM docentes")]
        asignaciones = [dict(f) for f in conn.execute("SELECT docente_id, dedicacion, horas FROM asignaciones")]

    # --- Docentes ---
    activos = [d for d in docentes if d["estado"] == "activo"]
    pendientes = [d for d in docentes if d["estado"] == "pendiente_revision"]

    por_titulo = {"grado": 0, "especializacion": 0, "maestria": 0, "doctorado": 0}
    for d in activos:
        por_titulo[d["titulo_maximo"]] += 1
    con_posgrado = sum(1 for d in activos if d["titulo_maximo"] in TITULOS_POSGRADO)

    # --- Horas y dedicaciones ---
    horas_por_docente: dict[int, int] = {}
    por_dedicacion = {"simple": 0, "semiexclusiva": 0, "exclusiva": 0}
    for a in asignaciones:
        horas_por_docente[a["docente_id"]] = horas_por_docente.get(a["docente_id"], 0) + a["horas"]
        por_dedicacion[a["dedicacion"]] += 1

    horas_totales = sum(horas_por_docente.values())
    sin_asignacion = sum(1 for d in activos if d["id"] not in horas_por_docente)

    # --- Materias y cobertura ---
    todas = materias.listar_materias()
    horas_requeridas = sum(m["horas_semanales"] for m in todas)
    # min(...) para que una materia con horas de más no "tape" a otra que le faltan
    horas_cubiertas = sum(min(m["horas_asignadas"], m["horas_semanales"]) for m in todas)
    sin_cobertura = [
        {
            "id": m["id"],
            "nombre": m["nombre"],
            "horas_faltantes": m["horas_semanales"] - m["horas_asignadas"],
        }
        for m in todas
        if not m["cubierta"]
    ]

    return {
        "docentes_total": len(docentes),
        "docentes_activos": len(activos),
        "docentes_pendientes_revision": len(pendientes),
        "docentes_sin_asignacion": sin_asignacion,
        "docentes_por_titulo": por_titulo,
        "porcentaje_posgrado": _porcentaje(con_posgrado, len(activos)),
        "horas_totales_asignadas": horas_totales,
        "promedio_horas_por_docente": round(horas_totales / len(activos), 1) if activos else 0.0,
        "asignaciones_por_dedicacion": por_dedicacion,
        "materias_total": len(todas),
        "porcentaje_cobertura_horas": _porcentaje(horas_cubiertas, horas_requeridas),
        "materias_sin_cobertura": sin_cobertura,
    }


def alertas_vencimiento(dias: int = 30) -> dict:
    """Busca asignaciones vencidas o que vencen dentro de los próximos `dias` días."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    with get_connection() as conn:
        filas = conn.execute(
            """SELECT a.id, d.nombre AS docente_nombre, d.email AS docente_email,
                      m.nombre AS materia_nombre, a.dedicacion, a.fecha_vencimiento
               FROM asignaciones a
               JOIN docentes d ON d.id = a.docente_id
               JOIN materias m ON m.id = a.materia_id
               WHERE a.fecha_vencimiento <= ?
               ORDER BY a.fecha_vencimiento""",
            (limite.isoformat(),),
        ).fetchall()

    alertas = []
    for fila in filas:
        alerta = dict(fila)
        vencimiento = date.fromisoformat(alerta["fecha_vencimiento"])
        alerta["dias_restantes"] = (vencimiento - hoy).days
        alerta["estado"] = "vencida" if vencimiento < hoy else "por_vencer"
        alertas.append(alerta)

    return {
        "fecha_consulta": hoy.isoformat(),
        "dias": dias,
        "cantidad": len(alertas),
        "alertas": alertas,
    }
