"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_instagram.py
JERARQUÍA: Padre  (Lógica de plataforma específica — Instagram / Meta Business)
================================================================================
"""

import asyncio
from pathlib import Path
from playwright.async_api import BrowserContext, Page
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga


class PadrePublicadorInstagram:
    """Gestiona el flujo completo de subida de Reels/Videos a Instagram."""

    URL_SUBIDA: str = "https://www.instagram.com/reels/upload"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        self._inyector = inyector

    async def iniciar_flujo_subida(
        self, contexto: BrowserContext, ruta_clip: Path,
        titulo: str, descripcion: str, numero_parte: int
    ) -> bool:
        """Navega a Instagram y publica el clip como Reel."""
        pagina: Page = await contexto.new_page()
        try:
            print(f"[IG] Navegando a Instagram para publicar Reel...")
            await pagina.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3.0)

            # Clic en botón de "Crear" (ícono +)
            boton_crear = pagina.locator("svg[aria-label='Nueva publicación'], a[href='/create/style/']").first
            await boton_crear.click(timeout=10_000)
            await asyncio.sleep(2.0)

            exito = await self._inyector.ejecutar_flujo_publicacion(
                pagina, ruta_clip, titulo, descripcion, numero_parte
            )

            if exito:
                valido = await self.validar_estado_procesamiento_plataforma(pagina)
                if valido:
                    print(f"[IG] [OK] Reel publicado y verificado en Instagram: {ruta_clip.name}")
                else:
                    print(f"[IG] [OK] Reel publicado en Instagram: {ruta_clip.name}")
            else:
                print(f"[IG] [ERROR] Fallo al publicar en Instagram: {ruta_clip.name}")

            return exito

        except Exception as error:
            print(f"[IG] [ERROR] {error}")
            return False
        finally:
            await pagina.close()

    async def validar_estado_procesamiento_plataforma(self, pagina: Page) -> bool:
        """Verifica confirmación visual de Instagram."""
        try:
            await pagina.wait_for_selector(
                "text=Tu reel fue compartido, text=Reel shared",
                timeout=60_000
            )
            return True
        except Exception:
            return False
