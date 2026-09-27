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
    modo_browser = str(data.get("modo_browser", "")).strip().lower()
    if modo_browser in ["headless", "invisible"]:
        headless = True
    elif modo_browser in ["visible", "headed"]:
        headless = False
    elif "headless" in data and data.get("headless") is not None:
        headless = bool(data["headless"])
    else:
        headless = None

    if not id_video:
        return jsonify({"ok": False, "error": "ID de video requerido."}), 400

    plataformas_validas = ["telegram", "youtube", "tiktok", "facebook", "instagram"]
    if plataforma not in plataformas_validas:
        return jsonify({"ok": False, "error": f"Plataforma '{plataforma}' no soportada."}), 400

    if Estado["fases"]["3"] == "running":
        return jsonify({"ok": False, "error": "Ya hay un proceso de publicación en ejecución."}), 409

    def run():
        desc_modo = "INVISIBLE (Headless)" if headless is True else ("VISIBLE" if headless is False else "AUTO")
        escribir_log("INFO", f"Iniciando publicación individual de video '{id_video}' en {plataforma.upper()} (Modo: {modo.upper()}, Ventana: {desc_modo})...")
        Estado["fases"]["3"] = "running"
        try:
            cmd = [
                sys.executable,
                str(RAIZ / "fase3_publicacion" / "orquestador_publicacion_individual.py"),
                "--id", id_video,
                "--plataforma", plataforma,
                "--modo", modo,
            ]
            if headless is True:
                cmd.append("--headless")
            elif headless is False:
                cmd.append("--visible")

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
                escribir_log("OK", f"Publicación individual de '{id_video}' en {plataforma.upper()} completada.")
                Estado["fases"]["3"] = "done"
            else:
                escribir_log("ERROR", f"Publicación individual de '{id_video}' terminó con código {returncode}.")
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
    """Lanza la Fase 3 global filtrando únicamente hacia la plataforma especificada (soporta modo visible/invisible)."""
    plataformas_validas = ["youtube", "tiktok", "facebook", "instagram", "telegram"]
    if plataforma not in plataformas_validas:
        return jsonify({"ok": False, "error": f"Plataforma '{plataforma}' no soportada"}), 400

    if Estado["fases"]["3"] == "running":
        return jsonify({"ok": False, "error": "Fase 3 ya está en ejecución"}), 409

    data = request.get_json(silent=True) or {}
    modo_browser = str(request.args.get("modo_browser") or data.get("modo_browser", "")).strip().lower()
    if modo_browser in ["headless", "invisible"]:
        headless = True
    elif modo_browser in ["visible", "headed"]:
        headless = False
    elif "headless" in data and data.get("headless") is not None:
        headless = bool(data["headless"])
    else:
        headless = None

    def run():
        str_fase = "3"
        Estado["fases"][str_fase] = "running"
        desc_modo = "INVISIBLE (Headless)" if headless is True else ("VISIBLE" if headless is False else "AUTO")
        escribir_log("INFO", f"Iniciando publicación en lote en: {plataforma.upper()} (Ventana: {desc_modo})")
        try:
            cmd = [
                sys.executable,
                str(RAIZ / "main.py"),
                "--fase", "3",
                "--plataforma", plataforma,
            ]
            if headless is True:
                cmd.append("--headless")
            elif headless is False:
                cmd.append("--visible")

            proc = subprocess.Popen(cmd, cwd=str(RAIZ))
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


@bp_publicacion.route("/api/publicar/lote/telegram", methods=["POST"])
def ejecutar_lote_telegram_endpoint():
    """Inicia la publicación por lotes a Telegram usando el orquestador secuencial Zero-RAM."""
    if Estado["fases"]["4"] == "running":
        return jsonify({"ok": False, "error": "Fase 4 (Lote Telegram) ya está en ejecución"}), 409

    data = request.get_json(silent=True) or {}
    canal = str(data.get("canal", "")).strip()
    modo_browser = str(data.get("modo_browser", "visible")).strip().lower()
    modo_video = str(data.get("modo_video", "completo")).strip().lower()
    forzar = bool(data.get("forzar", False))
    ids_videos = data.get("ids", [])

    if canal:
        _persistir_canal_telegram_si_nuevo(canal)

    def run():
        str_fase = "4"
        Estado["fases"][str_fase] = "running"
        escribir_log("INFO", f"Iniciando lote de Telegram (Canal: {canal or 'Config'}, Ventana: {modo_browser.upper()})...")
        try:
            cmd = [
                sys.executable,
                "-m",
                "fase3_publicacion.orquestador_publicacion_lotes",
                "--canal", canal,
                "--modo-browser", modo_browser,
                "--modo-video", modo_video,
            ]
            if forzar:
                cmd.append("--forzar")
            if ids_videos and isinstance(ids_videos, list):
                cmd.extend(["--ids"] + [str(i) for i in ids_videos])

            proc = subprocess.Popen(cmd, cwd=str(RAIZ))
            Estado["procesos"][str_fase] = proc
            returncode = proc.wait()
            Estado["procesos"][str_fase] = None

            if returncode == 0:
                escribir_log("OK", "Lote de Telegram finalizado con éxito.")
                Estado["fases"][str_fase] = "done"
            else:
                if Estado["fases"][str_fase] != "idle":
                    escribir_log("ERROR", f"Lote de Telegram finalizó con código {returncode}.")
                    Estado["fases"][str_fase] = "error"
        except Exception as e:
            escribir_log("ERROR", f"Excepción en lote de Telegram: {e}")
            Estado["fases"][str_fase] = "error"
            Estado["procesos"][str_fase] = None

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": "Publicación por lote iniciada en segundo plano."})


@bp_publicacion.route("/api/publicar/lote/estado", methods=["GET"])
def obtener_estado_lote_telegram():
    """Retorna el estado de la cola de publicación en disco (manifiesto Zero-RAM)."""
    ruta_cola = RAIZ / "datos_persistencia" / "cola_publicacion_telegram.json"
    if not ruta_cola.exists():
        return jsonify({"ok": True, "activo": False, "total": 0, "completados": 0, "elementos": []})
    try:
        with open(ruta_cola, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return jsonify({"ok": True, "activo": Estado["fases"]["4"] == "running", **datos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_publicacion.route("/api/publicar/memoria", methods=["GET"])
def obtener_memoria_publicaciones():
    """Retorna el estado consolidado de la memoria unificada de publicaciones."""
    from fase3_publicacion.gestor_memoria_publicaciones import GestorMemoriaPublicaciones
    mem = GestorMemoriaPublicaciones()
    ids_tg = list(mem.obtener_ids_publicados("telegram"))
    return jsonify({
        "ok": True,
        "total_publicados_telegram": len(ids_tg),
        "ids_telegram": ids_tg,
        "memoria": mem._cargar_memoria(),
    })


@bp_publicacion.route("/api/publicar/memoria/limpiar", methods=["POST"])
def limpiar_memoria_publicaciones():
    """Limpia la memoria unificada de publicaciones para reiniciar desde cero."""
    from fase3_publicacion.gestor_memoria_publicaciones import GestorMemoriaPublicaciones
    mem = GestorMemoriaPublicaciones()
    mem.limpiar_memoria()
    return jsonify({"ok": True, "mensaje": "Memoria de publicaciones reiniciada correctamente."})

