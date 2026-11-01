# Bitácora de uso de IA

| Fecha | Herramienta | Para qué se usó | Decisión / resultado | Correcciones |
|---|---|---|---|---|
| 31/10/2026 | Claude | Definir alcance del Proyecto B, endpoints, workflows y estructura del repo | Se eligió FastAPI + Streamlit + n8n en Docker Compose, SQLite y Ollama local | Se ajustó el alcance para cubrir "resumir perfiles" |
| 31/10–01/11/2026 | Claude | Generar endpoints de docentes, materias, asignaciones, indicadores y la interfaz Streamlit | Se separó la lógica (módulos) de la API (main.py) y de la pantalla (app.py + api_client.py); validación en tres capas | Se agregó la traducción de errores 422 a mensajes en español; se centralizó el manejo de excepciones |
| 01/11/2026 | Claude | Diseñar la integración de IA (extracción de CVs, resumen de perfil y reporte) | Ollama local con qwen2.5:3b: gratis, sin enviar datos personales a internet, buen soporte de JSON y español | La salida de la IA se valida con reglas en Python (título, email, áreas, años) y el docente queda pendiente de revisión humana |
| 01/11/2026 | Ollama (qwen2.5:3b) | Funcionalidad del sistema: leer CVs, resumir perfiles y redactar el reporte | La IA propone; Python valida; una persona confirma | Se manejan los casos de IA apagada (503), modelo sin descargar y respuesta inválida (502) |
