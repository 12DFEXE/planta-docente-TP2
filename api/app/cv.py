"""Proceso completo de alta de un docente desde su CV.

  archivo (.txt o .pdf) → texto → IA extrae datos → Python VALIDA y normaliza
  → si falta algo obligatorio: "incompleto" (no se guarda, hay que cargarlo a mano)
  → si está todo: se guarda como "pendiente_revision" + resumen generado por IA

La IA propone; las reglas de Python validan; un humano confirma en la pantalla.
"""
import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from . import docentes, ia
from .errores import DatosInvalidos
from .schemas import EMAIL_REGEX, DocenteCrear

EXTENSIONES_VALIDAS = (".txt", ".pdf")
TAMANIO_MAXIMO = 2 * 1024 * 1024  # 2 MB

# Palabras que puede usar la IA (o el CV) para cada título → valor que acepta el sistema
SINONIMOS_TITULO = {
    "doctorado": ["doctorado", "doctor", "doctora", "phd", "ph.d"],
    "maestria": ["maestria", "maestría", "magister", "magíster", "master", "máster"],
    "especializacion": ["especializacion", "especialización", "especialista", "especialidad"],
    "grado": ["grado", "licenciatura", "licenciado", "licenciada", "ingeniero", "ingeniera",
              "ingenieria", "ingeniería", "profesorado", "profesor", "profesora", "contador", "abogado"],
}


# ---------------- Leer el archivo ----------------

def leer_texto(nombre_archivo: str, contenido: bytes) -> str:
    """Saca el texto de un .txt o .pdf. Si no se puede, lanza DatosInvalidos (422)."""
    nombre = (nombre_archivo or "").lower()
    if not nombre.endswith(EXTENSIONES_VALIDAS):
        raise DatosInvalidos("El CV tiene que ser un archivo .txt o .pdf")
    if len(contenido) > TAMANIO_MAXIMO:
        raise DatosInvalidos("El archivo supera el máximo de 2 MB")

    if nombre.endswith(".txt"):
        try:
            texto = contenido.decode("utf-8")
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1")  # archivos guardados con la codificación vieja de Windows
    else:
        try:
            lector = PdfReader(io.BytesIO(contenido))
            texto = "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
        except (PdfReadError, ValueError):
            raise DatosInvalidos("No se pudo leer el PDF. ¿Está dañado o protegido con contraseña?")

    if len(texto.strip()) < 30:
        raise DatosInvalidos(
            "El archivo no tiene texto legible (puede ser un PDF escaneado como imagen)."
        )
    return texto


# ---------------- Validar y normalizar lo que propuso la IA ----------------

def _normalizar_titulo(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    texto = valor.strip().lower()
    for titulo, palabras in SINONIMOS_TITULO.items():  # el orden va de mayor a menor título
        if any(palabra in texto for palabra in palabras):
            return titulo
    return None


def _normalizar_areas(valor) -> list[str]:
    if isinstance(valor, str):
        valor = valor.split(",")
    if not isinstance(valor, list):
        return []
    return [str(a).strip() for a in valor if str(a).strip()][:5]


def _normalizar_anios(valor) -> int:
    try:
        anios = int(float(valor))
    except (TypeError, ValueError):
        return 0
    return min(max(anios, 0), 60)


def normalizar_extraccion(crudo: dict) -> tuple[dict, list[str]]:
    """Revisa con reglas de Python lo que devolvió la IA.

    Devuelve (datos_limpios, campos_faltantes). Nunca confía a ciegas en la IA:
    un email sin formato válido o un título desconocido cuentan como faltantes.
    """
    nombre = crudo.get("nombre") if isinstance(crudo.get("nombre"), str) else ""
    email = crudo.get("email") if isinstance(crudo.get("email"), str) else ""

    datos = {
        "nombre": nombre.strip(),
        "email": email.strip().lower(),
        "titulo_maximo": _normalizar_titulo(crudo.get("titulo_maximo")),
        "areas": _normalizar_areas(crudo.get("areas")),
        "anios_experiencia": _normalizar_anios(crudo.get("anios_experiencia")),
    }

    faltantes = []
    if len(datos["nombre"]) < 3:
        faltantes.append("nombre")
    if not re.match(EMAIL_REGEX, datos["email"]):
        faltantes.append("email")
    if datos["titulo_maximo"] is None:
        faltantes.append("titulo_maximo")
    return datos, faltantes


# ---------------- Proceso completo ----------------

def procesar_cv(nombre_archivo: str, contenido: bytes) -> dict:
    """Lee el CV, le pide los datos a la IA, los valida y, si está todo, crea el docente."""
    texto = leer_texto(nombre_archivo, contenido)
    crudo = ia.extraer_datos_cv(texto)
    datos, faltantes = normalizar_extraccion(crudo)

    if faltantes:
        # No se guarda nada: un humano tiene que completarlo a mano
        return {
            "resultado": "incompleto",
            "campos_faltantes": faltantes,
            "datos_extraidos": datos,
            "docente": None,
        }

    # Si el email ya existe, crear_docente lanza EmailDuplicado (409)
    docente = docentes.crear_docente(
        DocenteCrear(**datos), origen="ia", estado="pendiente_revision"
    )

    # El resumen es un extra: si la IA falla acá, el docente igual queda cargado
    try:
        resumen = ia.resumir_perfil(datos)
        docente = docentes.guardar_resumen(docente["id"], resumen)
    except (ia.IANoDisponible, ia.RespuestaIAInvalida):
        pass

    return {
        "resultado": "creado",
        "campos_faltantes": [],
        "datos_extraidos": datos,
        "docente": docente,
    }
