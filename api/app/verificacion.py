"""Verificación automática del sistema: prueba los casos correctos y los de error.

Uso (con los contenedores prendidos):
    docker compose exec api python -m app.verificacion

- Usa una base de datos TEMPORAL: no toca los datos reales.
- Reemplaza la IA por una simulada, para que las pruebas sean rápidas y siempre
  den el mismo resultado (la IA real se prueba a mano desde la pantalla o n8n).
- Al final muestra cuántos casos pasaron. Si alguno falla, termina con código 1.
"""
import os
import sys
import tempfile
from datetime import date, timedelta

from fastapi.testclient import TestClient

from . import database, ia

# ---------- Preparación: base temporal e IA simulada ----------

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_PATH = _tmp.name  # todas las funciones usan esta base mientras dura la prueba

MODO_IA = {"estado": "ok"}  # "ok" | "apagada" | "rota"


def _ia_simulada_extraer(texto: str) -> dict:
    if MODO_IA["estado"] == "apagada":
        raise ia.IANoDisponible("IA simulada apagada")
    if MODO_IA["estado"] == "rota":
        raise ia.RespuestaIAInvalida("IA simulada devolvió cualquier cosa")
    if "sin_email" in texto:
        return {"nombre": "Docente Sin Email", "email": None, "titulo_maximo": "Licenciado",
                "areas": ["Redes"], "anios_experiencia": 3}
    return {"nombre": "Laura Martínez", "email": "laura.cv@ejemplo.edu.ar", "titulo_maximo": "Magíster",
            "areas": "Bases de datos, Python", "anios_experiencia": "10"}


def _ia_simulada_texto(*_args) -> str:
    if MODO_IA["estado"] == "apagada":
        raise ia.IANoDisponible("IA simulada apagada")
    return "Texto generado por la IA simulada."


ia.extraer_datos_cv = _ia_simulada_extraer
ia.resumir_perfil = _ia_simulada_texto
ia.redactar_reporte = _ia_simulada_texto

from .main import app  # noqa: E402  (se importa después de preparar la base y la IA)

# ---------- Registro de resultados ----------

RESULTADOS = []


def caso(descripcion: str, obtenido, esperado) -> None:
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    marca = "OK  " if ok else "FALLA"
    detalle = "" if ok else f"  (esperado {esperado}, obtenido {obtenido})"
    print(f"  [{marca}] {descripcion}{detalle}")


