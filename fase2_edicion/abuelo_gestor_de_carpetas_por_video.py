"""
================================================================================
MÓDULO: fase2_edicion/abuelo_gestor_de_carpetas_por_video.py
JERARQUÍA: Abuelo  (Gestión de estructura de archivos y carpetas por video)
PROYECTO: FaceDPeli
DESCRIPCIÓN: Responsable de toda la taxonomía física de directorios del pipeline
             de edición. Crea las carpetas de salida en 'procesados/', construye
             la nomenclatura de partes, gestiona el archivo metadata_segmentada.json
             por cada video y ejecuta la purga del archivo original pesado tras
             confirmar que todos los clips fueron generados correctamente.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class AbueloGestorDeCarpetasPorVideo:
    """
    Administra la estructura física de directorios para cada video procesado.

    Responsabilidades:
        - Crear el directorio de salida en 'procesados/[id_video]/'.
        - Generar nombres de archivo de parte siguiendo la nomenclatura oficial.
        - Escribir y actualizar metadata_segmentada.json.
        - Ejecutar la eliminación del video original pesado (Garbage Collection).
    """

    def __init__(
        self,
        dir_procesados: str = "procesados",
        sufijo_parte: str = "Parte",
        separador: str = "_",
    ) -> None:
        """
        Inicializa el gestor con las rutas y convenciones de nomenclatura.

        Args:
            dir_procesados: Nombre del directorio raíz de salida de clips.
            sufijo_parte:   Sufijo de nomenclatura de parte (default: 'Parte').
            separador:      Separador en nombres de archivo (default: '_').
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._dir_procesados = self._ruta_base / dir_procesados
        self._sufijo_parte = sufijo_parte
        self._separador = separador

    # ------------------------------------------------------------------
    # GESTIÓN DE CARPETAS
    # ------------------------------------------------------------------

    def crear_carpeta_video(self, id_video: str) -> Path:
        """
        Crea el directorio de salida para los clips de un video específico.
        Si el directorio ya existe, no hace nada (idempotente).

        Args:
            id_video: Identificador único del video.

        Returns:
            Objeto Path apuntando al directorio creado.
        """
        ruta_video = self._dir_procesados / id_video
        ruta_video.mkdir(parents=True, exist_ok=True)
        print(f"[ABUELO] Directorio de procesado listo: {ruta_video}")
        return ruta_video

    def obtener_ruta_clip(self, dir_video: Path, numero_parte: int, titulo: str) -> Path:
        """
        Construye la ruta completa de un clip con su nomenclatura oficial.
        Formato: [Titulo_Limpio]_Parte_[N].mp4

        Args:
            dir_video:    Directorio de salida del video.
            numero_parte: Número ordinal de la parte (1, 2, 3...).
            titulo:       Título original del video (se limpiará de caracteres inválidos).

        Returns:
            Ruta completa del archivo de clip.
        """
        titulo_limpio = self._limpiar_nombre_archivo(titulo)
        nombre_clip = f"{titulo_limpio}{self._separador}{self._sufijo_parte}{self._separador}{numero_parte}.mp4"
        return dir_video / nombre_clip

    def listar_clips_generados(self, dir_video: Path) -> List[Path]:
        """
        Lista todos los archivos .mp4 presentes en el directorio de un video.

        Args:
            dir_video: Directorio de procesado del video.

        Returns:
            Lista ordenada de rutas a los clips MP4.
        """
        if not dir_video.exists():
            return []
        clips = sorted(dir_video.glob("*.mp4"))
        return clips

    def carpeta_esta_vacia_de_clips(self, dir_video: Path) -> bool:
        """
        Verifica si el directorio del video ya no contiene clips MP4.

        Args:
            dir_video: Directorio del video.

        Returns:
            True si no hay clips MP4 en el directorio.
        """
        return len(self.listar_clips_generados(dir_video)) == 0

    # ------------------------------------------------------------------
    # METADATA SEGMENTADA
    # ------------------------------------------------------------------

    def escribir_metadata_segmentada(
        self, dir_video: Path, metadata_original: dict, rangos_corte: list, factor_velocidad: float
    ) -> None:
        """
        Genera el archivo metadata_segmentada.json con información de los
        segmentos calculados para el video, heredando los datos originales.

        Args:
            dir_video:         Directorio de salida del video procesado.
            metadata_original: Diccionario con la metadata de la Fase 1.
            rangos_corte:      Lista de dicts [{inicio, fin, numero_parte}].
            factor_velocidad:  Factor de velocidad aplicado (1.0, 1.25, 1.5).
        """
        metadata_segmentada = {
            "id_video": metadata_original.get("id_video", ""),
            "url_original": metadata_original.get("url_original", ""),
            "titulo_original": metadata_original.get("titulo_original", ""),
            "descripcion_original": metadata_original.get("descripcion_original", ""),
            "fecha_segmentacion": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duracion_original_segundos": metadata_original.get("duracion_segundos", 0),
            "factor_velocidad_aplicado": factor_velocidad,
            "total_partes": len(rangos_corte),
            "segmentos": rangos_corte,
        }
        ruta_json = dir_video / "metadata_segmentada.json"
        with open(ruta_json, "w", encoding="utf-8") as archivo:
            json.dump(metadata_segmentada, archivo, ensure_ascii=False, indent=2)
        print(f"[ABUELO] metadata_segmentada.json escrita en: {ruta_json}")

    # ------------------------------------------------------------------
    # GARBAGE COLLECTION FÍSICO
    # ------------------------------------------------------------------

    def eliminar_video_original_pesado(self, ruta_video_original: Path) -> bool:
        """
        Elimina el archivo de video original pesado del directorio de descargas
        para recuperar espacio en disco (ROM). Esta operación sólo debe llamarse
        tras confirmar que todos los clips han sido generados y verificados.

        Args:
            ruta_video_original: Ruta absoluta al archivo video_original.mp4.

        Returns:
            True si la eliminación fue exitosa.
        """
        if not ruta_video_original.exists():
            print(f"[ABUELO] Video original no encontrado para eliminar: {ruta_video_original}")
            return False
        try:
            ruta_video_original.unlink()
            print(f"[ABUELO] [GC] Video original eliminado: {ruta_video_original}")
            return True
        except OSError as error:
            print(f"[ABUELO] [ERROR] No se pudo eliminar {ruta_video_original}: {error}")
            return False

    def eliminar_carpeta_raiz_video(self, dir_video: Path) -> bool:
        """
        Elimina el directorio completo de un video procesado y todo su contenido.
        Sólo ejecutar cuando el nieto_auditor_y_limpiador_rom confirme purga total.

        Args:
            dir_video: Ruta al directorio a eliminar.

        Returns:
            True si la eliminación fue exitosa.
        """
        if not dir_video.exists():
            return False
        try:
            shutil.rmtree(dir_video)
            print(f"[ABUELO] [GC] Carpeta eliminada en cascada: {dir_video}")
            return True
        except OSError as error:
            print(f"[ABUELO] [ERROR] No se pudo eliminar carpeta {dir_video}: {error}")
            return False

    # ------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # ------------------------------------------------------------------

    def _limpiar_nombre_archivo(self, nombre: str) -> str:
        """
        Sanitiza el nombre del título para que sea válido como nombre de archivo
        en Windows (elimina caracteres prohibidos y limita la longitud).

        Args:
            nombre: Título original del video.

        Returns:
            Nombre limpio apto para sistema de archivos.
        """
        if not nombre:
            return "video_sin_titulo"
        # Eliminar caracteres prohibidos en Windows
        limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre)
        # Reemplazar espacios por guiones bajos
        limpio = re.sub(r"\s+", "_", limpio)
        # Eliminar puntos consecutivos y al inicio/final
        limpio = limpio.strip("._")
        # Limitar a 80 caracteres para evitar rutas demasiado largas
        return limpio[:80] if limpio else "video_sin_titulo"
