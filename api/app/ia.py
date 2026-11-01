"""Conexión con la IA (Ollama, modelo local y gratuito).

Este módulo es el ÚNICO que habla con la IA. Tiene tres usos:
  1. extraer_datos_cv:   leer el texto de un CV y devolver los datos en JSON.
  2. resumir_perfil:     escribir un resumen corto del perfil de un docente.
  3. redactar_reporte:   convertir los indicadores (calculados con reglas) en un texto.

Todo lo que devuelve la IA se trata como una PROPUESTA: después se valida en
cv.py y un humano lo revisa en la pantalla antes de que el docente quede activo.
"""
import json
import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
# Un modelo local en una compu sin placa de video puede tardar bastante
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))

MAX_CARACTERES_CV = 6000  # recortamos CVs muy largos para no saturar al modelo


class IANoDisponible(Exception):
    """Ollama está apagado, no tiene el modelo descargado o no respondió a tiempo."""


class RespuestaIAInvalida(Exception):
    """La IA respondió algo que no se puede interpretar (por ejemplo, JSON roto)."""


def _generar(prompt: str, formato_json: bool = False, temperatura: float = 0.1) -> str:
    """Le manda un pedido a Ollama y devuelve el texto que generó el modelo."""
    pedido = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,                         # esperamos la respuesta completa
        "options": {"temperature": temperatura},  # baja = respuestas más estables
    }
    if formato_json:
        pedido["format"] = "json"  # obliga al modelo a responder JSON válido

    try:
        respuesta = httpx.post(f"{OLLAMA_URL}/api/generate", json=pedido, timeout=OLLAMA_TIMEOUT)
    except httpx.ConnectError:
        raise IANoDisponible(
            f"No se pudo conectar con Ollama en {OLLAMA_URL}. ¿Está abierto Ollama en la computadora?"
        )
    except httpx.TimeoutException:
        raise IANoDisponible("La IA tardó demasiado en responder. Probá de nuevo en unos segundos.")

    if respuesta.status_code == 404:
        raise IANoDisponible(
            f"El modelo {OLLAMA_MODEL} no está descargado. Corré en la terminal: ollama pull {OLLAMA_MODEL}"
        )
    if respuesta.status_code >= 400:
        raise IANoDisponible(f"Ollama respondió con error {respuesta.status_code}.")

    cuerpo = respuesta.json()
    if "error" in cuerpo:  # Ollama a veces informa el problema dentro de la respuesta
        if "not found" in str(cuerpo["error"]):
            raise IANoDisponible(
                f"El modelo {OLLAMA_MODEL} no está descargado. Corré en la terminal: ollama pull {OLLAMA_MODEL}"
            )
        raise IANoDisponible(f"Ollama informó un error: {cuerpo['error']}")
    return cuerpo.get("response", "")


def _texto_no_vacio(texto: str, que: str) -> str:
    """Verifica que la IA haya devuelto algo; si viene vacío, es una respuesta inválida."""
    texto = texto.strip()
    if not texto:
        raise RespuestaIAInvalida(f"La IA devolvió {que} vacío. Probá de nuevo.")
    return texto


def estado() -> dict:
    """Informa si Ollama responde y si el modelo configurado está descargado."""
    try:
        respuesta = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        modelos = [m.get("name", "") for m in respuesta.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return {"disponible": False, "modelo": OLLAMA_MODEL, "url": OLLAMA_URL,
                "detalle": "Ollama no responde. ¿Está abierto?"}

    descargado = any(m == OLLAMA_MODEL or m.startswith(OLLAMA_MODEL + ":") for m in modelos)
    return {
        "disponible": descargado,
        "modelo": OLLAMA_MODEL,
        "url": OLLAMA_URL,
        "detalle": "Listo para usar" if descargado else f"Falta descargar el modelo: ollama pull {OLLAMA_MODEL}",
    }


# ---------------- 1. Extraer datos de un CV ----------------

PROMPT_CV = """Sos un asistente de Recursos Humanos de una universidad.
Leé el siguiente currículum y extraé SOLO estos datos, en JSON:

{{
  "nombre": "nombre y apellido completos",
  "email": "email de contacto",
  "titulo_maximo": "uno de: grado, especializacion, maestria, doctorado",
  "areas": ["áreas de conocimiento o materias que puede dictar (máximo 5)"],
  "anios_experiencia": número entero de años de experiencia docente o profesional
}}

Reglas:
- Si un dato NO aparece en el CV, poné null. No inventes datos.
- "titulo_maximo" es el título más alto que tenga terminado.
- Respondé únicamente el JSON, sin explicaciones.

CURRÍCULUM:
\"\"\"
{texto}
\"\"\"
"""


def extraer_datos_cv(texto_cv: str) -> dict:
    """Le pide a la IA que lea el CV y devuelva los datos. Devuelve un diccionario 'crudo'."""
    prompt = PROMPT_CV.format(texto=texto_cv[:MAX_CARACTERES_CV])
    respuesta = _generar(prompt, formato_json=True)
    try:
        datos = json.loads(respuesta)
    except json.JSONDecodeError:
        raise RespuestaIAInvalida("La IA no devolvió un JSON válido al leer el CV. Probá de nuevo.")
    if not isinstance(datos, dict):
        raise RespuestaIAInvalida("La IA devolvió un formato inesperado al leer el CV.")
    return datos


# ---------------- 2. Resumir un perfil ----------------

PROMPT_PERFIL = """Escribí un resumen profesional de 2 oraciones, en español y en tercera persona,
del siguiente perfil docente. Usá solo estos datos, sin inventar nada:

Nombre: {nombre}
Título máximo: {titulo_maximo}
Áreas: {areas}
Años de experiencia: {anios_experiencia}

Respondé solo el resumen."""


def resumir_perfil(datos: dict) -> str:
    """Genera un resumen corto del perfil (texto libre, para mostrar al revisor)."""
    prompt = PROMPT_PERFIL.format(
        nombre=datos.get("nombre", ""),
        titulo_maximo=datos.get("titulo_maximo", ""),
        areas=", ".join(datos.get("areas", [])) or "sin especificar",
        anios_experiencia=datos.get("anios_experiencia", "sin especificar"),
    )
    return _texto_no_vacio(_generar(prompt, temperatura=0.3), "un resumen")


# ---------------- 3. Redactar el reporte ----------------

PROMPT_REPORTE = """Sos analista de la Secretaría Académica de una universidad.
Con estos indicadores de la planta docente (ya calculados, son datos exactos),
escribí un reporte breve en español (máximo 6 oraciones) para la Dirección:
- Empezá por la situación general.
- Destacá las materias sin cobertura y los docentes pendientes de revisión, si los hay.
- Terminá con 1 o 2 recomendaciones concretas.
No inventes números: usá solo los que aparecen abajo.

INDICADORES (JSON):
{indicadores}
"""


def redactar_reporte(indicadores: dict) -> str:
    """Convierte los indicadores (calculados con reglas) en un texto redactado por la IA."""
    prompt = PROMPT_REPORTE.format(indicadores=json.dumps(indicadores, ensure_ascii=False, indent=2))
    return _texto_no_vacio(_generar(prompt, temperatura=0.3), "un reporte")
