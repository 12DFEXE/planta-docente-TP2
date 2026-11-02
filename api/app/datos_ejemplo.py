"""Carga datos de ejemplo (ficticios) para la demo.

Uso (con los contenedores prendidos):
    docker compose exec api python -m app.datos_ejemplo           # agrega lo que falte
    docker compose exec api python -m app.datos_ejemplo --reset   # borra todo y vuelve a cargar

Los datos se cargan con las MISMAS funciones que usa la API (docentes.py, materias.py,
asignaciones.py), así que pasan por todas las validaciones y reglas de negocio.
Todos los nombres y emails son inventados.
"""
import sys
from datetime import date, timedelta

from . import asignaciones, docentes, materias
from .database import get_connection, init_db
from .errores import Conflicto
from .schemas import AsignacionCrear, DocenteCrear, MateriaCrear

HOY = date.today()


def en_dias(n: int) -> date:
    return HOY + timedelta(days=n)


DOCENTES = [
    # nombre, email, título, áreas, años de experiencia
    ("Ana Pérez", "ana.perez@ejemplo.edu.ar", "maestria", ["Programación", "Bases de datos"], 12),
    ("Bruno Díaz", "bruno.diaz@ejemplo.edu.ar", "grado", ["Redes", "Sistemas operativos"], 6),
    ("Carla Gómez", "carla.gomez@ejemplo.edu.ar", "doctorado", ["Inteligencia artificial", "Matemática"], 15),
    ("Diego Fernández", "diego.fernandez@ejemplo.edu.ar", "especializacion", ["Seguridad informática", "Redes"], 9),
    ("Elena Ruiz", "elena.ruiz@ejemplo.edu.ar", "grado", ["Programación", "Ingeniería de software"], 4),
    ("Federico López", "federico.lopez@ejemplo.edu.ar", "maestria", ["Gestión de proyectos", "Ingeniería de software"], 11),
]

# Un docente "cargado por IA" que todavía nadie revisó (para mostrar la revisión humana)
DOCENTE_PENDIENTE = (
    "Gabriela Torres", "gabriela.torres@ejemplo.edu.ar", "maestria", ["Ciencia de datos", "Estadística"], 7,
    "Magíster en Ciencia de Datos con 7 años de experiencia docente en estadística y análisis de datos. "
    "Perfil orientado a materias de datos e inteligencia artificial.",
)

MATERIAS = [
    # nombre, área, horas semanales que necesita
    ("Programación I", "Programación", 6),
    ("Programación II", "Programación", 6),
    ("Bases de Datos", "Datos", 6),
    ("Redes de Computadoras", "Infraestructura", 4),
    ("Seguridad Informática", "Infraestructura", 4),
    ("Inteligencia Artificial", "Datos", 4),
    ("Ingeniería de Software", "Gestión", 4),
    ("Estadística", "Matemática", 4),  # queda sin docente: muestra "materia sin cobertura"
]

ASIGNACIONES = [
    # email del docente, materia, dedicación, horas, vence en (días)
    ("ana.perez@ejemplo.edu.ar", "Programación I", "semiexclusiva", 6, 12),       # vence pronto
    ("ana.perez@ejemplo.edu.ar", "Bases de Datos", "semiexclusiva", 6, 200),
    ("bruno.diaz@ejemplo.edu.ar", "Redes de Computadoras", "simple", 4, 25),      # vence pronto
    ("carla.gomez@ejemplo.edu.ar", "Inteligencia Artificial", "exclusiva", 4, 300),
    ("diego.fernandez@ejemplo.edu.ar", "Seguridad Informática", "simple", 4, 150),
    ("elena.ruiz@ejemplo.edu.ar", "Programación II", "simple", 4, 180),            # cubre 4 de 6 h
    ("federico.lopez@ejemplo.edu.ar", "Ingeniería de Software", "simple", 4, 5),   # se marca como vencida (ver abajo)
]
EMAIL_VENCIDA = "federico.lopez@ejemplo.edu.ar"  # su designación se pasa a "ya vencida" para la demo


def borrar_todo() -> None:
    with get_connection() as conn:
        conn.executescript(
            "DELETE FROM asignaciones; DELETE FROM materias; DELETE FROM docentes; DELETE FROM notificaciones;"
            "DELETE FROM sqlite_sequence;"
        )
    print("Se borraron todos los datos.")


def cargar() -> None:
    init_db()
    creados = {"docentes": 0, "materias": 0, "asignaciones": 0}

    for nombre, email, titulo, areas, anios in DOCENTES:
        try:
            docentes.crear_docente(DocenteCrear(nombre=nombre, email=email, titulo_maximo=titulo,
                                                areas=areas, anios_experiencia=anios))
            creados["docentes"] += 1
        except Conflicto:
            pass  # ya existía

    nombre, email, titulo, areas, anios, resumen = DOCENTE_PENDIENTE
    try:
        d = docentes.crear_docente(
            DocenteCrear(nombre=nombre, email=email, titulo_maximo=titulo, areas=areas, anios_experiencia=anios),
            origen="ia", estado="pendiente_revision",
        )
        docentes.guardar_resumen(d["id"], resumen)
        creados["docentes"] += 1
    except Conflicto:
        pass

    for nombre, area, horas in MATERIAS:
        try:
            materias.crear_materia(MateriaCrear(nombre=nombre, area=area, horas_semanales=horas))
            creados["materias"] += 1
        except Conflicto:
            pass

    ids_docentes = {d["email"]: d["id"] for d in docentes.listar_docentes()}
    ids_materias = {m["nombre"]: m["id"] for m in materias.listar_materias()}

    for email, materia, dedicacion, horas, dias in ASIGNACIONES:
        try:
            nueva = asignaciones.crear_asignacion(AsignacionCrear(
                docente_id=ids_docentes[email], materia_id=ids_materias[materia],
                dedicacion=dedicacion, horas=horas, fecha_vencimiento=en_dias(dias),
            ))
            creados["asignaciones"] += 1
            if email == EMAIL_VENCIDA:
                # La API no deja crear designaciones vencidas (regla de negocio).
                # Para la demo simulamos que pasó el tiempo y esta ya venció.
                with get_connection() as conn:
                    conn.execute("UPDATE asignaciones SET fecha_vencimiento = ? WHERE id = ?",
                                 (en_dias(-3).isoformat(), nueva["id"]))
        except Conflicto:
            pass

    print(f"Cargados: {creados['docentes']} docentes, {creados['materias']} materias, "
          f"{creados['asignaciones']} asignaciones (lo que ya existía no se duplica).")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        borrar_todo()
    cargar()
