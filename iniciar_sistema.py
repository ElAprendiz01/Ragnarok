"""
================================================================================
ARCHIVO: iniciar_sistema.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Lanzador e instalador automático de Ragnarok en Python.
             Comprueba e instala las dependencias de `requirements.txt`,
             descarga los binarios de Chromium para Playwright y arranca
             el Panel de Control Web en http://127.0.0.1:5757.
================================================================================
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

RAIZ = Path(__file__).parent.resolve()


def ejecutar_comando(comando: list, descripcion: str) -> bool:
    """Ejecuta un comando en la consola informando el estado al usuario."""
    print(f"\n[SISTEMA] {descripcion}...")
    try:
        resultado = subprocess.run(comando, cwd=str(RAIZ), check=True)
        return resultado.returncode == 0
    except subprocess.CalledProcessError as error:
        print(f"[ERROR] Falló la ejecución: {error}")
        return False
    except Exception as error:
        print(f"[ERROR] Error inesperado: {error}")
        return False


def main() -> None:
    """Punto de entrada del instalador y lanzador automático."""
    print("=" * 60)
    print("  Ragnarok — Instalador y Lanzador Automático")
    print("=" * 60)

    # Paso 1: Instalar dependencias desde requirements.txt
    ruta_req = RAIZ / "requirements.txt"
    if ruta_req.exists():
        exito_pip = ejecutar_comando(
            [sys.executable, "-m", "pip", "install", "-r", str(ruta_req)],
            "Instalando paquetes de Python desde requirements.txt"
        )
        if not exito_pip:
            print("[ADVERTENCIA] Algunas dependencias de pip pudieron fallar. Intentando continuar...")

    # Paso 2: Instalar navegador Chromium para Playwright
    ejecutar_comando(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Instalando navegador Chromium para Playwright"
    )

    # Paso 3: Abrir navegador e iniciar el servidor web
    url_panel = "http://127.0.0.1:5757"
    print(f"\n[SISTEMA] Abriendo Panel de Control Web en: {url_panel}")
    try:
        webbrowser.open(url_panel)
    except Exception:
        pass

    print("\n[SISTEMA] Iniciando servidor de logs e interfaz visual...\n")
    script_servidor = RAIZ / "interfaz" / "servidor_logs.py"
    subprocess.run([sys.executable, str(script_servidor)], cwd=str(RAIZ))


if __name__ == "__main__":
    main()