def futuro(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()


# ---------- Casos ----------

def verificar(c: TestClient) -> None:
    print("\n1. Docentes")
    r = c.post("/docentes", json={"nombre": "Ana Pérez", "email": "ANA@ejemplo.edu.ar",
                                  "titulo_maximo": "maestria", "areas": ["Programación", " programación "]})
    caso("Alta válida → 201", r.status_code, 201)
    caso("Email se guarda en minúsculas", r.json()["email"], "ana@ejemplo.edu.ar")
    caso("Áreas repetidas se unifican", r.json()["areas"], ["Programación"])
    caso("Email repetido → 409", c.post("/docentes", json={"nombre": "Otra", "email": "ana@ejemplo.edu.ar",
                                                          "titulo_maximo": "grado"}).status_code, 409)
    caso("Nombre corto, email inválido, título inexistente → 422",
         c.post("/docentes", json={"nombre": "Jo", "email": "mal", "titulo_maximo": "secundario"}).status_code, 422)
    caso("Años de experiencia negativos → 422",
         c.post("/docentes", json={"nombre": "Pedro", "email": "p@e.ar", "titulo_maximo": "grado",
                                   "anios_experiencia": -1}).status_code, 422)
    caso("Docente inexistente → 404", c.get("/docentes/999").status_code, 404)
    c.post("/docentes", json={"nombre": "Bruno Díaz", "email": "bruno@ejemplo.edu.ar", "titulo_maximo": "grado",
                              "areas": ["Redes"]})
    caso("Filtro por título", [d["nombre"] for d in c.get("/docentes?titulo=grado").json()], ["Bruno Díaz"])
    caso("Búsqueda por texto", len(c.get("/docentes?texto=ana").json()), 1)
    caso("Modificar docente → 200", c.put("/docentes/2", json={"anios_experiencia": 5}).status_code, 200)

    print("\n2. Materias")
    caso("Alta de materia → 201", c.post("/materias", json={"nombre": "Programación I", "area": "Programación",
                                                           "horas_semanales": 6}).status_code, 201)
    caso("Materia repetida → 409", c.post("/materias", json={"nombre": "Programación I", "area": "Otra área",
                                                            "horas_semanales": 4}).status_code, 409)
    caso("Horas fuera de rango → 422", c.post("/materias", json={"nombre": "Redes", "area": "Infra",
                                                                "horas_semanales": 50}).status_code, 422)
    c.post("/materias", json={"nombre": "Redes", "area": "Infraestructura", "horas_semanales": 4})

    print("\n3. Asignaciones (reglas de negocio)")
    base = {"dedicacion": "simple", "fecha_vencimiento": futuro(90)}
    caso("Asignación válida → 201",
         c.post("/asignaciones", json={**base, "docente_id": 1, "materia_id": 1, "horas": 4}).status_code, 201)
    caso("Regla: asignación repetida → 409",
         c.post("/asignaciones", json={**base, "docente_id": 1, "materia_id": 1, "horas": 1}).status_code, 409)
    caso("Regla: más horas de las que necesita la materia → 409",
         c.post("/asignaciones", json={**base, "docente_id": 2, "materia_id": 1, "horas": 3}).status_code, 409)
    c.post("/materias", json={"nombre": "Bases de Datos", "area": "Datos", "horas_semanales": 8})
    caso("Regla: supera el tope de 10 h (simple) → 409",
         c.post("/asignaciones", json={**base, "docente_id": 1, "materia_id": 3, "horas": 8}).status_code, 409)
    caso("Fecha de vencimiento pasada → 422",
         c.post("/asignaciones", json={**base, "docente_id": 2, "materia_id": 2, "horas": 2,
                                       "fecha_vencimiento": "2020-01-01"}).status_code, 422)
    caso("Materia inexistente → 404",
         c.post("/asignaciones", json={**base, "docente_id": 2, "materia_id": 99, "horas": 2}).status_code, 404)
    c.put("/docentes/2", json={"estado": "pendiente_revision"})
    caso("Regla: docente pendiente de revisión → 409",
         c.post("/asignaciones", json={**base, "docente_id": 2, "materia_id": 2, "horas": 2}).status_code, 409)
    c.put("/docentes/2", json={"estado": "activo"})

    print("\n4. Indicadores y alertas (reglas de cálculo)")
    c.post("/asignaciones", json={"docente_id": 2, "materia_id": 2, "dedicacion": "simple", "horas": 4,
                                  "fecha_vencimiento": futuro(10)})
    ind = c.get("/indicadores").json()
    caso("Docentes activos", ind["docentes_activos"], 2)
    caso("% con posgrado (1 de 2)", ind["porcentaje_posgrado"], 50.0)
    caso("Materias sin cobertura detectadas",
         sorted(m["nombre"] for m in ind["materias_sin_cobertura"]), ["Bases de Datos", "Programación I"])
    alertas = c.get("/alertas/vencimientos?dias=30").json()
    caso("Alerta: vence en 10 días aparece con 30 días de margen", alertas["cantidad"], 1)
    caso("Alerta: con 5 días de margen no aparece", c.get("/alertas/vencimientos?dias=5").json()["cantidad"], 0)
    caso("Días fuera de rango → 422", c.get("/alertas/vencimientos?dias=0").status_code, 422)

    print("\n4b. Renovación de designaciones (cierra el ciclo de las alertas)")
    id_por_vencer = alertas["alertas"][0]["id"]  # la que vence en 10 días
    ruta = f"/asignaciones/{id_por_vencer}/renovar"
    r = c.put(ruta, json={"fecha_vencimiento": futuro(365)})
    caso("Renovar designación → 200 con la fecha nueva",
         (r.status_code, r.json().get("fecha_vencimiento")), (200, futuro(365)))
    caso("Después de renovar, ya no aparece en las alertas",
         c.get("/alertas/vencimientos?dias=30").json()["cantidad"], 0)
    caso("Regla: fecha no posterior al vencimiento actual → 409",
         c.put(ruta, json={"fecha_vencimiento": futuro(200)}).status_code, 409)
    caso("Fecha de renovación pasada → 422",
         c.put(ruta, json={"fecha_vencimiento": "2020-01-01"}).status_code, 422)
    caso("Renovar asignación inexistente → 404",
         c.put("/asignaciones/999/renovar", json={"fecha_vencimiento": futuro(400)}).status_code, 404)
    c.put("/docentes/2", json={"estado": "pendiente_revision"})
    caso("Regla: docente no activo no se puede renovar → 409",
         c.put(ruta, json={"fecha_vencimiento": futuro(500)}).status_code, 409)
    c.put("/docentes/2", json={"estado": "activo"})

    print("\n5. Carga de CV con IA (IA simulada)")
    r = c.post("/docentes/cv", files={"archivo": ("cv.txt", "CV de Laura Martínez, magíster, 10 años".encode())})
    caso("CV completo → creado", r.json().get("resultado"), "creado")
    caso("Python normaliza 'Magíster' → maestria", r.json()["datos_extraidos"]["titulo_maximo"], "maestria")
    caso("Queda pendiente de revisión humana", r.json()["docente"]["estado"], "pendiente_revision")
    r = c.post("/docentes/cv", files={"archivo": ("cv.txt", "CV de prueba sin_email, licenciado en redes".encode())})
    caso("CV sin email → incompleto (no se guarda)", (r.json()["resultado"], r.json()["campos_faltantes"]),
         ("incompleto", ["email"]))
    caso("Archivo con formato no permitido → 422",
         c.post("/docentes/cv", files={"archivo": ("cv.docx", b"hola")}).status_code, 422)
    caso("Archivo sin texto suficiente → 422",
         c.post("/docentes/cv", files={"archivo": ("cv.txt", b"corto")}).status_code, 422)
    MODO_IA["estado"] = "apagada"
    caso("IA apagada → 503 (mensaje claro, el sistema sigue andando)",
         c.post("/docentes/cv", files={"archivo": ("cv.txt", "CV de otra persona con texto suficiente".encode())}
                ).status_code, 503)
    MODO_IA["estado"] = "rota"
    caso("IA responde algo inválido → 502",
         c.post("/docentes/cv", files={"archivo": ("cv.txt", "CV de otra persona con texto suficiente".encode())}
                ).status_code, 502)
    MODO_IA["estado"] = "ok"

    print("\n6. Reporte y notificaciones")
    r = c.post("/reportes/resumen")
    caso("Reporte → 200 con indicadores y texto de IA separados",
         (r.status_code, "indicadores" in r.json(), bool(r.json().get("resumen_ia"))), (200, True, True))
    caso("Crear notificación (lo que hace n8n) → 201",
         c.post("/notificaciones", json={"origen": "verificación", "nivel": "alerta", "titulo": "Prueba",
                                         "mensaje": "Mensaje de prueba"}).status_code, 201)
    caso("Notificación con nivel inválido → 422",
         c.post("/notificaciones", json={"origen": "x", "nivel": "rarísimo", "titulo": "abc",
                                         "mensaje": "m"}).status_code, 422)
    caso("Marcar como leída", c.put("/notificaciones/1/leida").json()["leida"], True)


if __name__ == "__main__":
    print("Verificación automática del sistema (base temporal + IA simulada)")
    try:
        with TestClient(app) as cliente:
            verificar(cliente)
    finally:
        os.unlink(_tmp.name)
    total, ok = len(RESULTADOS), sum(RESULTADOS)
    print(f"\nResultado: {ok} de {total} casos correctos.")
    sys.exit(0 if ok == total else 1)
