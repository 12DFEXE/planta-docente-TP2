"""Interfaz Streamlit de Planta Docente — punto de entrada.

Este archivo solo arma el menú lateral, controla que la API esté viva y
muestra la página elegida. Cada página está en su propio módulo (paginas/)
y expone una función mostrar().

La pantalla NO tiene lógica de negocio ni toca la base de datos:
todo lo pide a la API a través de api_client.py y solo muestra los resultados.
"""
import streamlit as st

import api_client as api
from api_client import ApiError
from paginas import asignaciones, docentes, materias, notificaciones, tablero

st.set_page_config(page_title="Planta Docente", page_icon="🎓", layout="wide")

# Opción del menú → módulo de la página. Para agregar una página: crear el módulo
# en paginas/ con su función mostrar() y sumarlo acá.
PAGINAS = {
    "📊 Tablero": tablero,
    "👩‍🏫 Docentes": docentes,
    "📚 Materias": materias,
    "🔗 Asignaciones": asignaciones,
    "🔔 Notificaciones": notificaciones,
}


# ======================= Menú lateral =======================

st.sidebar.title("🎓 Planta Docente")
pagina = st.sidebar.radio(
    "Ir a",
    list(PAGINAS),
    label_visibility="collapsed",
)

st.sidebar.divider()
try:
    api.health()
    st.sidebar.success("API conectada")
except ApiError as e:
    st.sidebar.error(str(e))
    st.error(str(e))
    st.stop()  # sin API no tiene sentido seguir dibujando la pantalla

try:
    estado_ia = api.estado_ia()
    if estado_ia["disponible"]:
        st.sidebar.success(f"IA lista ({estado_ia['modelo']})")
    else:
        st.sidebar.warning(f"IA no disponible: {estado_ia['detalle']}")
except ApiError:
    st.sidebar.warning("No se pudo consultar el estado de la IA")

try:
    sin_leer = len(api.listar_notificaciones(solo_no_leidas=True))
    if sin_leer:
        st.sidebar.info(f"🔔 {sin_leer} notificación(es) sin leer")
except ApiError:
    pass


# ======================= Página elegida =======================

PAGINAS[pagina].mostrar()
