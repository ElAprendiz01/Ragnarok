"""
================================================================================
MÓDULO: fase3_publicacion/orquestador_publicacion_lotes.py
JERARQUÍA: Orquestador (Publicación por lotes secuencial con cola persistente)
PROYECTO: Ragnarok
DESCRIPCIÓN: Procesa la cola de videos en lote para Telegram Web HD de forma
             secuencial (uno a uno) con fallback Zero-RAM en disco.
             Reutiliza OrquestadorPublicacionIndividual por subproceso.
LÍNEAS: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import argparse
import asyncio
import gc
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

RAIZ = Path(__file__).parent.parent.resolve()
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fase3_publicacion.nieto_auditor_y_limpiador_rom import NietoAuditorYLimpiadorROM
from fase3_publicacion.gestor_memoria_publicaciones import GestorMemoriaPublicaciones


class OrquestadorPublicacionLotes:
    """Orquestador de publicación en lote secuencial con cola Zero-RAM en disco."""

    def __init__(
        self,
        ruta_config: str = "config/parametros_globales.json",
        canal: str = "",
        modo_browser: str = "visible",
        modo_video: str = "completo",
        pausa_seg: int = 5,
        forzar: bool = False,
    ) -> None:
        self._ruta_base = RAIZ
        self._config = self._cargar_config(ruta_config)
        self._canal = self._resolver_canal(canal)
        self._modo_browser = "headless" if modo_browser in ["headless", "invisible"] else "visible"
        self._modo_video = "clips" if modo_video == "clips" else "completo"
        self._pausa_seg = max(2, int(pausa_seg))
        self._forzar = bool(forzar)
        self._dir_descargas = self._ruta_base / "descargas"
        self._dir_procesados = self._ruta_base / "procesados"
        self._ruta_cola = self._ruta_base / "datos_persistencia" / "cola_publicacion_telegram.json"
        self._ruta_log = self._ruta_base / "datos_persistencia" / "log_tiempo_real.txt"
        self._ruta_estado = self._ruta_base / "datos_persistencia" / "estado_publicaciones.txt"
        self._memoria = GestorMemoriaPublicaciones(ruta_base=self._ruta_base)
        self._auditor = NietoAuditorYLimpiadorROM(
            ruta_estado_publicaciones=str(self._ruta_estado.relative_to(self._ruta_base)),
            plataformas_requeridas=["telegram"],
        )

    def _resolver_canal(self, canal_solicitado: str) -> str:
        c = canal_solicitado.strip()
        if c:
            return c
        cfg_pub = self._config.get("publicacion", {})
        return cfg_pub.get("canal_telegram", "") or self._config.get("canal_telegram", "")

    def _cargar_config(self, ruta_rel: str) -> dict:
        p = self._ruta_base / ruta_rel
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _log(self, nivel: str, mensaje: str) -> None:
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{estampa} [{nivel}] {mensaje}")
        try:
            self._ruta_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_log, "a", encoding="utf-8") as f:
                f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")
        except OSError:
            pass

    def generar_cola(self, ids_filtro: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Construye un manifiesto liviano en disco con rutas y metadatos sin cargar video en RAM."""
        elementos = []
        ids_set = set(ids_filtro) if ids_filtro else None

        completados_previos = self._memoria.obtener_ids_publicados("telegram") if not self._forzar else set()

        if self._modo_video == "completo" and self._dir_descargas.exists():
            carpetas = sorted([d for d in self._dir_descargas.iterdir() if d.is_dir()], key=lambda d: d.name)
            for d in carpetas:
                id_vid = d.name
                if ids_set and id_vid not in ids_set:
                    continue
                v_orig = d / "video_original.mp4"
                if not v_orig.exists():
                    vids = list(d.glob("*.mp4"))
                    v_orig = vids[0] if vids else None
                if not v_orig or not v_orig.exists():
                    continue

                meta = self._cargar_metadata(d / "metadata.json")
                estado_ini = "COMPLETADO" if id_vid in completados_previos else "PENDIENTE"
                elementos.append({
                    "indice": len(elementos) + 1,
                    "id_video": id_vid,
                    "ruta_video": str(v_orig.resolve()),
                    "nombre_archivo": v_orig.name,
                    "titulo": meta.get("titulo", id_vid),
                    "descripcion": meta.get("descripcion", ""),
                    "numero_parte": 1,
                    "tamano_mb": round(v_orig.stat().st_size / (1024 * 1024), 2),
                    "estado": estado_ini,
                })

        elif self._modo_video == "clips" and self._dir_procesados.exists():
            carpetas = sorted([d for d in self._dir_procesados.iterdir() if d.is_dir()], key=lambda d: d.name)
            for d in carpetas:
                id_vid = d.name
                if ids_set and id_vid not in ids_set:
                    continue
                clips = sorted(d.glob("*.mp4"))
                if not clips:
                    continue
                meta = self._cargar_metadata(d / "metadata_segmentada.json") or self._cargar_metadata(d / "metadata.json")
                titulo_base = meta.get("titulo_original", meta.get("titulo", id_vid))
                desc_base = meta.get("descripcion_original", meta.get("descripcion", ""))
                estado_ini = "COMPLETADO" if id_vid in completados_previos else "PENDIENTE"

                for c in clips:
                    num_p = self._extraer_numero_parte(c.name)
                    elementos.append({
                        "indice": len(elementos) + 1,
                        "id_video": id_vid,
                        "ruta_video": str(c.resolve()),
                        "nombre_archivo": c.name,
                        "titulo": f"{titulo_base} (Parte {num_p})" if num_p > 1 else titulo_base,
                        "descripcion": desc_base,
                        "numero_parte": num_p,
                        "tamano_mb": round(c.stat().st_size / (1024 * 1024), 2),
                        "estado": estado_ini,
                    })

        self._guardar_manifiesto_cola(elementos)
        return elementos

    def _cargar_metadata(self, ruta: Path) -> dict:
        if ruta.exists():
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _extraer_numero_parte(self, nombre: str) -> int:
        import re
        m = re.search(r"Parte[_\s](\d+)", nombre, re.IGNORECASE)
        return int(m.group(1)) if m else 1

    def _guardar_manifiesto_cola(self, elementos: List[Dict[str, Any]]) -> None:
        completados = sum(1 for e in elementos if e.get("estado") == "COMPLETADO")
        fallidos = sum(1 for e in elementos if e.get("estado") == "ERROR")
        payload = {
            "canal": self._canal,
            "modo_browser": self._modo_browser,
            "modo_video": self._modo_video,
            "total": len(elementos),
            "completados": completados,
            "fallidos": fallidos,
            "actualizado_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "elementos": elementos,
        }
        try:
            self._ruta_cola.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_cola, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    async def ejecutar_lote(self, ids_filtro: Optional[List[str]] = None) -> bool:
        """Ejecuta la subida secuencial uno a uno reutilizando el publicador individual probado."""
        elementos = self.generar_cola(ids_filtro)
        total = len(elementos)
        if total == 0:
            self._log("WARN", "No se encontraron videos disponibles para encolar en Telegram.")
            return True

        if not self._canal:
            self._log("ERROR", "Canal de Telegram no configurado. Cancela y especifica un canal.")
            return False

        self._log("INFO", f"Iniciando cola de {total} video(s) a Telegram. Canal: {self._canal} (Ventana: {self._modo_browser.upper()})")

        completados = sum(1 for e in elementos if e.get("estado") == "COMPLETADO")
        fallidos = 0

        for item in elementos:
            idx = item["indice"]
            titulo = item["titulo"]
            id_vid = item["id_video"]
            tam_mb = item["tamano_mb"]

            if item.get("estado") == "COMPLETADO":
                self._log("INFO", f"(Video {idx}/{total}) '{titulo}' ya marcado como completado anteriormente. Omitiendo.")
                continue

            self._log("INFO", f"(Video {idx}/{total}) Encolando: '{titulo}' ({tam_mb} MB)...")

            # Invocación aislada por subproceso para garantizar Zero-RAM y prevenir cierre de contexto
            cmd = [
                sys.executable,
                str(self._ruta_base / "fase3_publicacion" / "orquestador_publicacion_individual.py"),
                "--id", id_vid,
                "--plataforma", "telegram",
                "--modo", self._modo_video,
                "--canal", self._canal,
            ]
            if self._modo_browser == "visible":
                cmd.append("--visible")
            else:
                cmd.append("--headless")

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self._ruta_base),
                )
                retcode = await proc.wait()
                exito = (retcode == 0)
            except Exception as err:
                self._log("ERROR", f"Excepción al invocar publicador individual para '{titulo}': {err}")
                exito = False

            if exito:
                completados += 1
                item["estado"] = "COMPLETADO"
                clip_id = f"{id_vid}_{Path(item['ruta_video']).stem}"
                self._auditor.marcar_plataforma_completada(clip_id, "telegram")
                self._memoria.registrar_publicacion(id_vid, "telegram", "lote", self._canal, self._modo_video, titulo, item["ruta_video"])
                self._log("OK", f"(Video {idx}/{total}) Confirmado y publicado en {self._canal}.")
            else:
                fallidos += 1
                item["estado"] = "ERROR"
                self._log("WARN", f"(Video {idx}/{total}) Falló. Se continuará con el siguiente...")

            self._guardar_manifiesto_cola(elementos)
            gc.collect()

            if idx < total and self._pausa_seg > 0:
                self._log("INFO", f"Pausa cautelosa de enfriamiento ({self._pausa_seg}s) antes del siguiente video...")
                await asyncio.sleep(self._pausa_seg)

        self._log("OK", f"Lote finalizado: {completados}/{total} videos completados con éxito ({fallidos} fallidos).")
        return fallidos == 0


def main():
    parser = argparse.ArgumentParser(description="Orquestador de Publicación en Lote para Telegram HD")
    parser.add_argument("--canal", type=str, default="", help="Canal de Telegram objetivo (@canal)")
    parser.add_argument("--modo-browser", type=str, default="visible", choices=["visible", "headless"])
    parser.add_argument("--modo-video", type=str, default="completo", choices=["completo", "clips"])
    parser.add_argument("--ids", nargs="*", default=None, help="Lista opcional de IDs de videos")
    parser.add_argument("--pausa", type=int, default=5, help="Pausa en segundos entre videos")
    parser.add_argument("--forzar", action="store_true", help="Ignorar historial previo y forzar subida total")
    args = parser.parse_args()

    orq = OrquestadorPublicacionLotes(
        canal=args.canal,
        modo_browser=args.modo_browser,
        modo_video=args.modo_video,
        pausa_seg=args.pausa,
        forzar=args.forzar,
    )
    exito = asyncio.run(orq.ejecutar_lote(ids_filtro=args.ids))
    sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
