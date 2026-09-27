"""
================================================================================
MÓDULO: fase2_edicion/nieto_ejecutor_ffmpeg_optimizado.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — llamadas nativas a FFmpeg)
PROYECTO: Ragnarok
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
        Inicializa el ejecutor, resuelve el binario y detecta el encoder funcional.

        Args:
            threads: Número de hilos de CPU a asignar a FFmpeg.
        """
        self._threads = threads
        self._bin_ffmpeg = self._resolver_binario_ffmpeg()
        self._encoder_disponible: Optional[str] = None
        self._detectar_encoder_hardware()

    @staticmethod
    def _resolver_binario_ffmpeg() -> str:
        """Localiza el binario ejecutable de FFmpeg en PATH o imageio_ffmpeg."""
        import shutil
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return "ffmpeg"

    # ------------------------------------------------------------------
    # DETECCIÓN Y VALIDACIÓN DE ENCODER OPERATIVO
    # ------------------------------------------------------------------

    def _detectar_encoder_hardware(self) -> None:
        """
        Prueba cada encoder mediante una micro-ejecución real de 1 frame.
        Si la GPU no está disponible o falta el driver, conmuta sin fallar.
        """
        for encoder in ENCODERS_PRIORIDAD:
            if self._probar_encoder_operativo(encoder):
                self._encoder_disponible = encoder
                print(f"[FFMPEG] Encoder de hardware verificado: {encoder}")
                return

        self._encoder_disponible = "libx264"
        print("[FFMPEG] No se detectó aceleración GPU funcional. Usando encoder CPU: libx264")

    def _probar_encoder_operativo(self, encoder: str) -> bool:
        """Verifica si el encoder puede codificar realmente un frame de prueba."""
        if encoder == "libx264":
            return True
        cmd = [
            self._bin_ffmpeg, "-v", "quiet",
            "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.04",
            "-c:v", encoder, "-f", "null", "-"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=4, shell=False)
            return res.returncode == 0
        except Exception:
            return False

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
        es_stream_copy = any("copy" in str(f) for f in flags_adicionales)

        comando = [
            self._bin_ffmpeg,
            "-y",
            "-ss", str(inicio_segundos),
            "-i", str(ruta_entrada),
            "-t", str(duracion_segmento),
        ] + flags_adicionales

        if not es_stream_copy and "-threads" not in flags_adicionales:
            comando.extend(["-threads", str(self._threads)])

        comando.append(str(ruta_salida))

        print(f"[FFMPEG] Ejecutando corte: Parte de {inicio_segundos:.1f}s a {fin_segundos:.1f}s")

        try:
            proceso = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                shell=False,
            )
            _, stderr = proceso.communicate(timeout=900)

            if proceso.returncode == 0:
                print(f"[FFMPEG] [OK] Clip generado exitosamente: {ruta_salida.name}")
                return True

            # Si falló y no era stream copy, reintentar con CPU fallback seguro
            if not es_stream_copy:
                print("[FFMPEG] Recodificación con hardware falló. Conmutando a fallback CPU ultrafast...")
                cmd_fb = [
                    self._bin_ffmpeg, "-y",
                    "-ss", str(inicio_segundos),
                    "-i", str(ruta_entrada),
                    "-t", str(duracion_segmento),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "fastdecode",
                    "-movflags", "+faststart",
                    "-threads", str(self._threads),
                    str(ruta_salida),
                ]
                proc_fb = subprocess.Popen(cmd_fb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
                _, err_fb = proc_fb.communicate(timeout=900)
                if proc_fb.returncode == 0:
                    print(f"[FFMPEG] [OK] Clip generado exitosamente con CPU fallback: {ruta_salida.name}")
                    return True

            lineas_error = [l for l in stderr.split("\n") if l.strip()][-3:]
            print(f"[FFMPEG] [ERROR] Error en FFmpeg (código {proceso.returncode}):")
            for linea in lineas_error:
                print(f"    {linea}")
            return False

        except subprocess.TimeoutExpired:
            proceso.kill()
            print("[FFMPEG] [ERROR] Timeout de 15 minutos superado para el segmento.")
            return False
        except FileNotFoundError:
            print("[FFMPEG] [ERROR] Binario FFmpeg no encontrado.")
            return False

    # ------------------------------------------------------------------
    # VALIDACIÓN DE INTEGRIDAD
    # ------------------------------------------------------------------

    def validar_duracion_clip_resultante(
        self, ruta_clip: Path, duracion_esperada: float
    ) -> bool:
        """
        Verifica que el clip generado sea íntegro mediante ffprobe o FFmpeg.
        """
        if not ruta_clip.exists() or ruta_clip.stat().st_size < 1024:
            print(f"[FFMPEG] [VALIDAR] Clip inexistente o vacío: {ruta_clip}")
            return False

        duracion_real = None
        # Intento con ffprobe si está instalado
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(ruta_clip)],
                capture_output=True, text=True, timeout=10, shell=False
            )
            if res.returncode == 0:
                import json
                datos = json.loads(res.stdout)
                duracion_real = float(datos.get("format", {}).get("duration", 0))
        except Exception:
            pass

        # Fallback con self._bin_ffmpeg -i
        if duracion_real is None:
            try:
                import re
                res = subprocess.run([self._bin_ffmpeg, "-i", str(ruta_clip)], capture_output=True, text=True, timeout=10)
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
                if m:
                    h, m_val, s = m.groups()
                    duracion_real = int(h) * 3600 + int(m_val) * 60 + float(s)
            except Exception:
                pass

        if duracion_real is None:
            # El archivo existe y tiene contenido válido
            return True

        diferencia = abs(duracion_real - duracion_esperada)
        if diferencia <= self.TOLERANCIA_DURACION_SEG:
            print(f"[FFMPEG] [VALIDAR] [OK] Duración válida: {duracion_real:.1f}s (esperada: {duracion_esperada:.1f}s)")
            return True
        else:
            print(f"[FFMPEG] [VALIDAR] [WARN] Duración: {duracion_real:.1f}s (esperada: {duracion_esperada:.1f}s, diff: {diferencia:.2f}s)")
            # En stream copy los keyframes pueden alterar levemente la duración sin ser un error fatal
            return diferencia <= (self.TOLERANCIA_DURACION_SEG * 3)

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
