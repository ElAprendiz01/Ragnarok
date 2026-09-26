"""
================================================================================
MÓDULO: interfaz/rutas/rutas_fuentes.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para la gestión de URLs fuente de Facebook
             y de la cola de enlaces de descarga pendientes.
LÍNEAS: < 140
================================================================================
"""

from flask import Blueprint, request, jsonify

from interfaz.rutas.compartido import RUTA_PENDIENTES, escribir_log

bp_fuentes = Blueprint("fuentes", __name__)


@bp_fuentes.route("/fuentes", methods=["GET"])
def listar_fuentes():
    """Lista todas las fuentes URL configuradas."""
    try:
        from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
        gestor = HijoGestorDeFuentesURL()
        return jsonify({"fuentes": gestor.listar_fuentes()})
    except Exception as e:
        return jsonify({"fuentes": [], "error": str(e)}), 500


@bp_fuentes.route("/fuentes", methods=["POST"])
def agregar_fuente():
    """Agrega una nueva fuente URL. Body JSON: {url: '...'}"""
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL vacía"}), 400
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
        gestor = HijoGestorDeFuentesURL()
        if not gestor.es_url_facebook_valida(url):
            return jsonify({"ok": False, "error": "URL no válida de Facebook. Debe ser de facebook.com o fb.watch"}), 400
        info = gestor.agregar_fuente(url)
        escribir_log("OK", f"Nueva fuente agregada desde UI: {info['tipo']} → {url}")
        return jsonify({"ok": True, "fuente": info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_fuentes.route("/fuentes/<path:url_enc>", methods=["DELETE"])
def eliminar_fuente(url_enc: str):
    """Elimina una fuente por su URL original."""
    try:
        from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
        gestor = HijoGestorDeFuentesURL()
        ok = gestor.eliminar_fuente(url_enc)
        if ok:
            escribir_log("OK", f"Fuente eliminada desde UI: {url_enc}")
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_fuentes.route("/fuentes/toggle", methods=["POST"])
def toggle_fuente():
    """Alterna o establece el estado activa (True/False) de una fuente."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    activa = data.get("activa", None)
    if not url:
        return jsonify({"ok": False, "error": "URL vacía"}), 400
    try:
        from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
        gestor = HijoGestorDeFuentesURL()
        ok = gestor.conmutar_estado_fuente(url, activa=activa)
        if ok:
            escribir_log("OK", f"Estado de fuente actualizado (activa={activa}): {url}")
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_fuentes.route("/pendientes", methods=["GET"])
def listar_pendientes():
    """Retorna la lista de URLs pendientes por descargar en cola_pendientes.txt."""
    if not RUTA_PENDIENTES.exists():
        return jsonify({"pendientes": []})
    lines = [l.strip() for l in RUTA_PENDIENTES.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    return jsonify({"pendientes": lines})


@bp_fuentes.route("/pendientes", methods=["POST"])
def agregar_pendiente():
    """Agrega manualmente una URL directa de video a la cola de pendientes."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL vacía"}), 400
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    RUTA_PENDIENTES.parent.mkdir(parents=True, exist_ok=True)
    existentes = set()
    if RUTA_PENDIENTES.exists():
        existentes = set(l.strip() for l in RUTA_PENDIENTES.read_text(encoding="utf-8").splitlines() if l.strip())

    if url in existentes:
        return jsonify({"ok": True, "mensaje": "La URL ya está en la cola de pendientes."})

    with open(RUTA_PENDIENTES, "a", encoding="utf-8") as f:
        f.write(url + "\n")
    escribir_log("OK", f"Enlace directo agregado a cola de pendientes: {url}")
    return jsonify({"ok": True, "mensaje": "Enlace agregado a la cola de pendientes."})


@bp_fuentes.route("/pendientes/<path:url_enc>", methods=["DELETE"])
def eliminar_pendiente(url_enc: str):
    """Elimina una URL de la cola de pendientes."""
    url = request.args.get("url", url_enc).strip()
    if not RUTA_PENDIENTES.exists():
        return jsonify({"ok": False})
    lines = [l.strip() for l in RUTA_PENDIENTES.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    nuevas = [l for l in lines if l != url and url not in l]
    RUTA_PENDIENTES.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
    return jsonify({"ok": True})
