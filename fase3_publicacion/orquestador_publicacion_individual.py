"""
================================================================================
MÓDULO: fase3_publicacion/orquestador_publicacion_individual.py
JERARQUÍA: Orquestador (Publicación directa y bajo demanda de un video activo)
PROYECTO: Ragnarok (FaceDPeli)
DESCRIPCIÓN: Coordina la publicación selectiva de un único video específico
             (por ID) hacia plataformas individuales (principalmente Telegram HD,
             con adaptadores preparados para YouTube, TikTok, Facebook e Instagram).
             Permite elegir entre subir el video completo original en HD
             o sus clips segmentados. Reutiliza los módulos ya desarrollados
             sin duplicar lógica.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Asegurar que la raíz del proyecto está en sys.path
RAIZ = Path(__file__).parent.parent.resolve()
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fase3_publicacion.abuelo_gestor_plataformas_multiplex import AbueloGestorPlataformasMultiplex
from fase3_publicacion.hijo_inyector_de_metadatos_y_carga import HijoInyectorDeMetadatosYCarga
from fase3_publicacion.padre_publicador_telegram import PadrePublicadorTelegram
from fase3_publicacion.padre_publicador_youtube import PadrePublicadorYouTube
from fase3_publicacion.padre_publicador_tiktok import PadrePublicadorTikTok
from fase3_publicacion.padre_publicador_facebook import PadrePublicadorFacebook
from fase3_publicacion.padre_publicador_instagram import PadrePublicadorInstagram
from fase3_publicacion.nieto_auditor_y_limpiador_rom import NietoAuditorYLimpiadorROM


class OrquestadorPublicacionIndividual:
    """
    Orquesta la publicación directa y bajo demanda de un video específico
    hacia la plataforma seleccionada (con soporte preferente y maduro para Telegram Web HD).
    """

    def __init__(self, ruta_config: str = "config/parametros_globales.json") -> None:
        self._ruta_base = RAIZ
        self._config = self._cargar_config(ruta_config)
        self._config_pub = self._config.get("publicacion", {})
        self._config_rutas = self._config.get("rutas", {})
        self._config_persist = self._config.get("persistencia", {})

        self._headless = self._config.get("extraccion", {}).get("headless", False)
        self._dir_descargas = self._ruta_base / self._config_rutas.get("directorio_descargas", "descargas")
        self._dir_procesados = self._ruta_base / self._config_rutas.get("directorio_procesados", "procesados")
        self._ruta_estado = self._ruta_base / self._config_persist.get("estado_publicaciones", "datos_persistencia/estado_publicaciones.txt")
        self._ruta_log = self._ruta_base / self._config_rutas.get("log_tiempo_real", "datos_persistencia/log_tiempo_real.txt")

        # Submódulos reutilizados
        self._inyector = HijoInyectorDeMetadatosYCarga()
        self._multiplex = AbueloGestorPlataformasMultiplex(headless=self._headless)
        self._auditor = NietoAuditorYLimpiadorROM(
            ruta_estado_publicaciones=str(self._ruta_estado.relative_to(self._ruta_base)),
            plataformas_requeridas=[self._config_pub.get("plataformas_activas", ["telegram"])[0]],
        )
        self._publicadores = {
            "telegram": PadrePublicadorTelegram(self._inyector),
            "youtube": PadrePublicadorYouTube(self._inyector),
            "tiktok": PadrePublicadorTikTok(self._inyector),
            "facebook": PadrePublicadorFacebook(self._inyector),
            "instagram": PadrePublicadorInstagram(self._inyector),
        }

    def _log(self, nivel: str, mensaje: str) -> None:
        """Escribe tanto en consola como en log_tiempo_real.txt para el panel web SSE."""
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{estampa} [{nivel}] {mensaje}")
        try:
            self._ruta_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_log, "a", encoding="utf-8") as f:
                f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")
        except OSError:
            pass

    async def publicar_video(
        self,
        id_video: str,
        plataforma: str = "telegram",
        modo: str = "completo",
        canal_target: Optional[str] = None,
    ) -> bool:
        """
        Publica el video especificado en la plataforma elegida.

        Args:
            id_video: Identificador único del video (hash).
            plataforma: Plataforma destino ('telegram', 'youtube', 'tiktok', 'facebook', 'instagram').
            modo: 'completo' (video original HD) o 'clips' (fragmentos segmentados).
            canal_target: Canal de destino (para Telegram). Si None, toma de config.

        Returns:
            True si la publicación fue exitosa.
        """
        plataforma = plataforma.lower().strip()
        publicador = self._publicadores.get(plataforma)
        if not publicador:
            self._log("ERROR", f"Plataforma '{plataforma}' no soportada o sin módulo publicador.")
            return False

        # Resolver canal de Telegram
        if plataforma == "telegram":
            if not canal_target:
                canal_target = self._config_pub.get("canal_telegram", "") or self._config.get("canal_telegram", "")
            if not canal_target:
                canales = self._config_pub.get("canales_telegram", []) or self._config.get("canales_telegram", [])
                if canales and isinstance(canales, list) and len(canales) > 0:
                    canal_target = canales[0]
            if not canal_target:
                self._log("ERROR", "No se especificó canal de Telegram para la publicación.")
                return False

        # Localizar archivos del video y metadatos
        info_video = self._obtener_archivos_y_metadatos(id_video, modo)
        if not info_video:
            self._log("ERROR", f"No se encontraron archivos de video o metadatos para el ID: {id_video}")
            return False

        titulo = info_video["titulo"]
        descripcion = info_video["descripcion"]
        archivos = info_video["archivos"]  # Lista de tuplas: (Path, numero_parte)

        self._log("INFO", f"Iniciando publicación directa de '{titulo}' en {plataforma.upper()}...")
        self._log("INFO", f"Modo: {modo.upper()} | {len(archivos)} archivo(s) | Canal/Destino: {canal_target or 'Por defecto'}")

        await self._multiplex.inicializar()
        exito_global = True

        try:
            metodo_contexto = getattr(self._multiplex, f"obtener_contexto_{plataforma}", None)
            if not metodo_contexto:
                self._log("ERROR", f"No se pudo crear contexto de navegador para {plataforma}.")
                return False

            contexto = await metodo_contexto()
            if not contexto:
                self._log("ERROR", f"Contexto de navegación no disponible para {plataforma}.")
                return False

            for ruta_archivo, num_parte in archivos:
                self._log("INFO", f"Subiendo: {ruta_archivo.name} ({ruta_archivo.stat().st_size / (1024*1024):.1f} MB)...")

                if plataforma == "telegram":
                    exito = await publicador.iniciar_flujo_subida(
                        contexto=contexto,
                        ruta_video=ruta_archivo,
                        titulo=titulo,
                        descripcion=descripcion,
                        canal_target=canal_target,
                        numero_parte=num_parte,
                    )
                else:
                    exito = await publicador.iniciar_flujo_subida(
                        contexto=contexto,
                        ruta_clip=ruta_archivo,
                        titulo=titulo,
                        descripcion=descripcion,
                        numero_parte=num_parte,
                    )

                clip_id = f"{id_video}_{ruta_archivo.stem}"
                if exito:
                    self._auditor.marcar_plataforma_completada(clip_id, plataforma)
                    self._log("OK", f"✓ {ruta_archivo.name} publicado exitosamente en {plataforma.upper()}.")
                else:
                    exito_global = False
                    self._auditor.registrar_error_publicacion(clip_id, plataforma, "Fallo en flujo de subida individual.")
                    self._log("ERROR", f"✗ Fallo al subir {ruta_archivo.name} a {plataforma.upper()}.")

        except Exception as err:
            self._log("ERROR", f"Excepción durante la publicación en {plataforma}: {err}")
            exito_global = False
        finally:
            await self._multiplex.cerrar_todo()

        if exito_global:
            self._log("OK", f"✓ Publicación directa de '{titulo}' en {plataforma.upper()} finalizada con éxito.")
        else:
            self._log("WARN", f"! Publicación directa completada con observaciones o errores.")

        return exito_global

    def _obtener_archivos_y_metadatos(self, id_video: str, modo: str) -> Optional[Dict[str, Any]]:
        """Busca el video en descargas/ o procesados/ y extrae sus metadatos."""
        dir_desc = self._dir_descargas / id_video
        dir_proc = self._dir_procesados / id_video

        archivos: List[Any] = []
        metadata: Dict[str, Any] = {}

        if modo == "completo" or not dir_proc.exists():
            if dir_desc.exists():
                vids = [f for f in dir_desc.iterdir() if f.is_file() and f.suffix.lower() in ('.mp4', '.webm', '.mkv') and f.stat().st_size > 0]
                if vids:
                    archivos.append((vids[0], 1))
                meta_file = dir_desc / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass

        if modo == "clips" or not archivos:
            if dir_proc.exists():
                clips = sorted(dir_proc.glob("*.mp4"))
                for idx, c in enumerate(clips, 1):
                    archivos.append((c, idx))
                meta_seg = dir_proc / "metadata_segmentada.json"
                if meta_seg.exists():
                    try:
                        with open(meta_seg, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass

        if not archivos:
            return None

        titulo = metadata.get("titulo_original", metadata.get("titulo", f"Video {id_video}"))
        descripcion = metadata.get("descripcion_original", metadata.get("descripcion", ""))

        return {
            "titulo": titulo,
            "descripcion": descripcion,
            "archivos": archivos,
            "metadata": metadata,
        }

    def _cargar_config(self, ruta_relativa: str) -> dict:
        ruta_abs = self._ruta_base / ruta_relativa
        if not ruta_abs.exists():
            return {}
        with open(ruta_abs, "r", encoding="utf-8") as f:
            return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publicación individual y directa de un video.")
    parser.add_argument("--id", required=True, help="ID único del video a publicar.")
    parser.add_argument("--plataforma", default="telegram", choices=["telegram", "youtube", "tiktok", "facebook", "instagram"], help="Plataforma de destino.")
    parser.add_argument("--modo", default="completo", choices=["completo", "clips"], help="Modo de video: completo (HD original) o clips (segmentos).")
    parser.add_argument("--canal", default=None, help="Canal de Telegram destino (ej: @mi_canal).")

    args = parser.parse_args()
    orquestador = OrquestadorPublicacionIndividual()
    exito = asyncio.run(orquestador.publicar_video(
        id_video=args.id,
        plataforma=args.plataforma,
        modo=args.modo,
        canal_target=args.canal,
    ))
    if not exito:
        sys.exit(1)


if __name__ == "__main__":
    main()
