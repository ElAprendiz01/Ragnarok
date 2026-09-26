"""
Diagnóstico de subida de video largo (256 MB) en Telegram Web A.
Inspecciona el DOM del mensaje mientras se sube para identificar los selectores exactos
de progreso, estado pendiente y confirmación final.
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = Path(__file__).resolve().parent.parent
DIR_PERFIL = RAIZ / "datos_persistencia" / "perfil_telegram"
RUTA_VIDEO = RAIZ / "descargas" / "073c1f4bd7b245bb" / "video_original.mp4"

async def test_subida_pesada():
    print(f"[TEST-PESADO] Probando con: {RUTA_VIDEO.name} ({RUTA_VIDEO.stat().st_size / (1024*1024):.1f} MB)...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(DIR_PERFIL),
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="es-MX",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(4.0)

        # Buscar @salip_pelis
        search = page.locator("#telegram-search-input, input[placeholder*='Search']").first
        await search.click()
        await search.fill("")
        await page.keyboard.type("@salip_pelis", delay=40)
        await asyncio.sleep(2.5)

        items = page.locator(".search-section .ListItem")
        for i in range(await items.count()):
            t = await items.nth(i).inner_text()
            if "subscribers" in t.lower() or "suscriptores" in t.lower():
                btn = items.nth(i).locator(".ListItem-button, a, div").first
                if await btn.count() > 0:
                    await btn.click()
                else:
                    await items.nth(i).click()
                break

        await asyncio.sleep(3.0)

        # Botón clip
        btn_attach = page.locator("#attach-menu-button, button.btn-attach, button.AttachMenu--button, .btn-icon-attach, button[title*='Attach']").first
        await btn_attach.click()
        await asyncio.sleep(1.2)

        item_video = page.locator(
            ".menu-container.shown .MenuItem:has-text('Photo or Video'), "
            ".menu-container.open .MenuItem:has-text('Photo or Video'), "
            ".MenuItem:visible:has-text('Photo or Video')"
        ).first

        print("[TEST-PESADO] Disparando FileChooser...")
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await item_video.click(force=True)

        file_chooser = await fc_info.value
        await file_chooser.set_files(str(RUTA_VIDEO.resolve()))
        print("[TEST-PESADO] Archivo entregado al FileChooser.")

        # Esperar modal
        portals = page.locator("#portals .modal-dialog, .modal-dialog").first
        await page.wait_for_selector(".modal-dialog", state="visible", timeout=15000)
        await asyncio.sleep(1.0)

        caption_box = portals.locator("div[contenteditable='true'], .ProseMirror, .tiptap").first
        if await caption_box.is_visible():
            await caption_box.click()
            await caption_box.fill("🎬 Video de Prueba 256MB - Monitoreo DOM")
            await asyncio.sleep(0.5)

        btn_send = portals.locator("button.primary, button.Button.primary, button.smaller.primary, button:has(.icon-new-send)").first
        print("[TEST-PESADO] Haciendo clic en Confirmar Envío...")
        await btn_send.click()

        # Esperar cierre del modal
        await page.wait_for_selector(".modal-dialog", state="detached", timeout=20000)
        print("[TEST-PESADO] Modal cerrado. Monitoreando .message-transfer-progress hasta 100%...")

        inicio_tiempo = asyncio.get_event_loop().time()
        transferencia_iniciada = False
        ultimo_pct = ""

        # Monitorear por hasta 10 minutos (600s)
        for tick in range(1, 300):
            await asyncio.sleep(2.0)
            transcurrido = int(asyncio.get_event_loop().time() - inicio_tiempo)

            # Buscar elementos de progreso en el DOM
            prog_el = page.locator(".message-transfer-progress, .Pdb1Jq02, .radial-progress, button[title*='Cancel']")
            cnt_prog = await prog_el.count()

            if cnt_prog > 0:
                transferencia_iniciada = True
                pct_text = (await prog_el.first.inner_text()).strip()
                if pct_text and pct_text != ultimo_pct:
                    ultimo_pct = pct_text
                    print(f"[{transcurrido}s] Progreso real Telegram Web: {pct_text}")
                elif transcurrido % 10 == 0:
                    print(f"[{transcurrido}s] Transfiriendo... ({ultimo_pct or 'en curso'})")
            else:
                if transferencia_iniciada:
                    print(f"[{transcurrido}s] ¡ELEMENTO DE PROGRESO DESAPARECIÓ! Subida completada al 100%.")
                    await asyncio.sleep(3.0)
                    # Inspeccionar mensaje final
                    ultimo_msg = page.locator(".Message").last
                    txt_final = (await ultimo_msg.inner_text()).replace('\n', ' | ')
                    print(f"[TEST-PESADO] Estado final del mensaje: {txt_final[:120]}")
                    print(f"[TEST-PESADO] [EXITO] Video de 256 MB transferido completamente en {transcurrido}s.")
                    break
                else:
                    if transcurrido <= 8:
                        print(f"[{transcurrido}s] Esperando que inicie la transferencia en el DOM...")
                    else:
                        print(f"[{transcurrido}s] No se detectó progreso activo aún...")

        print("[TEST-PESADO] Cerrando contexto...")
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_subida_pesada())
