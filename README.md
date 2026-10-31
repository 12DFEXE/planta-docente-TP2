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
- Ollama instalado en el host (se configura en el Paso 5)

## Cómo ejecutar

```bash
cp .env.example .env          # en Windows: copy .env.example .env
docker compose up -d --build  # iniciar
docker compose ps             # ver estado
docker compose logs -f api    # ver logs de un servicio
docker compose restart        # reiniciar
docker compose down           # detener
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
