"""Conexión con la base de datos SQLite y creación de tablas.

SQLite guarda toda la base en un solo archivo (data/planta_docente.db).
No necesita instalar ningún servidor de base de datos.
"""
import os
import sqlite3

# Ruta del archivo de la base. Se toma del .env; si no está, usa una por defecto.
DB_PATH = os.getenv("DB_PATH", "data/planta_docente.db")


def get_connection() -> sqlite3.Connection:
    """Abre una conexión a la base.

    row_factory = sqlite3.Row hace que cada fila se pueda leer por nombre de
    columna (fila["nombre"]) en vez de por posición (fila[1]).
    """
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # respeta las relaciones entre tablas
    return conn


def init_db() -> None:
    """Crea las tablas si todavía no existen. Se ejecuta al arrancar la API."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS docentes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre            TEXT    NOT NULL,
                email             TEXT    NOT NULL UNIQUE,
                titulo_maximo     TEXT    NOT NULL,
                areas             TEXT    NOT NULL DEFAULT '[]',
                anios_experiencia INTEGER NOT NULL DEFAULT 0,
                estado            TEXT    NOT NULL DEFAULT 'activo',
                origen            TEXT    NOT NULL DEFAULT 'manual',
                resumen           TEXT,
                creado_en         TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS materias (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre           TEXT    NOT NULL UNIQUE,
                area             TEXT    NOT NULL,
                horas_semanales  INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asignaciones (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                docente_id        INTEGER NOT NULL REFERENCES docentes(id),
                materia_id        INTEGER NOT NULL REFERENCES materias(id),
                dedicacion        TEXT    NOT NULL,
                horas             INTEGER NOT NULL,
                fecha_vencimiento TEXT    NOT NULL
            );
            """
        )
