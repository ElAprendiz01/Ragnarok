"""
================================================================================
MÓDULO: fase3_publicacion/abuelo_gestor_plataformas_multiplex.py
JERARQUÍA: Abuelo  (Gestión de instancias complejas — Browser Contexts aislados)
PROYECTO: Ragnarok
DESCRIPCIÓN: Administra sesiones de navegador completamente aisladas e
             independientes (Playwright BrowserContexts) para cada red social.
             Garantiza que las cookies de TikTok no contaminen las de YouTube,
             ni las de Facebook las de Instagram. Cada plataforma opera en su
             propio contexto con su perfil de cookies y agente de usuario.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import json
from pathlib import Path
from typing import Optional, Dict

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Playwright,
)


UA_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

# Configuración de cada plataforma: URL base de autenticación y User-Agent óptimo
CONFIGURACION_PLATAFORMAS: Dict[str, Dict] = {
    "youtube": {"url_base": "https://studio.youtube.com", "nombre_cookies": "cookies_youtube.json", "user_agent": UA_DEFAULT},
    "tiktok": {"url_base": "https://www.tiktok.com/creator-center/upload", "nombre_cookies": "cookies_tiktok.json", "user_agent": UA_DEFAULT},
    "facebook": {"url_base": "https://www.facebook.com", "nombre_cookies": "cookies_facebook.json", "user_agent": UA_DEFAULT},
    "instagram": {"url_base": "https://www.instagram.com", "nombre_cookies": "cookies_instagram.json", "user_agent": UA_DEFAULT},
    "telegram": {"url_base": "https://web.telegram.org/a/", "nombre_cookies": "cookies_telegram.json", "user_agent": UA_DEFAULT},
}

ARGUMENTOS_ANTIBLOQUEO_CHROMIUM = [
    "--start-maximized", "--window-size=1920,1080",
    "--disable-blink-features=AutomationControlled", "--no-sandbox",
    "--disable-setuid-sandbox", "--disable-infobars", "--disable-dev-shm-usage",
    "--disable-gpu", "--disable-gpu-shader-disk-cache",
    "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding", "--disable-background-networking",
    "--disable-sync", "--disable-translate", "--no-first-run", "--no-service-autorun",
    "--password-store=basic", "--use-gl=swiftshader", "--ignore-certificate-errors",
    "--allow-running-insecure-content", "--lang=es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
]

SCRIPT_STEALTH_ANTIDETECCION = """
// Ocultar navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['es-MX', 'es', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, [parameter]);
    };
} catch(e) {}
"""


class AbueloGestorPlataformasMultiplex:
    """
    Gestiona la creación, reutilización y cierre de BrowserContexts aislados
    para cada plataforma de publicación. Mantiene un diccionario de contextos
    activos para evitar reabrir el navegador innecesariamente entre clips.
    """

    def __init__(
        self,
        dir_config: str = "config",
        headless: bool = True,
    ) -> None:
        """
        Inicializa el gestor multiplex.

        Args:
            dir_config: Directorio donde se almacenan los archivos de cookies.
            headless:   Si True, el navegador no muestra ventana gráfica.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._dir_config = self._ruta_base / dir_config
        self._headless = headless

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contextos_activos: Dict[str, BrowserContext] = {}

    # ------------------------------------------------------------------
    # INICIALIZACIÓN DEL NAVEGADOR
    # ------------------------------------------------------------------

    async def inicializar(self) -> None:
        """
        Lanza Playwright y el navegador Chromium compartido con banderas antibloqueo.
        """
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=ARGUMENTOS_ANTIBLOQUEO_CHROMIUM,
            ignore_default_args=["--enable-automation"],
        )
        print("[MULTIPLEX] Navegador Chromium iniciado con banderas anti-detección.")

    async def cerrar_todo(self) -> None:
        """
        Cierra todos los contextos activos, el navegador y detiene Playwright.
        """
        for nombre_plataforma, contexto in self._contextos_activos.items():
            await contexto.close()
            print(f"[MULTIPLEX] Contexto cerrado: {nombre_plataforma}")
        self._contextos_activos.clear()

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("[MULTIPLEX] Todos los recursos de navegador liberados.")

    # ------------------------------------------------------------------
    # OBTENCIÓN DE CONTEXTOS POR PLATAFORMA
    # ------------------------------------------------------------------

    async def obtener_contexto_youtube(self) -> BrowserContext:
        """Retorna el BrowserContext aislado para YouTube."""
        return await self._obtener_o_crear_contexto("youtube")

    async def obtener_contexto_tiktok(self) -> BrowserContext:
        """Retorna el BrowserContext aislado para TikTok."""
        return await self._obtener_o_crear_contexto("tiktok")

    async def obtener_contexto_facebook(self) -> BrowserContext:
        """Retorna el BrowserContext aislado para Facebook."""
        return await self._obtener_o_crear_contexto("facebook")

    async def obtener_contexto_instagram(self) -> BrowserContext:
        """Retorna el BrowserContext aislado para Instagram."""
        return await self._obtener_o_crear_contexto("instagram")

    async def obtener_contexto_telegram(self) -> BrowserContext:
        """Retorna el BrowserContext aislado para Telegram."""
        return await self._obtener_o_crear_contexto("telegram")

    async def _obtener_o_crear_contexto(self, plataforma: str) -> BrowserContext:
        """
        Retorna el contexto existente para la plataforma o crea uno nuevo
        con las cookies correspondientes inyectadas y parches anti-bot.
        """
        if plataforma in self._contextos_activos:
            return self._contextos_activos[plataforma]

        config = CONFIGURACION_PLATAFORMAS.get(plataforma, {})
        dir_perfil_telegram = self._ruta_base / "datos_persistencia" / "perfil_telegram"

        if plataforma == "telegram" and dir_perfil_telegram.exists():
            print("[MULTIPLEX] Cargando perfil persistente optimizado para Telegram Web A (user_data_dir)...")
            contexto = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(dir_perfil_telegram),
                headless=self._headless,
                no_viewport=True if not self._headless else False,
                viewport={"width": 1440, "height": 900} if self._headless else None,
                user_agent=config.get("user_agent", ""),
                locale="es-MX",
                args=ARGUMENTOS_ANTIBLOQUEO_CHROMIUM,
                ignore_default_args=["--enable-automation"],
            )
            await contexto.add_init_script(SCRIPT_STEALTH_ANTIDETECCION)
            self._contextos_activos[plataforma] = contexto
            return contexto

        contexto = await self._browser.new_context(
            viewport=None,
            user_agent=config.get("user_agent", ""),
            locale="es-MX",
        )
        await contexto.add_init_script(SCRIPT_STEALTH_ANTIDETECCION)

        # Inyectar cookies de sesión de la plataforma
        ruta_cookies = self._dir_config / config.get("nombre_cookies", "")
        await self._inyectar_cookies_en_contexto(contexto, ruta_cookies, plataforma)

        self._contextos_activos[plataforma] = contexto
        print(f"[MULTIPLEX] Contexto aislado anti-detección creado para: {plataforma}")
        return contexto

    def _sanitizar_cookie_playwright(self, c: dict, plataforma: str) -> Optional[dict]:
        """Sanitiza una cookie para asegurar compatibilidad total con Playwright."""
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            return None
        cookie = {
            "name": str(c["name"]),
            "value": str(c["value"]),
        }
        if "domain" in c and c["domain"]:
            cookie["domain"] = str(c["domain"])
        else:
            doms = {"youtube": ".youtube.com", "tiktok": ".tiktok.com", "facebook": ".facebook.com", "instagram": ".instagram.com", "telegram": ".telegram.org"}
            cookie["domain"] = doms.get(plataforma, ".telegram.org")

        if "path" in c and c["path"]:
            cookie["path"] = str(c["path"])
        else:
            cookie["path"] = "/"

        if "secure" in c and c["secure"] is not None:
            cookie["secure"] = bool(c["secure"])
        if "httpOnly" in c and c["httpOnly"] is not None:
            cookie["httpOnly"] = bool(c["httpOnly"])

        if "expires" in c and c["expires"] is not None:
            try:
                cookie["expires"] = float(c["expires"])
            except (ValueError, TypeError):
                pass

        if "sameSite" in c and c["sameSite"] is not None:
            val = str(c["sameSite"]).lower()
            if val in ("strict", "lax", "none"):
                cookie["sameSite"] = val.capitalize()
            elif val == "no_restriction":
                cookie["sameSite"] = "None"

        return cookie

    async def _inyectar_cookies_en_contexto(
        self, contexto: BrowserContext, ruta_cookies: Path, plataforma: str
    ) -> None:
        """
        Carga, sanitiza e inyecta las cookies de sesión en el contexto de la plataforma.

        Args:
            contexto:       BrowserContext donde inyectar las cookies.
            ruta_cookies:   Ruta al archivo JSON de cookies.
            plataforma:     Nombre de la plataforma (para logs).
        """
        if not ruta_cookies.exists():
            print(f"[MULTIPLEX] [!] Sin cookies para {plataforma}: {ruta_cookies}")
            return
        with open(ruta_cookies, "r", encoding="utf-8") as archivo:
            cookies_raw = json.load(archivo)
        
        cookies_sanitizadas = []
        for c in cookies_raw:
            c_clean = self._sanitizar_cookie_playwright(c, plataforma)
            if c_clean:
                cookies_sanitizadas.append(c_clean)

        if cookies_sanitizadas:
            await contexto.add_cookies(cookies_sanitizadas)
            print(f"[MULTIPLEX] {len(cookies_sanitizadas)} cookies inyectadas en contexto de {plataforma}.")

    def verificar_estado_autenticacion_cookies(self, plataforma: str) -> Dict:
        """Verifica el estado y validez del archivo de cookies de una plataforma."""
        cfg = CONFIGURACION_PLATAFORMAS.get(plataforma, {})
        if not cfg:
            return {"plataforma": plataforma, "existe": False, "cookies_validas": 0, "estado": "ERROR", "mensaje": "Plataforma no soportada"}

        ruta = self._dir_config / cfg.get("nombre_cookies", "")
        if not ruta.exists():
            return {"plataforma": plataforma, "existe": False, "cookies_validas": 0, "estado": "REQUERIDO", "mensaje": f"Sin archivo {cfg.get('nombre_cookies', '')}"}

        try:
            with open(ruta, "r", encoding="utf-8") as f:
                validas = [c for c in json.load(f) if "name" in c and "value" in c]
            st = "ACTIVO" if validas else "INVALIDO"
            msg = f"{len(validas)} cookies cargadas" if validas else "Sin cookies válidas"
            return {"plataforma": plataforma, "existe": True, "cookies_validas": len(validas), "estado": st, "mensaje": msg}
        except Exception as err:
            return {"plataforma": plataforma, "existe": True, "cookies_validas": 0, "estado": "ERROR", "mensaje": f"Error: {err}"}
