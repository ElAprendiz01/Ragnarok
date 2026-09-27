"""
================================================================================
MÓDULO: fase3_publicacion/gestor_memoria_publicaciones.py
JERARQUÍA: Gestor de Persistencia Unificada (Manual y Lote)
PROYECTO: Ragnarok
DESCRIPCIÓN: Registra y audita qué videos han sido subidos exitosamente a cada
             plataforma (Telegram, YouTube, TikTok, Facebook, Instagram),
             ya sea de forma individual/manual o por lotes.
             Evita duplicados al ejecutar 'Subir Todo' ignorando los ya subidos.
LÍNEAS: < 220 (Regla de Responsabilidad Única)
================================================================================
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set, Optional, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = Path(__file__).parent.parent.resolve()


class GestorMemoriaPublicaciones:
    """
    Gestiona la memoria persistente unificada de videos publicados.
    Sincroniza tanto publicaciones manuales (individuales) como por lote.
    """

    NOMBRE_ARCHIVO_MEMORIA: str = "memoria_publicaciones.json"

    def __init__(self, ruta_base: Optional[Path] = None) -> None:
        self._base = ruta_base or RAIZ
        self._dir_persistencia = self._base / "datos_persistencia"
        self._ruta_memoria = self._dir_persistencia / self.NOMBRE_ARCHIVO_MEMORIA
        self._ruta_cola_tg = self._dir_persistencia / "cola_publicacion_telegram.json"
        self._ruta_estado_txt = self._dir_persistencia / "estado_publicaciones.txt"
        self._dir_persistencia.mkdir(parents=True, exist_ok=True)
        self._sincronizar_historial_existente()

    def _cargar_memoria(self) -> Dict[str, Any]:
        """Carga el diccionario de memoria desde disco de forma segura."""
        if not self._ruta_memoria.exists():
            return {}
        try:
            with open(self._ruta_memoria, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _guardar_memoria(self, datos: Dict[str, Any]) -> None:
        """Guarda la memoria en disco en formato JSON legible y atómico."""
        temp_file = self._ruta_memoria.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            temp_file.replace(self._ruta_memoria)
        except OSError:
            try:
                with open(self._ruta_memoria, "w", encoding="utf-8") as f:
                    json.dump(datos, f, indent=2, ensure_ascii=False)
            except OSError:
                pass

    def registrar_publicacion(
        self,
        id_video: str,
        plataforma: str = "telegram",
        origen: str = "manual",
        canal: str = "",
        modo: str = "completo",
        titulo: str = "",
        ruta_video: str = "",
    ) -> None:
        """
        Registra un video como publicado exitosamente (manual o lote).
        Sincroniza la memoria y la cola de Telegram si existe.
        """
        if not id_video:
            return

        id_clean = str(id_video).strip()
        plat_clean = str(plataforma).strip().lower()
        memoria = self._cargar_memoria()

        if id_clean not in memoria:
            memoria[id_clean] = {
                "id_video": id_clean,
                "titulo": titulo or id_clean,
                "publicaciones": {},
            }
        elif titulo and not memoria[id_clean].get("titulo"):
            memoria[id_clean]["titulo"] = titulo

        ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        registro_plat = {
            "estado": "COMPLETADO",
            "plataforma": plat_clean,
            "origen": origen,  # "manual" o "lote"
            "canal": canal,
            "modo": modo,
            "ruta_video": ruta_video,
            "fecha": ahora_str,
        }
        memoria[id_clean]["publicaciones"][plat_clean] = registro_plat
        memoria[id_clean]["ultimo_cambio"] = ahora_str
        self._guardar_memoria(memoria)

        # Sincronizar cola de Telegram en disco si aplica
        if plat_clean == "telegram":
            self._sincronizar_con_cola_telegram(id_clean, "COMPLETADO")

    def esta_publicado(self, id_video: str, plataforma: str = "telegram") -> bool:
        """Verifica si un video ya fue publicado en una plataforma dada."""
        id_clean = str(id_video).strip()
        plat_clean = str(plataforma).strip().lower()
        ids_publicados = self.obtener_ids_publicados(plataforma=plat_clean)
        return id_clean in ids_publicados

    def obtener_ids_publicados(self, plataforma: str = "telegram") -> Set[str]:
        """
        Retorna el conjunto consolidado de IDs publicados en la plataforma.
        Consulta memoria_publicaciones.json, estado_publicaciones.txt y cola_publicacion_telegram.json.
        """
        plat_clean = str(plataforma).strip().lower()
        completados: Set[str] = set()

        # 1. Fuente principal: memoria_publicaciones.json
        memoria = self._cargar_memoria()
        for id_vid, info in memoria.items():
            pubs = info.get("publicaciones", {})
            reg = pubs.get(plat_clean)
            if reg and reg.get("estado") == "COMPLETADO":
                completados.add(id_vid)

        # 2. Respaldo secundario: cola_publicacion_telegram.json (si aplica a telegram)
        if plat_clean == "telegram" and self._ruta_cola_tg.exists():
            try:
                with open(self._ruta_cola_tg, "r", encoding="utf-8") as f:
                    cola_data = json.load(f)
                    for item in cola_data.get("elementos", []):
                        if item.get("estado") == "COMPLETADO" and item.get("id_video"):
                            completados.add(item["id_video"])
            except Exception:
                pass

        # 3. Respaldo terciario: estado_publicaciones.txt
        if self._ruta_estado_txt.exists():
            try:
                with open(self._ruta_estado_txt, "r", encoding="utf-8", errors="replace") as f:
                    for linea in f:
                        partes = [p.strip() for p in linea.split("|")]
                        if len(partes) >= 3:
                            clip_id, plat_l, estado_l = partes[0], partes[1].lower(), partes[2].upper()
                            if plat_l == plat_clean and estado_l == "OK":
                                id_raiz = clip_id.split("_")[0]
                                if id_raiz:
                                    completados.add(id_raiz)
            except Exception:
                pass

        return completados

    def _sincronizar_historial_existente(self) -> None:
        """Puebla memoria_publicaciones.json con registros históricos previos si aún no existen."""
        if self._ruta_memoria.exists() and self._ruta_memoria.stat().st_size > 5:
            return

        memoria = {}
        # Importar desde cola de telegram si existe
        if self._ruta_cola_tg.exists():
            try:
                with open(self._ruta_cola_tg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    canal = data.get("canal", "")
                    for el in data.get("elementos", []):
                        if el.get("estado") == "COMPLETADO":
                            id_v = el.get("id_video")
                            if id_v:
                                memoria[id_v] = {
                                    "id_video": id_v,
                                    "titulo": el.get("titulo", id_v),
                                    "publicaciones": {
                                        "telegram": {
                                            "estado": "COMPLETADO",
                                            "plataforma": "telegram",
                                            "origen": "lote",
                                            "canal": canal,
                                            "modo": data.get("modo_video", "completo"),
                                            "ruta_video": el.get("ruta_video", ""),
                                            "fecha": data.get("actualizado_en", ""),
                                        }
                                    },
                                    "ultimo_cambio": data.get("actualizado_en", ""),
                                }
            except Exception:
                pass

        if memoria:
            self._guardar_memoria(memoria)

    def _sincronizar_con_cola_telegram(self, id_video: str, nuevo_estado: str = "COMPLETADO") -> None:
        """Actualiza el estado de un video en cola_publicacion_telegram.json."""
        if not self._ruta_cola_tg.exists():
            return
        try:
            with open(self._ruta_cola_tg, "r", encoding="utf-8") as f:
                cola = json.load(f)
            cambiado = False
            for item in cola.get("elementos", []):
                if item.get("id_video") == id_video:
                    item["estado"] = nuevo_estado
                    cambiado = True
            if cambiado:
                cola["completados"] = sum(1 for e in cola.get("elementos", []) if e.get("estado") == "COMPLETADO")
                cola["fallidos"] = sum(1 for e in cola.get("elementos", []) if e.get("estado") == "ERROR")
                cola["actualizado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self._ruta_cola_tg, "w", encoding="utf-8") as f:
                    json.dump(cola, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def eliminar_registro(self, id_video: str) -> None:
        """Elimina el registro de un video si fue purgado físicamente de disco."""
        memoria = self._cargar_memoria()
        if id_video in memoria:
            del memoria[id_video]
            self._guardar_memoria(memoria)

    def limpiar_memoria(self) -> None:
        """Reinicia la memoria unificada de publicaciones."""
        if self._ruta_memoria.exists():
            try:
                self._ruta_memoria.unlink()
            except OSError:
                pass
