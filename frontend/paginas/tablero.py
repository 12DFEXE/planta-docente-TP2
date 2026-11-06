"""Página Tablero: indicadores, cobertura, vencimientos y reporte redactado por IA."""
import pandas as pd
import streamlit as st

import api_client as api
from api_client import ApiError
from comun import etiqueta


def mostrar():
    st.title("📊 Tablero de la planta docente")
    st.caption("Todos estos números se calculan con reglas en Python (sin IA).")

    try:
        ind = api.obtener_indicadores()
    except ApiError as e:
        st.error(str(e))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Docentes activos", ind["docentes_activos"])
    c2.metric("Pendientes de revisión", ind["docentes_pendientes_revision"])
    c3.metric("Con posgrado", f"{ind['porcentaje_posgrado']} %")
    c4.metric("Cobertura de horas", f"{ind['porcentaje_cobertura_horas']} %")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Horas asignadas", ind["horas_totales_asignadas"])
    c2.metric("Promedio h/docente", ind["promedio_horas_por_docente"])
    c3.metric("Docentes sin materias", ind["docentes_sin_asignacion"])
    c4.metric("Materias", ind["materias_total"])

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("Docentes por título")
        st.bar_chart(pd.Series({etiqueta(k): v for k, v in ind["docentes_por_titulo"].items()}))
    with col_der:
        st.subheader("Asignaciones por dedicación")
        st.bar_chart(pd.Series({k.capitalize(): v for k, v in ind["asignaciones_por_dedicacion"].items()}))

    st.subheader("Materias sin cobertura")
    if ind["materias_sin_cobertura"]:
        st.dataframe(
            pd.DataFrame(ind["materias_sin_cobertura"]).rename(
                columns={"id": "ID", "nombre": "Materia", "horas_faltantes": "Horas faltantes"}
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.success("Todas las materias tienen docente por todas sus horas.")

    st.subheader("Designaciones por vencer")
    dias = st.slider("Mirar los próximos días", min_value=7, max_value=365, value=30, step=1)
    try:
        resp = api.obtener_alertas(dias)
    except ApiError as e:
        st.error(str(e))
        return
    if resp["cantidad"] == 0:
        st.info(f"No hay designaciones vencidas ni por vencer en los próximos {dias} días.")
    else:
        st.warning(
            f"Hay {resp['cantidad']} designación(es) vencida(s) o por vencer. "
            "Para renovarlas: **🔗 Asignaciones → Renovar designación**."
        )
        tabla = pd.DataFrame(resp["alertas"])[
            ["docente_nombre", "materia_nombre", "fecha_vencimiento", "dias_restantes", "estado"]
        ]
        tabla["estado"] = tabla["estado"].map({"vencida": "🔴 Vencida", "por_vencer": "🟡 Por vencer"})
        st.dataframe(
            tabla.rename(columns={
                "docente_nombre": "Docente", "materia_nombre": "Materia",
                "fecha_vencimiento": "Vence", "dias_restantes": "Días restantes", "estado": "Estado",
            }),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("🤖 Reporte redactado por IA")
    st.caption(
        "Los números de arriba se calculan con reglas. Este texto lo redacta la IA a partir de esos "
        "números: es una ayuda para leerlos y hay que revisarlo antes de usarlo."
    )
    if st.button("Generar reporte con IA"):
        with st.spinner("La IA está redactando el reporte... (puede tardar un minuto)"):
            try:
                reporte = api.generar_reporte()
                st.session_state["reporte_ia"] = reporte
            except ApiError as e:
                st.error(str(e))
    if "reporte_ia" in st.session_state:
        reporte = st.session_state["reporte_ia"]
        st.info(reporte["resumen_ia"])
        st.caption(f"Generado por {reporte['modelo_ia']} el {reporte['generado_en'].replace('T', ' ')}")
