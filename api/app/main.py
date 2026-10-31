"""Punto de entrada de la API de Planta Docente.

Acá solo se definen los endpoints (las "puertas" de la API).
La lógica real está en docentes.py; este archivo traduce entre HTTP y esa lógica.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status

from . import docentes
from .database import init_db
from .schemas import Docente, DocenteActualizar, DocenteCrear, EstadoDocente, TituloMaximo


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Se ejecuta una vez al arrancar la API: crea las tablas si no existen."""
    init_db()
    yield


app = FastAPI(
    title="API Planta Docente",
    description="Gestión de planta docente con IA y automatizaciones n8n",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Sistema"])
def health():
    """Chequeo simple de estado: lo usan Streamlit y n8n para saber si la API está viva."""
    return {"status": "ok"}


# ---------------- Docentes ----------------

@app.post("/docentes", response_model=Docente, status_code=status.HTTP_201_CREATED, tags=["Docentes"])
def crear_docente(datos: DocenteCrear):
    """Da de alta un docente cargado manualmente."""
    try:
        return docentes.crear_docente(datos)
    except docentes.EmailDuplicado as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
    try:
        return docentes.obtener_docente(docente_id)
    except docentes.DocenteNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.put("/docentes/{docente_id}", response_model=Docente, tags=["Docentes"])
def actualizar_docente(docente_id: int, cambios: DocenteActualizar):
    """Modifica un docente. También sirve para confirmar la revisión humana
    de un docente cargado por IA (estado: pendiente_revision → activo)."""
    try:
        return docentes.actualizar_docente(docente_id, cambios)
    except docentes.DocenteNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except docentes.EmailDuplicado as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
