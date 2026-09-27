import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

RAIZ = Path(__file__).parent.parent.resolve()
DIR_PERFIL = RAIZ / "datos_persistencia" / "perfil_telegram"

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

async def test_headless():
    print(f"[TEST] Probando Telegram Web con headless=True...")
    print(f"[TEST] Perfil: {DIR_PERFIL}")

    async with async_playwright() as p:
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

        pagina = contexto.pages[0] if contexto.pages else await contexto.new_page()

        print("[TEST] Navegando a https://web.telegram.org/a/ ...")
        try:
            await pagina.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=30_000)
        except Exception as e:
            print(f"[TEST] Error goto: {e}")

        await asyncio.sleep(4.0)

        # Capturar screenshot para ver qué ve Playwright en modo headless
        await pagina.screenshot(path="scratch/test_telegram_headless_screen.png")
        print("[TEST] Screenshot guardada en scratch/test_telegram_headless_screen.png")

        # Comprobar si hay login o si está autenticado
        login = pagina.locator("button:has-text('Log in'), .login-title, canvas.qr-canvas, input[name='phone_number']")
        if await login.count() > 0 and await login.first.is_visible():
            print("[TEST] [!] Detectada pantalla de login (sesión no iniciada).")
        else:
            print("[TEST] [OK] Sesión iniciada detectada en headless!")

        # Comprobar si existe el input de búsqueda
        search = pagina.locator("#telegram-search-input, input[placeholder*='Search']").first
        if await search.count() > 0:
            print("[TEST] [OK] Barra de búsqueda encontrada en headless!")
        else:
            print("[TEST] [!] Barra de búsqueda no encontrada aún.")

        await contexto.close()

if __name__ == "__main__":
    asyncio.run(test_headless())
