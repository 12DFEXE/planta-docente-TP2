"""Página Materias: listado con su cobertura de horas y alta."""
import pandas as pd
import streamlit as st

import api_client as api
from api_client import ApiError
from comun import mostrar_mensaje_guardado


def mostrar():
    st.title("📚 Materias")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta = st.tabs(["Listado y cobertura", "Nueva materia"])

    with tab_lista:
        _listado()
    with tab_alta:
        _alta()


def _listado():
    c1, c2 = st.columns([3, 1])
    area = c1.text_input("Filtrar por área")
    solo_sin = c2.checkbox("Solo sin cobertura")
    try:
        materias = api.listar_materias(area=area, sin_cobertura=solo_sin)
    except ApiError as e:
        st.error(str(e))
        materias = []

    if not materias:
        st.info("No hay materias que coincidan.")
    else:
        tabla = pd.DataFrame(materias)
        tabla["cubierta"] = tabla["cubierta"].map({True: "✅ Sí", False: "⚠️ No"})
        st.dataframe(
            tabla.rename(columns={
                "id": "ID", "nombre": "Materia", "area": "Área", "horas_semanales": "Horas necesarias",
                "horas_asignadas": "Horas asignadas", "cubierta": "Cubierta",
            }),
            hide_index=True,
            use_container_width=True,
        )


def _alta():
    with st.form("alta_materia", clear_on_submit=True):
        nombre = st.text_input("Nombre de la materia *")
        area_n = st.text_input("Área *", placeholder="Programación")
        horas = st.number_input("Horas semanales *", min_value=1, max_value=20, value=4)
        enviar = st.form_submit_button("Guardar materia", type="primary")
    if enviar:
        try:
            creada = api.crear_materia({"nombre": nombre, "area": area_n, "horas_semanales": int(horas)})
            st.session_state["mensaje_ok"] = f"Se guardó la materia {creada['nombre']}."
            st.rerun()
        except ApiError as e:
            st.error(str(e))
