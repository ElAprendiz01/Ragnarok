"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_facebook.py
JERARQUÍA: Padre  (Lógica de plataforma específica — Facebook Creator Studio)
================================================================================
"""

import asyncio
from pathlib import Path
from playwright.async_api import BrowserContext, Page
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga


class PadrePublicadorFacebook:
    """Gestiona el flujo completo de subida de video a Facebook (Meta Business Suite)."""

    URL_SUBIDA: str = "https://business.facebook.com/creatorstudio"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        self._inyector = inyector

    async def iniciar_flujo_subida(
        self, contexto: BrowserContext, ruta_clip: Path,
        titulo: str, descripcion: str, numero_parte: int
    ) -> bool:
        """Navega a Facebook Creator Studio y publica el clip."""
        pagina: Page = await contexto.new_page()
        try:
            print(f"[FB] Navegando a Facebook Creator Studio...")
            await pagina.goto(self.URL_SUBIDA, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3.0)

            # Hacer clic en botón de crear publicación/subir video
            boton_subir = pagina.locator("div[role='button']:has-text('Subir'), button:has-text('Upload')").first
            await boton_subir.click(timeout=10_000)
            await asyncio.sleep(2.0)

            exito = await self._inyector.ejecutar_flujo_publicacion(
                pagina, ruta_clip, titulo, descripcion, numero_parte
            )

            if exito:
                valido = await self.validar_estado_procesamiento_plataforma(pagina)
                if valido:
                    print(f"[FB] [OK] Video publicado y verificado en Facebook: {ruta_clip.name}")
                else:
                    print(f"[FB] [OK] Video publicado en Facebook: {ruta_clip.name}")
            else:
                print(f"[FB] [ERROR] Fallo al publicar en Facebook: {ruta_clip.name}")

            return exito

        except Exception as error:
            print(f"[FB] [ERROR] {error}")
            return False
        finally:
            await pagina.close()

    async def validar_estado_procesamiento_plataforma(self, pagina: Page) -> bool:
        """Verifica confirmación visual de Facebook."""
        try:
            await pagina.wait_for_selector(
                "text=publicado, text=Tu video se está cargando",
                timeout=60_000
            )
            return True
        except Exception:
            return False
