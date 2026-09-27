import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from interfaz.servidor_logs import app

PORT = 5005
URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = Path(r"C:\Users\gmayc\.gemini\antigravity\brain\ba456bf9-c0c3-4827-b6cd-157f06543d46")

def run_server():
    import werkzeug.serving
    werkzeug.serving.run_simple("127.0.0.1", PORT, app, threaded=True)

async def capture():
    # Iniciar servidor en hilo daemon
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        await asyncio.sleep(1.0)

        # 1. Abrir Modal de Publicación Individual / Directa
        await page.evaluate("""() => {
            if (typeof abrirModal === 'function') {
                abrirModal('m-publicar-activo');
                const t = document.getElementById('m-pub-video-titulo');
                if (t) t.textContent = 'Mi Video Original de Prueba HD';
                const id = document.getElementById('m-pub-video-id');
                if (id) id.textContent = '0539cda171c2c736';
            }
        }""")
        await asyncio.sleep(0.5)
        path_pub = OUT_DIR / "modal_publicacion_individual.png"
        await page.screenshot(path=str(path_pub))
        print(f"Captura guardada: {path_pub}")

        # 2. Cerrar y abrir Modal de Selección Telegram Lotes
        await page.evaluate("""() => {
            if (typeof cerrarModal === 'function') cerrarModal('m-publicar-activo');
            if (typeof abrirModalTelegramManual === 'function') abrirModalTelegramManual();
            else if (typeof abrirModal === 'function') abrirModal('m-telegram-manual');
        }""")
        await asyncio.sleep(0.5)
        path_tg = OUT_DIR / "modal_telegram_lotes.png"
        await page.screenshot(path=str(path_tg))
        print(f"Captura guardada: {path_tg}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture())
