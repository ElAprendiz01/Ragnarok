"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_telegram.py
JERARQUÍA: Padre (Publicador especializado para Telegram Web)
PROYECTO: Ragnarok
DESCRIPCIÓN: Automatización stealth para publicación de videos HD en Telegram Web
             (Versiones A y K) con gestión de modales, file chooser y progreso real.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Optional, Callable
from playwright.async_api import Page, BrowserContext

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga
from fase3_publicacion.hijo_monitor_transferencia_telegram import HijoMonitorTransferenciaTelegram


class PadrePublicadorTelegram:
    """Publicador especializado para Telegram Web (HD original)."""

    URL_BASE: str = "https://web.telegram.org/a/"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        self._inyector = inyector
        self._monitor = HijoMonitorTransferenciaTelegram()

    def _notificar(self, nivel: str, mensaje: str, callback: Optional[Callable[[str, str], None]] = None) -> None:
        print(f"[TELEGRAM] [{nivel}] {mensaje}")
        if callback:
            try:
                callback(nivel, f"[TELEGRAM] {mensaje}")
            except Exception:
                pass

    async def iniciar_flujo_subida(
        self,
        contexto: BrowserContext,
        ruta_video: Path,
        titulo: str,
        descripcion: str,
        canal_target: str = "",
        numero_parte: int = 1,
        callback_log: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """Navega a Telegram Web, abre el canal objetivo y sube el video HD."""
        pagina: Page = contexto.pages[0] if contexto.pages else await contexto.new_page()
        try:
            self._notificar("INFO", f"Cargando Telegram Web ({self.URL_BASE})...", callback_log)
            try:
                await pagina.goto(self.URL_BASE, wait_until="domcontentloaded", timeout=25_000)
            except Exception:
                self._notificar("INFO", "Fallback a Telegram Web K...", callback_log)
                await pagina.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=25_000)

            await self._esperar_renderizado(pagina)

            # Verificar login
            login = pagina.locator("button:has-text('Log in'), .login-title, canvas.qr-canvas, input[name='phone_number']")
            if await login.count() > 0 and await login.first.is_visible():
                self._notificar("WARN", "Sesión no iniciada en Telegram Web.", callback_log)
                return False

            # Paso 1: Abrir canal objetivo
            if not await self._abrir_canal_objetivo(pagina, canal_target):
                self._notificar("ERROR", f"No se pudo abrir el canal: {canal_target}", callback_log)
                return False

            # Paso 2: Adjuntar video HD con FileChooser
            self._notificar("INFO", f"Adjuntando video HD: {ruta_video.name}...", callback_log)
            if not await self._adjuntar_video_hd(pagina, ruta_video):
                self._notificar("ERROR", "Fallo al adjuntar archivo de video.", callback_log)
                return False

            # Paso 3: Inyectar caption en el modal de confirmación
            caption = self._formatear_caption(titulo, descripcion, numero_parte)
            await self._inyectar_caption(pagina, caption)

            # Paso 4: Confirmar y enviar
            if not await self._confirmar_envio_modal(pagina):
                self._notificar("ERROR", "No se pudo confirmar el envío en el modal.", callback_log)
                return False

            # Paso 5: Monitorear subida real en el DOM con el monitor de transferencia
            exito_subida = await self._monitor.esperar_subida_individual(
                pagina=pagina,
                titulo=titulo,
                timeout_seg=1800,
                callback_log=callback_log,
            )

            if exito_subida:
                self._notificar("OK", f"Video HD publicado exitosamente en: {canal_target}", callback_log)
                return True
            else:
                self._notificar("ERROR", "No se pudo confirmar la subida completa del video.", callback_log)
                return False

        except Exception as error:
            self._notificar("ERROR", f"Excepción en subida: {error}", callback_log)
            return False
        finally:
            if not pagina.is_closed():
                await self._monitor.autorizar_cierre_navegador(pagina)

    async def esperar_subida_lote(
        self,
        pagina: Page,
        cantidad_videos: int,
        timeout_seg: int = 3600,
        callback_log: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """Supervisa que un lote completo de videos finalice antes de cerrar sesión."""
        return await self._monitor.esperar_subida_lote(
            pagina=pagina,
            cantidad_videos=cantidad_videos,
            timeout_seg=timeout_seg,
            callback_log=callback_log,
        )

    async def autorizar_cierre_navegador(self, pagina: Page) -> bool:
        """Verifica si es seguro cerrar Chromium sin interrumpir subidas."""
        return await self._monitor.autorizar_cierre_navegador(pagina)

    async def _esperar_renderizado(self, pagina: Page) -> bool:
        """Espera a que cargue la interfaz principal de Telegram."""
        try:
            sel = "#telegram-search-input, input[placeholder*='Search'], .chatlist, .ChatList"
            await pagina.wait_for_selector(sel, timeout=20_000)
            await asyncio.sleep(2.0)
            return True
        except Exception:
            return False

    def _extraer_handle(self, canal_target: str) -> str:
        s = canal_target.strip()
        if not s:
            return ""
        if "telegram.org" in s or "t.me" in s:
            m = re.search(r'(?:#@|#|t\.me\/)([\w_]+)', s)
            if m:
                return m.group(1)
            s = s.rstrip('/').split('/')[-1]
        return s.replace("@", "").strip()

    async def _abrir_canal_objetivo(self, pagina: Page, canal_target: str) -> bool:
        """Busca y selecciona el canal objetivo legítimo en la interfaz."""
        limpio = self._extraer_handle(canal_target)
        if not limpio:
            print("[TELEGRAM] [!] Canal no especificado.")
            return False

        handle_completo = f"@{limpio}"
        print(f"[TELEGRAM] Buscando canal en interfaz: '{limpio}' ({handle_completo})...")

        try:
            search = pagina.locator("#telegram-search-input, input[placeholder*='Search']").first
            await search.click()
            await search.fill("")
            await pagina.keyboard.type(handle_completo, delay=40)
            await asyncio.sleep(2.5)

            items = pagina.locator(".search-section .ListItem, .ListItem.search-result")
            cant = await items.count()
            print(f"[TELEGRAM] Resultados de búsqueda: {cant}")

            canal_sel = None
            for i in range(cant):
                item = items.nth(i)
                if not await item.is_visible():
                    continue
                txt = (await item.inner_text()).lower()
                if limpio.lower() in txt:
                    if "subscriber" in txt or "suscriptor" in txt or not ("chat" in txt or "member" in txt):
                        canal_sel = item
                        print(f"[TELEGRAM] Canal coincidente en resultado #{i+1}")
                        break

            if not canal_sel and cant > 0:
                canal_sel = items.nth(0)

            if canal_sel:
                btn = canal_sel.locator(".ListItem-button, a, div").first
                if await btn.count() > 0:
                    await btn.click()
                else:
                    await canal_sel.click()
                await asyncio.sleep(3.0)

                hdr = pagina.locator(".top-bar .title, .MiddleHeader .title, .ChatInfo .title").first
                if await hdr.count() > 0 and await hdr.is_visible():
                    print(f"[TELEGRAM] [OK] Canal abierto: '{await hdr.inner_text()}'")
                    return True
                return True

        except Exception as err:
            print(f"[TELEGRAM] Error en búsqueda de canal: {err}")

        return False

    async def _adjuntar_video_hd(self, pagina: Page, ruta_video: Path) -> bool:
        """Abre el menú de adjuntos y entrega el archivo al FileChooser nativo."""
        try:
            ruta_abs = str(ruta_video.resolve())
            btn_attach = pagina.locator("#attach-menu-button, button.btn-attach, button.AttachMenu--button, .btn-icon-attach, button[title*='Attach']").first
            if not await btn_attach.is_visible():
                print("[TELEGRAM] [!] Botón de adjuntos no visible.")
                return False

            await btn_attach.click()
            await asyncio.sleep(1.2)

            item_video = pagina.locator(
                ".menu-container.shown .MenuItem:has-text('Photo or Video'), "
                ".menu-container.open .MenuItem:has-text('Photo or Video'), "
                ".MenuItem:visible:has-text('Photo or Video'), "
                ".MenuItem:visible:has-text('File')"
            ).first

            if not await item_video.is_visible():
                print("[TELEGRAM] [!] Opción 'Photo or Video' no visible en menú.")
                return False

            print("[TELEGRAM] Disparando FileChooser con Playwright...")
            async with pagina.expect_file_chooser(timeout=10_000) as fc_info:
                await item_video.click(force=True)

            file_chooser = await fc_info.value
            await file_chooser.set_files(ruta_abs)
            print(f"[TELEGRAM] [OK] Archivo entregado al FileChooser: {ruta_video.name}")

            # Esperar apertura del modal de confirmación
            await pagina.wait_for_selector(".modal-dialog, div[class*='Modal'], .popup", state="visible", timeout=45_000)
            await asyncio.sleep(1.0)
            return True

        except Exception as error:
            print(f"[TELEGRAM] Error adjuntando archivo: {error}")
            return False

    def _formatear_caption(self, titulo: str, descripcion: str, numero_parte: int) -> str:
        parte_txt = f" (Parte {numero_parte})" if numero_parte > 1 else ""
        caption = f"{titulo}{parte_txt}\n\n"
        if descripcion:
            caption += f"{descripcion}\n\n"
        caption += "Disponible en HD"
        return caption.strip()

    async def _inyectar_caption(self, pagina: Page, caption: str) -> None:
        """Pega el caption en el editor tip-tap / ProseMirror del modal."""
        try:
            portals = pagina.locator("#portals .modal-dialog, .modal-dialog, div[class*='Modal']").first
            caption_box = portals.locator("div[contenteditable='true'], .ProseMirror, .tiptap").first
            if await caption_box.is_visible():
                await caption_box.click()
                await caption_box.fill(caption)
                print("[TELEGRAM] Caption inyectado en modal de confirmación.")
                await asyncio.sleep(0.5)
        except Exception as err:
            print(f"[TELEGRAM] Aviso caption: {err}")

    async def _confirmar_envio_modal(self, pagina: Page) -> bool:
        """Hace clic en el botón primario de enviar del modal y espera su cierre."""
        try:
            portals = pagina.locator("#portals .modal-dialog, .modal-dialog, div[class*='Modal']").first
            btn_send = portals.locator("button.primary, button.Button.primary, button.smaller.primary, button:has(.icon-new-send)").first
            if await btn_send.is_visible():
                print("[TELEGRAM] Confirmando envío del video...")
                await btn_send.click()
            else:
                await pagina.keyboard.press("Enter")

            # Esperar cierre del modal confirmando inicio de transmisión
            try:
                await pagina.wait_for_selector(".modal-dialog, div[class*='Modal'], .popup", state="detached", timeout=25_000)
            except Exception:
                pass
            print("[TELEGRAM] [OK] Modal confirmado y transmisión en curso.")
            return True
        except Exception as err:
            print(f"[TELEGRAM] Error al confirmar envío: {err}")
            return False

    async def validar_estado_procesamiento_plataforma(self, pagina: Page, titulo: str = "", timeout_seg: int = 600) -> bool:
        """Monitorea progreso delegando al supervisor de transferencias."""
        return await self._monitor.esperar_subida_individual(pagina, titulo=titulo, timeout_seg=timeout_seg)
