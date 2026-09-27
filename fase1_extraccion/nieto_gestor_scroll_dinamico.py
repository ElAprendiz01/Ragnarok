"""
================================================================================
MÓDULO: fase1_extraccion/nieto_gestor_scroll_dinamico.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — control de navegador Playwright)
PROYECTO: Ragnarok
DESCRIPCIÓN: Gestiona el ciclo de vida completo del navegador Chromium mediante
             la API asíncrona de Playwright. Implementa:
               - headless=False (VISIBLE) por defecto para que el usuario vea
                 el navegador y confirme que el scroll funciona correctamente.
                 Cambiar a True solo en producción desatendida.
               - Modo stealth con banderas diferenciadas visible/headless.
               - Inyección de cookies de sesión de Facebook.
               - Intercepción de red para bloquear imágenes, CSS y fuentes.
               - Scroll con inercia natural y jitter aleatorio (emulación humana).
               - Captura de todos los href de video visibles en el DOM.
               - Detección de fin de página o bucle sin nuevos nodos.
               - Escritura de logs al archivo log_tiempo_real.txt para la UI.
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Route,
    Playwright,
)


# ──────────────────────────────────────────────────────────────────
# BANDERAS DE CHROMIUM
# Modo VISIBLE (headless=False): sin --disable-gpu para que el
# renderizado gráfico funcione correctamente en Windows.
# ──────────────────────────────────────────────────────────────────
BANDERAS_CHROMIUM_VISIBLE: List[str] = [
    "--no-sandbox", "--disable-dev-shm-usage", "--disable-setuid-sandbox",
    "--no-first-run", "--disable-extensions", "--mute-audio",
    "--disable-background-networking", "--disable-sync", "--start-maximized",
]

BANDERAS_CHROMIUM_HEADLESS: List[str] = [
    "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
    "--disable-setuid-sandbox", "--no-first-run", "--disable-extensions",
    "--mute-audio", "--blink-settings=imagesEnabled=false",
    "--disable-background-networking", "--disable-sync", "--metrics-recording-only",
]

RECURSOS_BLOQUEADOS_HEADLESS: set = {"image", "stylesheet", "font", "media", "other", "manifest", "texttrack"}
RECURSOS_BLOQUEADOS_VISIBLE: set = {"font", "manifest", "texttrack"}


class NietoGestorScrollDinamico:
    """Controla la sesión de Chromium para extracción DOM de videos de Facebook."""

    def __init__(
        self,
        ruta_cookies: str = "config/cookies_facebook.json",
        headless: bool = False,
        max_scrolls: int = 50,
        pausa_min_seg: float = 1.2,
        pausa_max_seg: float = 3.5,
        ruta_log: str = "datos_persistencia/log_tiempo_real.txt",
    ) -> None:
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._ruta_cookies = self._ruta_base / ruta_cookies
        self._headless = headless
        self._max_scrolls = max_scrolls
        self._pausa_min = pausa_min_seg
        self._pausa_max = pausa_max_seg
        self._ruta_log = self._ruta_base / ruta_log

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexto: Optional[BrowserContext] = None
        self._pagina: Optional[Page] = None

    async def inicializar_browser(self) -> None:
        """Inicia Playwright y lanza Chromium con configuración optimizada."""
        modo = "HEADLESS" if self._headless else "VISIBLE"
        self._log(f"[BROWSER] Iniciando Chromium en modo {modo}...")
        banderas = BANDERAS_CHROMIUM_HEADLESS if self._headless else BANDERAS_CHROMIUM_VISIBLE
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless, args=banderas)
        self._contexto = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="es-MX",
        )
        await self._inyectar_cookies()
        self._pagina = await self._contexto.new_page()
        self._recursos_bloqueados = RECURSOS_BLOQUEADOS_HEADLESS if self._headless else RECURSOS_BLOQUEADOS_VISIBLE
        await self._pagina.route("**/*", self._interceptar_y_bloquear_recursos)
        self._log(f"[BROWSER] Chromium listo en modo {modo}.")

    def _sanitizar_cookie_playwright(self, c: dict) -> Optional[dict]:
        """Sanitiza una cookie asegurando tipos y atributos válidos."""
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            return None
        cookie = {
            "name": str(c["name"]),
            "value": str(c["value"]),
            "domain": str(c.get("domain") or ".facebook.com"),
            "path": str(c.get("path") or "/"),
        }
        if "secure" in c and c["secure"] is not None:
            cookie["secure"] = bool(c["secure"])
        if "httpOnly" in c and c["httpOnly"] is not None:
            cookie["httpOnly"] = bool(c["httpOnly"])
        if "expires" in c and c["expires"] is not None:
            try: cookie["expires"] = float(c["expires"])
            except (ValueError, TypeError): pass
        if "sameSite" in c and c["sameSite"] is not None:
            val = str(c["sameSite"]).lower()
            cookie["sameSite"] = "None" if val == "no_restriction" else val.capitalize()
        return cookie

    async def _inyectar_cookies(self) -> None:
        """Inyecta las cookies de sesión en el contexto de Chromium."""
        if not self._ruta_cookies.exists():
            return
        try:
            with open(self._ruta_cookies, "r", encoding="utf-8") as f:
                cookies_raw = json.load(f)
            cookies_sanitizadas = [self._sanitizar_cookie_playwright(c) for c in cookies_raw if self._sanitizar_cookie_playwright(c)]
            if cookies_sanitizadas:
                await self._contexto.add_cookies(cookies_sanitizadas)
                print(f"[BROWSER] {len(cookies_sanitizadas)} cookies inyectadas.")
        except Exception as e:
            print(f"[BROWSER] [WARN] Error inyectando cookies: {e}")

    async def cerrar(self) -> None:
        """
        Cierra la página, el contexto y el navegador ordenadamente
        para liberar todos los recursos del SO.
        """
        if self._pagina and not self._pagina.is_closed():
            await self._pagina.close()
        if self._contexto:
            await self._contexto.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("[BROWSER] Navegador cerrado y recursos liberados.")

    # ------------------------------------------------------------------
    # INTERCEPCIÓN DE RED
    # ------------------------------------------------------------------

    async def _interceptar_y_bloquear_recursos(self, ruta: Route) -> None:
        """
        Intercepta peticiones HTTP. En modo headless bloquea imágenes, CSS y fuentes.
        En modo visible bloquea solo fuentes y manifests para mantener el render.

        Args:
            ruta: Objeto Route de Playwright con información de la petición.
        """
        if ruta.request.resource_type in self._recursos_bloqueados:
            await ruta.abort()
        else:
            await ruta.continue_()

    # ------------------------------------------------------------------
    # NAVEGACIÓN Y SCROLL
    # ------------------------------------------------------------------

    async def navegar_a_url(self, url: str) -> bool:
        """
        Navega a la URL objetivo y espera a que el DOM esté cargado.

        Args:
            url: URL de la página de Facebook a raspar.

        Returns:
            True si la navegación fue exitosa.
        """
        try:
            await self._pagina.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2.0)
            print(f"[BROWSER] Página cargada: {url}")
            return True
        except Exception as error:
            print(f"[ERROR] Fallo al navegar a {url}: {error}")
            return False

    async def simular_scroll_humano(self) -> None:
        """
        Realiza un scroll con inercia natural simulando movimiento humano:
          - Múltiples micro-pasos con distancias variables (inercia decreciente).
          - Pausas micro-aleatorias entre pasos.
          - Pausa ocasional larga (simula que el usuario lee contenido).
        """
        pasos = random.randint(2, 4)
        distancia_base = random.randint(300, 600)
        for i in range(pasos):
            factor = 1.0 - (i * 0.15)
            distancia = int(distancia_base * max(0.4, factor)) + random.randint(-50, 50)
            await self._pagina.evaluate(f"window.scrollBy({{top: {distancia}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(0.2, 0.5))
        if random.random() < 0.12:
            await asyncio.sleep(random.uniform(1.2, 2.5))

    async def extraer_enlaces_visibles(self) -> List[str]:
        """Extrae URLs de video del DOM de Facebook."""
        script = """() => {
            const urls = new Set();
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.href || '';
                if (h.includes('/watch') || h.includes('/reel/') || h.includes('/reels/') || h.includes('/videos/') || h.includes('fb.watch') || h.includes('/share/v/') || (h.includes('v=') && h.includes('facebook'))) urls.add(h);
            });
            document.querySelectorAll('[data-video-id]').forEach(el => {
                const vid = el.getAttribute('data-video-id');
                if (vid) urls.add('https://www.facebook.com/watch/?v=' + vid);
            });
            return Array.from(urls);
        }"""
        try:
            return await self._pagina.evaluate(script)
        except Exception as err:
            self._log(f"[ERROR] Error extrayendo enlaces: {err}")
            return []

    async def evaluar_fin_de_pagina(self) -> bool:
        """Detecta si se alcanzó el fin del scroll en la página."""
        try:
            return bool(await self._pagina.evaluate("() => (window.scrollY + window.innerHeight) >= (document.documentElement.scrollHeight - 250)"))
        except Exception:
            return False

    async def ejecutar_bucle_extraccion(self, url_objetivo: str) -> List[str]:
        """Ejecuta el bucle de navegación y scroll dinámico."""
        self._log(f"[SCROLL] Iniciando extracción en: {url_objetivo}")
        if not await self.navegar_a_url(url_objetivo):
            return []

        todas_las_urls: List[str] = []
        sin_nuevas = 0
        prev_count = 0
        MAX_SIN_NUEVAS = 3

        for i in range(self._max_scrolls):
            self._log(f"[SCROLL] Iteración {i + 1}/{self._max_scrolls} — URLs: {len(todas_las_urls)}")
            urls_lote = await self.extraer_enlaces_visibles()
            todas_las_urls.extend(urls_lote)

            if len(todas_las_urls) == prev_count:
                sin_nuevas += 1
                if sin_nuevas >= MAX_SIN_NUEVAS:
                    self._log("[SCROLL] Límite de iteraciones sin nuevo contenido alcanzado.")
                    break
            else:
                sin_nuevas = 0
                nuevas = len(todas_las_urls) - prev_count
                self._log(f"[SCROLL] +{nuevas} URLs nuevas detectadas.")
                prev_count = len(todas_las_urls)

            if await self.evaluar_fin_de_pagina():
                self._log("[SCROLL] Fin de página alcanzado.")
                break

            await self.simular_scroll_humano()
            await asyncio.sleep(random.uniform(self._pausa_min, self._pausa_max))

        self._log(f"[SCROLL] [OK] Extracción finalizada. {len(todas_las_urls)} URLs brutas.")
        return todas_las_urls

    def _log(self, mensaje: str) -> None:
        """Registra mensaje en consola y log_tiempo_real.txt para UI SSE."""
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nivel = "ERROR" if "[ERROR]" in mensaje else ("WARN" if "Sin nuevas" in mensaje else ("OK" if "[OK]" in mensaje else "INFO"))
        print(f"{estampa}  {mensaje}")
        try:
            self._ruta_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_log, "a", encoding="utf-8") as f:
                f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")
        except OSError:
            pass
