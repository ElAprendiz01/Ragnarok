"""
================================================================================
ARCHIVO: interfaz/servidor_logs.py
PROYECTO: FaceDPeli
DESCRIPCIÓN: Servidor HTTP liviano (Flask) que expone:
             1. GET /  → Sirve el panel_control.html
             2. GET /eventos  → Server-Sent Events (SSE): transmite en tiempo real
                las líneas nuevas del archivo log_tiempo_real.txt al navegador.
             3. POST /fuentes → Agrega una nueva fuente URL desde la UI.
             4. GET  /fuentes → Lista las fuentes URL configuradas.
             5. POST /ejecutar/<fase> → Lanza una fase del pipeline en hilo separado.
             6. GET  /estado → Retorna el estado JSON actual de todas las fases.

MODO DE USO:
    pip install flask
    python interfaz/servidor_logs.py

    Luego abrir: http://127.0.0.1:5757
================================================================================
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Agregar raíz del proyecto al path de Python
RAIZ = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(RAIZ))

try:
    from flask import Flask, Response, request, jsonify, send_from_directory
except ImportError:
    print("[ERROR] Flask no instalado. Ejecutar: pip install flask")
    sys.exit(1)

app = Flask(__name__, static_folder=str(RAIZ / "interfaz"))

@app.after_request
def add_cors_headers(response):
    """Permite CORS globalmente para atender peticiones desde cualquier origen o file://."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

# ─────────────────────────────────────────────────────────
# RUTAS DE ARCHIVOS
# ─────────────────────────────────────────────────────────
RUTA_LOG_RT     = RAIZ / "datos_persistencia" / "log_tiempo_real.txt"
RUTA_CONFIG     = RAIZ / "config" / "parametros_globales.json"
RUTA_FUENTES    = RAIZ / "datos_persistencia" / "fuentes_url.txt"
RUTA_HISTORIAL  = RAIZ / "datos_persistencia" / "historial_global_enlaces.txt"
RUTA_PENDIENTES = RAIZ / "datos_persistencia" / "cola_pendientes.txt"
RUTA_COMPLETADOS= RAIZ / "datos_persistencia" / "enlaces_completados.txt"

# Estado en memoria de las fases (compartido entre hilos)
Estado = {
    "fases": {"1": "idle", "2": "idle", "3": "idle", "4": "idle"},
    "procesos": {"1": None, "2": None, "3": None, "4": None},
}

# ─────────────────────────────────────────────────────────
# HELPERS DE LOG
# ─────────────────────────────────────────────────────────

def escribir_log(nivel: str, mensaje: str) -> None:
    """Escribe una línea en el archivo log_tiempo_real.txt."""
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

# ─────────────────────────────────────────────────────────
# RUTAS HTTP
# ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Sirve el panel de control HTML principal."""
    return send_from_directory(str(RAIZ / "interfaz"), "panel_control.html")


@app.route("/favicon.ico")
def favicon():
    """Retorna 204 No Content para evitar errores 404 de favicon en la consola del navegador."""
    return "", 204


@app.route("/<path:path>")
def servir_estaticos_interfaz(path):
    """Sirve archivos estáticos de la interfaz (.css, .js, imágenes, etc.)."""
    target = RAIZ / "interfaz" / path
    if target.exists() and target.is_file():
        return send_from_directory(str(RAIZ / "interfaz"), path)
    return jsonify({"error": "File not found"}), 404


