"""Página Docentes: listado con filtros, alta manual, alta desde CV con IA y
edición / confirmación de la revisión humana."""
import pandas as pd
import streamlit as st

import api_client as api
from api_client import NOMBRES_CAMPOS, ApiError
from comun import TITULOS, etiqueta, mostrar_mensaje_guardado


def mostrar():
    st.title("👩‍🏫 Docentes")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta, tab_cv, tab_editar = st.tabs(
        ["Listado", "Nuevo docente", "🤖 Cargar desde CV (IA)", "Editar / confirmar revisión"]
    )

    with tab_lista:
        _listado()
    with tab_alta:
        _alta()
    with tab_cv:
        _desde_cv()
    with tab_editar:
        _editar()


def _listado():
    """Listado con filtros."""
    f1, f2, f3, f4 = st.columns(4)
    texto = f1.text_input("Buscar por nombre o email")
    area = f2.text_input("Área")
    titulo = f3.selectbox("Título", [""] + TITULOS, format_func=lambda v: etiqueta(v) if v else "Todos")
    estado = f4.selectbox(
        "Estado", ["", "activo", "pendiente_revision"], format_func=lambda v: etiqueta(v) if v else "Todos"
    )
    try:
        docentes = api.listar_docentes(area=area, titulo=titulo, estado=estado, texto=texto)
    except ApiError as e:
        st.error(str(e))
        docentes = []

    if not docentes:
        st.info("No hay docentes que coincidan con los filtros.")
    else:
        tabla = pd.DataFrame(docentes)
        tabla["areas"] = tabla["areas"].apply(", ".join)
        for col in ("titulo_maximo", "estado", "origen"):
            tabla[col] = tabla[col].map(etiqueta)
        st.dataframe(
            tabla[["id", "nombre", "email", "titulo_maximo", "areas", "anios_experiencia", "estado", "origen"]]
            .rename(columns={
                "id": "ID", "nombre": "Nombre", "email": "Email", "titulo_maximo": "Título",
                "areas": "Áreas", "anios_experiencia": "Años exp.", "estado": "Estado", "origen": "Origen",
            }),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(f"{len(docentes)} docente(s)")


def _alta():
    """Alta manual."""
    with st.form("alta_docente", clear_on_submit=True):
        nombre = st.text_input("Nombre y apellido *")
        email = st.text_input("Email *")
        c1, c2 = st.columns(2)
        titulo_nuevo = c1.selectbox("Título máximo *", TITULOS, format_func=etiqueta)
        anios = c2.number_input("Años de experiencia", min_value=0, max_value=60, value=0)
        areas_txt = st.text_input("Áreas de conocimiento (separadas por coma)", placeholder="Programación, Redes")
        enviar = st.form_submit_button("Guardar docente", type="primary")

    if enviar:
        datos = {
            "nombre": nombre,
            "email": email,
            "titulo_maximo": titulo_nuevo,
            "anios_experiencia": int(anios),
            "areas": [a.strip() for a in areas_txt.split(",") if a.strip()],
        }
        try:
            creado = api.crear_docente(datos)
            st.session_state["mensaje_ok"] = f"Se guardó a {creado['nombre']} (ID {creado['id']})."
            st.rerun()
        except ApiError as e:
            st.error(str(e))


def _desde_cv():
    """Alta desde CV con IA."""
    st.write(
        "Subí el CV de un docente (.txt o .pdf). La IA extrae los datos, el sistema los valida "
        "y el docente queda **pendiente de revisión** hasta que una persona lo confirme."
    )
    archivo = st.file_uploader("CV del docente", type=["txt", "pdf"])
    if archivo is not None and st.button("Analizar CV con IA", type="primary"):
        with st.spinner("La IA está leyendo el CV... (puede tardar un minuto)"):
            try:
                st.session_state["resultado_cv"] = api.cargar_cv(archivo.name, archivo.getvalue())
            except ApiError as e:
                st.session_state.pop("resultado_cv", None)
                st.error(str(e))

    resultado = st.session_state.get("resultado_cv")
    if resultado:
        datos = resultado["datos_extraidos"]
        st.markdown("**Datos que leyó la IA (ya validados por el sistema):**")
        st.dataframe(
            pd.DataFrame([{
                "Nombre": datos["nombre"] or "—",
                "Email": datos["email"] or "—",
                "Título": etiqueta(datos["titulo_maximo"]) if datos["titulo_maximo"] else "—",
                "Áreas": ", ".join(datos["areas"]) or "—",
                "Años exp.": datos["anios_experiencia"],
            }]),
            hide_index=True,
            use_container_width=True,
        )
        if resultado["resultado"] == "creado":
            docente = resultado["docente"]
            st.success(
                f"Se cargó a {docente['nombre']} como **pendiente de revisión**. "
                "Revisalo en la pestaña *Editar / confirmar revisión* para habilitarlo."
            )
            if docente.get("resumen"):
                st.info(f"**Resumen generado por IA:** {docente['resumen']}")
        else:
            faltan = ", ".join(NOMBRES_CAMPOS.get(c, c) for c in resultado["campos_faltantes"])
            st.warning(
                f"No se cargó el docente: en el CV faltan datos obligatorios ({faltan}). "
                "Completalo a mano en la pestaña *Nuevo docente*."
            )


def _editar():
    """Edición y confirmación de revisión humana."""
    try:
        todos = api.listar_docentes()
    except ApiError as e:
        st.error(str(e))
        return
    if not todos:
        st.info("Todavía no hay docentes cargados.")
        return

    elegido = st.selectbox(
        "Elegí un docente",
        todos,
        format_func=lambda d: f"{d['nombre']} — {etiqueta(d['estado'])}",
    )

    if elegido["estado"] == "pendiente_revision":
        st.warning(
            "Este docente fue cargado por la IA desde un CV. Revisá los datos, corregí lo que haga "
            "falta y marcá **Confirmar revisión** para habilitarlo."
        )
    if elegido.get("resumen"):
        st.info(f"**Resumen generado por IA:** {elegido['resumen']}")

    with st.form(f"editar_{elegido['id']}"):
        nombre_e = st.text_input("Nombre y apellido", elegido["nombre"])
        email_e = st.text_input("Email", elegido["email"])
        c1, c2 = st.columns(2)
        titulo_e = c1.selectbox(
            "Título máximo", TITULOS, index=TITULOS.index(elegido["titulo_maximo"]), format_func=etiqueta
        )
        anios_e = c2.number_input("Años de experiencia", 0, 60, elegido["anios_experiencia"])
        areas_e = st.text_input("Áreas (separadas por coma)", ", ".join(elegido["areas"]))
        confirmar = False
        if elegido["estado"] == "pendiente_revision":
            confirmar = st.checkbox("Confirmar revisión (pasa a Activo)")
        guardar = st.form_submit_button("Guardar cambios", type="primary")

    if guardar:
        cambios = {
            "nombre": nombre_e,
            "email": email_e,
            "titulo_maximo": titulo_e,
            "anios_experiencia": int(anios_e),
            "areas": [a.strip() for a in areas_e.split(",") if a.strip()],
        }
        if confirmar:
            cambios["estado"] = "activo"
        try:
            api.actualizar_docente(elegido["id"], cambios)
            st.session_state["mensaje_ok"] = f"Se actualizó a {nombre_e}."
            st.rerun()
        except ApiError as e:
            st.error(str(e))
