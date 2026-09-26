"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_youtube.py
JERARQUÍA: Padre  (Lógica de plataforma específica — YouTube Studio)
PROYECTO: Ragnarok
DESCRIPCIÓN: Contiene el flujo de navegación específico del portal YouTube
             Studio para subir videos. Navega a la URL de subida, espera
             el cargador y delega las acciones de formulario al inyector.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga


class PadrePublicadorYouTube:
    """Gestiona el flujo completo de subida de video a YouTube Studio."""

    URL_SUBIDA: str = "https://studio.youtube.com"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        self._inyector = inyector

    async def iniciar_flujo_subida(
        self, contexto: BrowserContext, ruta_clip: Path,
        titulo: str, descripcion: str, numero_parte: int
    ) -> bool:
        """
        Navega a YouTube Studio y ejecuta el flujo de publicación completo.

        Args:
            contexto:      BrowserContext aislado de YouTube.
            ruta_clip:     Clip MP4 a subir.
            titulo:        Título del video.
            descripcion:   Descripción del video.
            numero_parte:  Número de parte del clip.

        Returns:
            True si la publicación fue exitosa.
        """
        pagina: Page = await contexto.new_page()
        try:
            print(f"[YT] Navegando a YouTube Studio...")
            await pagina.goto(self.URL_SUBIDA, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2.0)

            # Hacer clic en botón de crear/subir video
            boton_crear = pagina.locator("ytcp-button#create-icon, button[aria-label*='reate']").first
            await boton_crear.click(timeout=10_000)
            await asyncio.sleep(1.5)

            # Hacer clic en opción "Subir videos"
            opcion_subir = pagina.locator("tp-yt-paper-item:has-text('Subir'), tp-yt-paper-item:has-text('Upload')").first
            await opcion_subir.click(timeout=10_000)
            await asyncio.sleep(1.5)

            # Ejecutar flujo de inyección de archivo y metadatos
            exito = await self._inyector.ejecutar_flujo_publicacion(
                pagina, ruta_clip, titulo, descripcion, numero_parte
            )

            if exito:
                valido = await self.validar_estado_procesamiento_plataforma(pagina)
                if valido:
                    print(f"[YT] [✓] Video publicado y confirmado en YouTube: {ruta_clip.name}")
                else:
                    print(f"[YT] [✓] Video subido a YouTube (confirmación visual primaria OK): {ruta_clip.name}")
            else:
                print(f"[YT] [✗] Fallo al publicar: {ruta_clip.name}")

            return exito

        except Exception as error:
            print(f"[YT] [ERROR] {error}")
            return False
        finally:
            await pagina.close()

    async def validar_estado_procesamiento_plataforma(self, pagina: Page) -> bool:
        """Verifica que YouTube haya procesado el video correctamente."""
        try:
            await pagina.wait_for_selector(
                "text=Procesamiento completo, text=Processing complete",
                timeout=60_000
            )
            return True
        except Exception:
            return False
