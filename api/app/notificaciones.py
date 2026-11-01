"""Notificaciones del sistema.

Los workflows de n8n dejan acá sus avisos (CV procesado, vencimientos, reportes)
y la pantalla los muestra. Así las automatizaciones se ven dentro del sistema
sin necesidad de configurar un servidor de email.
"""
from typing import Optional

from .database import get_connection
from .errores import NoEncontrado
from .schemas import NotificacionCrear


class NotificacionNoEncontrada(NoEncontrado):
    """La notificación pedida no existe."""


def _a_dict(fila) -> dict:
    notificacion = dict(fila)
    notificacion["leida"] = bool(notificacion["leida"])
    return notificacion


def crear_notificacion(datos: NotificacionCrear) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notificaciones (origen, nivel, titulo, mensaje) VALUES (?, ?, ?, ?)",
            (datos.origen.strip(), datos.nivel.value, datos.titulo.strip(), datos.mensaje.strip()),
        )
        nuevo_id = cursor.lastrowid
    return obtener_notificacion(nuevo_id)


def obtener_notificacion(notificacion_id: int) -> dict:
    with get_connection() as conn:
        fila = conn.execute("SELECT * FROM notificaciones WHERE id = ?", (notificacion_id,)).fetchone()
    if fila is None:
        raise NotificacionNoEncontrada(f"No existe una notificación con id {notificacion_id}")
    return _a_dict(fila)


def listar_notificaciones(solo_no_leidas: bool = False, limite: int = 50) -> list[dict]:
    consulta = "SELECT * FROM notificaciones"
    if solo_no_leidas:
        consulta += " WHERE leida = 0"
    consulta += " ORDER BY id DESC LIMIT ?"
    with get_connection() as conn:
        filas = conn.execute(consulta, (limite,)).fetchall()
    return [_a_dict(f) for f in filas]


def marcar_leida(notificacion_id: int) -> dict:
    obtener_notificacion(notificacion_id)  # si no existe, lanza 404
    with get_connection() as conn:
        conn.execute("UPDATE notificaciones SET leida = 1 WHERE id = ?", (notificacion_id,))
    return obtener_notificacion(notificacion_id)
