"""
================================================================================
MÓDULO: interfaz/rutas/compartido.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Estado global en memoria, rutas a archivos persistentes y helpers
             compartidos por los diferentes Blueprints de la interfaz web.
LÍNEAS: < 100
================================================================================
"""

import sys
from datetime import datetime
from pathlib import Path

# Raíz del proyecto
RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Rutas persistentes
RUTA_LOG_RT      = RAIZ / "datos_persistencia" / "log_tiempo_real.txt"
RUTA_CONFIG      = RAIZ / "config" / "parametros_globales.json"
RUTA_FUENTES     = RAIZ / "datos_persistencia" / "fuentes_url.txt"
RUTA_HISTORIAL   = RAIZ / "datos_persistencia" / "historial_global_enlaces.txt"
RUTA_PENDIENTES  = RAIZ / "datos_persistencia" / "cola_pendientes.txt"
RUTA_COMPLETADOS = RAIZ / "datos_persistencia" / "enlaces_completados.txt"

# Estado en memoria de las fases (compartido entre hilos y Blueprints)
Estado = {
    "fases": {"1": "idle", "2": "idle", "3": "idle", "4": "idle"},
    "procesos": {"1": None, "2": None, "3": None, "4": None},
}


def escribir_log(nivel: str, mensaje: str) -> None:
    """Escribe una línea en el archivo log_tiempo_real.txt para transmisión SSE."""
    estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    RUTA_LOG_RT.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_LOG_RT, "a", encoding="utf-8") as f:
        f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")


def contar_lineas(ruta: Path) -> int:
    """Cuenta las líneas no vacías de un archivo de texto."""
    if not ruta.exists():
        return 0
    with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for l in f if l.strip())
