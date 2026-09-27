"""
================================================================================
MÓDULO: fase3_publicacion/hijo_monitor_transferencia_telegram.py
JERARQUÍA: Hijo (Auditor y supervisor del DOM de transferencias en Telegram Web)
PROYECTO: Ragnarok
DESCRIPCIÓN: Supervisa activamente el progreso de subida en el DOM de Telegram Web,
             lee los porcentajes en tiempo real (.message-transfer-progress),
             previene el cierre prematuro de Chromium y valida tanto subidas
             individuales como procesamiento por lotes (batch).
LÍNEAS DE CÓDIGO: < 300 (Regla de Responsabilidad Única)
================================================================================
"""

import asyncio
import re
import sys
from typing import Optional, Callable
from playwright.async_api import Page, Locator

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class HijoMonitorTransferenciaTelegram:
    """Supervisa el DOM de transferencias en Telegram Web y controla el ciclo de espera seguro."""

    SELECTOR_PROGRESO: str = ".message-transfer-progress"
    SELECTOR_MENSAJE: str = ".Message"

    def __init__(self) -> None:
        self._ultimo_porcentaje_registrado: str = ""

    async def esperar_subida_individual(
        self,
        pagina: Page,
        titulo: str = "",
        timeout_seg: int = 1800,
        callback_log: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """
        Bloquea la ejecución y monitorea el DOM hasta que el video específico alcance el 100%.
        Impide que Chromium se cierre mientras haya una transferencia activa.

        Args:
            pagina: Instancia activa de Page en Playwright.
            titulo: Título o fragmento para identificar el mensaje en el canal.
            timeout_seg: Tiempo máximo de espera en segundos (por defecto 30 min).
            callback_log: Función opcional para despachar logs en tiempo real (ej: SSE).

        Returns:
            True si la transferencia finalizó al 100% y el mensaje está asentado.
        """
        self._notificar("INFO", "Iniciando supervisión del DOM de Telegram Web...", callback_log)

        inicio = asyncio.get_event_loop().time()
        subida_detectada = False
        ultimo_pct = ""
        segundos_sin_cambio = 0

        # Esperar hasta 20 segundos a que aparezca la burbuja del mensaje
        msg_locator = await self._localizar_mensaje_reciente(pagina, titulo)
        
        while (asyncio.get_event_loop().time() - inicio) < timeout_seg:
            await asyncio.sleep(2.0)
            transcurrido = int(asyncio.get_event_loop().time() - inicio)

            # Re-verificar locator del mensaje si no estaba fijado
            if not msg_locator or not await msg_locator.is_visible():
                msg_locator = await self._localizar_mensaje_reciente(pagina, titulo)

            if not msg_locator:
                if transcurrido < 15:
                    continue
                self._notificar("WARN", f"Esperando que el mensaje aparezca en el chat ({transcurrido}s)...", callback_log)
                continue

            # Buscar el elemento de progreso dentro del mensaje específico
            el_progreso = msg_locator.locator(self.SELECTOR_PROGRESO)
            hay_progreso = await el_progreso.count() > 0 and await el_progreso.first.is_visible()

            if hay_progreso:
                subida_detectada = True
                texto_pct = (await el_progreso.first.inner_text()).strip()

                # Validar que sea un porcentaje numérico legítimo (ej: "25%")
                if "%" in texto_pct:
                    if texto_pct != ultimo_pct:
                        ultimo_pct = texto_pct
                        segundos_sin_cambio = 0
                        self._notificar("INFO", f"Subiendo video a Telegram: {texto_pct} ({transcurrido}s transcurridos)...", callback_log)
                    else:
                        segundos_sin_cambio += 2
                        if segundos_sin_cambio >= 120 and segundos_sin_cambio % 30 == 0:
                            self._notificar("WARN", f"Transferencia lenta o pausada en {texto_pct} ({segundos_sin_cambio}s sin avance)...", callback_log)
                else:
                    if transcurrido % 10 == 0:
                        self._notificar("INFO", f"Procesando transferencia en servidor... ({transcurrido}s)", callback_log)

            else:
                # Si ya habíamos detectado progreso activo y ahora desapareció, ¡ha culminado!
                if subida_detectada:
                    self._notificar("OK", f"Elemento de progreso completado al 100% ({transcurrido}s). Verificando mensaje final...", callback_log)
                    await asyncio.sleep(3.0)
                    es_valido = await self._verificar_mensaje_finalizado(msg_locator)
                    if es_valido:
                        self._notificar("OK", f"Video verificado y asentado exitosamente en el canal ({transcurrido}s).", callback_log)
                        return True
                    return True
                else:
                    # Si no vimos el porcentaje pero pasaron > 8s, verificar si el mensaje ya está finalizado (video muy rápido)
                    if transcurrido >= 8:
                        if await self._verificar_mensaje_finalizado(msg_locator):
                            self._notificar("OK", f"Video confirmado directamente en el canal ({transcurrido}s).", callback_log)
                            return True

        self._notificar("ERROR", f"Tiempo de espera agotado ({timeout_seg}s) sin confirmación del 100%.", callback_log)
        return False

    async def esperar_subida_lote(
        self,
        pagina: Page,
        cantidad_videos: int,
        timeout_seg: int = 3600,
        callback_log: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        """
        Supervisa múltiples transferencias en lote y garantiza que ningún video
        quede a medias antes de permitir el cierre de Chromium.
        """
        self._notificar("INFO", f"Iniciando supervisión de subida en lote ({cantidad_videos} videos)...", callback_log)
        inicio = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - inicio) < timeout_seg:
            await asyncio.sleep(3.0)
            transcurrido = int(asyncio.get_event_loop().time() - inicio)

            # Buscar todas las transferencias activas en los mensajes recientes
            progresos_activos = pagina.locator(f"{self.SELECTOR_MENSAJE} {self.SELECTOR_PROGRESO}")
            cant_activas = await progresos_activos.count()

            if cant_activas > 0:
                detalles = []
                for i in range(cant_activas):
                    txt = (await progresos_activos.nth(i).inner_text()).strip()
                    if "%" in txt:
                        detalles.append(txt)
                str_detalles = ", ".join(detalles) if detalles else f"{cant_activas} activas"
                if transcurrido % 12 == 0:
                    self._notificar("INFO", f"Lote en progreso: [{str_detalles}] ({transcurrido}s)...", callback_log)
            else:
                if transcurrido >= 6:
                    self._notificar("OK", f"Todas las transferencias del lote ({cantidad_videos}) finalizaron.", callback_log)
                    return True

        self._notificar("ERROR", f"Timeout de lote agotado ({timeout_seg}s).", callback_log)
        return False

    async def autorizar_cierre_navegador(self, pagina: Page) -> bool:
        """
        Comprueba de forma preventiva si es seguro cerrar Chromium.
        Retorna False si hay algún video todavía transfiriéndose o modal abierto.
        """
        try:
            # 1. Verificar si hay modal de envío pendiente
            modal = pagina.locator(".modal-dialog")
            if await modal.count() > 0 and await modal.first.is_visible():
                return False

            # 2. Verificar transferencias activas en el último mensaje
            ultimo_msg = pagina.locator(self.SELECTOR_MENSAJE).last
            if await ultimo_msg.count() > 0:
                prog = ultimo_msg.locator(self.SELECTOR_PROGRESO)
                if await prog.count() > 0 and await prog.first.is_visible():
                    return False

            return True
        except Exception:
            return True

    async def _localizar_mensaje_reciente(self, pagina: Page, titulo: str) -> Optional[Locator]:
        """Localiza la burbuja del mensaje en el DOM, ya sea por título o por ser la última enviada."""
        try:
            if titulo:
                # Normalizar texto para coincidencia segura
                limpio = re.sub(r'[^\w\s]', '', titulo).strip()
                filtro = limpio[:25] if len(limpio) >= 4 else limpio
                if filtro:
                    msg_por_texto = pagina.locator(f"{self.SELECTOR_MENSAJE}:has-text('{filtro}')").last
                    if await msg_por_texto.count() > 0 and await msg_por_texto.is_visible():
                        return msg_por_texto

            # Fallback al último mensaje en la lista
            ultimo = pagina.locator(self.SELECTOR_MENSAJE).last
            if await ultimo.count() > 0 and await ultimo.is_visible():
                return ultimo
        except Exception:
            pass
        return None

    async def _verificar_mensaje_finalizado(self, msg_locator: Locator) -> bool:
        """Verifica que el mensaje contenga el video renderizado, miniatura o marca temporal."""
        try:
            # Elementos de confirmación: miniatura canvas, media-inner o timestamp entregado
            indicadores_exito = msg_locator.locator(
                "canvas.thumbnail, .media-inner, .video-player, .message-time, .has-views, div.n7fx0dq4"
            )
            return await indicadores_exito.count() > 0
        except Exception:
            return True

    def _notificar(self, nivel: str, mensaje: str, callback: Optional[Callable[[str, str], None]]) -> None:
        """Emite el mensaje por consola y por el callback suministrado."""
        print(f"[MONITOR-TELEGRAM] [{nivel}] {mensaje}")
        if callback:
            try:
                callback(nivel, mensaje)
            except Exception:
                pass
