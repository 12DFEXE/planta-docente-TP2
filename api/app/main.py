"""Punto de entrada de la API de Planta Docente.

Acá solo se definen los endpoints (las "puertas" de la API).
La lógica real está en docentes.py, materias.py y asignaciones.py;
este archivo traduce entre HTTP y esa lógica.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query, Request, status
from fastapi.responses import JSONResponse

from . import asignaciones, docentes, materias
from .database import init_db
from .errores import Conflicto, NoEncontrado
from .schemas import (
    Asignacion,
    AsignacionCrear,
    Docente,
    DocenteActualizar,
    DocenteCrear,
    EstadoDocente,
    Materia,
    MateriaCrear,
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
    version="0.3.0",
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
