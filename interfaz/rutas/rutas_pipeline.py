"""
================================================================================
MÓDULO: interfaz/rutas/rutas_pipeline.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para el ciclo de vida de las fases del pipeline
             (ejecución, cancelación, Server-Sent Events en tiempo real y métricas).
LÍNEAS: < 170
================================================================================
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from flask import Blueprint, Response, jsonify

from interfaz.rutas.compartido import (
    RAIZ, RUTA_LOG_RT, RUTA_HISTORIAL, RUTA_PENDIENTES, RUTA_COMPLETADOS, RUTA_FUENTES,
    Estado, escribir_log, contar_lineas
)

bp_pipeline = Blueprint("pipeline", __name__)


@bp_pipeline.route("/eventos")
def stream_logs():
    """
    Server-Sent Events: vigila log_tiempo_real.txt y transmite en tiempo real
    las nuevas líneas al navegador cliente vía EventSource.
    """
    def generar():
        RUTA_LOG_RT.parent.mkdir(parents=True, exist_ok=True)
        if not RUTA_LOG_RT.exists():
            RUTA_LOG_RT.write_text("", encoding="utf-8")

        with open(RUTA_LOG_RT, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            while True:
                linea = f.readline()
                if linea and linea.strip():
                    partes = linea.strip().split(" ||| ", 2)
                    if len(partes) == 3:
                        timestamp, nivel, msg = partes
                        payload = json.dumps({
                            "t": timestamp[11:19],
                            "nivel": nivel.strip(),
                            "msg": msg.strip(),
                        }, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                else:
                    time.sleep(0.3)

    return Response(
        generar(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@bp_pipeline.route("/estado")
def estado_sistema():
    """Retorna el estado JSON de las fases y estadísticas de los archivos."""
    return jsonify({
        "fases": Estado["fases"],
        "estadisticas": {
            "historial": contar_lineas(RUTA_HISTORIAL),
            "pendientes": contar_lineas(RUTA_PENDIENTES),
            "completados": contar_lineas(RUTA_COMPLETADOS),
            "fuentes": contar_lineas(RUTA_FUENTES),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@bp_pipeline.route("/ejecutar/descargar", methods=["POST"])
def ejecutar_solo_descarga():
    """Lanza únicamente la descarga de pendientes con yt-dlp (Fase 1 con --solo-descargar)."""
    if Estado["fases"]["1"] == "running":
        return jsonify({"ok": False, "error": "Fase 1 ya está en ejecución"}), 409

    def run():
        str_fase = "1"
        Estado["fases"][str_fase] = "running"
        escribir_log("INFO", "Iniciando proceso de descarga única de cola de pendientes (yt-dlp)...")
        try:
            proc = subprocess.Popen(
                [sys.executable, str(RAIZ / "main.py"), "--fase", "1", "--solo-descargar"],
                cwd=str(RAIZ),
            )
            Estado["procesos"][str_fase] = proc
            returncode = proc.wait()
            Estado["procesos"][str_fase] = None

            if returncode == 0:
                escribir_log("OK", "Descarga de pendientes completada exitosamente.")
                Estado["fases"][str_fase] = "done"
            else:
                if Estado["fases"][str_fase] != "idle":
                    escribir_log("ERROR", f"Proceso de descarga terminó con código {returncode}.")
                    Estado["fases"][str_fase] = "error"
        except Exception as e:
            escribir_log("ERROR", f"Excepción en descarga de pendientes: {e}")
            Estado["fases"][str_fase] = "error"
            Estado["procesos"][str_fase] = None

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": "Proceso de descarga única iniciado en segundo plano."})


@bp_pipeline.route("/ejecutar/<int:fase>", methods=["POST"])
def ejecutar_fase(fase: int):
    """Lanza la fase solicitada (1, 2, 3 o 4) en un subproceso independiente."""
    if fase not in [1, 2, 3, 4]:
        return jsonify({"ok": False, "error": "Fase inválida"}), 400

    str_fase = str(fase)
    if Estado["fases"][str_fase] == "running":
        return jsonify({"ok": False, "error": f"Fase {fase} ya está en ejecución"}), 409

    def run():
        Estado["fases"][str_fase] = "running"
        nombre_fase = "Telegram HD Directo" if fase == 4 else f"Fase {fase}"
        escribir_log("INFO", f"{nombre_fase} iniciada desde el Panel de Control.")
        try:
            if fase == 4:
                cmd = [sys.executable, "-m", "fase3_publicacion.orquestador_publicacion_lotes"]
            else:
                cmd = [sys.executable, str(RAIZ / "main.py"), "--fase", str_fase]
            proc = subprocess.Popen(cmd, cwd=str(RAIZ))
            Estado["procesos"][str_fase] = proc
            returncode = proc.wait()
            Estado["procesos"][str_fase] = None

            if returncode == 0:
                escribir_log("OK", f"{nombre_fase} completada exitosamente.")
                Estado["fases"][str_fase] = "done"
            else:
                if Estado["fases"][str_fase] != "idle":
                    escribir_log("ERROR", f"{nombre_fase} terminó con código {returncode}.")
                    Estado["fases"][str_fase] = "error"
        except Exception as e:
            escribir_log("ERROR", f"Fase {fase} — excepción: {e}")
            Estado["fases"][str_fase] = "error"
            Estado["procesos"][str_fase] = None

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": f"Fase {fase} iniciada en segundo plano."})


@bp_pipeline.route("/detener/<int:fase>", methods=["POST"])
def detener_fase(fase: int):
    """Cancela y termina el subproceso de la fase usando taskkill para matar el árbol en Windows."""
    str_fase = str(fase)
    proc = Estado["procesos"].get(str_fase)
    Estado["fases"][str_fase] = "idle"

    if proc and proc.poll() is None:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            proc.kill()
        except Exception as e:
            escribir_log("ERROR", f"Error al cancelar proceso Fase {fase}: {e}")
        escribir_log("WARN", f"Fase {fase} (PID {proc.pid}) cancelada y terminada desde el Panel de Control.")
        Estado["procesos"][str_fase] = None
    else:
        escribir_log("WARN", f"Fase {fase} marcada como detenida desde el Panel de Control.")
    return jsonify({"ok": True})
