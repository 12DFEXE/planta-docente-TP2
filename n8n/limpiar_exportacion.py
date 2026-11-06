"""Limpia los workflows exportados de n8n antes de subirlos a Git.

n8n 2.x, al exportar, agrega datos de la instalación de quien exporta:
el dueño del proyecto (con su EMAIL), IDs internos, versiones de publicación
y fechas. Nada de eso hace falta para importar el workflow en otra computadora,
y el email no se tiene que subir al repositorio.

Este script deja solo lo necesario (nombre, nodos, conexiones y configuración)
y guarda cada workflow con el nombre de archivo de siempre (1_ingreso_cv.json, ...).

Uso (desde la carpeta del proyecto, con Python instalado en la computadora):
    docker compose exec n8n n8n export:workflow --all --separate --pretty --output=/workflows/exportados
    python n8n/limpiar_exportacion.py
    (después se puede borrar la carpeta n8n/workflows/exportados, que Git ignora)
"""
import json
import re
import sys
from pathlib import Path

CARPETA_WORKFLOWS = Path(__file__).parent / "workflows"
CARPETA_EXPORTADOS = CARPETA_WORKFLOWS / "exportados"

# Lo único que se conserva de cada workflow (en este orden, igual que los archivos del repo)
CAMPOS = ["name", "nodes", "connections", "active", "settings", "pinData"]


def limpiar(workflow: dict) -> dict:
    """Devuelve una copia del workflow solo con los campos necesarios."""
    limpio = {campo: workflow[campo] for campo in CAMPOS if campo in workflow}
    limpio["active"] = False   # se publica a mano en cada instalación
    limpio["pinData"] = {}     # datos de prueba fijados en el editor: no se versionan
    for nodo in limpio["nodes"]:
        if "credentials" in nodo:  # por si alguien agrega un nodo con credenciales
            print(f"  Aviso: se quitaron las credenciales del nodo '{nodo['name']}'")
            del nodo["credentials"]
    return limpio


def nombre_de_archivo(nombre_workflow: str) -> str:
    """'1 - Ingreso de CV con IA' → el archivo que ya existe y empieza con '1_'.
    Si no existe ninguno, arma uno nuevo a partir del nombre."""
    numero = re.match(r"\s*(\d+)", nombre_workflow)
    if numero:
        existentes = sorted(CARPETA_WORKFLOWS.glob(f"{numero.group(1)}_*.json"))
        if existentes:
            return existentes[0].name
    texto = re.sub(r"[^a-z0-9]+", "_", nombre_workflow.lower()).strip("_")
    return f"{texto}.json"


def main() -> int:
    archivos = sorted(CARPETA_EXPORTADOS.glob("*.json"))
    if not archivos:
        print(f"No hay archivos en {CARPETA_EXPORTADOS}. Primero exportá los workflows desde n8n.")
        return 1

    for archivo in archivos:
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        # sin --separate, n8n exporta una lista con todos los workflows en un solo archivo
        workflows = contenido if isinstance(contenido, list) else [contenido]
        for workflow in workflows:
            destino = CARPETA_WORKFLOWS / nombre_de_archivo(workflow["name"])
            texto = json.dumps(limpiar(workflow), indent=2, ensure_ascii=False)
            destino.write_text(texto, encoding="utf-8", newline="\n")
            print(f"{workflow['name']}  →  {destino.relative_to(CARPETA_WORKFLOWS.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
