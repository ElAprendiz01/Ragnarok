"""
================================================================================
MÓDULO: interfaz/rutas/rutas_publicacion.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para la publicación individual de videos bajo demanda
             y ejecución filtrada por plataforma (Telegram HD, YouTube, TikTok, etc.).
LÍNEAS: < 160
================================================================================
"""

import json
import subprocess
import sys
import threading
from flask import Blueprint, request, jsonify

from interfaz.rutas.compartido import RAIZ, RUTA_CONFIG, Estado, escribir_log

bp_publicacion = Blueprint("publicacion", __name__)


def _persistir_canal_telegram_si_nuevo(canal: str) -> None:
    """Registra y persiste un nuevo canal en la lista canales_telegram de config."""
    if not canal or not RUTA_CONFIG.exists():
        return
    try:
        with open(RUTA_CONFIG, "r", encoding="utf-8") as f_cfg:
            cfg = json.load(f_cfg)
        if "publicacion" not in cfg:
            cfg["publicacion"] = {}
        canales = cfg["publicacion"].get("canales_telegram", [])
        if not isinstance(canales, list):
            canales = [canales] if canales else []
        cambio = False
        if canal not in canales:
            canales.append(canal)
            cfg["publicacion"]["canales_telegram"] = canales
            cfg["canales_telegram"] = canales
            cambio = True
        if cfg["publicacion"].get("canal_telegram") != canal:
            cfg["publicacion"]["canal_telegram"] = canal
            cfg["canal_telegram"] = canal
            cambio = True
        if cambio:
            with open(RUTA_CONFIG, "w", encoding="utf-8") as f_cfg:
                json.dump(cfg, f_cfg, ensure_ascii=False, indent=2)
    except Exception:
        pass


@bp_publicacion.route("/api/publicar/individual", methods=["POST"])
def api_publicar_individual():
    """
    Publica directamente un video individual (por ID) hacia la plataforma seleccionada
    (Telegram HD, YouTube, TikTok, Facebook, Instagram) en modo completo o clips.
    """
    data = request.get_json() or {}
    id_video = str(data.get("id_video", "")).strip()
    plataforma = str(data.get("plataforma", "telegram")).strip().lower()
    modo = str(data.get("modo", "completo")).strip().lower()
    canal = str(data.get("canal", "")).strip()

    if not id_video:
        return jsonify({"ok": False, "error": "ID de video requerido."}), 400

    plataformas_validas = ["telegram", "youtube", "tiktok", "facebook", "instagram"]
    if plataforma not in plataformas_validas:
        return jsonify({"ok": False, "error": f"Plataforma '{plataforma}' no soportada."}), 400

    if Estado["fases"]["3"] == "running":
        return jsonify({"ok": False, "error": "Ya hay un proceso de publicación en ejecución."}), 409

    def run():
        escribir_log("INFO", f"Iniciando publicación individual de video '{id_video}' en {plataforma.upper()} (Modo: {modo.upper()})...")
        Estado["fases"]["3"] = "running"
        try:
            cmd = [
                sys.executable,
                str(RAIZ / "fase3_publicacion" / "orquestador_publicacion_individual.py"),
                "--id", id_video,
                "--plataforma", plataforma,
                "--modo", modo,
            ]
            if canal and plataforma == "telegram":
                cmd.extend(["--canal", canal])
                _persistir_canal_telegram_si_nuevo(canal)
            elif canal:
                cmd.extend(["--canal", canal])

            proc = subprocess.Popen(cmd, cwd=str(RAIZ))
            Estado["procesos"]["3"] = proc
            returncode = proc.wait()
            Estado["procesos"]["3"] = None

            if returncode == 0:
                escribir_log("OK", f"✓ Publicación individual de '{id_video}' en {plataforma.upper()} completada.")
                Estado["fases"]["3"] = "done"
            else:
                escribir_log("ERROR", f"✗ Publicación individual de '{id_video}' terminó con código {returncode}.")
                Estado["fases"]["3"] = "error"
        except Exception as e:
            escribir_log("ERROR", f"Excepción en publicación individual de '{id_video}': {e}")
            Estado["fases"]["3"] = "error"
            Estado["procesos"]["3"] = None

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": f"Publicación de '{id_video}' en {plataforma.upper()} iniciada."})


@bp_publicacion.route("/ejecutar/publicar/<plataforma>", methods=["POST"])
def ejecutar_publicacion_individual_fase(plataforma: str):
    """Lanza la Fase 3 global filtrando únicamente hacia la plataforma especificada."""
    plataformas_validas = ["youtube", "tiktok", "facebook", "instagram", "telegram"]
    if plataforma not in plataformas_validas:
        return jsonify({"ok": False, "error": f"Plataforma '{plataforma}' no soportada"}), 400

    if Estado["fases"]["3"] == "running":
        return jsonify({"ok": False, "error": "Fase 3 ya está en ejecución"}), 409

    def run():
        str_fase = "3"
        Estado["fases"][str_fase] = "running"
        escribir_log("INFO", f"Iniciando publicación en lote en: {plataforma.upper()}")
        try:
            proc = subprocess.Popen(
                [sys.executable, str(RAIZ / "main.py"), "--fase", "3", "--plataforma", plataforma],
                cwd=str(RAIZ),
            )
            Estado["procesos"][str_fase] = proc
            returncode = proc.wait()
            Estado["procesos"][str_fase] = None

            if returncode == 0:
                escribir_log("OK", f"Publicación en {plataforma.upper()} completada con éxito.")
                Estado["fases"][str_fase] = "done"
            else:
                if Estado["fases"][str_fase] != "idle":
                    escribir_log("ERROR", f"Publicación en {plataforma.upper()} terminó con código {returncode}.")
                    Estado["fases"][str_fase] = "error"
        except Exception as e:
            escribir_log("ERROR", f"Excepción en publicación de {plataforma}: {e}")
            Estado["fases"][str_fase] = "error"
            Estado["procesos"][str_fase] = None

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": f"Publicación en {plataforma.upper()} iniciada en segundo plano."})
