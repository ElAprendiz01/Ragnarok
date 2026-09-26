"""
================================================================================
MÓDULO: interfaz/rutas/rutas_configuracion.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para la lectura y actualización de la configuración
             global (JSON), incluyendo canales de Telegram, Playwright y FFmpeg.
LÍNEAS: < 100
================================================================================
"""

import json
from flask import Blueprint, request, jsonify

from interfaz.rutas.compartido import RUTA_CONFIG, escribir_log

bp_configuracion = Blueprint("configuracion", __name__)


@bp_configuracion.route("/config", methods=["GET"])
def get_config():
    """Retorna la configuración global actual."""
    if not RUTA_CONFIG.exists():
        return jsonify({}), 404
    with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        # Sincronizar canal_telegram y canales_telegram a nivel raíz para facilitarle acceso a la UI
        if "publicacion" in cfg:
            if "canal_telegram" in cfg["publicacion"]:
                cfg["canal_telegram"] = cfg["publicacion"]["canal_telegram"]
            if "canales_telegram" in cfg["publicacion"]:
                cfg["canales_telegram"] = cfg["publicacion"]["canales_telegram"]
        return jsonify(cfg)


@bp_configuracion.route("/config", methods=["POST"])
def set_config():
    """Actualiza campos de la configuración global. Body JSON con los campos a cambiar."""
    data = request.get_json() or {}
    if not RUTA_CONFIG.exists():
        return jsonify({"ok": False, "error": "Archivo de configuración no encontrado"}), 404
    with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
        config_actual = json.load(f)

    if "publicacion" not in config_actual:
        config_actual["publicacion"] = {}

    if "canal_telegram" in data:
        val_canal = str(data["canal_telegram"]).strip()
        config_actual["canal_telegram"] = val_canal
        config_actual["publicacion"]["canal_telegram"] = val_canal
        # Si se especifica un canal activo, agregarlo a canales_telegram si no existe
        if val_canal:
            canales = config_actual["publicacion"].get("canales_telegram", [])
            if not isinstance(canales, list):
                canales = [canales] if canales else []
            if val_canal not in canales:
                canales.append(val_canal)
            config_actual["publicacion"]["canales_telegram"] = canales
            config_actual["canales_telegram"] = canales

    if "canales_telegram" in data:
        canales = data["canales_telegram"]
        if isinstance(canales, list):
            canales_limpios = [str(c).strip() for c in canales if str(c).strip()]
            config_actual["canales_telegram"] = canales_limpios
            config_actual["publicacion"]["canales_telegram"] = canales_limpios

    # Merge superficial de secciones
    for seccion, valores in data.items():
        if seccion in ("canal_telegram", "canales_telegram"):
            continue
        if seccion in config_actual and isinstance(valores, dict):
            config_actual[seccion].update(valores)
        else:
            config_actual[seccion] = valores

    with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config_actual, f, ensure_ascii=False, indent=2)
    escribir_log("OK", "Configuración actualizada desde el Panel de Control.")
    return jsonify({"ok": True})
