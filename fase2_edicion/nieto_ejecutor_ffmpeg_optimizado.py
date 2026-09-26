"""
================================================================================
MÓDULO: fase2_edicion/nieto_ejecutor_ffmpeg_optimizado.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — llamadas nativas a FFmpeg)
PROYECTO: FaceDPeli
DESCRIPCIÓN: Ejecuta el binario FFmpeg como proceso hijo del SO mediante
             subprocess.Popen. Detecta automáticamente los encoders de
             hardware disponibles (NVENC > QSV > libx264 como CPU fallback),
             aplica los flags del hijo_procesador_de_velocidad y valida
             la integridad del clip generado comparando su duración con la
             duración esperada del segmento.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


# Encoders en orden de prioridad (NVIDIA > Intel > CPU)
ENCODERS_PRIORIDAD: List[str] = ["h264_nvenc", "h264_qsv", "libx264"]


class NietoEjecutorFFmpegOptimizado:
    """
    Ejecuta cortes y recodificaciones de video mediante FFmpeg nativo,
    detecta el encoder de hardware disponible y valida la integridad
    de cada clip generado mediante ffprobe.
    """

    TOLERANCIA_DURACION_SEG: float = 2.0  # Tolerancia en segundos para validación

    def __init__(self, threads: int = 4) -> None:
        """
        Inicializa el ejecutor y detecta el encoder de hardware disponible.

        Args:
            threads: Número de hilos de CPU a asignar a FFmpeg.
        """
        self._threads = threads
        self._encoder_disponible: Optional[str] = None
        self._detectar_encoder_hardware()

    # ------------------------------------------------------------------
    # DETECCIÓN DE ENCODER DE HARDWARE
    # ------------------------------------------------------------------

    def _detectar_encoder_hardware(self) -> None:
        """
        Prueba cada encoder en orden de prioridad consultando los encoders
        disponibles en la instalación de FFmpeg del sistema.
        Asigna el primer encoder funcional a self._encoder_disponible.
        """
        try:
            resultado = subprocess.run(
                ["ffmpeg", "-encoders", "-v", "quiet"],
                capture_output=True, text=True, timeout=10, shell=False
            )
            salida = resultado.stdout
            for encoder in ENCODERS_PRIORIDAD:
                if encoder in salida:
                    self._encoder_disponible = encoder
                    print(f"[FFMPEG] Encoder de hardware detectado: {encoder}")
                    return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: libx264 (siempre disponible en FFmpeg estándar)
        self._encoder_disponible = "libx264"
        print(f"[FFMPEG] No se detectó GPU. Usando encoder CPU: libx264")

    def obtener_encoder_disponible(self) -> str:
        """Retorna el nombre del encoder de video detectado en el sistema."""
        return self._encoder_disponible or "libx264"

    # ------------------------------------------------------------------
    # EJECUCIÓN DE CORTE / SEGMENTO
    # ------------------------------------------------------------------

    def ejecutar_corte_ffmpeg(
        self,
        ruta_entrada: Path,
        ruta_salida: Path,
        inicio_segundos: float,
        fin_segundos: float,
        flags_adicionales: List[str],
    ) -> bool:
        """
        Ejecuta un corte de video con FFmpeg desde inicio_segundos hasta fin_segundos.
        Construye el comando completo y lanza FFmpeg como proceso hijo.

        Args:
            ruta_entrada:       Ruta al video original MP4.
            ruta_salida:        Ruta de destino del clip cortado.
            inicio_segundos:    Punto de inicio del segmento en segundos.
            fin_segundos:       Punto de fin del segmento en segundos.
            flags_adicionales:  Flags del hijo_procesador_de_velocidad (encoder, filtros).

        Returns:
            True si FFmpeg retornó código 0 (éxito).
        """
        duracion_segmento = fin_segundos - inicio_segundos
        comando = (
            [
                "ffmpeg",
                "-y",                         # Sobreescribir sin preguntar
                "-ss", str(inicio_segundos),   # Punto de inicio
                "-i", str(ruta_entrada),       # Archivo de entrada
                "-t", str(duracion_segmento),  # Duración del segmento
            ]
            + flags_adicionales
            + [
                "-threads", str(self._threads),
                str(ruta_salida),
            ]
        )

        print(f"[FFMPEG] Ejecutando corte: Parte de {inicio_segundos:.1f}s a {fin_segundos:.1f}s")
        print(f"[FFMPEG] Comando: {' '.join(comando)}")

        try:
            proceso = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                shell=False,
            )
            _, stderr = proceso.communicate(timeout=900)  # 15 minutos máximo por segmento

            if proceso.returncode == 0:
                print(f"[FFMPEG] [✓] Clip generado exitosamente: {ruta_salida.name}")
                return True
            else:
                # Mostrar últimas 5 líneas del error de FFmpeg
                lineas_error = [l for l in stderr.split("\n") if l.strip()][-5:]
                print(f"[FFMPEG] [✗] Error en FFmpeg (código {proceso.returncode}):")
                for linea in lineas_error:
                    print(f"    {linea}")
                return False

        except subprocess.TimeoutExpired:
            proceso.kill()
            print(f"[FFMPEG] [✗] Timeout de 15 minutos superado para el segmento.")
            return False
        except FileNotFoundError:
            print("[FFMPEG] [✗] Binario 'ffmpeg' no encontrado. Instalar FFmpeg y añadir al PATH.")
            return False

    # ------------------------------------------------------------------
    # VALIDACIÓN DE INTEGRIDAD
    # ------------------------------------------------------------------

    def validar_duracion_clip_resultante(
        self, ruta_clip: Path, duracion_esperada: float
    ) -> bool:
        """
        Verifica que el clip generado tenga una duración real cercana a la
        esperada usando ffprobe. Acepta una tolerancia de ±2 segundos.

        Args:
            ruta_clip:          Ruta al archivo MP4 generado.
            duracion_esperada:  Duración esperada del clip en segundos.

        Returns:
            True si la duración es válida dentro de la tolerancia.
        """
        if not ruta_clip.exists():
            print(f"[FFMPEG] [VALIDAR] Clip no encontrado: {ruta_clip}")
            return False

        comando = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(ruta_clip),
        ]
        try:
            resultado = subprocess.run(
                comando, capture_output=True, text=True, timeout=15, shell=False
            )
            if resultado.returncode != 0:
                return False

            import json
            datos = json.loads(resultado.stdout)
            duracion_real = float(datos.get("format", {}).get("duration", 0))
            diferencia = abs(duracion_real - duracion_esperada)

            if diferencia <= self.TOLERANCIA_DURACION_SEG:
                print(f"[FFMPEG] [VALIDAR] [✓] Duración válida: {duracion_real:.1f}s "
                      f"(esperada: {duracion_esperada:.1f}s, diff: {diferencia:.2f}s)")
                return True
            else:
                print(f"[FFMPEG] [VALIDAR] [✗] Duración fuera de tolerancia: {duracion_real:.1f}s "
                      f"(esperada: {duracion_esperada:.1f}s, diff: {diferencia:.2f}s)")
                return False

        except Exception as error:
            print(f"[FFMPEG] [VALIDAR] [ERROR] {error}")
            return False

    def verificar_integridad_todos_los_clips(
        self, clips_y_duraciones: List[Tuple[Path, float]]
    ) -> bool:
        """
        Verifica la integridad de todos los clips generados en una sola llamada.

        Args:
            clips_y_duraciones: Lista de tuplas (ruta_clip, duracion_esperada).

        Returns:
            True si TODOS los clips pasaron la validación de integridad.
        """
        todos_validos = True
        for ruta_clip, duracion_esperada in clips_y_duraciones:
            valido = self.validar_duracion_clip_resultante(ruta_clip, duracion_esperada)
            if not valido:
                todos_validos = False
        return todos_validos
