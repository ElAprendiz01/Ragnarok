"""
================================================================================
SCRIPT: scratch/ejecutar_lote_completo_telegram.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Dispara la publicación por lotes de Telegram HD (tocando el botón
             del panel vía API/UI), supervisa la ejecución secuencial uno a uno
             de los 53 videos y muestra el resumen y logs al final.
================================================================================
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = Path(__file__).parent.parent.resolve()
RUTA_LOG = RAIZ / "datos_persistencia" / "log_tiempo_real.txt"
RUTA_COLA = RAIZ / "datos_persistencia" / "cola_publicacion_telegram.json"
URL_BASE = "http://127.0.0.1:5757"


def verificar_servidor() -> bool:
    """Verifica si el servidor Flask en el puerto 5757 está en línea."""
    try:
        req = urllib.request.Request(f"{URL_BASE}/estado")
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status == 200
    except Exception:
        return False


def disparar_lote_api(canal: str = "@salip_pelis", modo_browser: str = "visible", modo_video: str = "completo") -> dict:
    """Dispara la acción del botón de lote en el servidor local vía HTTP POST."""
    payload = json.dumps({
        "canal": canal,
        "modo_browser": modo_browser,
        "modo_video": modo_video
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{URL_BASE}/api/publicar/lote/telegram",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detalles = err.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {err.code}: {detalles}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def obtener_estado_lote() -> dict:
    """Consulta el estado del lote en disco y memoria."""
    try:
        req = urllib.request.Request(f"{URL_BASE}/api/publicar/lote/estado")
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        # Fallback directo a leer disco si el servidor no responde
        if RUTA_COLA.exists():
            try:
                with open(RUTA_COLA, "r", encoding="utf-8") as f:
                    return {"ok": True, "activo": False, **json.load(f)}
            except Exception:
                pass
        return {"ok": False, "activo": False}


def mostrar_logs_finales(lineas: int = 50) -> None:
    """Muestra las últimas líneas del archivo de registro al culminar."""
    print("\n" + "=" * 70)
    print(f"  REGISTRO FINAL DE OPERACIÓN ({RUTA_LOG.name})")
    print("=" * 70)
    if not RUTA_LOG.exists():
        print("[!] No se encontró el archivo de log.")
        return

    try:
        with open(RUTA_LOG, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.readlines()
        ultimas = contenido[-lineas:] if len(contenido) > lineas else contenido
        for l in ultimas:
            print("  " + l.strip())
    except Exception as e:
        print(f"[!] Error leyendo log: {e}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Disparador y monitor de lote Telegram HD")
    parser.add_argument("--canal", type=str, default="@salip_pelis", help="Canal de Telegram destino")
    parser.add_argument("--browser", type=str, default="visible", choices=["visible", "headless"])
    parser.add_argument("--modo", type=str, default="completo", choices=["completo", "clips"])
    parser.add_argument("--intervalo", type=int, default=15, help="Segundos entre cada sondeo")
    args = parser.parse_args()

    print("=" * 70)
    print("  RAGNAROK — DISPARADOR DE LOTE TELEGRAM HD")
    print(f"  Canal:   {args.canal}")
    print(f"  Ventana: {args.browser.upper()}")
    print(f"  Modo:    {args.modo.upper()}")
    print("=" * 70)

    # 1. Comprobar servidor
    if not verificar_servidor():
        print(f"[ERROR] El servidor en {URL_BASE} no está respondiendo. Inicia main.py o el panel.")
        sys.exit(1)

    print("[OK] Servidor Python activo en el puerto 5757.")

    # 2. Comprobar si el lote ya está corriendo o dispararlo
    estado_prev = obtener_estado_lote()
    if estado_prev.get("activo", False):
        print(f"[INFO] Lote actualmente en ejecución activa en segundo plano. Continuando supervisión...")
    else:
        print(f"\n[1/3] Activando botón de subida por lote hacia {args.canal}...")
        resp = disparar_lote_api(canal=args.canal, modo_browser=args.browser, modo_video=args.modo if hasattr(args, 'modo') else "completo")
        if not resp.get("ok"):
            print(f"[ERROR] No se pudo iniciar el lote: {resp.get('error')}")
            sys.exit(1)
        print(f"[OK] {resp.get('mensaje', 'Lote iniciado correctamente.')}")

    print("\n[2/3] Tarea en ejecución secuencial en segundo plano.")
    print("      (Este proceso toma tiempo debido al volumen de videos).")
    print(f"      Supervisando progreso cada {args.intervalo} segundos...\n", flush=True)

    time.sleep(2)
    inicio = time.time()
    ultimo_estado_str = ""

    # 3. Bucle de espera silencioso y constante
    try:
        while True:
            estado = obtener_estado_lote()
            activo = estado.get("activo", False)
            total = estado.get("total", 0)
            completados = estado.get("completados", 0)
            fallidos = estado.get("fallidos", 0)
            elementos = estado.get("elementos", [])

            # Localizar el video que se está procesando actualmente
            video_actual = "Iniciando..."
            for el in elementos:
                if el.get("estado") == "PENDIENTE":
                    video_actual = f"#{el.get('indice')} '{el.get('titulo')}' ({el.get('tamano_mb')} MB)"
                    break

            transcurrido_min = int((time.time() - inicio) / 60)
            linea_estado = f"[{transcurrido_min}m] Progreso: {completados}/{total} completados | Fallidos: {fallidos} | Actual: {video_actual}"

            if linea_estado != ultimo_estado_str:
                try:
                    print(f"  {linea_estado}", flush=True)
                except UnicodeEncodeError:
                    limpia = linea_estado.encode("ascii", errors="replace").decode("ascii")
                    print(f"  {limpia}", flush=True)
                ultimo_estado_str = linea_estado

            if not activo:
                # Verificar si ya finalizó todo el manifiesto
                if total > 0 and (completados + fallidos) >= total:
                    print("\n[OK] ¡Todos los videos de la cola han sido procesados!")
                    break
                elif total > 0 and (completados + fallidos) > 0 and not activo:
                    # Esperar 5s adicionales para confirmar que no fue una pausa entre subprocesos
                    time.sleep(5)
                    estado_confirm = obtener_estado_lote()
                    if not estado_confirm.get("activo", False):
                        print("\n[INFO] Ejecución de la cola detenida o finalizada.")
                        break

            time.sleep(args.intervalo)

    except KeyboardInterrupt:
        print("\n[AVISO] Monitoreo interrumpido por el usuario. El proceso en segundo plano continúa.")

    # 4. Revisión final de los logs
    print("\n[3/3] Proceso finalizado. Consultando logs...")
    mostrar_logs_finales(lineas=35)


if __name__ == "__main__":
    main()
