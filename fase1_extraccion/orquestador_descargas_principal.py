"""
================================================================================
MÓDULO: fase1_extraccion/orquestador_descargas_principal.py
JERARQUÍA: Orquestador  (Punto de entrada de la Fase 1 — Sin lógica interna pesada)
PROYECTO: Ragnarok
DESCRIPCIÓN: Punto de entrada de la Fase 1: Extracción & Descarga. Coordina
             los tres módulos subordinados (padre_control_de_estados_txt,
             nieto_gestor_scroll_dinamico, nieto_auditor_de_duplicados) y
             gestiona el bucle de descarga de videos mediante el binario
             nativo yt-dlp invocado como proceso hijo del sistema operativo.
             No contiene lógica de negocio pesada; delega todo a los módulos
             de nivel inferior.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fase1_extraccion.padre_control_de_estados_txt import PadreControlDeEstadosTXT
from fase1_extraccion.nieto_auditor_de_duplicados import NietoAuditorDeDuplicados
from fase1_extraccion.nieto_gestor_scroll_dinamico import NietoGestorScrollDinamico
from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL


class OrquestadorDescargasPrincipal:
    """
    Coordina el pipeline completo de la Fase 1: Extracción & Descarga.

    Flujo de ejecución:
        1. Inicializa archivos de persistencia.
        2. Obtiene todas las fuentes URL de Facebook activas.
        3. Ejecuta el scraping con scroll en cada fuente y filtra duplicados.
        4. Procesa la cola de pendientes descargando cada video con yt-dlp.
        5. Genera el archivo metadata.json por cada descarga exitosa.
    """

    def __init__(self, ruta_config: str = "config/parametros_globales.json") -> None:
        """
        Carga la configuración global e instancia todos los submódulos.

        Args:
            ruta_config: Ruta relativa al archivo de parámetros globales.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._config = self._cargar_config(ruta_config)
        self._config_extraccion = self._config.get("extraccion", {})
        self._config_rutas = self._config.get("rutas", {})

        # Instanciar submódulos en orden de dependencia
        self._gestor_estados = PadreControlDeEstadosTXT(ruta_config)
        self._auditor = NietoAuditorDeDuplicados(self._gestor_estados)
        self._gestor_fuentes = HijoGestorDeFuentesURL(
            ruta_fuentes=self._config.get("persistencia", {}).get("fuentes_url", "datos_persistencia/fuentes_url.txt")
        )
        self._gestor_scroll = NietoGestorScrollDinamico(
            ruta_cookies=self._config_rutas.get("cookies_facebook", "config/cookies_facebook.json"),
            headless=self._config_extraccion.get("headless", False),
            max_scrolls=self._config_extraccion.get("max_scrolls_por_sesion", 50),
            pausa_min_seg=self._config_extraccion.get("pausa_minima_entre_scrolls_seg", 1.2),
            pausa_max_seg=self._config_extraccion.get("pausa_maxima_entre_scrolls_seg", 3.5),
        )

        self._dir_descargas = self._ruta_base / self._config_rutas.get("directorio_descargas", "descargas")

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL DE EJECUCIÓN
    # ------------------------------------------------------------------

    async def ejecutar_fase(self, solo_descargar: bool = False) -> None:
        """
        Ejecuta el ciclo de vida completo de la Fase 1: inicialización, etapa
        de scraping de fuentes activas (si solo_descargar=False), filtrado y descarga.
        """
        print("\n" + "="*60)
        print("  Ragnarok — FASE 1: EXTRACCIÓN & DESCARGA")
        print("="*60 + "\n")

        # Paso 1: Inicializar persistencia
        print("[ORQ] Inicializando archivos de persistencia...")
        self._gestor_estados.inicializar_archivos_si_no_existen()

        if not solo_descargar:
            # Paso 2: Obtener lista de fuentes activas
            urls_fuentes = self._gestor_fuentes.listar_fuentes_activas()
            url_config = self._config_extraccion.get("url_objetivo_facebook", "")
            if url_config and url_config not in urls_fuentes:
                urls_fuentes.append(url_config)

            if urls_fuentes:
                print(f"[ORQ] {len(urls_fuentes)} fuente(s) activa(s) encontrada(s) para scraping.")
                for idx, url_fuente in enumerate(urls_fuentes, 1):
                    print(f"\n[ORQ] === Fuente {idx}/{len(urls_fuentes)}: {url_fuente} ===")
                    await self._ejecutar_ciclo_scraping(url_fuente)
            else:
                print("[ORQ] No se encontraron fuentes configuradas ni activas. Saltando etapa de scraping.")
        else:
            print("[ORQ] Modo solo-descargar activado. Omitiendo etapa de scraping.")

        # Paso 3: Procesar cola de pendientes
        print("\n[ORQ] Iniciando procesamiento de cola de pendientes...")
        await self._ejecutar_ciclo_descargas()

        print("\n[ORQ] Fase 1 completada.")

    # ------------------------------------------------------------------
    # CICLO DE SCRAPING
    # ------------------------------------------------------------------

    async def _ejecutar_ciclo_scraping(self, url_objetivo: str) -> None:
        """
        Lanza el navegador, extrae URLs del DOM y las filtra y encola.

        Args:
            url_objetivo: URL de la fuente de videos de Facebook.
        """
        try:
            await self._gestor_scroll.inicializar_browser()
            urls_brutas = await self._gestor_scroll.ejecutar_bucle_extraccion(url_objetivo)
            print(f"\n[ORQ] {len(urls_brutas)} URLs brutas capturadas. Filtrando duplicados...")

            # Filtrar y encolar URLs nuevas
            urls_nuevas = self._auditor.filtrar_lote_nuevo(urls_brutas)
            if urls_nuevas:
                encoladas = self._auditor.registrar_y_encolar_urls_nuevas(urls_nuevas)
                print(f"[ORQ] {encoladas} URLs nuevas encoladas en cola_pendientes.txt")
            else:
                print("[ORQ] No se encontraron URLs nuevas en esta sesión.")

        except Exception as error:
            self._gestor_estados.registrar_error(
                url_objetivo, "OrquestadorDescargas._ejecutar_ciclo_scraping",
                "SCRAPING_ERROR", str(error)
            )
            print(f"[ERROR] Fallo durante el scraping: {error}")
        finally:
            await self._gestor_scroll.cerrar()

    # ------------------------------------------------------------------
    # CICLO DE DESCARGA
    # ------------------------------------------------------------------

    async def _ejecutar_ciclo_descargas(self) -> None:
        """
        Lee la cola de pendientes y descarga cada video con yt-dlp hasta
        que la cola esté vacía o se supere el límite de reintentos.
        """
        max_reintentos = self._config_extraccion.get("max_reintentos_descarga", 3)
        pausas_reintento = self._config_extraccion.get("pausa_reintento_seg", [5, 15, 45])

        while not self._gestor_estados.cola_pendientes_esta_vacia():
            url_actual = self._gestor_estados.obtener_siguiente_pendiente()
            if not url_actual:
                break

            print(f"\n[DESCARGA] Procesando: {url_actual}")
            id_video = self._generar_id_video(url_actual)
            dir_destino = self._dir_descargas / id_video
            dir_destino.mkdir(parents=True, exist_ok=True)

            # Candado Anti-Duplicados: Verificar si ya fue completado o existe en disco
            archivos_existentes = [f for f in dir_destino.iterdir() if f.is_file() and f.suffix.lower() in ('.mp4', '.webm', '.mkv') and f.stat().st_size > 0] if dir_destino.exists() else []
            if self._gestor_estados.existe_en_enlaces_completados(url_actual) or archivos_existentes:
                print(f"  [✓] Video ya descargado anteriormente en disco. Omitiendo re-descarga: {id_video}")
                self._gestor_estados.remover_de_cola_pendientes(url_actual)
                self._gestor_estados.registrar_completado(id_video, url_actual)
                continue

            exito = False
            for intento in range(1, max_reintentos + 1):
                print(f"  [DESCARGA] Intento {intento}/{max_reintentos}...")
                exito, info_raw = self._descargar_con_ytdlp(url_actual, str(dir_destino))
                if exito:
                    self._generar_metadata_json(id_video, url_actual, dir_destino, info_raw)
                    self._gestor_estados.remover_de_cola_pendientes(url_actual)
                    self._gestor_estados.registrar_completado(id_video, url_actual)
                    print(f"  [✓] Descarga exitosa: ID {id_video}")
                    pausa_sec = self._config_extraccion.get("pausa_entre_descargas_seg", 2)
                    if pausa_sec > 0:
                        await asyncio.sleep(pausa_sec)
                    break
                else:
                    if intento < max_reintentos:
                        pausa = pausas_reintento[intento - 1] if intento - 1 < len(pausas_reintento) else 60
                        print(f"  [!] Fallo. Reintentando en {pausa}s...")
                        await asyncio.sleep(pausa)

            if not exito:
                self._gestor_estados.registrar_error(
                    url_actual, "OrquestadorDescargas._ejecutar_ciclo_descargas",
                    "DESCARGA_FALLIDA", f"Máximo de {max_reintentos} reintentos agotado."
                )
                self._gestor_estados.remover_de_cola_pendientes(url_actual)
                print(f"  [✗] Descarga fallida tras {max_reintentos} intentos: {url_actual}")

    # ------------------------------------------------------------------
    # DESCARGA VÍA yt-dlp (Proceso hijo del SO — Zero RAM en Python)
    # ------------------------------------------------------------------

    def _descargar_con_ytdlp(self, url: str, dir_destino: str):
        """
        Invoca el binario yt-dlp como proceso hijo mediante subprocess.
        El video NUNCA se carga en la memoria RAM de Python; se escribe
        directamente en disco por el proceso nativo de yt-dlp.

        Args:
            url:         URL del video a descargar.
            dir_destino: Ruta del directorio donde se guardará el MP4.

        Returns:
            Tupla (exito: bool, info_dict: dict con metadata cruda o {}).
        """
        # Primero extraer metadata JSON sin descargar
        cmd_info = [
            "yt-dlp",
            "--skip-download",
            "--dump-json",
            "--no-warnings",
            url
        ]
        try:
            resultado_info = subprocess.run(
                cmd_info, capture_output=True, text=True,
                timeout=30, encoding="utf-8", shell=False
            )
            info_raw = {}
            if resultado_info.returncode == 0 and resultado_info.stdout.strip():
                info_raw = json.loads(resultado_info.stdout.strip())
        except Exception:
            info_raw = {}

        # Luego descargar el video con regulador de ancho de banda y fragmentos
        plantilla_salida = str(Path(dir_destino) / "video_original.%(ext)s")
        cmd_descarga = [
            "yt-dlp",
            "--format", "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--no-warnings",
            "--retries", "10",
            "--fragment-retries", "10",
            "--concurrent-fragments", "1",
            "--output", plantilla_salida,
        ]

        # Si se configuró un límite de velocidad en parametros_globales.json (ej. "5M" o "10M")
        limite_velocidad = self._config_extraccion.get("limite_velocidad_descarga", "")
        if limite_velocidad:
            cmd_descarga.extend(["--limit-rate", str(limite_velocidad)])

        cmd_descarga.append(url)

        try:
            resultado = subprocess.run(
                cmd_descarga, capture_output=True, text=True,
                timeout=600, encoding="utf-8", shell=False
            )
            exito = resultado.returncode == 0
            if not exito:
                print(f"    [yt-dlp ERROR] {resultado.stderr[:300]}")
            return exito, info_raw
        except subprocess.TimeoutExpired:
            print("    [yt-dlp ERROR] Timeout de descarga superado (600s).")
            return False, {}
        except FileNotFoundError:
            print("    [yt-dlp ERROR] Binario 'yt-dlp' no encontrado. Instalar con: pip install yt-dlp")
            return False, {}

    # ------------------------------------------------------------------
    # GENERACIÓN DE METADATA JSON
    # ------------------------------------------------------------------

    def _generar_metadata_json(
        self, id_video: str, url: str, dir_destino: Path, info_raw: dict
    ) -> None:
        """
        Construye y escribe el archivo metadata.json en el directorio del video.

        Args:
            id_video:    ID único del video.
            url:         URL original de la fuente.
            dir_destino: Ruta del directorio del video.
            info_raw:    Diccionario de metadata cruda retornado por yt-dlp.
        """
        ruta_mp4 = dir_destino / "video_original.mp4"
        tamanio_bytes = ruta_mp4.stat().st_size if ruta_mp4.exists() else 0
        resolucion = (
            f"{info_raw.get('width', 0)}x{info_raw.get('height', 0)}"
            if info_raw else "desconocida"
        )
        metadata = {
            "id_video": id_video,
            "url_original": url,
            "titulo_original": info_raw.get("title", "Sin título") if info_raw else "Sin título",
            "descripcion_original": info_raw.get("description", "") if info_raw else "",
            "fecha_extraccion": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duracion_segundos": info_raw.get("duration", 0) if info_raw else 0,
            "resolucion": resolucion,
            "formato": "mp4",
            "codec_video": "h264",
            "codec_audio": "aac",
            "tamanio_bytes": tamanio_bytes,
        }
        ruta_json = dir_destino / "metadata.json"
        with open(ruta_json, "w", encoding="utf-8") as archivo:
            json.dump(metadata, archivo, ensure_ascii=False, indent=2)
        print(f"  [META] metadata.json generado en: {ruta_json}")

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    def _generar_id_video(self, url: str) -> str:
        """
        Genera un ID único y reproducible para cada video usando MD5 de la URL.

        Args:
            url: URL normalizada del video.

        Returns:
            Cadena hexadecimal de 16 caracteres como ID único.
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:16]

    def _cargar_config(self, ruta_relativa: str) -> dict:
        """Carga y retorna el archivo JSON de configuración global."""
        ruta_abs = self._ruta_base / ruta_relativa
        if not ruta_abs.exists():
            print(f"[ADVERTENCIA] Configuración no encontrada: {ruta_abs}")
            return {}
        with open(ruta_abs, "r", encoding="utf-8") as archivo:
            return json.load(archivo)


# ------------------------------------------------------------------
# PUNTO DE ENTRADA DIRECTO
# ------------------------------------------------------------------

if __name__ == "__main__":
    orquestador = OrquestadorDescargasPrincipal()
    asyncio.run(orquestador.ejecutar_fase_1())
