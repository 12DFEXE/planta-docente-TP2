"""Lógica de negocio de docentes: crear, listar, buscar y actualizar.

Este módulo NO sabe nada de HTTP ni de FastAPI: solo trabaja con datos y la base.
Si algo sale mal, lanza una excepción propia y main.py decide qué error HTTP devolver.
Así la lógica queda separada de la interfaz, como pide el TP.
"""
import json
import sqlite3
from typing import Optional

from .database import get_connection
from .errores import Conflicto, NoEncontrado
from .schemas import DocenteActualizar, DocenteCrear


# ---------- Excepciones propias ----------
# Heredan de las genéricas de errores.py, así main.py sabe qué código HTTP devolver.

class DocenteNoEncontrado(NoEncontrado):
    """El docente pedido no existe."""


class EmailDuplicado(Conflicto):
    """Ya hay otro docente con ese email."""


# ---------- Funciones auxiliares ----------

def _fila_a_dict(fila: sqlite3.Row) -> dict:
    """Convierte una fila de la base en un diccionario.
    Las áreas se guardan como texto JSON y acá se vuelven a convertir en lista."""
    docente = dict(fila)
    docente["areas"] = json.loads(docente["areas"])
    return docente


def _normalizar_areas(areas: list[str]) -> list[str]:
    """Limpia la lista de áreas: saca espacios, vacíos y repetidos."""
    vistas = []
    for area in areas:
        limpia = area.strip()
        if limpia and limpia.lower() not in [a.lower() for a in vistas]:
            vistas.append(limpia)
    return vistas


# ---------- Operaciones ----------

def crear_docente(datos: DocenteCrear, origen: str = "manual", estado: str = "activo") -> dict:
    """Da de alta un docente y lo devuelve con su id asignado."""
    areas = _normalizar_areas(datos.areas)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO docentes
                   (nombre, email, titulo_maximo, areas, anios_experiencia, estado, origen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    datos.nombre.strip(),
                    datos.email.lower().strip(),
                    datos.titulo_maximo.value,
                    json.dumps(areas, ensure_ascii=False),
                    datos.anios_experiencia,
                    estado,
                    origen,
                ),
            )
            nuevo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # La columna email es UNIQUE: la base rechaza el duplicado
        raise EmailDuplicado(f"Ya existe un docente con el email {datos.email}")
    return obtener_docente(nuevo_id)


def obtener_docente(docente_id: int) -> dict:
    """Busca un docente por id. Si no existe, lanza DocenteNoEncontrado."""
    with get_connection() as conn:
        fila = conn.execute("SELECT * FROM docentes WHERE id = ?", (docente_id,)).fetchone()
    if fila is None:
        raise DocenteNoEncontrado(f"No existe un docente con id {docente_id}")
    return _fila_a_dict(fila)


def listar_docentes(
    area: Optional[str] = None,
    titulo: Optional[str] = None,
    estado: Optional[str] = None,
    texto: Optional[str] = None,
) -> list[dict]:
    """Lista docentes aplicando los filtros que vengan (todos son opcionales)."""
    consulta = "SELECT * FROM docentes WHERE 1=1"
    parametros: list = []

    if titulo:
        consulta += " AND titulo_maximo = ?"
        parametros.append(titulo)
    if estado:
        consulta += " AND estado = ?"
        parametros.append(estado)
    if texto:
        consulta += " AND (LOWER(nombre) LIKE ? OR LOWER(email) LIKE ?)"
        parametros += [f"%{texto.lower()}%", f"%{texto.lower()}%"]

    consulta += " ORDER BY nombre"

    with get_connection() as conn:
        filas = conn.execute(consulta, parametros).fetchall()

    docentes = [_fila_a_dict(f) for f in filas]

    # El filtro por área se hace en Python porque las áreas están guardadas como lista
    if area:
        docentes = [
            d for d in docentes
            if any(area.lower() in a.lower() for a in d["areas"])
        ]
    return docentes


def actualizar_docente(docente_id: int, cambios: DocenteActualizar) -> dict:
    """Modifica solo los campos que vienen en 'cambios'."""
    obtener_docente(docente_id)  # si no existe, lanza DocenteNoEncontrado

    datos = cambios.model_dump(exclude_none=True)
    if not datos:
        return obtener_docente(docente_id)  # no hay nada para cambiar

    # Preparar cada valor en el formato en que se guarda en la base
    if "areas" in datos:
        datos["areas"] = json.dumps(_normalizar_areas(datos["areas"]), ensure_ascii=False)
    if "email" in datos:
        datos["email"] = datos["email"].lower().strip()
    for campo in ("titulo_maximo", "estado"):
        if campo in datos:
            datos[campo] = datos[campo].value

    columnas = ", ".join(f"{campo} = ?" for campo in datos)
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE docentes SET {columnas} WHERE id = ?",
                [*datos.values(), docente_id],
            )
    except sqlite3.IntegrityError:
        raise EmailDuplicado(f"Ya existe otro docente con el email {cambios.email}")
    return obtener_docente(docente_id)
