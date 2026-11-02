# Guía para la defensa

Preguntas probables del docente y cómo responderlas. Cada integrante tiene que poder explicar **todas** las partes.

## Arquitectura

**¿Cómo está armado el sistema?**
Cuatro piezas: Streamlit (interfaz), FastAPI (API con la lógica), n8n (automatizaciones) y Ollama (IA). Las tres primeras corren en Docker Compose; Ollama corre en la computadora. La base es SQLite.

**¿Cómo se comunican?**
Por HTTP con JSON. Streamlit y n8n llaman a la API en `http://api:8000`: Compose crea una red interna donde cada servicio se encuentra por su nombre. La API llega a Ollama en `host.docker.internal:11434`.

**¿Por qué `api:8000` y no `localhost:8000` dentro de n8n?**
Porque para un contenedor, `localhost` es él mismo. `api` es el nombre del servicio en `compose.yaml`.

**¿Por qué Docker Compose?**
Levanta todo con un comando, conecta los servicios por nombre y hace que el sistema funcione igual en cualquier computadora. Los datos persisten en volúmenes (`./data` y `n8n_data`).

**¿Por qué Ollama fuera de Docker?**
En un contenedor sin placa de video es mucho más lento, y la consigna permite correr el modelo localmente.

## Python y API

**¿Cómo está organizada la API?**
En capas: `main.py` (endpoints), `schemas.py` (validación de forma con Pydantic), los módulos de lógica (`docentes.py`, `asignaciones.py`, etc.) y `database.py` (persistencia). La lógica no sabe nada de HTTP.

**¿Cómo manejan los errores?**
La lógica lanza excepciones propias (`NoEncontrado`, `Conflicto`, `DatosInvalidos`) y `main.py` las convierte en un solo lugar en códigos HTTP: 404, 409 y 422. Los errores de la IA dan 503 (no disponible) o 502 (respuesta inválida).

**¿Dónde validan?**
En tres capas: Pydantic valida la forma (422), la lógica valida las reglas que dependen de otros datos (404/409) y la base garantiza integridad con `NOT NULL` y `UNIQUE`.

**¿Qué hace `schemas.py`?**
Define los "formularios" de la API: qué campos acepta, de qué tipo y con qué límites, y qué devuelve cada endpoint.

**¿Qué diferencia hay entre `schemas.py` y `database.py`?**
`schemas.py` es la forma de los datos en la API; `database.py`, la forma en que se guardan. No son iguales: por ejemplo, la cobertura de una materia se calcula y no se guarda.

**Nombrá una regla de negocio.**
Un docente con dedicación simple no puede superar 10 horas semanales. Está en `asignaciones.py`, en `TOPE_HORAS`.

## Streamlit

**¿La interfaz tiene lógica?**
No. Todo lo pide a la API a través de `api_client.py`, que además traduce los errores técnicos a mensajes claros. Si se cambiara la interfaz, las reglas seguirían funcionando.

**¿Qué pasa si la API está apagada?**
La pantalla muestra "No se pudo conectar con la API" y no sigue dibujando.

## Inteligencia artificial

**¿Qué modelo usaron y por qué?**
`qwen2.5:3b` con Ollama: gratis, local (los CVs tienen datos personales y no salen de la computadora), liviano, en español y responde en JSON.

**¿Cuáles son sus límites?**
Puede equivocarse o inventar datos y es lento sin placa de video.

**¿Cómo controlan lo que hace la IA?**
La IA propone, Python valida y una persona confirma. Lo que devuelve se normaliza y valida (título, email, años); si falta algo obligatorio no se guarda; y el docente queda pendiente de revisión hasta que alguien lo confirma. Mientras esté pendiente, no se le pueden asignar materias.

**¿Qué se calcula con reglas y qué con IA?**
Indicadores, alertas y validaciones son reglas (resultado exacto). La IA solo interpreta texto libre (CVs) y redacta (resumen y reporte). En el reporte, la API devuelve los números y el texto de la IA en campos separados.

**¿Qué pasa si Ollama está apagado?**
La API responde 503 con un mensaje claro y el resto del sistema sigue funcionando. En n8n, el workflow toma el camino de error y deja un aviso.

## n8n

**¿Para qué usan n8n?**
Para las tareas que tienen que pasar solas: ingreso de CVs por webhook, aviso diario de vencimientos y reporte semanal. La lógica está en la API; n8n decide cuándo ejecutar cada cosa y a quién avisar.

**¿Cuál es la decisión de cada workflow?**
1: ¿se creó el docente o el CV está incompleto? · 2: ¿hay designaciones por vencer? · 3: ¿hay materias sin cobertura?

**¿Por qué las notificaciones quedan en el sistema y no por email?**
Para que la demo no dependa de credenciales ni de servicios externos. Cambiar el destino a email o Telegram sería reemplazar un nodo.

**¿Por qué n8n y no un agente de IA?**
Las tareas son repetitivas y con reglas fijas: n8n las ejecuta de forma predecible, auditable y sin costo. La IA se usa solo donde hace falta interpretar texto.

## Verificación

**¿Cómo verificaron el sistema?**
Con 38 casos automáticos (`python -m app.verificacion`) sobre una base temporal y con IA simulada, más pruebas manuales de la IA real y de todos los caminos de los workflows. Detalle en `docs/verificacion.md`.

**¿Qué dificultades tuvieron?**
- El modelo devolvía el título con otras palabras ("Magíster") o los años como texto → se agregó la normalización en Python.
- Ollama no era accesible desde Docker en Windows → variable `OLLAMA_HOST=0.0.0.0`.
- Los errores de la API llegaban a n8n como texto técnico → se extrajo el mensaje `detail` en el nodo de aviso.

## Si piden una modificación en vivo

| Pedido | Dónde se cambia |
|---|---|
| Cambiar el tope de horas | `api/app/asignaciones.py` → `TOPE_HORAS` (la API se recarga sola) |
| Agregar un indicador | `api/app/indicadores.py` + el campo en `schemas.py` (`Indicadores`) + mostrarlo en `frontend/app.py` |
| Agregar un campo al docente | `database.py` (tabla), `schemas.py`, `docentes.py` y el formulario en `app.py` |
| Cambiar los días de la alerta | En n8n, nodo "Consultar vencimientos", parámetro `dias` |
| Cambiar el horario de un workflow | En n8n, nodo Schedule |
| Cambiar el modelo de IA | `.env` → `OLLAMA_MODEL`, descargarlo con `ollama pull` y `docker compose up -d api` |
