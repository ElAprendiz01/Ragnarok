"""
================================================================================
MÓDULO: fase1_extraccion/nieto_gestor_scroll_dinamico.py
JERARQUÍA: Nieto  (Ejecutor de bajo nivel — control de navegador Playwright)
PROYECTO: FaceDPeli
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
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
    "--no-first-run",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--mute-audio",
    "--disable-background-networking",
    "--disable-sync",
    "--start-maximized",
]

# Modo HEADLESS (headless=True): puede deshabilitar GPU y demás
# para rendimiento ultra-bajo en RAM y CPU en servidores.
BANDERAS_CHROMIUM_HEADLESS: List[str] = [
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
    "--no-first-run",
    "--no-zygote",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--mute-audio",
    "--blink-settings=imagesEnabled=false",
    "--disable-background-networking",
    "--disable-sync",
    "--metrics-recording-only",
]

# Recursos de red a bloquear (solo en modo headless para no romper render visual)
RECURSOS_BLOQUEADOS_HEADLESS: set = {"image", "stylesheet", "font", "media", "other", "manifest", "texttrack"}
RECURSOS_BLOQUEADOS_VISIBLE: set = {"font", "manifest", "texttrack"}


class NietoGestorScrollDinamico:
    """
    Controla la sesión de Chromium headless para realizar scraping de videos
    de Facebook mediante emulación de scroll humano y extracción DOM de enlaces.
    """

    def __init__(
        self,
        ruta_cookies: str = "config/cookies_facebook.json",
        headless: bool = False,          # FALSE = navegador VISIBLE (recomendado)
        max_scrolls: int = 50,
        pausa_min_seg: float = 1.2,
        pausa_max_seg: float = 3.5,
        ruta_log: str = "datos_persistencia/log_tiempo_real.txt",
    ) -> None:
        """
        Inicializa el gestor con los parámetros de la sesión.

        Args:
            ruta_cookies:  Ruta al archivo JSON con cookies de sesión de Facebook.
            headless:      Si False (defecto), el navegador es VISIBLE — el usuario
                           puede ver en tiempo real lo que está haciendo el scraper.
                           Cambiar a True solo para ejecución en segundo plano.
            max_scrolls:   Límite de iteraciones de scroll para evitar bucles infinitos.
            pausa_min_seg: Mínimo de pausa entre scrolls (emulación humana).
            pausa_max_seg: Máximo de pausa entre scrolls (emulación humana).
            ruta_log:      Ruta del archivo de log en tiempo real para la UI.
        """
        self._ruta_base = Path(__file__).parent.parent.resolve()
        self._ruta_cookies = self._ruta_base / ruta_cookies
        self._headless = headless
        self._max_scrolls = max_scrolls
        self._pausa_min = pausa_min_seg
        self._pausa_max = pausa_max_seg
        self._ruta_log = self._ruta_base / ruta_log

        # Referencias al ciclo de vida del navegador (se asignan en inicializar)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexto: Optional[BrowserContext] = None
        self._pagina: Optional[Page] = None

    # ------------------------------------------------------------------
    # CICLO DE VIDA DEL NAVEGADOR
    # ------------------------------------------------------------------

    async def inicializar_browser(self) -> None:
        """
        Inicia Playwright, lanza Chromium con las banderas correctas según el modo
        (visible o headless), crea un contexto aislado e inyecta las cookies.
        """
        modo = "HEADLESS" if self._headless else "VISIBLE"
        self._log(f"[BROWSER] Iniciando Chromium en modo {modo}...")

        banderas = BANDERAS_CHROMIUM_HEADLESS if self._headless else BANDERAS_CHROMIUM_VISIBLE
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=banderas,
        )
        self._contexto = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="es-MX",
            timezone_id="America/Mexico_City",
        )
        await self._inyectar_cookies()
        self._pagina = await self._contexto.new_page()

        # En headless bloqueamos más recursos para máximo rendimiento
        recursos_bloqueados = RECURSOS_BLOQUEADOS_HEADLESS if self._headless else RECURSOS_BLOQUEADOS_VISIBLE
        self._recursos_bloqueados = recursos_bloqueados
        await self._pagina.route("**/*", self._interceptar_y_bloquear_recursos)
        self._log(f"[BROWSER] Chromium listo. Modo: {modo}. Recursos bloqueados: {len(recursos_bloqueados)} tipos.")

    def _sanitizar_cookie_playwright(self, c: dict) -> Optional[dict]:
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
            cookie["domain"] = ".facebook.com"

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

    async def _inyectar_cookies(self) -> None:
        """
        Carga las cookies del archivo JSON, las sanitiza e inyecta en el contexto
        del navegador para mantener la sesión autenticada de Facebook.
        """
        if not self._ruta_cookies.exists():
            print(f"[ADVERTENCIA] No se encontró el archivo de cookies: {self._ruta_cookies}")
            return
        with open(self._ruta_cookies, "r", encoding="utf-8") as archivo:
            cookies_raw = json.load(archivo)
        
        cookies_sanitizadas = []
        for c in cookies_raw:
            c_clean = self._sanitizar_cookie_playwright(c)
            if c_clean:
                cookies_sanitizadas.append(c_clean)

        if cookies_sanitizadas:
            await self._contexto.add_cookies(cookies_sanitizadas)
            print(f"[BROWSER] {len(cookies_sanitizadas)} cookies de sesión inyectadas exitosamente.")
        else:
            print("[ADVERTENCIA] No se encontraron cookies válidas para inyectar.")

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
        pasos = random.randint(2, 5)
        distancia_base = random.randint(300, 700)
        for i in range(pasos):
            # Inercia: los pasos más alejados van perdiendo velocidad
            factor_inercia = 1.0 - (i * 0.15)
            distancia = int(distancia_base * max(0.4, factor_inercia))
            distancia += random.randint(-80, 80)   # jitter natural
            await self._pagina.evaluate(f"window.scrollBy({{top: {distancia}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(0.25, 0.7))

        # 15% de probabilidad de pausa larga (simula lectura)
        if random.random() < 0.15:
            pausa_lectura = random.uniform(1.5, 3.5)
            await asyncio.sleep(pausa_lectura)

    async def extraer_enlaces_visibles(self) -> List[str]:
        """
        Captura todos los atributos href de los elementos <a> presentes
        en el DOM actual que contengan palabras clave de video de Facebook.
        También extrae data-video-id de atributos de datos del DOM.

        Returns:
            Lista cruda de strings href (pueden contener duplicados y URLs inválidas).
        """
        selector_script = """
            () => {
                const urls = new Set();
                // Método 1: etiquetas <a> con href de video
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href || '';
                    if (
                        href.includes('/watch') ||
                        href.includes('/reel/') ||
                        href.includes('/reels/') ||
                        href.includes('/videos/') ||
                        href.includes('fb.watch') ||
                        href.includes('/share/v/') ||
                        href.includes('v=') && href.includes('facebook')
                    ) urls.add(href);
                });
                // Método 2: atributos data- con IDs de video
                document.querySelectorAll('[data-video-id],[data-store]').forEach(el => {
                    const vid = el.getAttribute('data-video-id');
                    if (vid) urls.add('https://www.facebook.com/watch/?v=' + vid);
                });
                return Array.from(urls);
            }
        """
        try:
            urls_crudas: List[str] = await self._pagina.evaluate(selector_script)
            return urls_crudas
        except Exception as error:
            self._log(f"[ERROR] Fallo al extraer enlaces del DOM: {error}")
            return []

    async def evaluar_fin_de_pagina(self) -> bool:
        """
        Detecta si el scroll llegó al final de la página verificando
        si la posición actual de desplazamiento es cercana a la altura total del documento.

        Returns:
            True si se detectó el final de página.
        """
        resultado = await self._pagina.evaluate("""
            () => {
                const alturaTotal = document.documentElement.scrollHeight;
                const posicionActual = window.scrollY + window.innerHeight;
                return posicionActual >= alturaTotal - 200;
            }
        """)
        return bool(resultado)

    # ------------------------------------------------------------------
    # BUCLE PRINCIPAL DE EXTRACCIÓN
    # ------------------------------------------------------------------

    async def ejecutar_bucle_extraccion(self, url_objetivo: str) -> List[str]:
        """
        Ejecuta el bucle completo de navegación y scroll incremental.
        El bucle se detiene por: límite de scrolls, fin de página, o
        N iteraciones consecutivas sin nuevas URLs.

        Args:
            url_objetivo: URL de Facebook a raspar (puede ser grupo, página, watch...)

        Returns:
            Lista completa de URLs crudas acumuladas (sin deduplicar).
        """
        self._log(f"[SCROLL] Iniciando extracción en: {url_objetivo}")
        navegacion_exitosa = await self.navegar_a_url(url_objetivo)
        if not navegacion_exitosa:
            return []

        todas_las_urls: List[str] = []
        iteraciones_sin_nuevas = 0
        urls_previas_count = 0
        MAX_SIN_NUEVAS = 3

        for iteracion in range(self._max_scrolls):
            msg = f"[SCROLL] Iteración {iteracion + 1}/{self._max_scrolls} — URLs acumuladas: {len(todas_las_urls)}"
            self._log(msg)

            urls_lote = await self.extraer_enlaces_visibles()
            todas_las_urls.extend(urls_lote)

            if len(todas_las_urls) == urls_previas_count:
                iteraciones_sin_nuevas += 1
                self._log(f"[SCROLL] Sin nuevas URLs ({iteraciones_sin_nuevas}/{MAX_SIN_NUEVAS})")
                if iteraciones_sin_nuevas >= MAX_SIN_NUEVAS:
                    self._log("[SCROLL] Límite de iteraciones sin contenido nuevo alcanzado. Finalizando.")
                    break
            else:
                iteraciones_sin_nuevas = 0
                nuevas = len(todas_las_urls) - urls_previas_count
                self._log(f"[SCROLL] +{nuevas} URLs nuevas detectadas en DOM.")
                urls_previas_count = len(todas_las_urls)

            if await self.evaluar_fin_de_pagina():
                self._log("[SCROLL] Fin de página alcanzado. Deteniendo extracción.")
                break

            await self.simular_scroll_humano()
            await asyncio.sleep(random.uniform(self._pausa_min, self._pausa_max))

        self._log(f"[SCROLL] ✓ Extracción completada. {len(todas_las_urls)} URLs brutas totales.")
        return todas_las_urls

    # ------------------------------------------------------------------
    # LOGGING AL ARCHIVO DE TIEMPO REAL
    # ------------------------------------------------------------------

    def _log(self, mensaje: str) -> None:
        """
        Escribe el mensaje en la consola Y en el archivo log_tiempo_real.txt
        para que el servidor SSE de la UI pueda leerlo y enviarlo al navegador.

        Formato de línea: YYYY-MM-DD HH:MM:SS ||| NIVEL ||| MENSAJE

        Args:
            mensaje: Texto del log a registrar.
        """
        estampa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Detectar nivel por prefijo
        nivel = "INFO"
        if "[ERROR]" in mensaje or "Fallo" in mensaje:
            nivel = "ERROR"
        elif "[ADVERTENCIA]" in mensaje or "Sin nuevas" in mensaje:
            nivel = "WARN"
        elif "✓" in mensaje or "listo" in mensaje.lower() or "completad" in mensaje.lower():
            nivel = "OK"

        linea_consola = f"{estampa}  {mensaje}"
        print(linea_consola)

        try:
            self._ruta_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_log, "a", encoding="utf-8") as f:
                f.write(f"{estampa} ||| {nivel} ||| {mensaje}\n")
        except OSError:
            pass  # No interrumpir el scraping por un fallo de log
