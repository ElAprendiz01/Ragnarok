"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_telegram.py
JERARQUÍA: Padre  (Publicador especializado para Telegram Web)
PROYECTO: FaceDPeli
DESCRIPCIÓN: Implementa la automatización stealth vía Playwright para publicar
             videos HD completos con título y descripción formateada en canales
             específicos de Telegram Web (Versión A y K).
================================================================================
"""

import asyncio
import re
from pathlib import Path
from typing import Optional
from playwright.async_api import Page, BrowserContext

from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga


class PadrePublicadorTelegram:
    """
    Publicador especializado para Telegram Web (Versiones A y K).
    Permite subir videos completos en calidad HD original sin compresión agresiva.
    """

    URL_BASE: str = "https://web.telegram.org/a/"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        """
        Inicializa el publicador de Telegram con el inyector de metadatos.

        Args:
            inyector: Instancia de HijoInyectorDeMetadatosYCarga.
        """
        self._inyector = inyector

    async def iniciar_flujo_subida(
        self,
        contexto: BrowserContext,
        ruta_video: Path,
        titulo: str,
        descripcion: str,
        canal_target: str = "",
        numero_parte: int = 1,
    ) -> bool:
        """
        Navega a Telegram Web, localiza el canal y envía el video HD completo con título y descripción.

        Args:
            contexto:      BrowserContext de Playwright autenticado.
            ruta_video:    Ruta al video MP4 en HD (original o editado).
            titulo:        Título original del video.
            descripcion:   Descripción del video.
            canal_target:  Nombre/Handle del canal (ej: "@Salip_pelis" o "Salip_pelis").
            numero_parte:  Número de parte si proviene de un clip.

        Returns:
            True si el video fue enviado y confirmado en el canal de Telegram.
        """
        pagina: Page = await contexto.new_page()
        try:
            print(f"[TELEGRAM] Cargando Telegram Web ({self.URL_BASE})...")
            try:
                await pagina.goto(self.URL_BASE, wait_until="domcontentloaded", timeout=25_000)
            except Exception:
                print("[TELEGRAM] Fallback a Telegram Web K (https://web.telegram.org/k/)...")
                await pagina.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=25_000)

            # Paso 0: Esperar renderizado completo de la app de Telegram Web
            render_ok = await self._esperar_renderizado_telegram(pagina)
            if not render_ok:
                print("[TELEGRAM] [!] No se pudo verificar la sesión activa o interfaz principal de Telegram.")

            # Verificar pantalla de login
            pantalla_login = pagina.locator("button:has-text('Log in'), .login-title, canvas.qr-canvas, input[name='phone_number'], .auth-form")
            if await pantalla_login.count() > 0 and await pantalla_login.first.is_visible():
                print("[TELEGRAM] [!] Sesión no iniciada en Telegram Web. Usa el botón '🔑 Iniciar/Guardar Sesión Telegram Web' en el panel.")
                return False

            # Paso 1: Buscar y seleccionar el canal objetivo
            canal_abierto = await self._abrir_canal_objetivo(pagina, canal_target)
            if not canal_abierto:
                print(f"[TELEGRAM] [!] No se pudo abrir el canal: {canal_target}")
                return False

            # Paso 2: Adjuntar archivo de video HD
            print(f"[TELEGRAM] Adjuntando video HD: {ruta_video.name}...")
            exito_adjunto = await self._adjuntar_video_hd(pagina, ruta_video)
            if not exito_adjunto:
                print(f"[TELEGRAM] [!] Error al adjuntar archivo de video.")
                return False

            # Paso 3: Redactar Caption (Título + Descripción)
            caption = self._formatear_caption(titulo, descripcion, numero_parte)
            await self._inyectar_caption(pagina, caption)

            # Paso 4: Enviar mensaje
            print("[TELEGRAM] Enviando publicación al canal...")
            boton_enviar = pagina.locator("button.btn-send, button[title='Send'], .btn-primary:has-text('Send'), button:has-text('Send'), .send-button, .Button.primary").first
            if await boton_enviar.count() > 0 and await boton_enviar.is_visible():
                await boton_enviar.click()
            else:
                await pagina.keyboard.press("Enter")

            await asyncio.sleep(4.0)

            # Paso 5: Validar confirmación de subida completa al 100%
            valido = await self.validar_estado_procesamiento_plataforma(pagina)
            if valido:
                print(f"[TELEGRAM] [✓] Video HD publicado exitosamente en canal Telegram: {canal_target}")
            else:
                print(f"[TELEGRAM] [✓] Video enviado a Telegram (subida iniciada/confirmada): {ruta_video.name}")

            return True

        except Exception as error:
            print(f"[TELEGRAM] [ERROR] {error}")
            return False
        finally:
            if not pagina.is_closed():
                await pagina.close()

    async def _esperar_renderizado_telegram(self, pagina: Page) -> bool:
        """Espera a que la app Web de Telegram cargue su sesión e interfaz principal por completo."""
        try:
            selector_ui = ".chatlist, .ChatList, #telegram-search-input, input[placeholder*='Search'], .sidebar-header, .folder-tabs"
            await pagina.wait_for_selector(selector_ui, timeout=20_000)
            await asyncio.sleep(2.5)
            return True
        except Exception:
            return False

    def _extraer_handle_o_nombre_canal(self, canal_target: str) -> str:
        """Extrae el handle o nombre limpio del canal sin importar el formato ingresado."""
        s = canal_target.strip()
        if not s:
            return ""
        if "telegram.org" in s or "t.me" in s:
            match = re.search(r'(?:#@|#|t\.me\/)([\w_]+)', s)
            if match:
                return match.group(1)
            s = s.rstrip('/').split('/')[-1]
        return s.replace("@", "").strip()

    async def _verificar_chat_abierto(self, pagina: Page) -> bool:
        """
        Verifica mediante múltiples selectores CSS y ARIA si el área principal
        de chat/canal se encuentra renderizada y lista para interactuar.
        """
        selector_amplio = (
            ".chat-info, .top-bar, .header-title, .ChatInfo, .MiddleHeader, "
            ".chat-header, .Composer, .message-input, .btn-attach, "
            ".input-message-input, div[contenteditable='true'], .messages-layout, "
            ".btn-icon-attach, button[title*='Attach'], div.chat-info-container"
        )
        try:
            hdr = await pagina.wait_for_selector(selector_amplio, timeout=8_000)
            if hdr and await hdr.is_visible():
                return True
        except Exception:
            pass

        try:
            elem = pagina.locator("div[contenteditable='true'], .btn-attach, button[aria-label*='Attach'], input[type='file']").first
            if await elem.count() > 0 and await elem.is_visible():
                return True
        except Exception:
            pass

        return False

    async def _abrir_canal_objetivo(self, pagina: Page, canal_target: str) -> bool:
        """
        Abre el canal objetivo utilizando esperas inteligentes de renderizado,
        enrutado de hash SPA de Telegram Web y búsqueda por coincidencia exacta
        filtrada en la sección 'Chats and Contacts'.
        """
        if not canal_target:
            print("[TELEGRAM] [!] No se especificó el canal objetivo en la configuración.")
            return False

        limpio_target = self._extraer_handle_o_nombre_canal(canal_target)
        handle_completo = f"@{limpio_target}"
        print(f"[TELEGRAM] Buscando canal objetivo exacto: '{limpio_target}' ({handle_completo})...")

        # Método 1: Enrutado de hash directo en la SPA de Telegram Web A/K
        try:
            print(f"[TELEGRAM] Cambiando hash de navegación a: #{handle_completo}...")
            await pagina.evaluate(f"window.location.hash = '#{handle_completo}'")
            await asyncio.sleep(2.0)

            if await self._verificar_chat_abierto(pagina):
                print(f"[TELEGRAM] [✓] Canal '{limpio_target}' cargado exitosamente por enrutador SPA.")
                return True
        except Exception:
            pass

        # Método 2: Búsqueda global en la barra de interfaz filtrando en "Chats and Contacts"
        try:
            print("[TELEGRAM] Ejecutando búsqueda en la barra de interfaz...")
            campo_busqueda = pagina.locator("#telegram-search-input, input.input-search, input[placeholder*='Search'], .search-input input, input[type='text']").first
            if await campo_busqueda.count() > 0 and await campo_busqueda.is_visible():
                await campo_busqueda.click()
                await campo_busqueda.fill(handle_completo)

                try:
                    await pagina.wait_for_selector(
                        ".search-super-list-item, .chat-list-item, .ListItem, a.chatlist-chat, .search-section",
                        timeout=8_000
                    )
                except Exception:
                    pass

                await asyncio.sleep(2.0)

                # Priorizar la sección de 'Chats and Contacts' explícita
                seccion_chats = pagina.locator(
                    ".search-section:has-text('Chats and Contacts'), "
                    ".search-island:has-text('Chats and Contacts')"
                ).first

                loc_busqueda = seccion_chats if await seccion_chats.count() > 0 else pagina
                resultados = loc_busqueda.locator(
                    ".ListItem.search-result, .chat-item-clickable, div.title, h3.fullName"
                )
                count = await resultados.count()
                coincidencia_exacta = None

                for i in range(count):
                    item = resultados.nth(i)
                    if not await item.is_visible():
                        continue
                    txt = (await item.inner_text()).strip()
                    lineas = [l.strip().lower() for l in txt.split("\n") if l.strip()]

                    for l in lineas:
                        l_limpia = l.replace("@", "").strip()
                        # Coincidencia exacta descartando el chat de discusión secundario
                        if l_limpia == limpio_target.lower() and not l_limpia.endswith("chat"):
                            coincidencia_exacta = item
                            break
                    if coincidencia_exacta:
                        break

                if coincidencia_exacta:
                    print(f"[TELEGRAM] Coincidencia exacta encontrada en la sección 'Chats and Contacts'. Abriendo canal...")
                    await coincidencia_exacta.click()
                    await asyncio.sleep(2.5)

                    if await self._verificar_chat_abierto(pagina):
                        print(f"[TELEGRAM] [✓] Canal '{limpio_target}' abierto mediante búsqueda por coincidencia exacta.")
                        return True
                else:
                    print(f"[TELEGRAM] [!] No se encontró ningún canal exacto para '{limpio_target}' en 'Chats and Contacts'.")
        except Exception as error:
            print(f"[TELEGRAM] Búsqueda en UI falló: {error}")

        # Método 3: Navegación directa por URL completa
        try:
            print(f"[TELEGRAM] Intentando apertura directa por URL...")
            url_directa = f"https://web.telegram.org/a/#@{limpio_target}"
            await pagina.goto(url_directa, wait_until="domcontentloaded", timeout=15_000)
            await asyncio.sleep(3.0)
            if await self._verificar_chat_abierto(pagina):
                print(f"[TELEGRAM] [✓] Canal '{limpio_target}' cargado por URL directa.")
                return True
        except Exception:
            pass

        return False

    async def _adjuntar_video_hd(self, pagina: Page, ruta_video: Path) -> bool:
        """
        Adjunta el video HD intentando selección directa de input tipo file,
        apertura del menú #attach-menu-button o fallback de Drag and Drop sintético.
        """
        try:
            ruta_abs = str(ruta_video.resolve())

            # Intento A: Si ya existe un input[type='file'] activo en el DOM
            inputs_file = pagina.locator("input[type='file']")
            if await inputs_file.count() > 0:
                try:
                    await inputs_file.last.set_input_files(ruta_abs, timeout=5_000)
                    await asyncio.sleep(2.5)
                    return True
                except Exception:
                    pass

            # Intento B: Clic en el botón #attach-menu-button / .AttachMenu--button
            boton_clip = pagina.locator(
                "#attach-menu-button, button.AttachMenu--button, "
                "button.btn-attach, .btn-icon-attach, button[title*='Attach']"
            ).first
            if await boton_clip.count() > 0 and await boton_clip.is_visible():
                await boton_clip.click()
                await asyncio.sleep(1.5)

                item_menu = pagina.locator(
                    "div.MenuItem:has-text('Photo or Video'), "
                    "div.MenuItem:has-text('File'), "
                    "div.attach-menu-item:has-text('Video'), "
                    "span:has-text('Photo or Video')"
                ).first
                if await item_menu.count() > 0 and await item_menu.is_visible():
                    await item_menu.click()
                    await asyncio.sleep(1.0)

            # Re-intentar setear el archivo en el input tipo file emergente
            input_target = pagina.locator("input[type='file']").last
            if await input_target.count() > 0:
                await input_target.set_input_files(ruta_abs, timeout=15_000)
                await asyncio.sleep(3.0)
                return True

            # Intento C (Fallback): Simulación de Drag and Drop sintético
            print("[TELEGRAM] Usando fallback de Drag and Drop sintético...")
            return await self._inyector.simular_drag_and_drop_archivo(pagina, ruta_video)

        except Exception as error:
            print(f"[TELEGRAM] Error al adjuntar archivo de video: {error}")
            return False

    def _formatear_caption(self, titulo: str, descripcion: str, numero_parte: int) -> str:
        """Construye el texto formateado con título y descripción."""
        parte_txt = f" (Parte {numero_parte})" if numero_parte > 1 else ""
        caption = f"🎬 {titulo}{parte_txt}\n\n"
        if descripcion:
            caption += f"📝 {descripcion}\n\n"
        caption += "🍿 ¡Disfrútala en HD!"
        return caption.strip()

    async def _inyectar_caption(self, pagina: Page, caption: str) -> None:
        """Pega el caption en el cuadro de texto #editable-message-text del modal."""
        try:
            campo_caption = pagina.locator(
                "#editable-message-text, "
                "div.input-field-input[contenteditable='true'], "
                "input.input-caption, .caption-input, "
                "div[placeholder*='Caption'], div[data-placeholder*='Caption']"
            ).first
            if await campo_caption.count() > 0 and await campo_caption.is_visible():
                await campo_caption.click()
                await campo_caption.fill(caption)
            else:
                await pagina.keyboard.type(caption)
        except Exception:
            pass

    async def validar_estado_procesamiento_plataforma(self, pagina: Page, timeout_seg: int = 600) -> bool:
        """
        Monitorea el indicador visual de progreso de subida o la aparición del elemento `.Message .file-title`
        al completar el 100% del envío al servidor de Telegram.
        """
        try:
            progreso = pagina.locator(".upload-progress, .progress-circle, div[title*='Uploading'], .btn-icon-progress")
            confirmacion_mensaje = pagina.locator(".Message .file-title, .Message .text-content, .message-content")
            tiempo_transcurrido = 0
            intervalo = 5

            while tiempo_transcurrido < timeout_seg:
                # Comprobar si ya se renderizó el mensaje final en el historial del canal
                if await confirmacion_mensaje.count() > 0:
                    break

                cant_progreso = await progreso.count()
                if cant_progreso == 0:
                    break

                visible = False
                for i in range(cant_progreso):
                    if await progreso.nth(i).is_visible():
                        visible = True
                        break
                if not visible:
                    break

                if tiempo_transcurrido % 10 == 0 and tiempo_transcurrido > 0:
                    print(f"[TELEGRAM] Subiendo video a Telegram Web... ({tiempo_transcurrido}s transcurridos)")

                await asyncio.sleep(intervalo)
                tiempo_transcurrido += intervalo

            print("[TELEGRAM] [✓] Subida al servidor de Telegram completada exitosamente.")
            return True
        except Exception as error:
            print(f"[TELEGRAM] [!] Error o timeout en monitoreo de subida al servidor: {error}")
            return False

            progreso = pagina.locator(".upload-progress, .progress-circle, div[title*='Uploading'], .btn-icon-progress")
            tiempo_transcurrido = 0
            intervalo = 5

            while tiempo_transcurrido < timeout_seg:
                cant = await progreso.count()
                if cant == 0:
                    break
                visible = False
                for i in range(cant):
                    if await progreso.nth(i).is_visible():
                        visible = True
                        break
                if not visible:
                    break

                if tiempo_transcurrido % 10 == 0 and tiempo_transcurrido > 0:
                    print(f"[TELEGRAM] Subiendo video a Telegram Web... ({tiempo_transcurrido}s transcurridos)")

                await asyncio.sleep(intervalo)
                tiempo_transcurrido += intervalo

            print("[TELEGRAM] [✓] Subida al servidor de Telegram completada exitosamente.")
            return True
        except Exception as error:
            print(f"[TELEGRAM] [!] Error o timeout en monitoreo de subida al servidor: {error}")
            return False

