"""Modelos de datos (Pydantic): definen QUÉ datos se aceptan y QUÉ se devuelve.

Si alguien manda datos que no cumplen estas reglas, FastAPI responde
automáticamente con un error 422 explicando qué campo está mal.
"""
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


# ---------------- Materias ----------------

class MateriaCrear(BaseModel):
    """Datos para dar de alta una materia."""
    nombre: str = Field(min_length=3, max_length=100, examples=["Programación I"])
    area: str = Field(min_length=3, max_length=60, examples=["Programación"])
    horas_semanales: int = Field(ge=1, le=20, examples=[6])


class Materia(BaseModel):
    """Lo que la API devuelve de una materia, incluida su cobertura."""
    id: int
    nombre: str
    area: str
    horas_semanales: int
    horas_asignadas: int   # cuántas horas ya tienen docente
    cubierta: bool         # True si horas_asignadas >= horas_semanales


# ---------------- Asignaciones ----------------

class Dedicacion(str, Enum):
    """Tipo de designación del docente en esa materia."""
    simple = "simple"
    semiexclusiva = "semiexclusiva"
    exclusiva = "exclusiva"


class AsignacionCrear(BaseModel):
    """Datos para asignar un docente a una materia."""
    docente_id: int = Field(gt=0)
    materia_id: int = Field(gt=0)
    dedicacion: Dedicacion
    horas: int = Field(ge=1, le=20, examples=[4])
    fecha_vencimiento: date = Field(examples=["2027-03-31"])

    @field_validator("fecha_vencimiento")
    @classmethod
    def vencimiento_futuro(cls, valor: date) -> date:
        """Una designación nueva no puede nacer vencida."""
        if valor <= date.today():
            raise ValueError("La fecha de vencimiento tiene que ser posterior a hoy")
        return valor


class Asignacion(BaseModel):
    """Lo que la API devuelve de una asignación (con nombres para leerla fácil)."""
    id: int
    docente_id: int
    docente_nombre: str
    materia_id: int
    materia_nombre: str
    dedicacion: Dedicacion
    horas: int
    fecha_vencimiento: date


# ---------------- Indicadores y alertas ----------------

class MateriaSinCobertura(BaseModel):
    id: int
    nombre: str
    horas_faltantes: int


class Indicadores(BaseModel):
    """Números de resumen de la planta docente (todos calculados con reglas, sin IA)."""
    docentes_total: int
    docentes_activos: int
    docentes_pendientes_revision: int
    docentes_sin_asignacion: int
    docentes_por_titulo: dict[str, int]
    porcentaje_posgrado: float
    horas_totales_asignadas: int
    promedio_horas_por_docente: float
    asignaciones_por_dedicacion: dict[str, int]
    materias_total: int
    porcentaje_cobertura_horas: float
    materias_sin_cobertura: list[MateriaSinCobertura]


class EstadoVencimiento(str, Enum):
    vencida = "vencida"
    por_vencer = "por_vencer"


class AlertaVencimiento(BaseModel):
    id: int
    docente_nombre: str
    docente_email: str
    materia_nombre: str
    dedicacion: Dedicacion
    fecha_vencimiento: date
    dias_restantes: int      # negativo si ya venció
    estado: EstadoVencimiento


class RespuestaAlertas(BaseModel):
    """Respuesta de /alertas/vencimientos. n8n decide según 'cantidad'."""
    fecha_consulta: date
    dias: int
    cantidad: int
    alertas: list[AlertaVencimiento]


# ---------------- Inteligencia artificial ----------------

class EstadoIA(BaseModel):
    """Si la IA (Ollama) está lista para usar."""
    disponible: bool
    modelo: str
    url: str
    detalle: str


class ResultadoCV(str, Enum):
    creado = "creado"          # se cargó el docente como pendiente de revisión
    incompleto = "incompleto"  # faltan datos obligatorios: hay que cargarlo a mano


class DatosExtraidosCV(BaseModel):
    """Lo que la IA leyó del CV, ya limpiado y validado por Python."""
    nombre: str
    email: str
    titulo_maximo: Optional[TituloMaximo] = None
    areas: list[str]
    anios_experiencia: int


class RespuestaCV(BaseModel):
    """Respuesta de POST /docentes/cv. n8n decide según 'resultado'."""
    resultado: ResultadoCV
    campos_faltantes: list[str]
    datos_extraidos: DatosExtraidosCV
    docente: Optional[Docente] = None


class Reporte(BaseModel):
    """Reporte: indicadores calculados con reglas + texto redactado por IA."""
    generado_en: str
    indicadores: Indicadores
    resumen_ia: str
    modelo_ia: str
    hay_materias_sin_cobertura: bool


# ---------------- Notificaciones (las crea n8n) ----------------

class NivelNotificacion(str, Enum):
    info = "info"          # informativa
    alerta = "alerta"      # requiere atención
    urgente = "urgente"    # requiere atención prioritaria


class NotificacionCrear(BaseModel):
    """Lo que manda n8n para dejar un aviso en el sistema."""
    origen: str = Field(min_length=2, max_length=60, examples=["n8n: vencimientos"])
    nivel: NivelNotificacion
    titulo: str = Field(min_length=3, max_length=120, examples=["Hay 2 designaciones por vencer"])
    mensaje: str = Field(min_length=1, max_length=4000)


class Notificacion(BaseModel):
    id: int
    origen: str
    nivel: NivelNotificacion
    titulo: str
    mensaje: str
    leida: bool
    creada_en: str
