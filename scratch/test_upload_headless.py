import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent.resolve()
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from playwright.async_api import async_playwright
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga
from fase3_publicacion.padre_publicador_telegram import PadrePublicadorTelegram

RAIZ = Path(__file__).parent.parent.resolve()
DIR_PERFIL = RAIZ / "datos_persistencia" / "perfil_telegram"
RUTA_VIDEO = RAIZ / "descargas" / "0539cda171c2c736" / "video_original.mp4"

ARGUMENTOS_ANTIBLOQUEO = [
    "--window-size=1920,1080",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
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

async def test_subida_headless():
    print("=" * 60)
    print("  TEST DE SUBIDA A TELEGRAM WEB EN MODO HEADLESS (INVISIBLE)")
    print(f"  Video: {RUTA_VIDEO.name} ({RUTA_VIDEO.stat().st_size / (1024*1024):.2f} MB)")
    print(f"  Canal: @salip_pelis")
    print("=" * 60)

    inyector = HijoInyectorDeMetadatosYCarga()
    publicador = PadrePublicadorTelegram(inyector)

    async with async_playwright() as p:
        print("[TEST] Lanzando Chromium en modo HEADLESS (sin ventana)...")
        contexto = await p.chromium.launch_persistent_context(
            user_data_dir=str(DIR_PERFIL),
            headless=True,
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-MX",
            args=ARGUMENTOS_ANTIBLOQUEO,
            ignore_default_args=["--enable-automation"],
        )
        await contexto.add_init_script(SCRIPT_STEALTH)

        def log_cb(nivel, msg):
            print(f"[CALLBACK {nivel}] {msg}")

        exito = await publicador.iniciar_flujo_subida(
            contexto=contexto,
            ruta_video=RUTA_VIDEO,
            titulo="Test Video Headless",
            descripcion="Prueba de subida automática en modo invisible / headless.",
            canal_target="@salip_pelis",
            numero_parte=1,
            callback_log=log_cb,
        )

        print(f"\n[TEST] Resultado de subida en modo headless: {exito}")
        await contexto.close()

if __name__ == "__main__":
    asyncio.run(test_subida_headless())
