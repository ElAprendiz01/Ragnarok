"""
================================================================================
MÓDULO: fase3_publicacion/hijo_inyector_de_metadatos_y_carga.py
JERARQUÍA: Hijo  (Inyección de datos — formularios de publicación)
PROYECTO: FaceDPeli
DESCRIPCIÓN: Encargado de las acciones concretas de relleno de formularios
             en los portales de publicación de cada red social: sube el archivo
             MP4 mediante set_input_files o eventos de drop, escribe el título
             con sufijo de parte, escribe la descripción con hashtags, y hace
             clic en el botón de publicar. Usa selectores ARIA y XPath relativos
             para resistir cambios en clases CSS dinámicas de los portales.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import Page


class HijoInyectorDeMetadatosYCarga:
    """
    Automatiza el formulario de publicación de video en cada plataforma,
    rellena los metadatos extraídos de metadata_segmentada.json y confirma
    la publicación esperando la respuesta visual de éxito de la plataforma.
    """

    TIMEOUT_CAMPO_MS: int = 10_000   # 10 segundos para localizar un campo
    TIMEOUT_CARGA_MS: int = 120_000  # 2 minutos para esperar upload/procesamiento

    def __init__(self, pausa_entre_acciones_seg: float = 1.5) -> None:
        """
        Inicializa el inyector con la pausa de seguridad entre acciones.

        Args:
            pausa_entre_acciones_seg: Tiempo de espera entre acciones del formulario.
        """
        self._pausa = pausa_entre_acciones_seg

    # ------------------------------------------------------------------
    # CARGA DEL ARCHIVO MP4
    # ------------------------------------------------------------------

    async def inyectar_archivo_mp4(self, pagina: Page, ruta_clip: Path) -> bool:
        """
        Sube el archivo MP4 al portal de la plataforma usando el input de archivo
        HTML (<input type="file">) o un selector ARIA alternativo.

        Args:
            pagina:    Página de Playwright con el portal de subida abierto.
            ruta_clip: Ruta absoluta al archivo MP4 a subir.

        Returns:
            True si el archivo fue seleccionado correctamente.
        """
        if not ruta_clip.exists():
            print(f"[INYECTOR] [ERROR] Clip no encontrado: {ruta_clip}")
            return False

        try:
            # Intentar selector estándar de input file
            selector_input = "input[type='file']"
            input_file = pagina.locator(selector_input).first
            await input_file.set_input_files(str(ruta_clip), timeout=self.TIMEOUT_CAMPO_MS)
            print(f"[INYECTOR] Archivo MP4 inyectado: {ruta_clip.name}")
            await asyncio.sleep(self._pausa)
            return True
        except Exception as error:
            print(f"[INYECTOR] [ERROR] No se pudo inyectar el archivo: {error}")
            return False

    # ------------------------------------------------------------------
    # RELLENO DE FORMULARIO
    # ------------------------------------------------------------------

    async def escribir_titulo(
        self, pagina: Page, titulo_original: str, numero_parte: int,
        selector_titulo: str = "input[placeholder*='ítulo'], textarea[placeholder*='ítulo']"
    ) -> bool:
        """
        Escribe el título del video en el formato: '[Título Original] - Parte N'.

        Args:
            pagina:          Página del portal de publicación.
            titulo_original: Título extraído de la metadata.
            numero_parte:    Número de parte (1, 2, 3...).
            selector_titulo: Selector CSS/ARIA del campo de título.

        Returns:
            True si el título fue escrito correctamente.
        """
        titulo_formateado = f"{titulo_original} - Parte {numero_parte}"
        # Limitar a 100 caracteres (límite común en la mayoría de plataformas)
        titulo_recortado = titulo_formateado[:100]
        try:
            campo = pagina.locator(selector_titulo).first
            await campo.click(timeout=self.TIMEOUT_CAMPO_MS)
            await campo.fill(titulo_recortado)
            print(f"[INYECTOR] Título escrito: '{titulo_recortado}'")
            await asyncio.sleep(self._pausa)
            return True
        except Exception as error:
            print(f"[INYECTOR] [ERROR] No se pudo escribir el título: {error}")
            return False

    async def escribir_descripcion(
        self, pagina: Page, descripcion_original: str, numero_parte: int,
        selector_descripcion: str = "textarea[placeholder*='escripción'], div[contenteditable='true']"
    ) -> bool:
        """
        Escribe la descripción con hashtags en el campo correspondiente.
        Formato: '[Descripción original] #resumen #pelicula #parteN'

        Args:
            pagina:                 Página del portal de publicación.
            descripcion_original:   Descripción extraída de la metadata.
            numero_parte:           Número de parte para el hashtag.
            selector_descripcion:   Selector CSS del campo de descripción.

        Returns:
            True si la descripción fue escrita correctamente.
        """
        hashtags = f"#resumen #pelicula #parte{numero_parte} #facedpeli"
        descripcion_completa = f"{descripcion_original}\n{hashtags}"
        # Limitar a 2200 caracteres (límite de Instagram/TikTok)
        descripcion_recortada = descripcion_completa[:2200]
        try:
            campo = pagina.locator(selector_descripcion).first
            await campo.click(timeout=self.TIMEOUT_CAMPO_MS)
            await campo.fill(descripcion_recortada)
            print(f"[INYECTOR] Descripción escrita ({len(descripcion_recortada)} caracteres).")
            await asyncio.sleep(self._pausa)
            return True
        except Exception as error:
            print(f"[INYECTOR] [ERROR] No se pudo escribir la descripción: {error}")
            return False

    # ------------------------------------------------------------------
    # PUBLICACIÓN
    # ------------------------------------------------------------------

    async def hacer_clic_publicar(
        self, pagina: Page,
        selector_boton: str = "button:has-text('Publicar'), button:has-text('Publish'), button:has-text('Post')"
    ) -> bool:
        """
        Hace clic en el botón de publicar del portal de la plataforma.
        Usa texto del botón como selector para resistir cambios de clases CSS.

        Args:
            pagina:          Página del portal de publicación.
            selector_boton:  Selector del botón de publicar.

        Returns:
            True si se hizo clic exitosamente.
        """
        try:
            boton = pagina.locator(selector_boton).first
            await boton.click(timeout=self.TIMEOUT_CAMPO_MS)
            print("[INYECTOR] Clic en botón de publicar ejecutado.")
            await asyncio.sleep(self._pausa * 2)
            return True
        except Exception as error:
            print(f"[INYECTOR] [ERROR] No se pudo hacer clic en publicar: {error}")
            return False

    async def esperar_confirmacion_visual(
        self, pagina: Page,
        selector_confirmacion: str = "text=publicado, text=published, text=Upload complete",
        timeout_ms: int = 120_000,
    ) -> bool:
        """
        Espera a que aparezca el indicador visual de publicación exitosa
        (texto de confirmación o icono de éxito) en el portal.

        Args:
            pagina:                 Página del portal de publicación.
            selector_confirmacion:  Selector del elemento de confirmación.
            timeout_ms:             Tiempo máximo de espera en milisegundos.

        Returns:
            True si la confirmación visual fue detectada.
        """
        try:
            await pagina.wait_for_selector(
                selector_confirmacion,
                timeout=timeout_ms,
                state="visible"
            )
            print("[INYECTOR] [✓] Confirmación visual de publicación detectada.")
            return True
        except Exception:
            print("[INYECTOR] [!] No se detectó confirmación visual dentro del timeout.")
            return False

    # ------------------------------------------------------------------
    # FLUJO COMPLETO DE PUBLICACIÓN
    # ------------------------------------------------------------------

    async def ejecutar_flujo_publicacion(
        self, pagina: Page, ruta_clip: Path, titulo: str, descripcion: str, numero_parte: int
    ) -> bool:
        """
        Ejecuta el flujo completo de publicación de un clip en una página
        de portal de red social ya abierta y autenticada.

        Secuencia: Subir archivo -> Escribir título -> Escribir descripción
                   -> Hacer clic publicar -> Esperar confirmación

        Args:
            pagina:        Página del portal de publicación de la plataforma.
            ruta_clip:     Ruta al archivo MP4 a publicar.
            titulo:        Título original del video.
            descripcion:   Descripción original del video.
            numero_parte:  Número de parte del clip.

        Returns:
            True si todo el flujo de publicación fue exitoso.
        """
        # Paso 1: Subir archivo
        if not await self.inyectar_archivo_mp4(pagina, ruta_clip):
            return False

        # Esperar a que el archivo se procese en la plataforma
        await asyncio.sleep(3.0)

        # Paso 2: Escribir título
        await self.escribir_titulo(pagina, titulo, numero_parte)

        # Paso 3: Escribir descripción
        await self.escribir_descripcion(pagina, descripcion, numero_parte)

        # Paso 4: Publicar
        if not await self.hacer_clic_publicar(pagina):
            return False

        # Paso 5: Esperar confirmación
        confirmado = await self.esperar_confirmacion_visual(pagina)
        return confirmado

    # ------------------------------------------------------------------
    # SOPORTE DRAG & DROP SINTÉTICO
    # ------------------------------------------------------------------

    async def simular_drag_and_drop_archivo(
        self, pagina: Page, ruta_archivo: Path, selector_destino: str = ".messages-container, .chat, .Chat, body"
    ) -> bool:
        """
        Simula el evento sintético Drag and Drop enviando un archivo local hacia un elemento objetivo del DOM.
        Utiliza set_input_files de Playwright sobre el selector de destino o dispara eventos de arrastre.

        Args:
            pagina:           Instancia de la página de Playwright.
            ruta_archivo:     Ruta absoluta del archivo local en disco.
            selector_destino: Selector CSS del contenedor objetivo donde se soltará el archivo.

        Returns:
            True si el archivo fue enlazado o soltado exitosamente.
        """
        if not ruta_archivo.exists():
            print(f"[INYECTOR] [ERROR] Archivo no existe para Drag and Drop: {ruta_archivo}")
            return False

        try:
            ruta_abs = str(ruta_archivo.resolve())
            print(f"[INYECTOR] Ejecutando simulación de Drag and Drop para: {ruta_archivo.name}")
            inputs = pagina.locator("input[type='file']")
            if await inputs.count() > 0:
                await inputs.last.set_input_files(ruta_abs)
                await asyncio.sleep(self._pausa)
                return True

            script_js = """
            (element) => {
                const emitEvent = (type) => {
                    const event = new DragEvent(type, {
                        bubbles: true,
                        cancelable: true,
                    });
                    element.dispatchEvent(event);
                };
                emitEvent('dragenter');
                emitEvent('dragover');
            }
            """
            target = pagina.locator(selector_destino).first
            if await target.count() > 0 and await target.is_visible():
                await target.evaluate(script_js)
                await asyncio.sleep(1.0)
                inputs_after = pagina.locator("input[type='file']")
                if await inputs_after.count() > 0:
                    await inputs_after.last.set_input_files(ruta_abs)
                    await asyncio.sleep(self._pausa)
                    return True

            return False
        except Exception as error:
            print(f"[INYECTOR] [ERROR] Falló la simulación de Drag and Drop: {error}")
            return False

