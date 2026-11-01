"""Excepciones propias del sistema.

La lógica (docentes.py, materias.py, asignaciones.py) lanza estas excepciones
cuando algo no se puede hacer. main.py las atrapa en un solo lugar y las
convierte en el error HTTP que corresponde:

    NoEncontrado   -> 404 (lo que pediste no existe)
    Conflicto      -> 409 (choca con datos existentes o rompe una regla del sistema)
    DatosInvalidos -> 422 (los datos no se pueden procesar, ej: un CV ilegible)
"""


class NoEncontrado(Exception):
    """El registro pedido no existe."""


class Conflicto(Exception):
    """La operación choca con datos que ya existen o con una regla de negocio."""


class DatosInvalidos(Exception):
    """Los datos recibidos no se pueden procesar (por ejemplo, un archivo ilegible)."""
