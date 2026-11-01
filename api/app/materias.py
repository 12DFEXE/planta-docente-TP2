"""Lógica de materias: alta y consulta, con su cobertura calculada.

La "cobertura" dice si la materia ya tiene docentes asignados por todas sus
horas semanales. Se calcula con una regla en Python, no con IA.
"""
import sqlite3
from typing import Optional

from .database import get_connection
from .errores import Conflicto, NoEncontrado
from .schemas import MateriaCrear


class MateriaNoEncontrada(NoEncontrado):
    """La materia pedida no existe."""


class MateriaDuplicada(Conflicto):
    """Ya existe una materia con ese nombre."""


# Trae cada materia junto con la suma de horas que ya tiene asignadas.
# LEFT JOIN: incluye también las materias que todavía no tienen ninguna asignación.
_CONSULTA_BASE = """
    SELECT m.id, m.nombre, m.area, m.horas_semanales,
           COALESCE(SUM(a.horas), 0) AS horas_asignadas
    FROM materias m
    LEFT JOIN asignaciones a ON a.materia_id = m.id
"""


def _armar_materia(fila: sqlite3.Row) -> dict:
    """Convierte la fila en diccionario y calcula si está cubierta (regla de negocio)."""
    materia = dict(fila)
    materia["cubierta"] = materia["horas_asignadas"] >= materia["horas_semanales"]
    return materia


def crear_materia(datos: MateriaCrear) -> dict:
    """Da de alta una materia y la devuelve."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO materias (nombre, area, horas_semanales) VALUES (?, ?, ?)",
                (datos.nombre.strip(), datos.area.strip(), datos.horas_semanales),
            )
            nuevo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise MateriaDuplicada(f"Ya existe una materia llamada '{datos.nombre}'")
    return obtener_materia(nuevo_id)


def obtener_materia(materia_id: int) -> dict:
    """Busca una materia por id. Si no existe, lanza MateriaNoEncontrada."""
    with get_connection() as conn:
        fila = conn.execute(
            _CONSULTA_BASE + " WHERE m.id = ? GROUP BY m.id", (materia_id,)
        ).fetchone()
    if fila is None:
        raise MateriaNoEncontrada(f"No existe una materia con id {materia_id}")
    return _armar_materia(fila)


def listar_materias(area: Optional[str] = None, sin_cobertura: bool = False) -> list[dict]:
    """Lista materias. Con sin_cobertura=True devuelve solo las que les faltan horas."""
    consulta = _CONSULTA_BASE
    parametros: list = []
    if area:
        consulta += " WHERE LOWER(m.area) LIKE ?"
        parametros.append(f"%{area.lower()}%")
    consulta += " GROUP BY m.id ORDER BY m.nombre"

    with get_connection() as conn:
        filas = conn.execute(consulta, parametros).fetchall()

    materias = [_armar_materia(f) for f in filas]
    if sin_cobertura:
        materias = [m for m in materias if not m["cubierta"]]
    return materias
