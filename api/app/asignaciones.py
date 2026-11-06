"""Lógica de asignaciones: vincular un docente con una materia.

Antes de guardar, se verifican las REGLAS DE NEGOCIO (todas en Python, sin IA):
  1. El docente y la materia tienen que existir.
  2. El docente tiene que estar activo (no pendiente de revisión).
  3. No se puede asignar dos veces el mismo docente a la misma materia.
  4. Las horas no pueden superar las horas que le faltan cubrir a la materia.
  5. El docente no puede superar el tope de horas según su dedicación.

Renovar una designación también tiene reglas:
  - La asignación tiene que existir.
  - El docente tiene que seguir activo.
  - La nueva fecha tiene que ser posterior a hoy y a la fecha actual de vencimiento.
"""
from typing import Optional

from . import docentes, materias
from .database import get_connection
from .errores import Conflicto, NoEncontrado
from .schemas import AsignacionCrear, AsignacionRenovar

# Tope de horas semanales que puede sumar un docente según su dedicación
TOPE_HORAS = {
    "simple": 10,
    "semiexclusiva": 20,
    "exclusiva": 40,
}


class ReglaIncumplida(Conflicto):
    """La asignación rompe alguna regla de negocio."""


class AsignacionNoEncontrada(NoEncontrado):
    """La asignación pedida no existe."""


_CONSULTA_BASE = """
    SELECT a.id, a.docente_id, d.nombre AS docente_nombre,
           a.materia_id, m.nombre AS materia_nombre,
           a.dedicacion, a.horas, a.fecha_vencimiento
    FROM asignaciones a
    JOIN docentes d ON d.id = a.docente_id
    JOIN materias m ON m.id = a.materia_id
"""


def horas_del_docente(docente_id: int) -> int:
    """Suma las horas que el docente ya tiene asignadas."""
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT COALESCE(SUM(horas), 0) AS total FROM asignaciones WHERE docente_id = ?",
            (docente_id,),
        ).fetchone()
    return fila["total"]


def crear_asignacion(datos: AsignacionCrear) -> dict:
    """Valida las reglas de negocio y, si todo está bien, guarda la asignación."""
    # Reglas 1 y 2: existencia y estado (si no existen, estas funciones lanzan NoEncontrado)
    docente = docentes.obtener_docente(datos.docente_id)
    materia = materias.obtener_materia(datos.materia_id)

    if docente["estado"] != "activo":
        raise ReglaIncumplida(
            f"{docente['nombre']} está pendiente de revisión: hay que confirmarlo antes de asignarle materias"
        )

    # Regla 3: asignación repetida
    with get_connection() as conn:
        repetida = conn.execute(
            "SELECT 1 FROM asignaciones WHERE docente_id = ? AND materia_id = ?",
            (datos.docente_id, datos.materia_id),
        ).fetchone()
    if repetida:
        raise ReglaIncumplida(f"{docente['nombre']} ya está asignado/a a {materia['nombre']}")

    # Regla 4: no pasarse de las horas que necesita la materia
    horas_faltantes = materia["horas_semanales"] - materia["horas_asignadas"]
    if datos.horas > horas_faltantes:
        raise ReglaIncumplida(
            f"{materia['nombre']} solo necesita {horas_faltantes} hora(s) más y se pidieron {datos.horas}"
        )

    # Regla 5: tope de horas del docente según dedicación
    tope = TOPE_HORAS[datos.dedicacion.value]
    total = horas_del_docente(datos.docente_id) + datos.horas
    if total > tope:
        raise ReglaIncumplida(
            f"{docente['nombre']} quedaría con {total} h semanales y el tope para dedicación "
            f"{datos.dedicacion.value} es {tope} h"
        )

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO asignaciones (docente_id, materia_id, dedicacion, horas, fecha_vencimiento)
               VALUES (?, ?, ?, ?, ?)""",
            (
                datos.docente_id,
                datos.materia_id,
                datos.dedicacion.value,
                datos.horas,
                datos.fecha_vencimiento.isoformat(),
            ),
        )
        nuevo_id = cursor.lastrowid

    with get_connection() as conn:
        fila = conn.execute(_CONSULTA_BASE + " WHERE a.id = ?", (nuevo_id,)).fetchone()
    return dict(fila)


def listar_asignaciones(
    docente_id: Optional[int] = None, materia_id: Optional[int] = None
) -> list[dict]:
    """Lista asignaciones, opcionalmente filtradas por docente o por materia."""
    consulta = _CONSULTA_BASE + " WHERE 1=1"
    parametros: list = []
    if docente_id:
        consulta += " AND a.docente_id = ?"
        parametros.append(docente_id)
    if materia_id:
        consulta += " AND a.materia_id = ?"
        parametros.append(materia_id)
    consulta += " ORDER BY a.fecha_vencimiento"

    with get_connection() as conn:
        filas = conn.execute(consulta, parametros).fetchall()
    return [dict(f) for f in filas]


def obtener_asignacion(asignacion_id: int) -> dict:
    """Busca una asignación por id. Si no existe, lanza AsignacionNoEncontrada (404)."""
    with get_connection() as conn:
        fila = conn.execute(_CONSULTA_BASE + " WHERE a.id = ?", (asignacion_id,)).fetchone()
    if fila is None:
        raise AsignacionNoEncontrada(f"No existe una asignación con id {asignacion_id}")
    return dict(fila)


def renovar_asignacion(asignacion_id: int, datos: AsignacionRenovar) -> dict:
    """Extiende la fecha de vencimiento de una designación (por ejemplo, después
    de que n8n avisó que estaba por vencer). Valida las reglas antes de guardar."""
    asignacion = obtener_asignacion(asignacion_id)
    docente = docentes.obtener_docente(asignacion["docente_id"])

    if docente["estado"] != "activo":
        raise ReglaIncumplida(
            f"{docente['nombre']} no está activo/a: no se puede renovar su designación"
        )

    fecha_actual = asignacion["fecha_vencimiento"]  # viene como texto 'AAAA-MM-DD'
    nueva_fecha = datos.fecha_vencimiento.isoformat()
    if nueva_fecha <= fecha_actual:  # el formato ISO se puede comparar como texto
        raise ReglaIncumplida(
            f"La nueva fecha ({nueva_fecha}) tiene que ser posterior al vencimiento actual ({fecha_actual})"
        )

    with get_connection() as conn:
        conn.execute(
            "UPDATE asignaciones SET fecha_vencimiento = ? WHERE id = ?",
            (nueva_fecha, asignacion_id),
        )
    return obtener_asignacion(asignacion_id)
