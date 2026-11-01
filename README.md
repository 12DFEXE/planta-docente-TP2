# Sistema de Gestión de Planta Docente

TP2 — Elementos de Programación IA y LowCode (2.º cuatrimestre 2026).

## Objetivo
Organizar, consultar y analizar la planta docente de una institución: alta de docentes desde formulario o CV (con extracción por IA y revisión humana), asignación de materias, indicadores y automatizaciones con n8n.

## Componentes y puertos

| Servicio | Tecnología | Puerto | URL |
|---|---|---|---|
| api | FastAPI | 8000 | http://localhost:8000/docs |
| frontend | Streamlit | 8501 | http://localhost:8501 |
| n8n | n8n | 5678 | http://localhost:5678 |
| IA | Ollama (en el host) | 11434 | http://localhost:11434 |

Dentro de Docker, los servicios se comunican por nombre: el frontend llama a `http://api:8000` y n8n también usa `http://api:8000`. La API llega a Ollama en `host.docker.internal:11434`.

## Requisitos
- Docker Desktop (o Docker Engine + Compose)
- Ollama instalado en el host, con el modelo descargado: `ollama pull qwen2.5:3b`

## Cómo ejecutar

```bash
cp .env.example .env          # en Windows: copy .env.example .env
docker compose up -d --build  # iniciar
docker compose ps             # ver estado
docker compose logs -f api    # ver logs de un servicio
docker compose restart        # reiniciar
docker compose down           # detener
```

## Workflows de n8n

Los tres workflows están exportados en `n8n/workflows/` (también se pueden regenerar con `python n8n/generar_workflows.py`).

| Workflow | Disparador | Qué hace | Decisión |
|---|---|---|---|
| 1 - Ingreso de CV con IA | Webhook `POST /webhook/cv` | Manda el CV a `POST /docentes/cv` | ¿Se creó el docente? → aviso "pendiente de revisión" / aviso "CV incompleto". Si la API falla → aviso de error |
| 2 - Alertas de vencimiento | Todos los días 8:00 (o manual) | Consulta `GET /alertas/vencimientos?dias=30` | ¿Hay designaciones por vencer? → aviso (urgente si alguna ya venció) / sin novedades |
| 3 - Reporte semanal con IA | Lunes 9:00 (o manual) | Pide `POST /reportes/resumen` (indicadores + texto de IA) | ¿Hay materias sin cobertura? → alerta prioritaria / reporte normal. Si la IA falla → aviso de error |

Los avisos se guardan con `POST /notificaciones` y se ven en la pantalla, sección **Notificaciones**.

Importar los workflows (una sola vez, con los contenedores prendidos):

```bash
docker compose exec n8n n8n import:workflow --separate --input=/workflows
```

Probar el workflow 1 enviando un CV de ejemplo (después de activarlo en n8n):

```bash
curl -F "archivo=@data/ejemplos/cv_laura_martinez.txt" http://localhost:5678/webhook/cv
```

## Estructura

```
api/            FastAPI (lógica, endpoints, persistencia)
frontend/       Streamlit (interfaz)
n8n/workflows/  Workflows exportados en JSON
data/           Base SQLite (no se versiona) y datos de ejemplo
docs/           Arquitectura y bitácora de IA
```

## Integrantes y responsabilidades
- Martin: _completar_
- Exequiel: _completar_
