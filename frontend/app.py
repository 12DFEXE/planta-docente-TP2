"""Interfaz Streamlit de Planta Docente.

Paso 2: solo verifica la conexión con la API.
"""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Planta Docente", page_icon="🎓")
st.title("🎓 Sistema de Gestión de Planta Docente")

try:
    r = requests.get(f"{API_URL}/health", timeout=5)
    r.raise_for_status()
    st.success(f"Conectado a la API ({API_URL})")
except requests.exceptions.ConnectionError:
    st.error("No se pudo conectar con la API. ¿Está levantado el contenedor `api`?")
except requests.exceptions.RequestException as e:
    st.error(f"La API respondió con un error: {e}")
