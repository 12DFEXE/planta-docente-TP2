"""Genera los 3 workflows de n8n en formato JSON (para importar en n8n).

Uso: python n8n/generar_workflows.py   →  escribe los archivos en n8n/workflows/
No hace falta correrlo para usar el sistema: los JSON ya están en el repositorio.
"""
import json
import uuid
from pathlib import Path

API = "http://api:8000"  # dentro de Docker, n8n llega a la API por el nombre del servicio
SALIDA = Path(__file__).parent / "workflows"


def nid():
    return str(uuid.uuid4())


def nodo(nombre, tipo, version, pos, parametros, **extra):
    return {"id": nid(), "name": nombre, "type": tipo, "typeVersion": version,
            "position": pos, "parameters": parametros, **extra}


def condicion_if(nombre, pos, izquierda, operador, derecha=None, tipo="string"):
    cond = {"id": nid(), "leftValue": izquierda, "operator": {"type": tipo, "operation": operador}}
    if derecha is not None:
        cond["rightValue"] = derecha
    if operador in ("true", "false"):
        cond["operator"]["singleValue"] = True
    return nodo(nombre, "n8n-nodes-base.if", 2, pos, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [cond],
            "combinator": "and",
        },
        "options": {},
    })


def notificar(nombre, pos, origen, nivel, titulo, mensaje):
    """Nodo que crea una notificación en la API (POST /notificaciones)."""
    cuerpo = (
        "={{ JSON.stringify({"
        f" origen: {json.dumps(origen)},"
        f" nivel: {nivel},"
        f" titulo: {titulo},"
        f" mensaje: {mensaje}"
        " }) }}"
    )
    return nodo(nombre, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST",
        "url": f"{API}/notificaciones",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": cuerpo,
        "options": {},
    })


def conectar(*pares):
    """pares: (origen, salida, destino). salida 0 = principal/true, 1 = false/error."""
    conexiones = {}
    for origen, salida, destino in pares:
        salidas = conexiones.setdefault(origen, {"main": []})["main"]
        while len(salidas) <= salida:
            salidas.append([])
        salidas[salida].append({"node": destino, "type": "main", "index": 0})
    return conexiones


def workflow(nombre, nodos, conexiones):
    return {"name": nombre, "nodes": nodos, "connections": conexiones,
            "active": False, "settings": {"executionOrder": "v1"}, "pinData": {}}


# Texto de error legible, venga como venga desde el nodo HTTP
ERROR = ("(() => { const e = $json.error;"
         " const m = typeof e === 'object' ? (e.message || JSON.stringify(e)) : String(e || 'error desconocido');"
         " try { const d = JSON.parse(JSON.parse(m.slice(m.indexOf(' - ') + 3))); return d.detail || m; }"
         " catch (x) { return m; } })()")


# =============== Workflow 1: ingreso de CV ===============
def wf_cv():
    nodos = [
        nodo("Recibir CV (webhook)", "n8n-nodes-base.webhook", 2, [0, 300], {
            "httpMethod": "POST", "path": "cv", "responseMode": "responseNode", "options": {},
        }, webhookId=nid()),
        nodo("Procesar CV con IA (API)", "n8n-nodes-base.httpRequest", 4.2, [240, 300], {
            "method": "POST",
            "url": f"{API}/docentes/cv",
            "sendBody": True,
            "contentType": "multipart-form-data",
            "bodyParameters": {"parameters": [
                {"parameterType": "formBinaryData", "name": "archivo", "inputDataFieldName": "archivo"},
            ]},
            "options": {"timeout": 300000},
        }, onError="continueErrorOutput"),
        condicion_if("¿Se creó el docente?", [500, 200], "={{ $json.resultado }}", "equals", "creado"),
        notificar("Avisar: pendiente de revisión", [760, 100], "n8n: ingreso de CV", "'info'",
                  "'Nuevo docente desde CV: ' + $json.docente.nombre",
                  "'La IA cargó a ' + $json.docente.nombre + ' (' + $json.docente.email + ') como PENDIENTE DE REVISIÓN. "
                  "Revisalo y confirmalo en Docentes → Editar / confirmar revisión.'"),
        notificar("Avisar: CV incompleto", [760, 300], "n8n: ingreso de CV", "'alerta'",
                  "'CV incompleto: requiere carga manual'",
                  "'No se cargó el docente porque en el CV faltan datos obligatorios: ' + $json.campos_faltantes.join(', ') + "
                  "'. Datos leídos: ' + ($json.datos_extraidos.nombre || 'sin nombre') + '.'"),
        notificar("Avisar: error al procesar", [500, 480], "n8n: ingreso de CV", "'alerta'",
                  "'No se pudo procesar un CV'", ERROR),
        nodo("Responder", "n8n-nodes-base.respondToWebhook", 1.1, [1020, 300], {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ aviso: $json.titulo, detalle: $json.mensaje }) }}",
            "options": {},
        }),
    ]
    conexiones = conectar(
        ("Recibir CV (webhook)", 0, "Procesar CV con IA (API)"),
        ("Procesar CV con IA (API)", 0, "¿Se creó el docente?"),
        ("Procesar CV con IA (API)", 1, "Avisar: error al procesar"),
        ("¿Se creó el docente?", 0, "Avisar: pendiente de revisión"),
        ("¿Se creó el docente?", 1, "Avisar: CV incompleto"),
        ("Avisar: pendiente de revisión", 0, "Responder"),
        ("Avisar: CV incompleto", 0, "Responder"),
        ("Avisar: error al procesar", 0, "Responder"),
    )
    return workflow("1 - Ingreso de CV con IA", nodos, conexiones)


