"""
================================================================================
MÓDULO: fase3_publicacion/padre_publicador_tiktok.py
JERARQUÍA: Padre  (Lógica de plataforma específica — TikTok Creator Center)
================================================================================
"""

import asyncio
from pathlib import Path
from playwright.async_api import BrowserContext, Page
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga


class PadrePublicadorTikTok:
    """Gestiona el flujo completo de subida de video al TikTok Creator Center."""

    URL_SUBIDA: str = "https://www.tiktok.com/creator-center/upload"

    def __init__(self, inyector: HijoInyectorDeMetadatosYCarga) -> None:
        self._inyector = inyector

    async def iniciar_flujo_subida(
        self, contexto: BrowserContext, ruta_clip: Path,
        titulo: str, descripcion: str, numero_parte: int
    ) -> bool:
        """Navega a TikTok Creator Center y publica el clip."""
        pagina: Page = await contexto.new_page()
        try:
            print(f"[TK] Navegando a TikTok Creator Center...")
            await pagina.goto(self.URL_SUBIDA, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(3.0)

            exito = await self._inyector.ejecutar_flujo_publicacion(
                pagina, ruta_clip, titulo, descripcion, numero_parte
            )

            if exito:
                valido = await self.validar_estado_procesamiento_plataforma(pagina)
                if valido:
                    print(f"[TK] [OK] Video publicado y verificado en TikTok: {ruta_clip.name}")
                else:
                    print(f"[TK] [OK] Video publicado en TikTok: {ruta_clip.name}")
            else:
                print(f"[TK] [ERROR] Fallo al publicar en TikTok: {ruta_clip.name}")

            return exito

        except Exception as error:
            print(f"[TK] [ERROR] {error}")
            return False
        finally:
            await pagina.close()

    async def validar_estado_procesamiento_plataforma(self, pagina: Page) -> bool:
        """Verifica confirmación visual de TikTok."""
        try:
            await pagina.wait_for_selector(
                "text=fue subido, text=uploaded successfully",
                timeout=60_000
            )
            return True
        except Exception:
            return False
