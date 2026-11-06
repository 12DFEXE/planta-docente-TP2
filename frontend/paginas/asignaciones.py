"""Página Asignaciones: listado, alta (las reglas las valida la API) y
renovación de designaciones."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import api_client as api
from api_client import ApiError
from comun import DEDICACIONES, etiqueta, mostrar_mensaje_guardado


def mostrar():
    st.title("🔗 Asignaciones")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta, tab_renovar = st.tabs(["Listado", "Nueva asignación", "Renovar designación"])

    with tab_lista:
        _listado()
    with tab_alta:
        _alta()
    with tab_renovar:
        _renovar()


def _listado():
    """Listado de asignaciones, ordenadas por vencimiento."""
    try:
        asignaciones = api.listar_asignaciones()
    except ApiError as e:
        st.error(str(e))
        asignaciones = []
    if not asignaciones:
        st.info("Todavía no hay asignaciones.")
    else:
        tabla = pd.DataFrame(asignaciones)
        st.dataframe(
            tabla[["id", "docente_nombre", "materia_nombre", "dedicacion", "horas", "fecha_vencimiento"]]
            .rename(columns={
                "id": "ID", "docente_nombre": "Docente", "materia_nombre": "Materia",
                "dedicacion": "Dedicación", "horas": "Horas", "fecha_vencimiento": "Vence",
            }),
            hide_index=True,
            use_container_width=True,
        )


def _alta():
    """Alta de una asignación: la pantalla solo junta los datos, las reglas las valida la API."""
    try:
        docentes = api.listar_docentes(estado="activo")
        materias = api.listar_materias()
    except ApiError as e:
        st.error(str(e))
        return

    if not docentes or not materias:
        st.info("Para asignar hace falta al menos un docente activo y una materia.")
        return

    st.caption(
        "Las reglas (docente activo, sin repetir, horas de la materia y tope por dedicación) "
        "las valida la API. Si algo no se cumple, vas a ver el motivo acá."
    )
    with st.form("alta_asignacion"):
        docente = st.selectbox("Docente *", docentes, format_func=lambda d: d["nombre"])
        materia = st.selectbox(
            "Materia *",
            materias,
            format_func=lambda m: f"{m['nombre']} ({m['horas_asignadas']}/{m['horas_semanales']} h asignadas)",
        )
        c1, c2, c3 = st.columns(3)
        dedicacion = c1.selectbox("Dedicación *", DEDICACIONES, format_func=etiqueta)
        horas = c2.number_input("Horas semanales *", min_value=1, max_value=20, value=2)
        vence = c3.date_input("Vence el *", value=date.today() + timedelta(days=180))
        enviar = st.form_submit_button("Asignar", type="primary")

    if enviar:
        datos = {
            "docente_id": docente["id"],
            "materia_id": materia["id"],
            "dedicacion": dedicacion,
            "horas": int(horas),
            "fecha_vencimiento": vence.isoformat(),
        }
        try:
            api.crear_asignacion(datos)
            st.session_state["mensaje_ok"] = f"Se asignó a {docente['nombre']} en {materia['nombre']}."
            st.rerun()
        except ApiError as e:
            st.error(str(e))


def _renovar():
    """Extiende la fecha de vencimiento de una designación (cierra el ciclo de las alertas de n8n)."""
    try:
        asignaciones = api.listar_asignaciones()  # vienen ordenadas por fecha de vencimiento
    except ApiError as e:
        st.error(str(e))
        return
    if not asignaciones:
        st.info("Todavía no hay asignaciones para renovar.")
        return

    st.caption(
        "Las designaciones están ordenadas de la que vence antes a la que vence después. "
        "La API valida que el docente siga activo y que la nueva fecha sea posterior a la actual."
    )
    hoy = date.today()

    def describir(a: dict) -> str:
        dias = (date.fromisoformat(a["fecha_vencimiento"]) - hoy).days
        estado = "🔴 vencida" if dias < 0 else ("🟡 vence en %d días" % dias if dias <= 30 else "🟢 vigente")
        return f"{a['docente_nombre']} — {a['materia_nombre']} (vence {a['fecha_vencimiento']}, {estado})"

    # Sin st.form a propósito: así la fecha propuesta se actualiza al elegir otra designación
    asignacion = st.selectbox("Designación *", asignaciones, format_func=describir)
    # Por defecto se propone un año más desde hoy o desde el vencimiento actual (lo que sea más tarde)
    actual = date.fromisoformat(asignacion["fecha_vencimiento"])
    nueva = st.date_input("Nueva fecha de vencimiento *", value=max(hoy, actual) + timedelta(days=365))
    enviar = st.button("Renovar", type="primary")

    if enviar:
        try:
            api.renovar_asignacion(asignacion["id"], nueva.isoformat())
            st.session_state["mensaje_ok"] = (
                f"Se renovó la designación de {asignacion['docente_nombre']} en "
                f"{asignacion['materia_nombre']} hasta el {nueva.strftime('%d/%m/%Y')}."
            )
            st.rerun()
        except ApiError as e:
            st.error(str(e))
