"""Modelos de datos (Pydantic): definen QUÉ datos se aceptan y QUÉ se devuelve.

Si alguien manda datos que no cumplen estas reglas, FastAPI responde
automáticamente con un error 422 explicando qué campo está mal.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TituloMaximo(str, Enum):
    """Valores permitidos para el título máximo del docente."""
    grado = "grado"
    especializacion = "especializacion"
    maestria = "maestria"
    doctorado = "doctorado"


class EstadoDocente(str, Enum):
    pendiente_revision = "pendiente_revision"  # cargado por IA, falta que un humano lo confirme
    activo = "activo"


class OrigenDocente(str, Enum):
    manual = "manual"  # cargado por formulario
    ia = "ia"          # extraído de un CV por la IA


EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class DocenteCrear(BaseModel):
    """Datos que hay que mandar para dar de alta un docente."""
    nombre: str = Field(min_length=3, max_length=100, examples=["Ana Pérez"])
    email: str = Field(pattern=EMAIL_REGEX, examples=["ana.perez@ejemplo.edu.ar"])
    titulo_maximo: TituloMaximo
    areas: list[str] = Field(default_factory=list, examples=[["Programación", "Bases de datos"]])
    anios_experiencia: int = Field(default=0, ge=0, le=60)


class DocenteActualizar(BaseModel):
    """Datos para modificar un docente. Todos son opcionales:
    solo se cambia lo que se manda."""
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=100)
    email: Optional[str] = Field(default=None, pattern=EMAIL_REGEX)
    titulo_maximo: Optional[TituloMaximo] = None
    areas: Optional[list[str]] = None
    anios_experiencia: Optional[int] = Field(default=None, ge=0, le=60)
    estado: Optional[EstadoDocente] = None


class Docente(BaseModel):
    """Lo que la API devuelve cuando consultás un docente."""
    id: int
    nombre: str
    email: str
    titulo_maximo: TituloMaximo
    areas: list[str]
    anios_experiencia: int
    estado: EstadoDocente
    origen: OrigenDocente
    resumen: Optional[str] = None
    creado_en: str
