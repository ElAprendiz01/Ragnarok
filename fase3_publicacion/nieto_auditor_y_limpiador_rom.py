"""
================================================================================
MÓDULO: fase3_publicacion/nieto_auditor_y_limpiador_rom.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — auditoría y purga física de disco)
PROYECTO: Ragnarok
DESCRIPCIÓN: Encargado de la purga física y segura del almacenamiento ROM.
             Lee el archivo estado_publicaciones.txt, verifica que un clip
             haya sido publicado exitosamente en el 100% de las plataformas
             configuradas y sólo entonces ejecuta la eliminación del clip
             local. Implementa la purga en cascada de carpetas vacías.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class NietoAuditorYLimpiadorROM:
    """
    Audita el estado de publicaciones en disco y ejecuta la purga física
    de clips y carpetas sólo cuando se cumplen todas las condiciones de éxito.

    Regla Estricta de Borrado:
        Un clip NUNCA se elimina hasta que estado_publicaciones.txt confirme
        el código de éxito para el 100% de las plataformas configuradas.
    """

    CODIFICACION: str = "utf-8"
    SEPARADOR_ESTADO: str = " | "

    def __init__(
        self,
        ruta_estado_publicaciones: str = "datos_persistencia/estado_publicaciones.txt",
        plataformas_requeridas: List[str] = None,
    ) -> None:
        """
        Inicializa el auditor con la ruta del archivo de estado y las plataformas.

        Args:
            ruta_estado_publicaciones: Ruta al archivo de control de publicaciones.
            plataformas_requeridas:    Lista de plataformas que deben confirmar éxito.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._ruta_estado = self._ruta_base / ruta_estado_publicaciones
        self._plataformas = plataformas_requeridas or ["youtube", "tiktok", "facebook", "instagram"]

    # ------------------------------------------------------------------
    # REGISTRO DE ESTADO DE PUBLICACIÓN
    # ------------------------------------------------------------------

    def marcar_plataforma_completada(self, clip_id: str, plataforma: str) -> None:
        """
        Registra que un clip fue publicado exitosamente en una plataforma.
        Formato de línea: CLIP_ID | PLATAFORMA | OK | YYYY-MM-DD HH:MM:SS

        Args:
            clip_id:    Identificador único del clip (ej: id_video_parte1).
            plataforma: Nombre de la plataforma ('youtube', 'tiktok', etc.).
        """
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = f"{clip_id} | {plataforma} | OK | {estampa}\n"
        with open(self._ruta_estado, "a", encoding=self.CODIFICACION) as archivo:
            archivo.write(linea)
        print(f"[AUDITOR] Estado registrado: {clip_id} -> {plataforma}: OK")

    def registrar_error_publicacion(self, clip_id: str, plataforma: str, detalle: str) -> None:
        """
        Registra un fallo de publicación en el archivo de estado.
        Formato: CLIP_ID | PLATAFORMA | ERROR | YYYY-MM-DD HH:MM:SS | DETALLE

        Args:
            clip_id:    Identificador único del clip.
            plataforma: Nombre de la plataforma.
            detalle:    Descripción del error ocurrido.
        """
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = f"{clip_id} | {plataforma} | ERROR | {estampa} | {detalle}\n"
        with open(self._ruta_estado, "a", encoding=self.CODIFICACION) as archivo:
            archivo.write(linea)
        print(f"[AUDITOR] Error registrado: {clip_id} -> {plataforma}: ERROR")

    # ------------------------------------------------------------------
    # AUDITORÍA DE COMPLETADO
    # ------------------------------------------------------------------

    def verificar_si_clip_completo_en_todas_las_redes(self, clip_id: str) -> bool:
        """
        Consulta el archivo de estado y verifica que el clip haya recibido
        confirmación de éxito en el 100% de las plataformas configuradas.

        Args:
            clip_id: Identificador único del clip a verificar.

        Returns:
            True si todas las plataformas marcaron el clip como 'OK'.
        """
        if not self._ruta_estado.exists():
            return False

        plataformas_ok: set = set()
        with open(self._ruta_estado, "r", encoding=self.CODIFICACION) as archivo:
            for linea in archivo:
                partes = linea.strip().split(self.SEPARADOR_ESTADO)
                if len(partes) >= 3:
                    id_en_linea = partes[0].strip()
                    plataforma_en_linea = partes[1].strip()
                    estado = partes[2].strip()
                    if id_en_linea == clip_id and estado == "OK":
                        plataformas_ok.add(plataforma_en_linea.lower())

        plataformas_requeridas_set = set(p.lower() for p in self._plataformas)
        completo = plataformas_requeridas_set.issubset(plataformas_ok)

        if completo:
            print(f"[AUDITOR] [OK] Clip {clip_id} completado en todas las redes: {plataformas_ok}")
        else:
            faltantes = plataformas_requeridas_set - plataformas_ok
            print(f"[AUDITOR] Clip {clip_id} pendiente en: {faltantes}")

        return completo

    def obtener_estado_clip(self, clip_id: str) -> Dict[str, str]:
        """
        Retorna el estado de publicación de un clip por plataforma.

        Args:
            clip_id: Identificador único del clip.

        Returns:
            Diccionario {plataforma: estado} con los registros encontrados.
        """
        estados: Dict[str, str] = {}
        if not self._ruta_estado.exists():
            return estados
        with open(self._ruta_estado, "r", encoding=self.CODIFICACION) as archivo:
            for linea in archivo:
                partes = linea.strip().split(self.SEPARADOR_ESTADO)
                if len(partes) >= 3 and partes[0].strip() == clip_id:
                    plataforma = partes[1].strip().lower()
                    estado = partes[2].strip()
                    estados[plataforma] = estado
        return estados

    # ------------------------------------------------------------------
    # PURGA FÍSICA (Eliminación segura de clips y carpetas)
    # ------------------------------------------------------------------

    def validar_requisitos_borrado(self, clip_id: str) -> bool:
        """
        Valida que se cumplen todos los requisitos antes de eliminar un clip.
        Alias semántico de verificar_si_clip_completo_en_todas_las_redes.

        Args:
            clip_id: Identificador del clip a validar.

        Returns:
            True si el clip puede ser eliminado de forma segura.
        """
        return self.verificar_si_clip_completo_en_todas_las_redes(clip_id)

    def ejecutar_eliminacion_clip(self, ruta_clip: Path) -> bool:
        """
        Elimina físicamente un archivo clip MP4 del disco.
        Esta operación es IRREVERSIBLE. Sólo llamar tras validar_requisitos_borrado().

        Args:
            ruta_clip: Ruta absoluta al archivo MP4 a eliminar.

        Returns:
            True si la eliminación fue exitosa.
        """
        if not ruta_clip.exists():
            print(f"[AUDITOR] [!] Clip ya no existe en disco: {ruta_clip}")
            return True  # Considerar como exitoso si ya no está

        try:
            ruta_clip.unlink()
            print(f"[AUDITOR] [PURGA] Clip eliminado de ROM: {ruta_clip.name}")
            return True
        except OSError as error:
            print(f"[AUDITOR] [ERROR] No se pudo eliminar {ruta_clip}: {error}")
            return False

    def ejecutar_eliminacion_cascada(self, dir_video: Path) -> bool:
        """
        Elimina el directorio completo de un video procesado (purga en cascada)
        una vez que todos sus clips han sido eliminados individualmente.

        Args:
            dir_video: Directorio raíz del video en 'procesados/'.

        Returns:
            True si la carpeta fue eliminada exitosamente.
        """
        if not dir_video.exists():
            return True
        # Verificar que la carpeta esté vacía de clips MP4
        clips_restantes = list(dir_video.glob("*.mp4"))
        if clips_restantes:
            print(f"[AUDITOR] [!] No se puede eliminar carpeta; aún hay {len(clips_restantes)} clips.")
            return False
        try:
            shutil.rmtree(dir_video)
            print(f"[AUDITOR] [PURGA] Carpeta eliminada en cascada: {dir_video}")
            return True
        except OSError as error:
            print(f"[AUDITOR] [ERROR] No se pudo eliminar carpeta {dir_video}: {error}")
            return False
