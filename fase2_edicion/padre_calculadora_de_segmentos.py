"""
================================================================================
MÓDULO: fase2_edicion/padre_calculadora_de_segmentos.py
JERARQUÍA: Padre  (Lógica de negocio — cálculo matemático de puntos de corte)
PROYECTO: Ragnarok
DESCRIPCIÓN: Consulta la duración exacta de un video usando el binario ffprobe
             invocado como proceso hijo sin cargar píxeles en RAM. A partir de
             la duración, calcula los rangos de tiempo (inicio/fin) para dividir
             el video en bloques de exactamente 8 minutos, aplicando la regla
             de fusión cuando el remanente final es menor a 60 segundos.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


# Constantes de regla de negocio
DURACION_BLOQUE_SEGUNDOS: int = 480        # 8 minutos exactos
DURACION_MINIMA_REMANENTE: int = 60        # 1 minuto mínimo para segmento final


class PadreCalculadoraDeSegmentos:
    """
    Calcula matemáticamente los rangos de corte de un video en bloques de
    8 minutos sin procesar ni cargar el archivo de video en memoria RAM.

    Regla de negocio para el remanente final:
        - Si el último segmento dura >= 60 segundos: se crea como parte independiente.
        - Si el último segmento dura < 60 segundos: se fusiona con el segmento anterior.
    """

    def __init__(
        self,
        duracion_bloque: int = DURACION_BLOQUE_SEGUNDOS,
        duracion_minima_remanente: int = DURACION_MINIMA_REMANENTE,
    ) -> None:
        """
        Inicializa la calculadora con los parámetros de corte.

        Args:
            duracion_bloque:           Duración de cada segmento en segundos (default: 480).
            duracion_minima_remanente: Mínimo de segundos para crear un segmento final (default: 60).
        """
        self._duracion_bloque = duracion_bloque
        self._duracion_minima_remanente = duracion_minima_remanente

    # ------------------------------------------------------------------
    # CONSULTA DE DURACIÓN VÍA ffprobe
    # ------------------------------------------------------------------

    def obtener_duracion_exacta(self, ruta_video: Path) -> Optional[float]:
        """
        Ejecuta ffprobe para obtener la duración exacta del video en segundos
        sin decodificar ni cargar el archivo de video en memoria RAM.

        Args:
            ruta_video: Ruta absoluta al archivo MP4.

        Returns:
            Duración en segundos (float), o None si ffprobe falla.
        """
        if not ruta_video.exists():
            print(f"[CALC] Video no encontrado: {ruta_video}")
            return None

        # 1. Intento primario: ffprobe nativo
        comando = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(ruta_video),
        ]
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                shell=False,
            )
            if resultado.returncode == 0:
                datos = json.loads(resultado.stdout)
                duracion_str = datos.get("format", {}).get("duration", None)
                if duracion_str is not None:
                    duracion = float(duracion_str)
                    print(f"[CALC] Duración detectada vía ffprobe: {duracion:.2f}s ({self._segundos_a_hms(duracion)})")
                    return duracion
        except Exception:
            pass

        # 2. Fallback ultra rápido: metadata.json generado en descarga (0ms, Zero RAM)
        meta_ruta = ruta_video.parent / "metadata.json"
        if meta_ruta.exists():
            try:
                with open(meta_ruta, "r", encoding="utf-8") as f_meta:
                    datos_meta = json.load(f_meta)
                dur = float(datos_meta.get("duracion_segundos", 0))
                if dur > 0:
                    print(f"[CALC] [OK] Duración desde metadata.json: {dur:.2f}s ({self._segundos_a_hms(dur)})")
                    return dur
            except Exception:
                pass

        # 3. Fallback secundario: FFmpeg nativo/imageio_ffmpeg
        bin_ff = self._resolver_binario_ffmpeg()
        if bin_ff:
            try:
                import re
                res = subprocess.run([bin_ff, "-i", str(ruta_video)], capture_output=True, text=True, timeout=15)
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
                if m:
                    h, m_val, s = m.groups()
                    dur = int(h) * 3600 + int(m_val) * 60 + float(s)
                    print(f"[CALC] [OK] Duración vía FFmpeg: {dur:.2f}s ({self._segundos_a_hms(dur)})")
                    return dur
            except Exception:
                pass

        print(f"[CALC] [ERROR] No se pudo determinar la duración de: {ruta_video.name}")
        return None

    @staticmethod
    def _resolver_binario_ffmpeg() -> Optional[str]:
        """Localiza el ejecutable de FFmpeg en PATH o imageio_ffmpeg."""
        import shutil
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # CÁLCULO DE RANGOS DE CORTE
    # ------------------------------------------------------------------

    def generar_rangos_corte(self, duracion_total: float) -> List[Dict]:
        """
        Genera la lista de rangos de tiempo (inicio/fin en segundos) para
        dividir el video en bloques de 8 minutos.

        Aplica la regla de remanente:
            - Remanente >= 60s: Se crea como parte N+1 independiente.
            - Remanente < 60s: Se fusiona con la última parte (extendiéndola).

        Args:
            duracion_total: Duración total del video en segundos.

        Returns:
            Lista de diccionarios con:
                {
                    "numero_parte": int,
                    "inicio_segundos": float,
                    "fin_segundos": float,
                    "duracion_segundos": float
                }
        """
        if duracion_total <= 0:
            print("[CALC] [ERROR] Duración inválida (<= 0). No se generan rangos.")
            return []

        rangos: List[Dict] = []
        inicio = 0.0
        numero_parte = 1

        while inicio < duracion_total:
            fin = min(inicio + self._duracion_bloque, duracion_total)
            remanente = duracion_total - fin

            # Aplicar regla de fusión de remanente corto
            if 0 < remanente < self._duracion_minima_remanente:
                fin = duracion_total
                print(f"[CALC] Remanente corto ({remanente:.1f}s < {self._duracion_minima_remanente}s). "
                      f"Fusionando con Parte {numero_parte}.")

            rangos.append({
                "numero_parte": numero_parte,
                "inicio_segundos": round(inicio, 3),
                "fin_segundos": round(fin, 3),
                "duracion_segundos": round(fin - inicio, 3),
            })

            print(
                f"[CALC] Parte {numero_parte}: "
                f"{self._segundos_a_hms(inicio)} -> {self._segundos_a_hms(fin)} "
                f"({fin - inicio:.1f}s)"
            )

            inicio = fin
            numero_parte += 1

            if inicio >= duracion_total:
                break

        print(f"[CALC] Total de partes calculadas: {len(rangos)}")
        return rangos

    # ------------------------------------------------------------------
    # MÉTODO COMBINADO
    # ------------------------------------------------------------------

    def calcular_segmentos_para_video(self, ruta_video: Path) -> List[Dict]:
        """
        Obtiene la duración del video y calcula sus rangos de corte en una
        sola llamada conveniente.

        Args:
            ruta_video: Ruta absoluta al archivo MP4.

        Returns:
            Lista de rangos de corte, o lista vacía si falla.
        """
        duracion = self.obtener_duracion_exacta(ruta_video)
        if duracion is None:
            return []
        return self.generar_rangos_corte(duracion)

    # ------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # ------------------------------------------------------------------

    @staticmethod
    def _segundos_a_hms(segundos: float) -> str:
        """
        Convierte segundos a formato legible HH:MM:SS.mmm.

        Args:
            segundos: Valor en segundos a convertir.

        Returns:
            Cadena en formato 'HH:MM:SS'.
        """
        horas = int(segundos // 3600)
        minutos = int((segundos % 3600) // 60)
        segs = segundos % 60
        return f"{horas:02d}:{minutos:02d}:{segs:06.3f}"
