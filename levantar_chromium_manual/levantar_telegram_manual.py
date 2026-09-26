"""
================================================================================
ARCHIVO: levantar_chromium_manual/levantar_telegram_manual.py
PROYECTO: FaceDPeli
DESCRIPCIÓN: Script de ejecución manual para iniciar Chromium visible utilizando
             el perfil persistente de Telegram Web (datos_persistencia/perfil_telegram).
             Mantiene la ventana abierta para inspección manual y cierra de forma
             limpia ante Ctrl+C sin dejar procesos huérfanos.
================================================================================
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Determinar la raíz del proyecto
RAIZ = Path(__file__).parent.parent.resolve()
DIR_PERFIL = RAIZ / "datos_persistencia" / "perfil_telegram"

ARGUMENTOS_ANTIBLOQUEO = [
    "--start-maximized",
    "--window-size=1920,1080",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-first-run",
    "--no-service-autorun",
    "--password-store=basic",
    "--ignore-certificate-errors",
    "--lang=es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
]

SCRIPT_STEALTH = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['es-MX', 'es', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
"""


async def ejecutar_navegador_manual() -> None:
    """Inicia el navegador visible de Telegram Web y lo mantiene abierto hasta recibir orden de cierre."""
    DIR_PERFIL.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  FaceDPeli — Navegador Manual de Telegram Web")
    print(f"  Perfil: {DIR_PERFIL}")
    print("  Instrucciones: Presiona Ctrl + C en la consola para cerrar limpiamente.")
    print("=" * 60)

    async with async_playwright() as p:
        print("\n[MANUAL] Lanzando Chromium en modo visible...")
        contexto = await p.chromium.launch_persistent_context(
            user_data_dir=str(DIR_PERFIL),
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="es-MX",
            args=ARGUMENTOS_ANTIBLOQUEO,
            ignore_default_args=["--enable-automation"],
        )
        await contexto.add_init_script(SCRIPT_STEALTH)

        pagina = contexto.pages[0] if contexto.pages else await contexto.new_page()

        print("[MANUAL] Navegando a Telegram Web Version A (https://web.telegram.org/a/)...")
        try:
            await pagina.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=30_000)
        except Exception as err:
            print(f"[MANUAL] Error navegando a Telegram Web A: {err}")

        print("\n[MANUAL] Navegador listo y sincronizado. Presiona Ctrl + C para terminar.")

        try:
            while not pagina.is_closed():
                await asyncio.sleep(1.0)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[MANUAL] Interrupción detectada. Cerrando sesión de navegador...")
        finally:
            if contexto:
                await contexto.close()
                print("[MANUAL] [✓] Contexto de navegador cerrado correctamente. Sin procesos huérfanos.")


if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_navegador_manual())
    except KeyboardInterrupt:
        print("\n[MANUAL] Programa finalizado por el usuario.")
