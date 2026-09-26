"""
================================================================================
MÓDULO: fase1_extraccion/padre_control_de_estados_txt.py
JERARQUÍA: Padre  (Lógica de negocio — E/S de archivos de persistencia)
PROYECTO: FaceDPeli
DESCRIPCIÓN: Administra de forma atómica toda la lectura y escritura en los
             archivos de texto plano (datos_persistencia/*.txt). Garantiza
             la estrategia Zero-RAM: ningún enlace se guarda en variables
             globales de Python, todo se persiste directamente en disco (ROM).
             Si un archivo de persistencia no existe, este módulo lo crea.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


class PadreControlDeEstadosTXT:
    """
    Encapsula todas las operaciones de E/S en disco para mantener la
    persistencia del estado del sistema sin consumir memoria RAM.

    Archivos gestionados (definidos en config/parametros_globales.json):
        - historial_global_enlaces.txt : Anti-duplicados histórico.
        - cola_pendientes.txt          : URLs en espera de descarga (FIFO).
        - enlaces_completados.txt      : URLs descargadas con éxito.
        - registro_errores.txt         : Log auditado de fallos.
        - estado_publicaciones.txt     : Control de publicaciones por red.
    """

    CODIFICACION: str = "utf-8"

    def __init__(self, ruta_config: str = "config/parametros_globales.json") -> None:
        """
        Carga la configuración global y resuelve las rutas absolutas
        de todos los archivos de persistencia.

        Args:
            ruta_config: Ruta relativa al archivo de parámetros globales.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._config = self._cargar_configuracion(ruta_config)
        rutas = self._config.get("persistencia", {})

        self.ruta_historial: Path = self._ruta_base / rutas.get(
            "historial_global", "datos_persistencia/historial_global_enlaces.txt"
        )
        self.ruta_pendientes: Path = self._ruta_base / rutas.get(
            "cola_pendientes", "datos_persistencia/cola_pendientes.txt"
        )
        self.ruta_completados: Path = self._ruta_base / rutas.get(
            "enlaces_completados", "datos_persistencia/enlaces_completados.txt"
        )
        self.ruta_errores: Path = self._ruta_base / rutas.get(
            "registro_errores", "datos_persistencia/registro_errores.txt"
        )
        self.ruta_publicaciones: Path = self._ruta_base / rutas.get(
            "estado_publicaciones", "datos_persistencia/estado_publicaciones.txt"
        )

    # ------------------------------------------------------------------
    # INICIALIZACIÓN
    # ------------------------------------------------------------------

    def inicializar_archivos_si_no_existen(self) -> None:
        """
        Verifica la existencia de todos los archivos de persistencia y
        crea los directorios y archivos faltantes con contenido vacío.
        No sobreescribe archivos existentes.
        """
        archivos = [
            self.ruta_historial,
            self.ruta_pendientes,
            self.ruta_completados,
            self.ruta_errores,
            self.ruta_publicaciones,
        ]
        for ruta_archivo in archivos:
            ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
            if not ruta_archivo.exists():
                ruta_archivo.touch(exist_ok=True)
                print(f"[INIT] Archivo creado: {ruta_archivo.name}")
            else:
                print(f"[INIT] Archivo verificado: {ruta_archivo.name}")

    # ------------------------------------------------------------------
    # HISTORIAL GLOBAL (Anti-duplicados persistente)
    # ------------------------------------------------------------------

    def existe_en_historial_global(self, url: str) -> bool:
        """
        Busca una URL en el historial global línea a línea sin cargar
        el archivo completo en RAM (complejidad O(n) en disco, O(1) en RAM).

        Args:
            url: URL normalizada a buscar.

        Returns:
            True si la URL ya existe en el historial, False si es nueva.
        """
        if not self.ruta_historial.exists():
            return False
        with open(self.ruta_historial, "r", encoding=self.CODIFICACION) as archivo:
            for linea in archivo:
                if linea.strip() == url.strip():
                    return True
        return False

    def agregar_a_historial_global(self, url: str) -> bool:
        """
        Agrega una URL nueva al final del historial global (append-only).

        Args:
            url: URL normalizada a registrar.

        Returns:
            True si se registró exitosamente.
        """
        try:
            with open(self.ruta_historial, "a", encoding=self.CODIFICACION) as archivo:
                archivo.write(url.strip() + "\n")
            return True
        except OSError as error:
            self._log_error_interno("agregar_a_historial_global", str(error))
            return False

    # ------------------------------------------------------------------
    # COLA DE PENDIENTES (FIFO de descarga)
    # ------------------------------------------------------------------

    def agregar_a_cola_pendientes(self, url: str) -> bool:
        """
        Escribe una URL al final de cola_pendientes.txt (append).

        Args:
            url: URL normalizada y verificada como nueva.

        Returns:
            True si se agregó exitosamente.
        """
        try:
            with open(self.ruta_pendientes, "a", encoding=self.CODIFICACION) as archivo:
                archivo.write(url.strip() + "\n")
            return True
        except OSError as error:
            self._log_error_interno("agregar_a_cola_pendientes", str(error))
            return False

    def obtener_siguiente_pendiente(self) -> Optional[str]:
        """
        Lee y retorna la primera URL de cola_pendientes.txt sin eliminarla.
        El borrado ocurre sólo tras confirmación de descarga exitosa o fallo.

        Returns:
            Primera URL de la cola, o None si la cola está vacía.
        """
        if not self.ruta_pendientes.exists():
            return None
        with open(self.ruta_pendientes, "r", encoding=self.CODIFICACION) as archivo:
            for linea in archivo:
                if linea.strip():
                    return linea.strip()
        return None

    def remover_de_cola_pendientes(self, url: str) -> bool:
        """
        Elimina una URL específica de cola_pendientes.txt reescribiendo
        el archivo sin la línea objetivo.

        Args:
            url: URL a eliminar de la cola.

        Returns:
            True si se removió exitosamente.
        """
        if not self.ruta_pendientes.exists():
            return False
        try:
            with open(self.ruta_pendientes, "r", encoding=self.CODIFICACION) as archivo:
                lineas = archivo.readlines()
            lineas_filtradas = [l for l in lineas if l.strip() != url.strip()]
            with open(self.ruta_pendientes, "w", encoding=self.CODIFICACION) as archivo:
                archivo.writelines(lineas_filtradas)
            return True
        except OSError as error:
            self._log_error_interno("remover_de_cola_pendientes", str(error))
            return False

    def cola_pendientes_esta_vacia(self) -> bool:
        """Retorna True si no hay URLs pendientes en la cola."""
        if not self.ruta_pendientes.exists():
            return True
        with open(self.ruta_pendientes, "r", encoding=self.CODIFICACION) as archivo:
            for linea in archivo:
                if linea.strip():
                    return False
        return True

    # ------------------------------------------------------------------
    # ENLACES COMPLETADOS
    # ------------------------------------------------------------------

    def existe_en_enlaces_completados(self, url: str) -> bool:
        """
        Verifica si la URL ya está registrada en enlaces_completados.txt.

        Args:
            url: URL a consultar.

        Returns:
            True si la URL ya fue completada exitosamente.
        """
        if not self.ruta_completados.exists():
            return False
        url_target = url.strip()
        try:
            with open(self.ruta_completados, "r", encoding=self.CODIFICACION) as archivo:
                for linea in archivo:
                    if url_target in linea:
                        return True
        except OSError:
            pass
        return False

    def registrar_completado(self, id_video: str, url: str) -> None:
        """
        Agrega una entrada al log de URLs procesadas exitosamente.
        Formato: ID_VIDEO | URL | YYYY-MM-DD HH:MM:SS

        Args:
            id_video: Identificador único del video descargado.
            url:      URL original de la fuente.
        """
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = f"{id_video} | {url} | {estampa}\n"
        with open(self.ruta_completados, "a", encoding=self.CODIFICACION) as archivo:
            archivo.write(linea)

    # ------------------------------------------------------------------
    # REGISTRO DE ERRORES
    # ------------------------------------------------------------------

    def registrar_error(self, url: str, modulo: str, codigo: str, detalle: str) -> None:
        """
        Escribe una entrada formateada en registro_errores.txt.
        Formato: [YYYY-MM-DD HH:MM:SS] | MODULO | URL | CODIGO | DETALLE

        Args:
            url:     URL que generó el error.
            modulo:  Nombre del módulo donde ocurrió el fallo.
            codigo:  Código corto del error (ej: '404_NOT_FOUND').
            detalle: Mensaje de error legible o traceback resumido.
        """
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = f"[{estampa}] | {modulo} | {url} | {codigo} | {detalle}\n"
        with open(self.ruta_errores, "a", encoding=self.CODIFICACION) as archivo:
            archivo.write(linea)

    # ------------------------------------------------------------------
    # UTILIDADES INTERNAS
    # ------------------------------------------------------------------

    def _cargar_configuracion(self, ruta_relativa: str) -> dict:
        """
        Carga el archivo parametros_globales.json relativo a la raíz del proyecto.

        Args:
            ruta_relativa: Ruta relativa desde la raíz del proyecto.

        Returns:
            Diccionario con la configuración global, o dict vacío si hay error.
        """
        ruta_abs = self._ruta_base / ruta_relativa
        if not ruta_abs.exists():
            print(f"[ADVERTENCIA] No se encontró configuración en: {ruta_abs}")
            return {}
        with open(ruta_abs, "r", encoding=self.CODIFICACION) as archivo:
            return json.load(archivo)

    def _log_error_interno(self, metodo: str, mensaje: str) -> None:
        """Registro de errores internos del propio módulo padre (fallback a consola)."""
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[ERROR INTERNO {estampa}] PadreControlDeEstadosTXT.{metodo}: {mensaje}")
