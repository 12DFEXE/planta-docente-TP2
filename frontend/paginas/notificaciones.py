"""Página Notificaciones: avisos generados por los workflows de n8n."""
import streamlit as st

import api_client as api
from api_client import ApiError


ICONOS_NIVEL = {"info": "🔵", "alerta": "🟡", "urgente": "🔴"}


def mostrar():
    st.title("🔔 Notificaciones")
    st.caption(
        "Avisos generados automáticamente por los workflows de n8n "
        "(ingreso de CVs, vencimientos y reporte semanal)."
    )
    solo_sin_leer = st.checkbox("Mostrar solo las no leídas")
    try:
        avisos = api.listar_notificaciones(solo_no_leidas=solo_sin_leer)
    except ApiError as e:
        st.error(str(e))
        return

    if not avisos:
        st.info("No hay notificaciones. Aparecen acá cuando se ejecuta un workflow de n8n.")
        return

    for aviso in avisos:
        icono = ICONOS_NIVEL.get(aviso["nivel"], "⚪")
        estado = "" if aviso["leida"] else " · **nueva**"
        with st.container(border=True):
            st.markdown(f"{icono} **{aviso['titulo']}**{estado}")
            st.caption(f"{aviso['origen']} · {aviso['creada_en']}")
            st.write(aviso["mensaje"])
            if not aviso["leida"] and st.button("Marcar como leída", key=f"leer_{aviso['id']}"):
                try:
                    api.marcar_notificacion_leida(aviso["id"])
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))
