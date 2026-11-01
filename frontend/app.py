"""Interfaz Streamlit de Planta Docente.

Esta pantalla NO tiene lógica de negocio ni toca la base de datos:
todo lo pide a la API a través de api_client.py y solo muestra los resultados.
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import api_client as api
from api_client import NOMBRES_CAMPOS, ApiError

st.set_page_config(page_title="Planta Docente", page_icon="🎓", layout="wide")

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


# ======================= Menú lateral =======================

st.sidebar.title("🎓 Planta Docente")
pagina = st.sidebar.radio(
    "Ir a",
    ["📊 Tablero", "👩‍🏫 Docentes", "📚 Materias", "🔗 Asignaciones"],
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


# ======================= Tablero =======================

def pagina_tablero():
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
        st.warning(f"Hay {resp['cantidad']} designación(es) vencida(s) o por vencer.")
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


# ======================= Docentes =======================

def pagina_docentes():
    st.title("👩‍🏫 Docentes")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta, tab_cv, tab_editar = st.tabs(
        ["Listado", "Nuevo docente", "🤖 Cargar desde CV (IA)", "Editar / confirmar revisión"]
    )

    # ---- Listado con filtros ----
    with tab_lista:
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

    # ---- Alta manual ----
    with tab_alta:
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

    # ---- Alta desde CV con IA ----
    with tab_cv:
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

    # ---- Edición y confirmación de revisión humana ----
    with tab_editar:
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


# ======================= Materias =======================

def pagina_materias():
    st.title("📚 Materias")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta = st.tabs(["Listado y cobertura", "Nueva materia"])

    with tab_lista:
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

    with tab_alta:
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


# ======================= Asignaciones =======================

def pagina_asignaciones():
    st.title("🔗 Asignaciones")
    mostrar_mensaje_guardado()

    tab_lista, tab_alta = st.tabs(["Listado", "Nueva asignación"])

    with tab_lista:
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

    with tab_alta:
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


# ======================= Router =======================

if pagina == "📊 Tablero":
    pagina_tablero()
elif pagina == "👩‍🏫 Docentes":
    pagina_docentes()
elif pagina == "📚 Materias":
    pagina_materias()
else:
    pagina_asignaciones()
