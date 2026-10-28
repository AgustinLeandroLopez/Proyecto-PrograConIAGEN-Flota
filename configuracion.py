"""Carga la configuración local del asistente sin dependencias externas."""
import os
from pathlib import Path


def cargar_configuracion(ruta=None):
    """Lee KEY=VALUE y comillas opcionales; el entorno tiene prioridad.

    Solo admite las dos variables de Gemini. No expande variables ni ejecuta
    contenido del archivo. Las líneas vacías y los comentarios se omiten.
    """
    ruta = Path(ruta) if ruta is not None else Path(__file__).with_name(".env")
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        nombre, separador, valor = linea.partition("=")
        nombre, valor = nombre.strip(), valor.strip()
        if not separador or nombre not in ("GEMINI_API_KEY", "GEMINI_MODEL"):
            continue
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        if valor:
            os.environ.setdefault(nombre, valor)
