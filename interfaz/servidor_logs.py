"""
================================================================================
ARCHIVO: interfaz/servidor_logs.py
PROYECTO: Ragnarok
JERARQUÍA: Orquestador y Punto de Entrada del Servidor Web (Flask)
DESCRIPCIÓN: Servidor HTTP liviano que inicializa la aplicación web, configura
             cabeceras CORS para streaming parcial (HTTP 206), sirve la interfaz
             gráfica (panel_control.html) y orquesta el registro de los Blueprints
             modulares (publicación, videos, fuentes, configuración, pipeline, auth).
LÍNEAS DE CÓDIGO: < 100 (Regla de Responsabilidad Única)
================================================================================
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Raíz del proyecto en sys.path
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

try:
    from flask import Flask, jsonify, send_from_directory
except ImportError:
    print("[ERROR] Flask no instalado. Ejecutar: pip install flask")
    sys.exit(1)

from interfaz.rutas.compartido import RUTA_LOG_RT, escribir_log
from interfaz.rutas import registrar_rutas

app = Flask(__name__, static_folder=str(RAIZ / "interfaz"))


@app.after_request
def add_cors_headers(response):
    """Permite CORS globalmente y habilita cabeceras para streaming de video por rangos parciales (HTTP 206)."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Range"
    response.headers["Access-Control-Expose-Headers"] = "Content-Range, Accept-Ranges, Content-Length"
    response.headers["Accept-Ranges"] = "bytes"
    return response


# ─────────────────────────────────────────────────────────
# RUTAS DE LA INTERFAZ ESTÁTICA
# ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Sirve el panel de control HTML principal."""
    return send_from_directory(str(RAIZ / "interfaz"), "panel_control.html")


@app.route("/favicon.ico")
def favicon():
    """Retorna 204 No Content para evitar errores 404 de favicon en la consola."""
    return "", 204


@app.route("/<path:path>")
def servir_estaticos_interfaz(path: str):
    """Sirve archivos estáticos de la interfaz (.css, .js, imágenes, etc.)."""
    target = RAIZ / "interfaz" / path
    if target.exists() and target.is_file():
        return send_from_directory(str(RAIZ / "interfaz"), path)
    return jsonify({"error": "File not found"}), 404


# ─────────────────────────────────────────────────────────
# REGISTRO MODULAR DE BLUEPRINTS (ORQUESTACIÓN)
# ─────────────────────────────────────────────────────────
registrar_rutas(app)


# ─────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Ragnarok — Servidor de Panel de Control (Modular)")
    print("  URL: http://127.0.0.1:5757")
    print("  Logs SSE: http://127.0.0.1:5757/eventos")
    print("=" * 60)

    # Inicializar archivo de log
    RUTA_LOG_RT.parent.mkdir(parents=True, exist_ok=True)
    escribir_log("INFO", "Servidor Ragnarok iniciado en http://127.0.0.1:5757")

    app.run(
        host="127.0.0.1",
        port=5757,
        debug=False,
        threaded=True,
    )