# =============== Workflow 2: vencimientos ===============
def wf_vencimientos():
    lista = ("$json.alertas.map(a => '• ' + a.docente_nombre + ' – ' + a.materia_nombre + ': vence el ' + "
             "a.fecha_vencimiento + (a.dias_restantes < 0 ? ' (VENCIDA hace ' + (-a.dias_restantes) + ' días)' "
             ": ' (faltan ' + a.dias_restantes + ' días)')).join('\\n')")
    nodos = [
        nodo("Todos los días 8:00", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 200], {
            "rule": {"interval": [{"field": "days", "triggerAtHour": 8}]},
        }),
        nodo("Ejecutar a mano (demo)", "n8n-nodes-base.manualTrigger", 1, [0, 400], {}),
        nodo("Consultar vencimientos (API)", "n8n-nodes-base.httpRequest", 4.2, [240, 300], {
            "url": f"{API}/alertas/vencimientos",
            "sendQuery": True,
            "queryParameters": {"parameters": [{"name": "dias", "value": "30"}]},
            "options": {},
        }),
        condicion_if("¿Hay designaciones por vencer?", [480, 300], "={{ $json.cantidad }}", "gt", 0, tipo="number"),
        notificar("Avisar vencimientos", [740, 200], "n8n: vencimientos",
                  "($json.alertas.some(a => a.estado === 'vencida') ? 'urgente' : 'alerta')",
                  "$json.cantidad + ' designación(es) vencida(s) o por vencer en ' + $json.dias + ' días'",
                  lista + " + '\\n\\nHay que renovarlas o reasignar las materias.'"),
        nodo("Sin novedades", "n8n-nodes-base.noOp", 1, [740, 400], {}),
    ]
    conexiones = conectar(
        ("Todos los días 8:00", 0, "Consultar vencimientos (API)"),
        ("Ejecutar a mano (demo)", 0, "Consultar vencimientos (API)"),
        ("Consultar vencimientos (API)", 0, "¿Hay designaciones por vencer?"),
        ("¿Hay designaciones por vencer?", 0, "Avisar vencimientos"),
        ("¿Hay designaciones por vencer?", 1, "Sin novedades"),
    )
    return workflow("2 - Alertas de vencimiento", nodos, conexiones)


# =============== Workflow 3: reporte semanal ===============
def wf_reporte():
    faltantes = ("$json.indicadores.materias_sin_cobertura.map(m => '• ' + m.nombre + ': faltan ' + "
                 "m.horas_faltantes + ' h').join('\\n')")
    nodos = [
        nodo("Lunes 9:00", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 200], {
            "rule": {"interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 9}]},
        }),
        nodo("Ejecutar a mano (demo)", "n8n-nodes-base.manualTrigger", 1, [0, 400], {}),
        nodo("Generar reporte con IA (API)", "n8n-nodes-base.httpRequest", 4.2, [240, 300], {
            "method": "POST", "url": f"{API}/reportes/resumen", "options": {"timeout": 300000},
        }, onError="continueErrorOutput"),
        condicion_if("¿Hay materias sin cobertura?", [500, 200], "={{ $json.hay_materias_sin_cobertura }}", "true",
                     tipo="boolean"),
        notificar("Alerta prioritaria", [760, 100], "n8n: reporte semanal", "'urgente'",
                  "'Reporte semanal: ' + $json.indicadores.materias_sin_cobertura.length + ' materia(s) sin cobertura'",
                  "'MATERIAS SIN COBERTURA (dato calculado):\\n' + " + faltantes +
                  " + '\\n\\nRESUMEN REDACTADO POR IA (' + $json.modelo_ia + '):\\n' + $json.resumen_ia"),
        notificar("Reporte normal", [760, 300], "n8n: reporte semanal", "'info'",
                  "'Reporte semanal de la planta docente'",
                  "'RESUMEN REDACTADO POR IA (' + $json.modelo_ia + '):\\n' + $json.resumen_ia"),
        notificar("Avisar: no se pudo generar", [500, 480], "n8n: reporte semanal", "'alerta'",
                  "'No se pudo generar el reporte semanal'", ERROR),
    ]
    conexiones = conectar(
        ("Lunes 9:00", 0, "Generar reporte con IA (API)"),
        ("Ejecutar a mano (demo)", 0, "Generar reporte con IA (API)"),
        ("Generar reporte con IA (API)", 0, "¿Hay materias sin cobertura?"),
        ("Generar reporte con IA (API)", 1, "Avisar: no se pudo generar"),
        ("¿Hay materias sin cobertura?", 0, "Alerta prioritaria"),
        ("¿Hay materias sin cobertura?", 1, "Reporte normal"),
    )
    return workflow("3 - Reporte semanal con IA", nodos, conexiones)


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    for archivo, wf in [("1_ingreso_cv.json", wf_cv()), ("2_alertas_vencimiento.json", wf_vencimientos()),
                        ("3_reporte_semanal.json", wf_reporte())]:
        (SALIDA / archivo).write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Generado:", SALIDA / archivo)
