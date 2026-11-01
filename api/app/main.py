"""Punto de entrada de la API de Planta Docente.

Acá solo se definen los endpoints (las "puertas" de la API).
La lógica real está en docentes.py, materias.py y asignaciones.py;
este archivo traduce entre HTTP y esa lógica.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse

from . import asignaciones, cv, docentes, ia, indicadores, materias, notificaciones, reportes
from .database import init_db
from .errores import Conflicto, DatosInvalidos, NoEncontrado
from .schemas import (
    Asignacion,
    AsignacionCrear,
    Docente,
    DocenteActualizar,
    DocenteCrear,
    EstadoDocente,
    EstadoIA,
    Indicadores,
    Materia,
    MateriaCrear,
    Notificacion,
    NotificacionCrear,
    Reporte,
    RespuestaAlertas,
    RespuestaCV,
    TituloMaximo,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Se ejecuta una vez al arrancar la API: crea las tablas si no existen."""
    init_db()
    yield


app = FastAPI(
    title="API Planta Docente",
    description="Gestión de planta docente con IA y automatizaciones n8n",
    version="0.6.0",
    lifespan=lifespan,
)


# ---------------- Manejo centralizado de errores ----------------
# Cualquier endpoint que lance estas excepciones devuelve automáticamente
# el código HTTP correcto, sin repetir try/except en cada uno.

@app.exception_handler(NoEncontrado)
async def manejar_no_encontrado(request: Request, exc: NoEncontrado):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(Conflicto)
async def manejar_conflicto(request: Request, exc: Conflicto):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(DatosInvalidos)
async def manejar_datos_invalidos(request: Request, exc: DatosInvalidos):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ia.IANoDisponible)
async def manejar_ia_no_disponible(request: Request, exc: ia.IANoDisponible):
    # 503 = "servicio no disponible": el sistema funciona, pero la IA no responde
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)})


@app.exception_handler(ia.RespuestaIAInvalida)
async def manejar_respuesta_ia_invalida(request: Request, exc: ia.RespuestaIAInvalida):
    # 502 = "la respuesta de un servicio externo vino mal"
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


# ---------------- Sistema ----------------

@app.get("/health", tags=["Sistema"])
def health():
    """Chequeo simple de estado: lo usan Streamlit y n8n para saber si la API está viva."""
    return {"status": "ok"}


# ---------------- Docentes ----------------

@app.post("/docentes", response_model=Docente, status_code=status.HTTP_201_CREATED, tags=["Docentes"])
def crear_docente(datos: DocenteCrear):
    """Da de alta un docente cargado manualmente."""
    return docentes.crear_docente(datos)


@app.post("/docentes/cv", response_model=RespuestaCV, tags=["Docentes", "IA"])
def cargar_docente_desde_cv(archivo: UploadFile = File(..., description="CV en .txt o .pdf (máx. 2 MB)")):
    """Carga un docente a partir de su CV usando IA.

    - La IA extrae los datos y Python los valida.
    - Si falta un dato obligatorio → resultado "incompleto" (no se guarda nada).
    - Si está todo → se crea como "pendiente_revision" con un resumen generado por IA,
      y un humano lo tiene que confirmar (PUT /docentes/{id} con estado "activo").
    """
    contenido = archivo.file.read()
    return cv.procesar_cv(archivo.filename, contenido)


@app.get("/docentes", response_model=list[Docente], tags=["Docentes"])
def listar_docentes(
    area: Optional[str] = Query(None, description="Filtra por área (ej: Programación)"),
    titulo: Optional[TituloMaximo] = Query(None, description="Filtra por título máximo"),
    estado: Optional[EstadoDocente] = Query(None, description="Filtra por estado"),
    texto: Optional[str] = Query(None, description="Busca en nombre o email"),
):
    """Lista docentes, con filtros opcionales."""
    return docentes.listar_docentes(
        area=area,
        titulo=titulo.value if titulo else None,
        estado=estado.value if estado else None,
        texto=texto,
    )


@app.get("/docentes/{docente_id}", response_model=Docente, tags=["Docentes"])
def obtener_docente(docente_id: int):
    """Devuelve un docente por su id."""
    return docentes.obtener_docente(docente_id)


