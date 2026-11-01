"""Cliente de la API: todas las llamadas de la pantalla a FastAPI pasan por acá.

La pantalla (app.py) nunca usa `requests` directamente: llama a estas funciones.
Así, si cambia una dirección de la API, se cambia en un solo lugar.
"""
import os
from typing import Optional

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")
TIMEOUT = 10      # segundos máximos de espera por respuesta
TIMEOUT_IA = 300  # la IA local puede tardar bastante en una compu sin placa de video


class ApiError(Exception):
    """Error al hablar con la API. Trae un mensaje listo para mostrar al usuario."""


# Nombres de campos tal como los ve el usuario
NOMBRES_CAMPOS = {
    "nombre": "Nombre",
    "email": "Email",
    "titulo_maximo": "Título máximo",
    "areas": "Áreas",
    "anios_experiencia": "Años de experiencia",
    "area": "Área",
    "horas_semanales": "Horas semanales",
    "docente_id": "Docente",
    "materia_id": "Materia",
    "dedicacion": "Dedicación",
    "horas": "Horas",
    "fecha_vencimiento": "Fecha de vencimiento",
    "dias": "Días",
}


def _traducir_error(error: dict) -> str:
    """Traduce un error de validación de Pydantic (en inglés y técnico) a un texto claro."""
    campo = NOMBRES_CAMPOS.get(str(error.get("loc", ["", "?"])[-1]), "Un campo")
    tipo = error.get("type", "")
    ctx = error.get("ctx", {})

    if tipo == "missing":
        return f"{campo}: es obligatorio."
    if tipo == "string_too_short":
        return f"{campo}: tiene que tener al menos {ctx.get('min_length')} caracteres."
    if tipo == "string_too_long":
        return f"{campo}: puede tener como máximo {ctx.get('max_length')} caracteres."
    if tipo == "string_pattern_mismatch":
        return f"{campo}: el formato no es válido."
    if tipo == "greater_than_equal":
        return f"{campo}: tiene que ser {ctx.get('ge')} o más."
    if tipo == "less_than_equal":
        return f"{campo}: tiene que ser {ctx.get('le')} o menos."
    if tipo == "greater_than":
        return f"{campo}: tiene que ser mayor a {ctx.get('gt')}."
    if tipo == "enum":
        return f"{campo}: el valor no está entre las opciones permitidas."
    if tipo == "value_error":
        # Errores de nuestras propias reglas (ej: la fecha tiene que ser futura)
        return f"{campo}: {error.get('msg', '').removeprefix('Value error, ')}."
    return f"{campo}: valor inválido."


def _mensaje_de_error(respuesta: requests.Response) -> str:
    """Convierte la respuesta de error de la API en un texto entendible."""
    try:
        detalle = respuesta.json().get("detail")
    except ValueError:
        return f"Error {respuesta.status_code} de la API"

    # 404 / 409: la API ya manda un texto claro
    if isinstance(detalle, str):
        return detalle

    # 422: Pydantic manda una lista con un error por campo
    if isinstance(detalle, list):
        lineas = [f"• {_traducir_error(error)}" for error in detalle]
        return "Hay datos inválidos:\n" + "\n".join(lineas)

    return f"Error {respuesta.status_code} de la API"


def _llamar(metodo: str, ruta: str, timeout: int = TIMEOUT, **kwargs):
    """Hace la llamada HTTP y devuelve el JSON, o lanza ApiError con un mensaje claro."""
    try:
        respuesta = requests.request(metodo, f"{API_URL}{ruta}", timeout=timeout, **kwargs)
    except requests.exceptions.ConnectionError:
        raise ApiError("No se pudo conectar con la API. ¿Está levantado el contenedor `api`?")
    except requests.exceptions.Timeout:
        raise ApiError("La API tardó demasiado en responder. Probá de nuevo en unos segundos.")

    if respuesta.status_code >= 400:
        raise ApiError(_mensaje_de_error(respuesta))
    return respuesta.json()


def _sin_vacios(params: dict) -> dict:
    """Saca los filtros vacíos para no mandarlos a la API."""
    return {k: v for k, v in params.items() if v not in (None, "", False)}


# ---------------- Sistema ----------------

def health() -> dict:
    return _llamar("GET", "/health")


# ---------------- Docentes ----------------

def listar_docentes(area: str = "", titulo: str = "", estado: str = "", texto: str = "") -> list[dict]:
    params = _sin_vacios({"area": area, "titulo": titulo, "estado": estado, "texto": texto})
    return _llamar("GET", "/docentes", params=params)


def crear_docente(datos: dict) -> dict:
    return _llamar("POST", "/docentes", json=datos)


def actualizar_docente(docente_id: int, cambios: dict) -> dict:
    return _llamar("PUT", f"/docentes/{docente_id}", json=cambios)


# ---------------- Materias ----------------

def listar_materias(area: str = "", sin_cobertura: bool = False) -> list[dict]:
    params = _sin_vacios({"area": area, "sin_cobertura": sin_cobertura})
    return _llamar("GET", "/materias", params=params)


def crear_materia(datos: dict) -> dict:
    return _llamar("POST", "/materias", json=datos)


# ---------------- Asignaciones ----------------

def listar_asignaciones(docente_id: Optional[int] = None, materia_id: Optional[int] = None) -> list[dict]:
    params = _sin_vacios({"docente_id": docente_id, "materia_id": materia_id})
    return _llamar("GET", "/asignaciones", params=params)


def crear_asignacion(datos: dict) -> dict:
    return _llamar("POST", "/asignaciones", json=datos)


# ---------------- Indicadores y alertas ----------------

def obtener_indicadores() -> dict:
    return _llamar("GET", "/indicadores")


def obtener_alertas(dias: int = 30) -> dict:
    return _llamar("GET", "/alertas/vencimientos", params={"dias": dias})


# ---------------- Inteligencia artificial ----------------

def estado_ia() -> dict:
    return _llamar("GET", "/ia/estado")


def cargar_cv(nombre_archivo: str, contenido: bytes) -> dict:
    """Manda el archivo del CV a la API (como un formulario con archivo adjunto)."""
    return _llamar("POST", "/docentes/cv", timeout=TIMEOUT_IA,
                   files={"archivo": (nombre_archivo, contenido)})


def generar_reporte() -> dict:
    return _llamar("POST", "/reportes/resumen", timeout=TIMEOUT_IA)


# ---------------- Notificaciones (las crean los workflows de n8n) ----------------

def listar_notificaciones(solo_no_leidas: bool = False) -> list[dict]:
    return _llamar("GET", "/notificaciones", params=_sin_vacios({"solo_no_leidas": solo_no_leidas}))


def marcar_notificacion_leida(notificacion_id: int) -> dict:
    return _llamar("PUT", f"/notificaciones/{notificacion_id}/leida")