@app.route("/eventos")
def stream_logs():
    """
    Server-Sent Events: vigila el archivo log_tiempo_real.txt y envía
    cada línea nueva al cliente en tiempo real. El cliente (JS en el
    panel) se suscribe a este endpoint con EventSource.
    """
    def generar():
        # Posicionarse al final del archivo para no reenviar logs viejos
        RUTA_LOG_RT.parent.mkdir(parents=True, exist_ok=True)
        if not RUTA_LOG_RT.exists():
            RUTA_LOG_RT.write_text("", encoding="utf-8")

        with open(RUTA_LOG_RT, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)  # ir al final
            while True:
                linea = f.readline()
                if linea and linea.strip():
                    partes = linea.strip().split(" ||| ", 2)
                    if len(partes) == 3:
                        timestamp, nivel, msg = partes
                        payload = json.dumps({
                            "t": timestamp[11:19],  # solo HH:MM:SS
                            "nivel": nivel.strip(),
                            "msg": msg.strip(),
                        }, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                else:
                    time.sleep(0.3)  # Polling ligero cuando no hay datos nuevos

    return Response(
        generar(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.route("/estado")
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


@app.route("/fuentes", methods=["GET"])
def listar_fuentes():
    """Lista todas las fuentes URL configuradas."""
    try:
        from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
        gestor = HijoGestorDeFuentesURL()
        return jsonify({"fuentes": gestor.listar_fuentes()})
    except Exception as e:
        return jsonify({"fuentes": [], "error": str(e)}), 500


@app.route("/fuentes", methods=["POST"])
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


@app.route("/pendientes", methods=["GET"])
def listar_pendientes():
    """Retorna la lista de URLs pendientes por descargar en cola_pendientes.txt."""
    if not RUTA_PENDIENTES.exists():
        return jsonify({"pendientes": []})
    lines = [l.strip() for l in RUTA_PENDIENTES.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    return jsonify({"pendientes": lines})


@app.route("/pendientes", methods=["POST"])
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


@app.route("/pendientes/<path:url_enc>", methods=["DELETE"])
def eliminar_pendiente(url_enc):
    """Elimina una URL de la cola de pendientes."""
    url = request.args.get("url", url_enc).strip()
    if not RUTA_PENDIENTES.exists():
        return jsonify({"ok": False})
    lines = [l.strip() for l in RUTA_PENDIENTES.read_text(encoding="utf-8").splitlines() if l.strip()]
    nuevas = [l for l in lines if l != url and url not in l]
    RUTA_PENDIENTES.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/fuentes/<path:url_enc>", methods=["DELETE"])
def eliminar_fuente(url_enc):
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


@app.route("/fuentes/toggle", methods=["POST"])
def toggle_fuente():
    """Alterna o establece el estado activa (True/False) de una fuente. Body JSON: {url: '...', activa: true/false/null}"""
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


@app.route("/api/cookies", methods=["GET"])
def estado_cookies():
    """Retorna el estado de verificación de las cookies de todas las plataformas."""
    try:
        from fase3_publicacion.abuelo_gestor_plataformas_multiplex import AbueloGestorPlataformasMultiplex
        gestor = AbueloGestorPlataformasMultiplex()
        plataformas = ["youtube", "tiktok", "facebook", "instagram", "telegram"]
        resultado = {p: gestor.verificar_estado_autenticacion_cookies(p) for p in plataformas}
        return jsonify({"ok": True, "cookies": resultado})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ejecutar/descargar", methods=["POST"])
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


@app.route("/ejecutar/publicar/<plataforma>", methods=["POST"])
def ejecutar_publicacion_individual(plataforma: str):
    """Lanza la Fase 3 filtrando únicamente hacia la plataforma especificada."""
    plataformas_validas = ["youtube", "tiktok", "facebook", "instagram", "telegram"]
    if plataforma not in plataformas_validas:
        return jsonify({"ok": False, "error": f"Plataforma '{plataforma}' no soportada"}), 400

    if Estado["fases"]["3"] == "running":
        return jsonify({"ok": False, "error": "Fase 3 ya está en ejecución"}), 409

    def run():
        str_fase = "3"
        Estado["fases"][str_fase] = "running"
        escribir_log("INFO", f"Iniciando publicación individual en: {plataforma.upper()}")
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


@app.route("/auth/telegram", methods=["POST"])
def iniciar_sesion_telegram():
    """Abre Chromium en modo VISIBLE con perfil de usuario persistente y banderas antibloqueo para Telegram Web."""
    def run():
        escribir_log("INFO", "Abriendo Chromium visible con banderas antibloqueo para inicio de sesión en Telegram Web...")
        dir_perfil = RAIZ / "datos_persistencia" / "perfil_telegram"
        dir_perfil.mkdir(parents=True, exist_ok=True)
        
        script_py = f"""
import asyncio
from playwright.async_api import async_playwright

ARGUMENTOS_ANTIBLOQUEO = [
    "--start-maximized",
    "--window-size=1920,1080",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-gpu-shader-disk-cache",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--no-first-run",
    "--no-service-autorun",
    "--password-store=basic",
    "--use-gl=swiftshader",
    "--ignore-certificate-errors",
    "--allow-running-insecure-content",
    "--lang=es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
]

SCRIPT_STEALTH = '''
Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
Object.defineProperty(navigator, 'languages', {{ get: () => ['es-MX', 'es', 'en-US', 'en'] }});
Object.defineProperty(navigator, 'plugins', {{ get: () => [1, 2, 3, 4, 5] }});
window.chrome = {{ runtime: {{}}, loadTimes: function() {{}}, csi: function() {{}}, app: {{}} }};
try {{
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, [parameter]);
    }};
}} catch(e) {{}}
'''

async def main():
    async with async_playwright() as p:
        print("[AUTH TELEGRAM] Lanzando navegador en pantalla completa (Telegram Web A)...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=r"{dir_perfil}",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="es-MX",
            args=ARGUMENTOS_ANTIBLOQUEO,
            ignore_default_args=["--enable-automation"],
        )
        await context.add_init_script(SCRIPT_STEALTH)
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            print("[AUTH TELEGRAM] Navegando a Telegram Web Version A...")
            await page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=25000)
        except Exception:
            print("[AUTH TELEGRAM] Fallback a Telegram Web Version K...")
            await page.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=25000)

        print("[AUTH TELEGRAM] Por favor inicia sesión en la ventana del navegador. Cierra la ventana cuando termines.")
        await page.wait_for_timeout(300_000)
        await context.close()

asyncio.run(main())
"""
        try:
            proc = subprocess.Popen([sys.executable, "-c", script_py], cwd=str(RAIZ))
            proc.wait()
            escribir_log("OK", "Sesión de Telegram Web guardada permanentemente en datos_persistencia/perfil_telegram.")
        except Exception as e:
            escribir_log("ERROR", f"Error durante autenticación de Telegram: {e}")

    hilo = threading.Thread(target=run, daemon=True)
    hilo.start()
    return jsonify({"ok": True, "mensaje": "Navegador de inicio de sesión de Telegram iniciado con parches anti-detección."})


@app.route("/ejecutar/<int:fase>", methods=["POST"])
def ejecutar_fase(fase: int):
    """
    Lanza la fase Python solicitada en un subproceso Popen independiente.
    Soporta Fase 1 (Scraping/Descarga), Fase 2 (Edición), Fase 3 (Publicación Multicanal)
    y Fase 4 (Publicación Telegram HD Directo).
    """
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
            cmd = [sys.executable, str(RAIZ / "main.py"), "--fase", "3", "--plataforma", "telegram"] if fase == 4 else [sys.executable, str(RAIZ / "main.py"), "--fase", str_fase]
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


@app.route("/detener/<int:fase>", methods=["POST"])
def detener_fase(fase: int):
    """Cancela y mata la fase en ejecución utilizando taskkill para el árbol de procesos en Windows."""
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


@app.route("/config", methods=["GET"])
def get_config():
    """Retorna la configuración global actual."""
    if not RUTA_CONFIG.exists():
        return jsonify({}), 404
    with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        # Sincronizar canal_telegram a nivel raíz para facilitarle acceso a la UI
        if "publicacion" in cfg and "canal_telegram" in cfg["publicacion"]:
            cfg["canal_telegram"] = cfg["publicacion"]["canal_telegram"]
        return jsonify(cfg)


@app.route("/config", methods=["POST"])
def set_config():
    """Actualiza campos de la configuración global. Body JSON con los campos a cambiar."""
    data = request.get_json() or {}
    if not RUTA_CONFIG.exists():
        return jsonify({"ok": False, "error": "Archivo de configuración no encontrado"}), 404
    with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
        config_actual = json.load(f)

    if "canal_telegram" in data:
        val_canal = str(data["canal_telegram"]).strip()
        config_actual["canal_telegram"] = val_canal
        if "publicacion" not in config_actual:
            config_actual["publicacion"] = {}
        config_actual["publicacion"]["canal_telegram"] = val_canal

    # Merge superficial de secciones
    for seccion, valores in data.items():
        if seccion == "canal_telegram":
            continue
        if seccion in config_actual and isinstance(valores, dict):
            config_actual[seccion].update(valores)
        else:
            config_actual[seccion] = valores

    with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config_actual, f, ensure_ascii=False, indent=2)
    escribir_log("OK", "Configuración actualizada desde el Panel de Control.")
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────
# RUTA API /api/videos Y SERVICIO DE MEDIOS (MP4)
# ─────────────────────────────────────────────────────────

@app.route("/media/descargas/<path:filename>")
def servir_descarga(filename):
    """Sirve archivos MP4 y JSON directamente desde el directorio descargas/."""
    return send_from_directory(str(RAIZ / "descargas"), filename)


@app.route("/media/procesados/<path:filename>")
def servir_procesado(filename):
    """Sirve archivos MP4 cortados directamente desde el directorio procesados/."""
    return send_from_directory(str(RAIZ / "procesados"), filename)


@app.route("/api/videos", methods=["GET"])
def listar_videos_reales():
    """
    Escanea los directorios descargas/ y procesados/ y construye la lista
    de videos reales con su metadata.json y metadata_segmentada.json.
    """
    dir_descargas = RAIZ / "descargas"
    dir_procesados = RAIZ / "procesados"
    videos = []

    # 1. Escanear descargas/
    if dir_descargas.exists():
        for carpeta_video in dir_descargas.iterdir():
            if carpeta_video.is_dir():
                archivos = [f for f in carpeta_video.iterdir() if f.is_file() and f.suffix.lower() in ('.mp4', '.webm', '.mkv', '.avi', '.mov')]
                if archivos:
                    ruta_video = archivos[0]
                    ruta_meta = carpeta_video / "metadata.json"
                    meta = {}
                    if ruta_meta.exists():
                        try:
                            with open(ruta_meta, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass
                    
                    dur_seg = meta.get("duracion_segundos", 0)
                    tam_bytes = ruta_video.stat().st_size
                    tam_mb = f"{tam_bytes / (1024*1024):.1f} MB" if tam_bytes < 1024*1024*1024 else f"{tam_bytes / (1024*1024*1024):.2f} GB"

                    videos.append({
                        "id": carpeta_video.name,
                        "titulo": meta.get("titulo_original", meta.get("titulo", carpeta_video.name)),
                        "descripcion": meta.get("descripcion_original", meta.get("descripcion", "")),
                        "url_original": meta.get("url_original", ""),
                        "fecha_extraccion": meta.get("fecha_extraccion", ""),
                        "resolucion": meta.get("resolucion", "Auto"),
                        "codec_video": meta.get("codec_video", "h264"),
                        "codec_audio": meta.get("codec_audio", "aac"),
                        "dur": f"{int(dur_seg//60)}:{int(dur_seg%60):02d}" if dur_seg else "Descargado",
                        "durSec": dur_seg,
                        "tamano": tam_mb,
                        "estado": "descargado",
                        "partes": 1,
                        "url_stream": f"/media/descargas/{carpeta_video.name}/{ruta_video.name}",
                    })

    # 2. Escanear procesados/
    if dir_procesados.exists():
        for carpeta_video in dir_procesados.iterdir():
            if carpeta_video.is_dir():
                ruta_meta_seg = carpeta_video / "metadata_segmentada.json"
                clips = list(carpeta_video.glob("*.mp4"))
                if clips:
                    meta = {}
                    if ruta_meta_seg.exists():
                        try:
                            with open(ruta_meta_seg, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass

                    dur_seg = meta.get("duracion_original_segundos", 0)
                    tam_total = sum(c.stat().st_size for c in clips)
                    tam_mb = f"{tam_total / (1024*1024):.1f} MB"

                    videos.append({
                        "id": carpeta_video.name,
                        "titulo": meta.get("titulo_original", meta.get("titulo", carpeta_video.name)),
                        "descripcion": meta.get("descripcion_original", meta.get("descripcion", "")),
                        "url_original": meta.get("url_original", ""),
                        "fecha_extraccion": meta.get("fecha_extraccion", ""),
                        "resolucion": meta.get("resolucion", "Auto"),
                        "codec_video": meta.get("codec_video", "h264"),
                        "codec_audio": meta.get("codec_audio", "aac"),
                        "dur": f"{int(dur_seg//60)}:{int(dur_seg%60):02d}" if dur_seg else "Procesado",
                        "durSec": dur_seg,
                        "tamano": tam_mb,
                        "estado": "editado",
                        "partes": len(clips),
                        "url_stream": f"/media/procesados/{carpeta_video.name}/{clips[0].name}",
                    })

    return jsonify({"videos": videos, "total": len(videos)})


@app.route("/api/videos/<id_video>/metadata", methods=["POST", "PUT"])
def actualizar_metadata_video(id_video: str):
    """
    Actualiza el título y descripción en los archivos JSON de metadata del video.
    Modifica descargas/<id_video>/metadata.json y, si existe,
    procesados/<id_video>/metadata_segmentada.json.
    """
    data = request.get_json() or {}
    nuevo_titulo = str(data.get("titulo", "")).strip()
    nueva_desc = str(data.get("descripcion", "")).strip()

    if not nuevo_titulo and not nueva_desc:
        return jsonify({"ok": False, "error": "Debe proporcionar título o descripción."}), 400

    actualizado = False
    ruta_meta_descarga = RAIZ / "descargas" / id_video / "metadata.json"
    ruta_meta_procesado = RAIZ / "procesados" / id_video / "metadata_segmentada.json"

    # 1. Actualizar en descargas/
    if ruta_meta_descarga.exists():
        try:
            with open(ruta_meta_descarga, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if nuevo_titulo:
                meta["titulo"] = nuevo_titulo
                meta["titulo_original"] = nuevo_titulo
            if nueva_desc is not None:
                meta["descripcion"] = nueva_desc
                meta["descripcion_original"] = nueva_desc
            with open(ruta_meta_descarga, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            actualizado = True
        except Exception as e:
            return jsonify({"ok": False, "error": f"Error al guardar en descargas: {e}"}), 500

    # 2. Actualizar en procesados/ si existe
    if ruta_meta_procesado.exists():
        try:
            with open(ruta_meta_procesado, "r", encoding="utf-8") as f:
                meta_seg = json.load(f)
            if nuevo_titulo:
                meta_seg["titulo"] = nuevo_titulo
                meta_seg["titulo_original"] = nuevo_titulo
            if nueva_desc is not None:
                meta_seg["descripcion"] = nueva_desc
                meta_seg["descripcion_original"] = nueva_desc
            with open(ruta_meta_procesado, "w", encoding="utf-8") as f:
                json.dump(meta_seg, f, ensure_ascii=False, indent=2)
            actualizado = True
        except Exception as e:
            pass

    if actualizado:
        resumen_titulo = (nuevo_titulo[:40] + "...") if len(nuevo_titulo) > 40 else nuevo_titulo
        escribir_log("OK", f"Metadatos JSON actualizados para {id_video}: '{resumen_titulo}'")
        return jsonify({"ok": True, "mensaje": "Metadatos actualizados en tiempo real", "id": id_video})
    else:
        return jsonify({"ok": False, "error": f"No se encontró metadata para el ID {id_video}"}), 404



# ─────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  FaceDPeli — Servidor de Panel de Control")
    print("  URL: http://127.0.0.1:5757")
    print("  Logs SSE: http://127.0.0.1:5757/eventos")
    print("=" * 60)

    # Inicializar archivo de log
    RUTA_LOG_RT.parent.mkdir(parents=True, exist_ok=True)
    escribir_log("INFO", "Servidor FaceDPeli iniciado en http://127.0.0.1:5757")

    app.run(
        host="127.0.0.1",
        port=5757,
        debug=False,
        threaded=True,
    )