@app.put("/docentes/{docente_id}", response_model=Docente, tags=["Docentes"])
def actualizar_docente(docente_id: int, cambios: DocenteActualizar):
    """Modifica un docente. También sirve para confirmar la revisión humana
    de un docente cargado por IA (estado: pendiente_revision → activo)."""
    return docentes.actualizar_docente(docente_id, cambios)


# ---------------- Materias ----------------

@app.post("/materias", response_model=Materia, status_code=status.HTTP_201_CREATED, tags=["Materias"])
def crear_materia(datos: MateriaCrear):
    """Da de alta una materia."""
    return materias.crear_materia(datos)


@app.get("/materias", response_model=list[Materia], tags=["Materias"])
def listar_materias(
    area: Optional[str] = Query(None, description="Filtra por área"),
    sin_cobertura: bool = Query(False, description="Solo materias a las que les faltan horas de docente"),
):
    """Lista materias con su cobertura (horas asignadas vs. horas que necesita)."""
    return materias.listar_materias(area=area, sin_cobertura=sin_cobertura)


# ---------------- Asignaciones ----------------

@app.post("/asignaciones", response_model=Asignacion, status_code=status.HTTP_201_CREATED, tags=["Asignaciones"])
def crear_asignacion(datos: AsignacionCrear):
    """Asigna un docente a una materia, validando las reglas de negocio
    (docente activo, sin duplicados, horas de la materia y tope por dedicación)."""
    return asignaciones.crear_asignacion(datos)


@app.get("/asignaciones", response_model=list[Asignacion], tags=["Asignaciones"])
def listar_asignaciones(
    docente_id: Optional[int] = Query(None, description="Filtra por docente"),
    materia_id: Optional[int] = Query(None, description="Filtra por materia"),
):
    """Lista asignaciones, ordenadas por fecha de vencimiento."""
    return asignaciones.listar_asignaciones(docente_id=docente_id, materia_id=materia_id)


# ---------------- Indicadores y alertas ----------------

@app.get("/indicadores", response_model=Indicadores, tags=["Indicadores y alertas"])
def obtener_indicadores():
    """Números de resumen de la planta docente: docentes, títulos, horas,
    dedicaciones y cobertura de materias. Todo calculado con reglas en Python."""
    return indicadores.calcular_indicadores()


@app.get("/alertas/vencimientos", response_model=RespuestaAlertas, tags=["Indicadores y alertas"])
def obtener_alertas_vencimiento(
    dias: int = Query(30, ge=1, le=365, description="Cuántos días hacia adelante mirar"),
):
    """Asignaciones vencidas o que vencen dentro de los próximos `dias` días.
    Lo consulta n8n todos los días: si 'cantidad' > 0, manda un aviso."""
    return indicadores.alertas_vencimiento(dias)


# ---------------- Inteligencia artificial ----------------

@app.get("/ia/estado", response_model=EstadoIA, tags=["IA"])
def estado_ia():
    """Indica si Ollama responde y si el modelo configurado está descargado."""
    return ia.estado()


@app.post("/reportes/resumen", response_model=Reporte, tags=["IA", "Indicadores y alertas"])
def generar_reporte():
    """Calcula los indicadores (reglas) y le pide a la IA que los redacte como reporte.
    La respuesta separa los números exactos ("indicadores") del texto de la IA ("resumen_ia")."""
    return reportes.generar_reporte()


# ---------------- Notificaciones (las crean los workflows de n8n) ----------------

@app.post("/notificaciones", response_model=Notificacion, status_code=status.HTTP_201_CREATED, tags=["Notificaciones"])
def crear_notificacion(datos: NotificacionCrear):
    """Registra un aviso generado por un workflow de n8n."""
    return notificaciones.crear_notificacion(datos)


@app.get("/notificaciones", response_model=list[Notificacion], tags=["Notificaciones"])
def listar_notificaciones(
    solo_no_leidas: bool = Query(False, description="Solo las que todavía no se leyeron"),
    limite: int = Query(50, ge=1, le=200),
):
    """Lista los avisos, del más nuevo al más viejo."""
    return notificaciones.listar_notificaciones(solo_no_leidas, limite)


@app.put("/notificaciones/{notificacion_id}/leida", response_model=Notificacion, tags=["Notificaciones"])
def marcar_notificacion_leida(notificacion_id: int):
    """Marca un aviso como leído."""
    return notificaciones.marcar_leida(notificacion_id)
