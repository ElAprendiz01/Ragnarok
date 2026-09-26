"""
================================================================================
MÓDULO: fase2_edicion/orquestador_edicion_principal.py
JERARQUÍA: Orquestador  (Punto de entrada de la Fase 2 — Sin lógica pesada)
PROYECTO: Ragnarok
DESCRIPCIÓN: Punto de entrada de la Fase 2: Edición & Segmentación. Lee los
             videos completados desde enlaces_completados.txt, coordina el
             pipeline de cálculo de segmentos, construcción de flags de FFmpeg
             y ejecución de cortes para cada video. Delega toda la lógica
             a los módulos de nivel inferior.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import json
from pathlib import Path
from typing import List, Tuple

from fase2_edicion.abuelo_gestor_de_carpetas_por_video import AbueloGestorDeCarpetasPorVideo
from fase2_edicion.padre_calculadora_de_segmentos import PadreCalculadoraDeSegmentos
from fase2_edicion.hijo_procesador_de_velocidad import HijoProcesadorDeVelocidad
from fase2_edicion.nieto_ejecutor_ffmpeg_optimizado import NietoEjecutorFFmpegOptimizado


class OrquestadorEdicionPrincipal:
    """
    Coordina el pipeline completo de la Fase 2: Edición & Segmentación.

    Flujo de ejecución:
        1. Leer videos completados desde enlaces_completados.txt.
        2. Para cada video: calcular segmentos y ejecutar cortes con FFmpeg.
        3. Verificar integridad de clips y purgar video original.
    """

    def __init__(self, ruta_config: str = "config/parametros_globales.json") -> None:
        """
        Carga la configuración y prepara los submódulos de edición.

        Args:
            ruta_config: Ruta relativa al archivo de parámetros globales.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._config = self._cargar_config(ruta_config)
        config_edicion = self._config.get("edicion", {})
        config_rutas = self._config.get("rutas", {})
        config_persist = self._config.get("persistencia", {})
        config_nomenclatura = self._config.get("nomenclatura", {})

        # Instanciar submódulos
        self._gestor_carpetas = AbueloGestorDeCarpetasPorVideo(
            dir_procesados=config_rutas.get("directorio_procesados", "procesados"),
            sufijo_parte=config_nomenclatura.get("sufijo_parte", "Parte"),
            separador=config_nomenclatura.get("separador_nombre", "_"),
        )
        self._calculadora = PadreCalculadoraDeSegmentos(
            duracion_bloque=config_edicion.get("duracion_bloque_segundos", 480),
            duracion_minima_remanente=config_edicion.get("duracion_minima_remanente_segundos", 60),
        )
        self._procesador_velocidad = HijoProcesadorDeVelocidad(
            factor_velocidad=config_edicion.get("factor_velocidad", 1.0),
            encoder_preferido=config_edicion.get("encoder_preferido", "auto"),
            threads=config_edicion.get("threads_ffmpeg", 4),
        )
        self._ejecutor_ffmpeg = NietoEjecutorFFmpegOptimizado(
            threads=config_edicion.get("threads_ffmpeg", 4)
        )

        self._ruta_completados = self._ruta_base / config_persist.get(
            "enlaces_completados", "datos_persistencia/enlaces_completados.txt"
        )
        self._dir_descargas = self._ruta_base / config_rutas.get("directorio_descargas", "descargas")

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # ------------------------------------------------------------------

    def ejecutar_fase_2(self) -> None:
        """
        Ejecuta el pipeline completo de edición para todos los videos
        disponibles en la cola de completados.
        """
        self._log("==========================================================")
        self._log("  Ragnarok — FASE 2: EDICIÓN & SEGMENTACIÓN")
        self._log("==========================================================")

        videos = self._leer_videos_completados()
        if not videos:
            self._log("[ORQ] No hay videos completados para procesar en la Fase 2.")
            return

        self._log(f"[ORQ] {len(videos)} video(s) encontrado(s) para editar.")
        for id_video, url in videos:
            self._log(f"[ORQ] Iniciando edición de video: {id_video}")
            self._procesar_video_completo(id_video, url)

        self._log("[ORQ] ✓ Fase 2 completada exitosamente.")

    def _log(self, mensaje: str) -> None:
        """Escribe en consola y en log_tiempo_real.txt para la UI SSE."""
        from datetime import datetime
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nivel = "INFO"
        if "[ERROR]" in mensaje or "Fallo" in mensaje:
            nivel = "ERROR"
        elif "!" in mensaje or "ADVERTENCIA" in mensaje:
            nivel = "WARN"
        elif "✓" in mensaje or "exitos" in mensaje.lower():
            nivel = "OK"

        print(f"{estampa}  {mensaje}")
        ruta_log = self._ruta_base / self._config.get("rutas", {}).get("log_tiempo_real", "datos_persistencia/log_tiempo_real.txt")
        try:
            ruta_log.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta_log, "a", encoding="utf-8") as f:
                f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # PROCESAMIENTO DE UN VIDEO
    # ------------------------------------------------------------------

    def _procesar_video_completo(self, id_video: str, url: str) -> None:
        """
        Ejecuta el flujo completo de edición para un único video:
        crea carpeta, calcula segmentos, ejecuta cortes y valida integridad.

        Args:
            id_video: ID único del video.
            url:      URL original del video.
        """
        ruta_video_original = self._dir_descargas / id_video / "video_original.mp4"
        ruta_metadata_original = self._dir_descargas / id_video / "metadata.json"

        if not ruta_video_original.exists():
            print(f"  [!] Video original no encontrado: {ruta_video_original}")
            return

        # Cargar metadata original
        metadata = self._cargar_metadata_json(ruta_metadata_original)
        titulo = metadata.get("titulo_original", f"video_{id_video}")

        # Paso 1: Crear carpeta de destino
        dir_video_procesado = self._gestor_carpetas.crear_carpeta_video(id_video)

        # Paso 2: Calcular segmentos
        rangos = self._calculadora.calcular_segmentos_para_video(ruta_video_original)
        if not rangos:
            print(f"  [!] No se pudieron calcular segmentos para: {id_video}")
            if self._gestor_carpetas.carpeta_esta_vacia_de_clips(dir_video_procesado):
                self._gestor_carpetas.eliminar_carpeta_raiz_video(dir_video_procesado)
            return

        # Paso 3: Obtener flags de FFmpeg
        encoder = self._ejecutor_ffmpeg.obtener_encoder_disponible()
        flags_ffmpeg = self._procesador_velocidad.obtener_flags_ffmpeg(encoder)

        # Paso 4: Ejecutar cortes
        clips_generados: List[Tuple[Path, float]] = []
        todos_exitosos = True
        for rango in rangos:
            ruta_clip = self._gestor_carpetas.obtener_ruta_clip(
                dir_video_procesado, rango["numero_parte"], titulo
            )
            exito = self._ejecutor_ffmpeg.ejecutar_corte_ffmpeg(
                ruta_entrada=ruta_video_original,
                ruta_salida=ruta_clip,
                inicio_segundos=rango["inicio_segundos"],
                fin_segundos=rango["fin_segundos"],
                flags_adicionales=flags_ffmpeg,
            )
            if exito:
                clips_generados.append((ruta_clip, rango["duracion_segundos"]))
            else:
                todos_exitosos = False
                print(f"  [✗] Fallo al generar Parte {rango['numero_parte']} de {id_video}")

        # Paso 5: Validar integridad de clips
        if clips_generados:
            integridad_ok = self._ejecutor_ffmpeg.verificar_integridad_todos_los_clips(clips_generados)
        else:
            integridad_ok = False

        # Paso 6: Escribir metadata segmentada
        self._gestor_carpetas.escribir_metadata_segmentada(
            dir_video_procesado, metadata, rangos,
            self._procesador_velocidad.obtener_factor()
        )

        # Paso 7: Garbage Collection del video original (sólo si todo fue exitoso)
        if todos_exitosos and integridad_ok:
            print(f"\n  [GC] Todos los clips válidos. Eliminando video original pesado...")
            self._gestor_carpetas.eliminar_video_original_pesado(ruta_video_original)
        else:
            print(f"\n  [!] Algunos clips fallaron. Video original retenido para reintento.")
            if self._gestor_carpetas.carpeta_esta_vacia_de_clips(dir_video_procesado):
                print(f"  [GC] Carpeta de procesado vacía. Limpiando directorio del video...")
                self._gestor_carpetas.eliminar_carpeta_raiz_video(dir_video_procesado)

    # ------------------------------------------------------------------
    # LECTURA DE COLA DE COMPLETADOS
    # ------------------------------------------------------------------

    def _leer_videos_completados(self) -> List[Tuple[str, str]]:
        """
        Lee el archivo enlaces_completados.txt y retorna los pares (id_video, url).
        Formato de línea: ID_VIDEO | URL | YYYY-MM-DD HH:MM:SS

        Returns:
            Lista de tuplas (id_video, url).
        """
        if not self._ruta_completados.exists():
            return []
        videos: List[Tuple[str, str]] = []
        with open(self._ruta_completados, "r", encoding="utf-8") as archivo:
            for linea in archivo:
                partes = linea.strip().split(" | ")
                if len(partes) >= 2:
                    id_video = partes[0].strip()
                    url = partes[1].strip()
                    # Verificar que el video original exista en disco
                    ruta_original = self._dir_descargas / id_video / "video_original.mp4"
                    if ruta_original.exists():
                        videos.append((id_video, url))
        return videos

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    def _cargar_metadata_json(self, ruta: Path) -> dict:
        """Carga y retorna el archivo metadata.json de un video, o dict vacío si falla."""
        if not ruta.exists():
            return {}
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    def _cargar_config(self, ruta_relativa: str) -> dict:
        """Carga y retorna el archivo JSON de configuración global."""
        ruta_abs = self._ruta_base / ruta_relativa
        if not ruta_abs.exists():
            return {}
        with open(ruta_abs, "r", encoding="utf-8") as archivo:
            return json.load(archivo)


# ------------------------------------------------------------------
# PUNTO DE ENTRADA DIRECTO
# ------------------------------------------------------------------

if __name__ == "__main__":
    orquestador = OrquestadorEdicionPrincipal()
    orquestador.ejecutar_fase_2()
