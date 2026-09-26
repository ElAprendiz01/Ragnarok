"""
================================================================================
MÓDULO: fase3_publicacion/orquestador_publicaciones_principal.py
JERARQUÍA: Orquestador  (Punto de entrada de la Fase 3 — Sin lógica pesada)
PROYECTO: Ragnarok
DESCRIPCIÓN: Punto de entrada de la Fase 3: Publicación & Limpieza Cascade.
             Escanea las carpetas de 'procesados/', verifica el estado contra
             estado_publicaciones.txt, delega la publicación a los publicadores
             de cada plataforma y coordina la purga en cascada de clips y
             carpetas una vez confirmado el éxito en todas las redes.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from fase3_publicacion.abuelo_gestor_plataformas_multiplex import AbueloGestorPlataformasMultiplex
from fase3_publicacion.padre_publicador_youtube import PadrePublicadorYouTube
from fase3_publicacion.padre_publicador_tiktok import PadrePublicadorTikTok
from fase3_publicacion.padre_publicador_facebook import PadrePublicadorFacebook
from fase3_publicacion.padre_publicador_instagram import PadrePublicadorInstagram
from fase3_publicacion.padre_publicador_telegram import PadrePublicadorTelegram
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga
from fase3_publicacion.nieto_auditor_y_limpiador_rom import NietoAuditorYLimpiadorROM


class OrquestadorPublicacionesPrincipal:
    """
    Coordina la distribución multicanal de clips procesados hacia todas
    las plataformas configuradas y ejecuta la purga en cascada final.
    """

    def __init__(self, ruta_config: str = "config/parametros_globales.json") -> None:
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._config = self._cargar_config(ruta_config)
        config_pub = self._config.get("publicacion", {})
        config_rutas = self._config.get("rutas", {})
        config_persist = self._config.get("persistencia", {})

        self._plataformas_activas: List[str] = config_pub.get(
            "plataformas_activas", ["youtube", "tiktok", "facebook", "instagram", "telegram"]
        )
        self._dir_procesados = self._ruta_base / config_rutas.get("directorio_procesados", "procesados")
        self._ruta_estado = self._ruta_base / config_persist.get(
            "estado_publicaciones", "datos_persistencia/estado_publicaciones.txt"
        )
        self._headless: bool = self._config.get("extraccion", {}).get("headless", True)

        # Instanciar submódulos
        self._inyector = HijoInyectorDeMetadatosYCarga()
        self._multiplex = AbueloGestorPlataformasMultiplex(headless=self._headless)
        self._auditor = NietoAuditorYLimpiadorROM(
            ruta_estado_publicaciones=str(self._ruta_estado.relative_to(self._ruta_base)),
            plataformas_requeridas=self._plataformas_activas,
        )
        self._publicadores = {
            "youtube": PadrePublicadorYouTube(self._inyector),
            "tiktok": PadrePublicadorTikTok(self._inyector),
            "facebook": PadrePublicadorFacebook(self._inyector),
            "instagram": PadrePublicadorInstagram(self._inyector),
            "telegram": PadrePublicadorTelegram(self._inyector),
        }

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # ------------------------------------------------------------------

    async def ejecutar_fase_3(self, plataforma_filtro: Optional[str] = None) -> None:
        """Ejecuta el pipeline completo de publicación y limpieza (o filtrado por plataforma)."""
        self._log("==========================================================")
        self._log("  Ragnarok — FASE 3: PUBLICACIÓN & LIMPIEZA CASCADE")
        if plataforma_filtro:
            self._log(f"  Filtro de plataforma única activo: {plataforma_filtro.upper()}")
        self._log("==========================================================")

        carpetas_videos = self._obtener_carpetas_procesadas()
        if not carpetas_videos:
            self._log("[ORQ] No hay carpetas procesadas disponibles para publicar.")
            return

        self._log(f"[ORQ] {len(carpetas_videos)} carpeta(s) de video encontrada(s).")
        await self._multiplex.inicializar()

        try:
            for idx, dir_video in enumerate(carpetas_videos, 1):
                self._log(f"[ORQ] (Video {idx}/{len(carpetas_videos)}) Procesando cautelosamente: {dir_video.name}")
                await self._procesar_carpeta_de_video(dir_video, plataforma_filtro=plataforma_filtro)

                # Pausa cautelosa de enfriamiento y liberación de memoria entre videos
                pausa_seg = self._config.get("publicacion", {}).get("pausa_entre_publicaciones_seg", 5)
                if pausa_seg > 0 and idx < len(carpetas_videos):
                    print(f"[ORQ] Pausa cautelosa de enfriamiento ({pausa_seg}s) antes de procesar el siguiente video...")
                    await asyncio.sleep(pausa_seg)
                    import gc
                    gc.collect()
        finally:
            await self._multiplex.cerrar_todo()

        self._log("[ORQ] ✓ Fase 3 completada exitosamente.")


    def _log(self, mensaje: str) -> None:
        """Escribe en consola y en log_tiempo_real.txt para la UI SSE."""
        from datetime import datetime
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nivel = "INFO"
        if "[ERROR]" in mensaje or "Fallo" in mensaje or "✗" in mensaje:
            nivel = "ERROR"
        elif "!" in mensaje or "PENDIENTE" in mensaje:
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
    # PROCESAMIENTO DE CARPETA
    # ------------------------------------------------------------------

    async def _procesar_carpeta_de_video(self, dir_video: Path, plataforma_filtro: Optional[str] = None) -> None:
        """Procesa todos los clips en la carpeta de un video."""
        id_video = dir_video.name
        print(f"\n[ORQ] Procesando carpeta de video: {id_video}")

        ruta_metadata = dir_video / "metadata_segmentada.json"
        if not ruta_metadata.exists():
            ruta_metadata = dir_video / "metadata.json"
        metadata = self._cargar_metadata_json(ruta_metadata)
        titulo = metadata.get("titulo_original", metadata.get("titulo", f"video_{id_video}"))
        descripcion = metadata.get("descripcion_original", metadata.get("descripcion", ""))
        segmentos = metadata.get("segmentos", [])

        clips_mp4 = sorted(dir_video.glob("*.mp4"))
        plataformas_a_procesar = [plataforma_filtro] if plataforma_filtro else self._plataformas_activas

        for ruta_clip in clips_mp4:
            clip_id = f"{id_video}_{ruta_clip.stem}"
            numero_parte = self._extraer_numero_parte(ruta_clip.name, segmentos)
            print(f"\n  [ORQ] Publicando clip/video: {ruta_clip.name} (Parte {numero_parte})")

            for plataforma in plataformas_a_procesar:
                estado_actual = self._auditor.obtener_estado_clip(clip_id)
                if estado_actual.get(plataforma, "PENDIENTE") == "OK":
                    print(f"    [{plataforma.upper()}] Ya publicado. Saltando.")
                    continue

                publicador = self._publicadores.get(plataforma)
                if not publicador:
                    continue

                contexto = await self._obtener_contexto_plataforma(plataforma)
                if not contexto:
                    continue

                if plataforma == "telegram":
                    ruta_hd = self._ruta_base / "descargas" / id_video / "video_original.mp4"
                    ruta_a_subir = ruta_hd if ruta_hd.exists() else ruta_clip
                    canal_target = self._config.get("publicacion", {}).get("canal_telegram", "")
                    exito = await publicador.iniciar_flujo_subida(
                        contexto, ruta_a_subir, titulo, descripcion, canal_target=canal_target, numero_parte=numero_parte
                    )
                else:
                    exito = await publicador.iniciar_flujo_subida(
                        contexto, ruta_clip, titulo, descripcion, numero_parte
                    )

                if exito:
                    self._auditor.marcar_plataforma_completada(clip_id, plataforma)
                else:
                    self._auditor.registrar_error_publicacion(
                        clip_id, plataforma, "Fallo en flujo de subida."
                    )

            # Purga física únicamente si la carpeta proviene de 'procesados/' y NO hay filtro activo
            es_directorio_procesados = "procesados" in str(dir_video.resolve())
            if es_directorio_procesados and not plataforma_filtro:
                if self._auditor.validar_requisitos_borrado(clip_id):
                    self._auditor.ejecutar_eliminacion_clip(ruta_clip)

        if es_directorio_procesados and not plataforma_filtro:
            clips_restantes = list(dir_video.glob("*.mp4"))
            if not clips_restantes:
                self._auditor.ejecutar_eliminacion_cascada(dir_video)

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    async def _obtener_contexto_plataforma(self, plataforma: str):
        """Obtiene el contexto de navegador para la plataforma indicada."""
        metodo = getattr(self._multiplex, f"obtener_contexto_{plataforma}", None)
        if metodo:
            return await metodo()
        return None

    def _obtener_carpetas_procesadas(self) -> List[Path]:
        """
        Retorna las carpetas de videos disponibles para publicar.
        Busca en 'procesados/' y también en 'descargas/' para soportar publicaciones HD (como Telegram).
        """
        carpetas = []
        # 1. Carpetas de procesados/ (clips segmentados)
        if self._dir_procesados.exists():
            carpetas.extend([d for d in self._dir_procesados.iterdir() if d.is_dir() and list(d.glob("*.mp4"))])

        # 2. Carpetas de descargas/ (videos originales completos)
        dir_descargas = self._ruta_base / "descargas"
        if dir_descargas.exists():
            for d in dir_descargas.iterdir():
                if d.is_dir() and ((d / "video_original.mp4").exists() or list(d.glob("*.mp4"))):
                    if not any(c.name == d.name for c in carpetas):
                        carpetas.append(d)

        return sorted(carpetas, key=lambda p: p.name)

    def _extraer_numero_parte(self, nombre_clip: str, segmentos: list) -> int:
        """Extrae el número de parte del nombre del clip."""
        import re
        coincidencia = re.search(r"Parte[_\s](\d+)", nombre_clip, re.IGNORECASE)
        if coincidencia:
            return int(coincidencia.group(1))
        return 1

    def _cargar_metadata_json(self, ruta: Path) -> dict:
        if not ruta.exists():
            return {}
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    def _cargar_config(self, ruta_relativa: str) -> dict:
        ruta_abs = self._ruta_base / ruta_relativa
        if not ruta_abs.exists():
            return {}
        with open(ruta_abs, "r", encoding="utf-8") as archivo:
            return json.load(archivo)


# ------------------------------------------------------------------
# PUNTO DE ENTRADA DIRECTO
# ------------------------------------------------------------------

if __name__ == "__main__":
    orquestador = OrquestadorPublicacionesPrincipal()
    asyncio.run(orquestador.ejecutar_fase_3())
