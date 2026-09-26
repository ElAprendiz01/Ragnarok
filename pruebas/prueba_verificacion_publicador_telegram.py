"""
================================================================================
ARCHIVO DE PRUEBA: pruebas/prueba_verificacion_publicador_telegram.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Script de verificación que prueba la instanciación del publicador de
             Telegram Web, el formateo de captions y la disponibilidad de los
             métodos de inyección de metadatos y Drag & Drop sintético.
================================================================================
"""

import sys
import unittest
from pathlib import Path

# Asegurar que la raíz del proyecto está en el sys.path
RAIZ = Path(__file__).parent.parent.resolve()
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga
from fase3_publicacion.padre_publicador_telegram import PadrePublicadorTelegram


class PruebaVerificacionPublicadorTelegram(unittest.TestCase):
    """Pruebas explícitas de verificación para los módulos de publicación en Telegram Web."""

    def setUp(self) -> None:
        """Inicializa las instancias del inyector y publicador antes de cada prueba."""
        self.inyector = HijoInyectorDeMetadatosYCarga()
        self.publicador = PadrePublicadorTelegram(self.inyector)

    def test_formateo_de_caption(self) -> None:
        """Verifica que el formateo del caption contenga los sufijos y emojis esperados."""
        caption = self.publicador._formatear_caption(
            titulo="Película de Prueba",
            descripcion="Una película excelente",
            numero_parte=2
        )
        self.assertIn("🎬 Película de Prueba (Parte 2)", caption)
        self.assertIn("📝 Una película excelente", caption)
        self.assertIn("🍿 ¡Disfrútala en HD!", caption)

    def test_disponibilidad_metodo_drag_and_drop(self) -> None:
        """Verifica que el método auxiliar simular_drag_and_drop_archivo exista y sea invocable."""
        self.assertTrue(hasattr(self.inyector, "simular_drag_and_drop_archivo"))
        self.assertTrue(callable(getattr(self.inyector, "simular_drag_and_drop_archivo")))

    def test_disponibilidad_metodo_adjuntar_hd(self) -> None:
        """Verifica que el método _adjuntar_video_hd exista en la clase PadrePublicadorTelegram."""
        self.assertTrue(hasattr(self.publicador, "_adjuntar_video_hd"))
        self.assertTrue(callable(getattr(self.publicador, "_adjuntar_video_hd")))


if __name__ == "__main__":
    print("[PRUEBA] Ejecutando suite de verificación para Telegram Web...")
    unittest.main()
