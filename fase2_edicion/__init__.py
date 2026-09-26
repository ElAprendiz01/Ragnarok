"""
================================================================================
MÓDULO: fase2_edicion/__init__.py
PROYECTO: FaceDPeli
DESCRIPCIÓN: Inicializador del paquete de la Fase 2 - Edición & Procesamiento.
================================================================================
"""

from fase2_edicion.orquestador_edicion_principal import OrquestadorEdicionPrincipal
from fase2_edicion.abuelo_gestor_de_carpetas_por_video import AbueloGestorDeCarpetasPorVideo
from fase2_edicion.padre_calculadora_de_segmentos import PadreCalculadoraDeSegmentos
from fase2_edicion.hijo_procesador_de_velocidad import HijoProcesadorDeVelocidad
from fase2_edicion.nieto_ejecutor_ffmpeg_optimizado import NietoEjecutorFFmpegOptimizado

__all__ = [
    "OrquestadorEdicionPrincipal",
    "AbueloGestorDeCarpetasPorVideo",
    "PadreCalculadoraDeSegmentos",
    "HijoProcesadorDeVelocidad",
    "NietoEjecutorFFmpegOptimizado",
]
