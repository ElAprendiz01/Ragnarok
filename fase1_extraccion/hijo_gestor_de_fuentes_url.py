"""
================================================================================
MÓDULO: fase1_extraccion/hijo_gestor_de_fuentes_url.py
JERARQUÍA: Hijo  (Lógica de negocio — clasificación y validación de fuentes)
PROYECTO: Ragnarok
DESCRIPCIÓN: Clasifica, valida y normaliza cualquier URL de Facebook que el
             usuario configure como fuente de videos. Soporta los 6 tipos de
             fuente que Facebook ofrece: Watch global, página, grupo, perfil,
             reel y URL directa de video. Genera la URL de entrada correcta
             para el gestor de scroll según el tipo detectado, y lee/escribe
             la lista de fuentes desde datos_persistencia/fuentes_url.txt.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs


# ─────────────────────────────────────────────────────────
# TIPOS DE FUENTE SOPORTADOS
# ─────────────────────────────────────────────────────────
TIPOS_FUENTE = {
    "watch_global":  "Facebook Watch (feed global de videos)",
    "pagina_videos": "Página de Facebook — sección Videos",
    "grupo_videos":  "Grupo de Facebook — sección Videos",
    "perfil_videos": "Perfil de usuario — sección Videos",
    "reel":          "Reel individual de Facebook",
    "video_directo": "URL directa de video de Facebook",
    "busqueda":      "Búsqueda de videos en Facebook",
    "desconocida":   "URL no reconocida",
}

# Patrones de regex para clasificar URLs de Facebook
PATRONES_CLASIFICACION = [
    ("watch_global",  re.compile(r"facebook\.com/watch/?$")),
    ("grupo_videos",  re.compile(r"facebook\.com/groups/([^/]+)(?:/videos)?")),
    ("pagina_videos", re.compile(r"facebook\.com/([^/]+)/videos")),
    ("perfil_videos", re.compile(r"facebook\.com/profile\.php")),
    ("reel",          re.compile(r"facebook\.com(?:/reel/|/reels/)")),
    ("video_directo", re.compile(r"facebook\.com.*(/videos/|/watch/?\?v=|fb\.watch/)")),
    ("busqueda",      re.compile(r"facebook\.com/search/videos")),
]


class HijoGestorDeFuentesURL:
    """
    Gestiona la lista de fuentes URL de Facebook desde las que se
    extraerán videos. Cada fuente se clasifica automáticamente y se
    le asigna la URL de entrada correcta para el scraper de scroll.
    """

    SEPARADOR = " ||| "

    def __init__(
        self,
        ruta_fuentes: str = "datos_persistencia/fuentes_url.txt",
    ) -> None:
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._ruta_fuentes = self._ruta_base / ruta_fuentes

    # ─────────────────────────────────────────────────────
    # CLASIFICACIÓN DE URLs
    # ─────────────────────────────────────────────────────

    def clasificar_url(self, url: str) -> Dict:
        """
        Detecta el tipo de fuente de una URL de Facebook y construye
        el diccionario de información completo para usarla como fuente.

        Args:
            url: URL de Facebook a clasificar.

        Returns:
            Dict con: url_original, tipo, descripcion, url_scroll, id_grupo/pagina.
        """
        url = url.strip().rstrip("/")
        tipo = "desconocida"
        for nombre_tipo, patron in PATRONES_CLASIFICACION:
            if patron.search(url):
                tipo = nombre_tipo
                break

        return {
            "url_original": url,
            "tipo": tipo,
            "descripcion": TIPOS_FUENTE[tipo],
            "url_scroll": self._construir_url_scroll(url, tipo),
            "activa": True,
            "agregada": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_descargados": 0,
        }

    def _construir_url_scroll(self, url: str, tipo: str) -> str:
        """
        Construye la URL exacta donde el scraper debe empezar el scroll,
        normalizando la URL según el tipo de fuente detectado.

        Args:
            url:  URL original de Facebook.
            tipo: Tipo de fuente clasificado.

        Returns:
            URL normalizada lista para navegar con Playwright.
        """
        if tipo == "watch_global":
            return "https://www.facebook.com/watch/"

        if tipo == "grupo_videos":
            m = re.search(r"facebook\.com/groups/([^/?#]+)", url)
            if m:
                grupo_id = m.group(1)
                return f"https://www.facebook.com/groups/{grupo_id}/videos/"
            return url

        if tipo == "pagina_videos":
            m = re.search(r"facebook\.com/([^/?#]+)/videos", url)
            if m:
                pagina_id = m.group(1)
                return f"https://www.facebook.com/{pagina_id}/videos/"
            return url

        if tipo == "perfil_videos":
            m = re.search(r"id=(\d+)", url)
            if m:
                return f"https://www.facebook.com/profile.php?id={m.group(1)}&sk=videos"
            return url

        if tipo == "busqueda":
            return "https://www.facebook.com/search/videos/?q=pelicula+completa"

        # Para reel, video_directo y desconocida: usar la URL tal cual
        return url

    # ─────────────────────────────────────────────────────
    # PERSISTENCIA EN ARCHIVO
    # ─────────────────────────────────────────────────────

    def agregar_fuente(self, url: str) -> Dict:
        """
        Clasifica la URL, la guarda en fuentes_url.txt y retorna
        el diccionario de la fuente para mostrar en la UI.

        Args:
            url: URL de Facebook a agregar como fuente.

        Returns:
            Diccionario de la fuente recién agregada.
        """
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        info = self.clasificar_url(url)
        # Verificar duplicados
        existentes = self.listar_fuentes()
        for f in existentes:
            if f["url_original"] == info["url_original"]:
                print(f"[FUENTES] URL ya existe: {url}")
                return info

        linea = (
            f"{info['url_original']}{self.SEPARADOR}"
            f"{info['tipo']}{self.SEPARADOR}"
            f"{info['url_scroll']}{self.SEPARADOR}"
            f"{info['activa']}{self.SEPARADOR}"
            f"{info['agregada']}\n"
        )
        self._ruta_fuentes.parent.mkdir(parents=True, exist_ok=True)
        with open(self._ruta_fuentes, "a", encoding="utf-8") as f:
            f.write(linea)
        print(f"[FUENTES] Nueva fuente agregada: {info['tipo']} → {url}")
        return info

    def listar_fuentes(self) -> List[Dict]:
        """
        Lee todas las fuentes desde fuentes_url.txt y las retorna
        como lista de diccionarios.

        Returns:
            Lista de fuentes con su información completa.
        """
        fuentes: List[Dict] = []
        if not self._ruta_fuentes.exists():
            return fuentes
        with open(self._ruta_fuentes, "r", encoding="utf-8") as f:
            for linea in f:
                partes = linea.strip().split(self.SEPARADOR)
                if len(partes) >= 5:
                    fuentes.append({
                        "url_original": partes[0],
                        "tipo": partes[1],
                        "descripcion": TIPOS_FUENTE.get(partes[1], "Tipo desconocido"),
                        "url_scroll": partes[2],
                        "activa": partes[3].lower() == "true",
                        "agregada": partes[4],
                        "total_descargados": 0,
                    })
        return fuentes

    def listar_fuentes_activas(self) -> List[str]:
        """
        Retorna sólo las URLs de scroll de las fuentes marcadas como activas.

        Returns:
            Lista de URLs listas para usar con el gestor de scroll.
        """
        return [f["url_scroll"] for f in self.listar_fuentes() if f["activa"]]

    def conmutar_estado_fuente(self, url_original: str, activa: Optional[bool] = None) -> bool:
        """
        Alterna o establece explícitamente el estado activa (True/False) de una fuente en fuentes_url.txt.

        Args:
            url_original: URL original de la fuente a actualizar.
            activa: Si es None, invierte el estado actual. Si es bool, establece ese estado.

        Returns:
            True si la fuente fue encontrada y actualizada.
        """
        if not self._ruta_fuentes.exists():
            return False
        lineas = self._ruta_fuentes.read_text(encoding="utf-8").splitlines()
        nuevas_lineas = []
        encontrada = False
        for linea in lineas:
            partes = linea.strip().split(self.SEPARADOR)
            if len(partes) >= 5 and partes[0] == url_original.strip():
                estado_actual = partes[3].lower() == "true"
                nuevo_estado = (not estado_actual) if activa is None else bool(activa)
                partes[3] = str(nuevo_estado)
                linea = self.SEPARADOR.join(partes)
                encontrada = True
            nuevas_lineas.append(linea)
        if encontrada:
            self._ruta_fuentes.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")
        return encontrada

    def desactivar_fuente(self, url_original: str) -> bool:
        """
        Marca una fuente como inactiva en el archivo sin eliminarla.

        Args:
            url_original: URL original de la fuente a desactivar.

        Returns:
            True si la fuente fue encontrada y desactivada.
        """
        return self.conmutar_estado_fuente(url_original, activa=False)

    def eliminar_fuente(self, url_original: str) -> bool:
        """
        Elimina permanentemente una fuente del archivo.

        Args:
            url_original: URL original de la fuente a eliminar.

        Returns:
            True si la fuente fue eliminada.
        """
        if not self._ruta_fuentes.exists():
            return False
        lineas = self._ruta_fuentes.read_text(encoding="utf-8").splitlines()
        nuevas = [l for l in lineas if url_original not in l]
        self._ruta_fuentes.write_text("\n".join(nuevas) + "\n", encoding="utf-8")
        return len(nuevas) < len(lineas)

    # ─────────────────────────────────────────────────────
    # VALIDACIÓN
    # ─────────────────────────────────────────────────────

    def es_url_facebook_valida(self, url: str) -> bool:
        """
        Verifica que la URL pertenezca al dominio de Facebook.

        Args:
            url: URL a validar.

        Returns:
            True si la URL es de Facebook (facebook.com o fb.watch).
        """
        try:
            url_limpia = url.strip()
            if not url_limpia.startswith("http://") and not url_limpia.startswith("https://"):
                url_limpia = "https://" + url_limpia
            parsed = urlparse(url_limpia)
            return any(dom in parsed.netloc for dom in ("facebook.com", "fb.watch"))
        except Exception:
            return False
