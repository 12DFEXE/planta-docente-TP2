# Verificación del funcionamiento

Cómo comprobamos que cada componente funciona por separado y que el sistema funciona integrado.

## 1. Verificación automática (API + reglas de negocio)

```bash
docker compose exec api python -m app.verificacion
```

- Prueba **44 casos** contra la API real (FastAPI), sobre una **base de datos temporal** (no toca los datos reales).
- La IA se reemplaza por una **simulada** para que las pruebas sean rápidas y repetibles. La IA real se prueba a mano (punto 3).
- Si algún caso falla, el comando termina con error y muestra qué se esperaba y qué se obtuvo.

| Grupo | Qué se verifica | Ejemplos de casos de error |
|---|---|---|
| Docentes | Alta, búsqueda, filtros, modificación, normalización de datos | Email repetido (409), nombre corto / email inválido / título inexistente (422), docente inexistente (404) |
| Materias | Alta y validación | Materia repetida (409), horas fuera de rango (422) |
| Asignaciones | Las 5 reglas de negocio | Asignación repetida, horas de más para la materia, tope por dedicación, docente pendiente de revisión (409), fecha pasada (422) |
| Renovación | Renovar y que la designación salga de las alertas | Fecha no posterior al vencimiento actual / docente no activo (409), fecha pasada (422), asignación inexistente (404) |
| Indicadores y alertas | Cálculos con reglas | % de posgrado, materias sin cobertura, ventana de días de las alertas, días fuera de rango (422) |
| CV con IA | Proceso completo con IA simulada | CV sin email → "incompleto", formato no permitido (422), archivo sin texto (422), IA apagada (503), IA con respuesta inválida (502) |
| Reporte y notificaciones | Separación regla / IA, avisos de n8n | Nivel de notificación inválido (422) |

## 2. Datos de ejemplo

```bash
docker compose exec api python -m app.datos_ejemplo --reset
```

Carga datos **ficticios** pensados para la demo (pasan por las mismas validaciones que la API):
- 6 docentes activos y 1 **pendiente de revisión** (cargado "por IA").
- 8 materias, de las cuales 2 quedan **sin cobertura** (Estadística y parte de Programación II).
- 7 asignaciones: 1 **ya vencida**, 2 **por vencer** en menos de 30 días y el resto a futuro.

Con `--reset` se borran los datos y se vuelven a cargar. Funciona también con la base vacía (antes fallaba con `no such table` si las tablas todavía no existían: se corrigió haciendo que `borrar_todo()` las cree primero).

## 3. Verificación manual de la IA real (Ollama)

| Prueba | Resultado esperado |
|---|---|
| `GET /ia/estado` | `"disponible": true` con el modelo `qwen2.5:3b` |
| Cargar `data/ejemplos/cv_laura_martinez.txt` desde la pantalla | Docente creado como *pendiente de revisión*, con resumen generado |
| Cargar `cv_martin_gomez_sin_email.txt` | Aviso "faltan datos obligatorios: Email", no se guarda |
| Cerrar Ollama y repetir | Mensaje claro "No se pudo conectar con Ollama…" (503); el resto del sistema sigue funcionando |
| Generar el reporte desde el Tablero | Texto redactado por IA, separado de los números calculados |

**Dificultad encontrada:** el modelo local a veces devuelve el título con otras palabras ("Magíster", "Licenciada") o los años como texto. Por eso la salida de la IA se **normaliza y valida en Python** antes de guardarse, y el docente queda pendiente hasta que una persona lo confirma.

## 4. Verificación de los workflows de n8n

Se probaron todos los caminos de cada workflow:

| Workflow | Caminos probados |
|---|---|
| 1 · Ingreso de CV | CV completo → "pendiente de revisión"; CV sin email → "incompleto"; email repetido, archivo inválido e IA apagada → aviso de error |
| 2 · Vencimientos | Con designaciones por vencer → aviso (urgente si alguna venció); sin vencimientos → "sin novedades" |
| 3 · Reporte semanal | Con materias sin cobertura → alerta prioritaria; todo cubierto → reporte normal; IA apagada → aviso de error |

En n8n, la pestaña **Executions** muestra cada ejecución con los datos de entrada y salida de cada nodo.

## 5. Guion para la demo

1. `docker compose ps` → los tres contenedores en *Up*. Mostrar que Ollama está corriendo.
2. **Tablero**: indicadores (calculados con reglas), materias sin cobertura y designaciones por vencer.
3. **Docentes → Cargar desde CV**: subir `cv_laura_martinez.txt` → queda *pendiente de revisión* con resumen de IA.
4. **Docentes → Editar / confirmar revisión**: revisar y confirmar → pasa a *activo* (supervisión humana).
5. **Asignaciones → Nueva**: asignarla a Programación II por 2 h → la materia queda cubierta.
6. **Caso de error**: repetir la misma asignación → mensaje de la regla de negocio. Cargar `cv_martin_gomez_sin_email.txt` → "faltan datos".
7. **n8n**: ejecutar el workflow 2 y el 3 y mostrar el camino que toma el IF. Mandar un CV al webhook del workflow 1.
8. **Notificaciones**: mostrar los avisos que dejaron los workflows.
9. **Asignaciones → Renovar designación**: renovar la designación vencida que avisó el workflow 2 → en el Tablero ya no aparece como vencida (se cierra el ciclo alerta → acción humana).
10. **Swagger** (`/docs`): mostrar los endpoints y probar uno.
11. `docker compose exec api python -m app.verificacion` → 44 de 44.
