"""
================================================================================
MÓDULO: fase2_edicion/hijo_procesador_de_velocidad.py
JERARQUÍA: Hijo  (Modificador de parámetros — construcción de flags de FFmpeg)
PROYECTO: Ragnarok
DESCRIPCIÓN: Construye la lista de argumentos (flags) correcta para el binario
             FFmpeg en función del factor de velocidad seleccionado. Encapsula
             la lógica de los filtros de video (setpts) y audio (atempo) para
             1.25x y 1.50x, y el modo de copia directa de stream (-c copy)
             para velocidad normal (1.0x) que garantiza 0% de uso de CPU/RAM.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

from typing import List, Dict, Optional


# Factores de velocidad soportados y sus configuraciones
CONFIGURACIONES_VELOCIDAD: Dict[float, Dict] = {
    1.0: {
        "descripcion": "Velocidad normal — Copia de stream sin recodificar",
        "modo": "stream_copy",
        "args_video": ["-c:v", "copy"],
        "args_audio": ["-c:a", "copy"],
        "args_filtros": [],
        "requiere_encoder": False,
    },
    1.25: {
        "descripcion": "1.25x — Recodificación con GPU NVENC/QSV",
        "modo": "recodificacion",
        "args_video": [],            # El encoder se añade dinámicamente
        "args_audio": [],
        "args_filtros": ["-vf", "setpts=0.8*PTS", "-af", "atempo=1.25"],
        "requiere_encoder": True,
        "setpts_factor": "0.8",
        "atempo_factor": "1.25",
    },
    1.5: {
        "descripcion": "1.50x — Recodificación con GPU NVENC/QSV",
        "modo": "recodificacion",
        "args_video": [],
        "args_audio": [],
        "args_filtros": ["-vf", "setpts=0.6666666666666666*PTS", "-af", "atempo=1.5"],
        "requiere_encoder": True,
        "setpts_factor": "0.6666666666666666",
        "atempo_factor": "1.5",
    },
}


class HijoProcesadorDeVelocidad:
    """
    Construye los argumentos de línea de comandos para FFmpeg según el
    factor de velocidad configurado, seleccionando automáticamente el
    encoder de hardware disponible (NVENC > QSV > libx264 como fallback).
    """

    ENCODERS_PRIORIDAD: List[str] = ["h264_nvenc", "h264_qsv", "libx264"]
    PRESET_RECODIFICACION: str = "ultrafast"
    LIMITE_HILOS: int = 4

    def __init__(
        self,
        factor_velocidad: float = 1.0,
        encoder_preferido: str = "auto",
        threads: int = 4,
    ) -> None:
        """
        Inicializa el procesador con el factor de velocidad y preferencias de encoder.

        Args:
            factor_velocidad: Factor de reproducción (1.0, 1.25 o 1.5).
            encoder_preferido: 'auto' para detección, o nombre explícito del encoder.
            threads:           Número de hilos de FFmpeg para recodificaciones.
        """
        if factor_velocidad not in CONFIGURACIONES_VELOCIDAD:
            factores_validos = list(CONFIGURACIONES_VELOCIDAD.keys())
            raise ValueError(
                f"Factor de velocidad '{factor_velocidad}' no válido. "
                f"Use uno de: {factores_validos}"
            )
        self._factor = factor_velocidad
        self._encoder_preferido = encoder_preferido
        self._threads = threads
        self._config = CONFIGURACIONES_VELOCIDAD[factor_velocidad]

    # ------------------------------------------------------------------
    # CONSTRUCCIÓN DE FLAGS
    # ------------------------------------------------------------------

    def obtener_flags_ffmpeg(self, encoder_detectado: Optional[str] = None) -> List[str]:
        """
        Retorna la lista completa de flags de FFmpeg para el segmento actual.

        Para velocidad 1.0x: Usa -c copy (ultra rápido, 0% CPU/RAM).
        Para 1.25x / 1.50x: Aplica filtros setpts/atempo con encoder de hardware.

        Args:
            encoder_detectado: Encoder confirmado disponible en el sistema.
                               Si None, se usa el preferido en la configuración.

        Returns:
            Lista de strings que conforman los argumentos de FFmpeg.
        """
        if self._config["modo"] == "stream_copy":
            return self._construir_flags_copia()
        else:
            encoder = encoder_detectado or self._resolver_encoder()
            return self._construir_flags_recodificacion(encoder)

    def _construir_flags_copia(self) -> List[str]:
        """
        Construye los flags para el modo de copia directa de stream.
        No hay recodificación: el video se corta en ~1 segundo sin pérdida de calidad.
        Incluye -movflags +faststart para inicio instantáneo de reproducción en navegadores.

        Returns:
            Lista de flags optimizados para stream copy directo y timestamps limpios.
        """
        flags = [
            "-c:v", "copy",
            "-c:a", "copy",
            "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts",
            "-movflags", "+faststart",
        ]
        print(f"[HIJO] Modo stream copy (1.0x). Flags: {' '.join(flags)}")
        return flags

    def _construir_flags_recodificacion(self, encoder: str) -> List[str]:
        """
        Construye los flags para recodificación con filtros de velocidad.
        Incluye -tune fastdecode para decodificación ultra fluida en CPUs de baja gama.

        Args:
            encoder: Nombre del encoder de video a usar (h264_nvenc, h264_qsv, libx264).

        Returns:
            Lista de flags de FFmpeg para la recodificación con velocidad ajustada.
        """
        filtros = self._config["args_filtros"]
        flags = (
            filtros
            + ["-c:v", encoder]
            + ["-preset", self.PRESET_RECODIFICACION]
            + ["-tune", "fastdecode"]
            + ["-movflags", "+faststart"]
            + ["-threads", str(self._threads)]
        )
        print(f"[HIJO] Modo recodificación ({self._factor}x). Encoder: {encoder}. Flags: {' '.join(flags)}")
        return flags

    def _resolver_encoder(self) -> str:
        """
        Retorna el encoder configurado o el primero de la lista de prioridades.

        Returns:
            Nombre del encoder de video a usar.
        """
        if self._encoder_preferido and self._encoder_preferido != "auto":
            return self._encoder_preferido
        # Retornar el primer encoder de prioridad como default (el nieto ejecutor lo verifica)
        return self.ENCODERS_PRIORIDAD[0]

    # ------------------------------------------------------------------
    # INFORMACIÓN DEL FACTOR ACTUAL
    # ------------------------------------------------------------------

    def obtener_descripcion(self) -> str:
        """Retorna la descripción legible del modo de velocidad configurado."""
        return self._config["descripcion"]

    def obtener_factor(self) -> float:
        """Retorna el factor de velocidad actual."""
        return self._factor

    def requiere_recodificacion(self) -> bool:
        """Indica si el factor actual requiere recodificación (True para 1.25x y 1.50x)."""
        return self._config["requiere_encoder"]
