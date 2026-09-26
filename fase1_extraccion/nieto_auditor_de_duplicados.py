"""
================================================================================
MÓDULO: fase1_extraccion/nieto_auditor_de_duplicados.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — filtro y normalización de URLs)
PROYECTO: Ragnarok
DESCRIPCIÓN: Recibe lotes de URLs crudas obtenidas del DOM de Playwright,
             las normaliza al formato canónico de Facebook, elimina duplicados
             internos del lote mediante un set temporal en memoria (O(1) lookup,
             liberado tras cada iteración) y consulta al padre de estados si la
             URL ya existe en el historial global persistido en disco.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import List, Optional

from fase1_extraccion.padre_control_de_estados_txt import PadreControlDeEstadosTXT


class NietoAuditorDeDuplicados:
    """
    Filtra y normaliza lotes de URLs de Facebook para garantizar que sólo
    se encolen URLs únicas y no vistas anteriormente, sin retener datos
    entre iteraciones del bucle de scroll.

    Patrones de URL de Facebook soportados:
        - https://www.facebook.com/watch/?v=1234567890
        - https://www.facebook.com/reel/1234567890
        - https://www.facebook.com/share/v/AbCdEfGh/
        - https://fb.watch/AbCdEfGh/
    """

    # Dominos válidos de Facebook que contienen video
    _DOMINIOS_FACEBOOK = {"www.facebook.com", "facebook.com", "fb.watch", "m.facebook.com"}

    # Patrones para extraer IDs de video de distintos formatos de URL
    _PATRON_WATCH_V = re.compile(r"[?&]v=(\d+)", re.IGNORECASE)
    _PATRON_REEL = re.compile(r"/reel/(\d+)", re.IGNORECASE)
    _PATRON_VIDEOS = re.compile(r"/videos/(\d+)", re.IGNORECASE)
    _PATRON_FBWATCH = re.compile(r"fb\.watch/([A-Za-z0-9_-]+)", re.IGNORECASE)
    _PATRON_SHARE_V = re.compile(r"/share/v/([A-Za-z0-9_-]+)", re.IGNORECASE)

    def __init__(self, gestor_estados: PadreControlDeEstadosTXT) -> None:
        """
        Inicializa el auditor con una referencia al gestor de estados TXT.

        Args:
            gestor_estados: Instancia del padre que gestiona la persistencia en disco.
        """
        self._gestor = gestor_estados

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL: Filtrado de lote
    # ------------------------------------------------------------------

    def filtrar_lote_nuevo(self, lista_urls_crudas: List[str]) -> List[str]:
        """
        Procesa un lote de URLs crudas del DOM y retorna sólo las URLs
        normalizadas que son nuevas (no vistas nunca antes).

        El proceso es:
            1. Normalizar cada URL al formato canónico.
            2. Eliminar duplicados internos del lote con un set temporal.
            3. Filtrar contra el historial global persistido en disco.

        El set temporal se crea y destruye dentro de este método, garantizando
        que no se acumule memoria entre iteraciones del scroll.

        Args:
            lista_urls_crudas: Lista de href strings capturados del DOM.

        Returns:
            Lista de URLs únicas y nuevas listas para encolar en pendientes.
        """
        conjunto_lote_temporal: set = set()
        lista_urls_nuevas: List[str] = []

        for url_cruda in lista_urls_crudas:
            # Paso 1: Normalizar URL
            url_limpia = self.normalizar_url_facebook(url_cruda)
            if url_limpia is None:
                continue

            # Paso 2: Deduplicar dentro del lote actual
            if url_limpia in conjunto_lote_temporal:
                continue
            conjunto_lote_temporal.add(url_limpia)

            # Paso 3: Consultar historial persistido en disco (Zero-RAM lookup)
            if not self._gestor.existe_en_historial_global(url_limpia):
                lista_urls_nuevas.append(url_limpia)

        # Liberar el set temporal explícitamente (ayuda al GC de Python)
        conjunto_lote_temporal.clear()
        del conjunto_lote_temporal

        return lista_urls_nuevas

    # ------------------------------------------------------------------
    # NORMALIZACIÓN DE URL
    # ------------------------------------------------------------------

    def normalizar_url_facebook(self, url_cruda: str) -> Optional[str]:
        """
        Convierte cualquier variante de URL de video de Facebook al formato
        canónico estándar: https://www.facebook.com/watch/?v=ID_NUMERICO
        o https://www.facebook.com/reel/ID_NUMERICO para reels.

        Elimina parámetros de tracking como `fbclid`, `ref`, `__cft__`, etc.

        Args:
            url_cruda: Cadena de texto href capturada del DOM.

        Returns:
            URL canónica si el enlace es un video/reel de Facebook, None en otro caso.
        """
        if not url_cruda or not isinstance(url_cruda, str):
            return None

        url_limpia = url_cruda.strip()

        # Completar URLs relativas a absolutas
        if url_limpia.startswith("/"):
            url_limpia = "https://www.facebook.com" + url_limpia

        # Verificar que pertenece a un dominio de Facebook
        try:
            partes = urlparse(url_limpia)
        except Exception:
            return None

        dominio = partes.netloc.lower().lstrip("www.")
        if partes.netloc.lower() not in self._DOMINIOS_FACEBOOK:
            return None

        # Intentar extraer ID numérico de video (formato watch)
        coincidencia_v = self._PATRON_WATCH_V.search(url_limpia)
        if coincidencia_v:
            id_video = coincidencia_v.group(1)
            return f"https://www.facebook.com/watch/?v={id_video}"

        # Intentar extraer ID de reel
        coincidencia_reel = self._PATRON_REEL.search(url_limpia)
        if coincidencia_reel:
            id_video = coincidencia_reel.group(1)
            return f"https://www.facebook.com/reel/{id_video}"

        # Intentar extraer ID de /videos/
        coincidencia_videos = self._PATRON_VIDEOS.search(url_limpia)
        if coincidencia_videos:
            id_video = coincidencia_videos.group(1)
            return f"https://www.facebook.com/watch/?v={id_video}"

        # Intentar fb.watch (short URL)
        coincidencia_fbwatch = self._PATRON_FBWATCH.search(url_limpia)
        if coincidencia_fbwatch:
            codigo = coincidencia_fbwatch.group(1)
            return f"https://fb.watch/{codigo}/"

        # Intentar /share/v/ (links compartidos de reels)
        coincidencia_share = self._PATRON_SHARE_V.search(url_limpia)
        if coincidencia_share:
            codigo = coincidencia_share.group(1)
            return f"https://www.facebook.com/share/v/{codigo}/"

        # La URL de Facebook no corresponde a un video válido
        return None

    # ------------------------------------------------------------------
    # REGISTRO Y ENCOLADO (coordina con el padre de estados)
    # ------------------------------------------------------------------

    def registrar_y_encolar_urls_nuevas(self, lista_urls_nuevas: List[str]) -> int:
        """
        Registra las URLs nuevas en el historial global y las encola en
        cola_pendientes.txt de manera secuencial.

        Args:
            lista_urls_nuevas: Lista de URLs normalizadas y verificadas como nuevas.

        Returns:
            Número de URLs efectivamente registradas y encoladas.
        """
        contador_encoladas: int = 0
        for url in lista_urls_nuevas:
            exito_historial = self._gestor.agregar_a_historial_global(url)
            exito_cola = self._gestor.agregar_a_cola_pendientes(url)
            if exito_historial and exito_cola:
                contador_encoladas += 1
                print(f"  [+] Nueva URL encolada: {url}")
            else:
                print(f"  [!] Error al encolar: {url}")
        return contador_encoladas
