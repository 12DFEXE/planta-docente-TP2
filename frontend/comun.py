"""Elementos compartidos por todas las páginas de la interfaz.

Acá van las constantes (valores permitidos y sus etiquetas) y las funciones
chicas que usan varias páginas. Ninguna página importa a otra: todas importan
de acá y de api_client.py.
"""
import streamlit as st

TITULOS = ["grado", "especializacion", "maestria", "doctorado"]
DEDICACIONES = ["simple", "semiexclusiva", "exclusiva"]
ETIQUETAS = {
    "grado": "Grado",
    "especializacion": "Especialización",
    "maestria": "Maestría",
    "doctorado": "Doctorado",
    "simple": "Simple (hasta 10 h)",
    "semiexclusiva": "Semiexclusiva (hasta 20 h)",
    "exclusiva": "Exclusiva (hasta 40 h)",
    "activo": "Activo",
    "pendiente_revision": "Pendiente de revisión",
    "manual": "Formulario",
    "ia": "IA (desde CV)",
}


def etiqueta(valor: str) -> str:
    return ETIQUETAS.get(valor, valor)


def mostrar_mensaje_guardado():
    """Muestra (una sola vez) el mensaje de éxito que dejó la acción anterior."""
    if "mensaje_ok" in st.session_state:
        st.success(st.session_state.pop("mensaje_ok"))
