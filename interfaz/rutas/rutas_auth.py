"""
================================================================================
MÓDULO: interfaz/rutas/rutas_auth.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para la verificación de cookies de plataformas y
             la apertura de navegadores visibles para login (Telegram Web A/K).
LÍNEAS: < 120
================================================================================
"""

import subprocess
import sys
import threading
from flask import Blueprint, jsonify

from interfaz.rutas.compartido import RAIZ, escribir_log

bp_auth = Blueprint("auth", __name__)


@bp_auth.route("/api/cookies", methods=["GET"])
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


@bp_auth.route("/auth/telegram", methods=["POST"])
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
