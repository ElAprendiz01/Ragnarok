"""
================================================================================
ARCHIVO: main.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Punto de entrada global del sistema Ragnarok.
             Permite ejecutar el pipeline completo (Fase 1 -> Fase 2 -> Fase 3)
             o fases individuales mediante argumentos de línea de comandos.

MODO DE USO:
    python main.py                  # Ejecuta las 3 fases en secuencia
    python main.py --fase 1         # Sólo Fase 1: Extracción & Descarga
    python main.py --fase 2         # Sólo Fase 2: Edición & Segmentación
    python main.py --fase 3         # Sólo Fase 3: Publicación & Limpieza
    python main.py --fase 1 2       # Fases 1 y 2 en secuencia
================================================================================
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional

# Asegurar que la raíz del proyecto está en el sys.path y soporte UTF-8 en consola Windows
sys.path.insert(0, str(Path(__file__).parent.resolve()))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fase1_extraccion.orquestador_descargas_principal import OrquestadorDescargasPrincipal
from fase2_edicion.orquestador_edicion_principal import OrquestadorEdicionPrincipal
from fase3_publicacion.orquestador_publicaciones_principal import OrquestadorPublicacionesPrincipal


RUTA_CONFIG: str = "config/parametros_globales.json"

BANNER = """
╔══════════════════════════════════════════════════════════╗
║          Ragnarok — Sistema de Distribución de Video    ║
║      Extracción • Edición • Publicación Automática       ║
╚══════════════════════════════════════════════════════════╝
"""


async def ejecutar_fase_1(solo_descargar: bool = False) -> None:
    """Lanza la Fase 1: Extracción & Descarga de Videos."""
    orquestador = OrquestadorDescargasPrincipal(ruta_config=RUTA_CONFIG)
    await orquestador.ejecutar_fase(solo_descargar=solo_descargar)


def ejecutar_fase_2() -> None:
    """Lanza la Fase 2: Edición & Segmentación de Videos."""
    orquestador = OrquestadorEdicionPrincipal(ruta_config=RUTA_CONFIG)
    orquestador.ejecutar_fase_2()


async def ejecutar_fase_3(plataforma: Optional[str] = None, headless: Optional[bool] = None) -> None:
    """Lanza la Fase 3: Publicación & Limpieza Cascade."""
    orquestador = OrquestadorPublicacionesPrincipal(ruta_config=RUTA_CONFIG, headless=headless)
    await orquestador.ejecutar_fase_3(plataforma_filtro=plataforma)


async def ejecutar_pipeline_completo() -> None:
    """Ejecuta las tres fases en secuencia completa."""
    print(BANNER)
    print("[MAIN] Iniciando pipeline completo Ragnarok...\n")
    await ejecutar_fase_1()
    print("\n" + "—"*60 + "\n")
    ejecutar_fase_2()
    print("\n" + "—"*60 + "\n")
    await ejecutar_fase_3()
    print("\n[MAIN] Pipeline completo finalizado.")


def construir_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="Ragnarok",
        description="Ragnarok — Pipeline automatizado de distribución de video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py                  Ejecutar todas las fases
  python main.py --fase 1         Solo Fase 1 (Extracción)
  python main.py --fase 1 --solo-descargar  Solo descarga cola de pendientes con yt-dlp
  python main.py --fase 2         Solo Fase 2 (Edición)
  python main.py --fase 3         Solo Fase 3 (Publicación)
  python main.py --fase 3 --plataforma telegram  Publicar solo en Telegram
  python main.py --fase 3 --plataforma telegram --headless  Publicar en Telegram en modo invisible
        """
    )
    parser.add_argument(
        "--fase",
        nargs="+",
        type=int,
        choices=[1, 2, 3],
        help="Número(s) de fase(s) a ejecutar. Sin argumento ejecuta las 3 fases.",
        metavar="N",
    )
    parser.add_argument(
        "--solo-descargar",
        action="store_true",
        help="En Fase 1, omite la etapa de scraping y ejecuta únicamente la descarga con yt-dlp de cola_pendientes.txt",
    )
    parser.add_argument(
        "--plataforma",
        type=str,
        choices=["youtube", "tiktok", "facebook", "instagram", "telegram"],
        help="En Fase 3, filtra la publicación únicamente hacia la red social especificada.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Forzar modo invisible (headless).",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        default=None,
        help="Forzar modo visible (con ventana de Chromium).",
    )
    return parser


async def main() -> None:
    """Función principal con gestión de argumentos."""
    print(BANNER)
    parser = construir_parser()
    args = parser.parse_args()

    fases_a_ejecutar = sorted(set(args.fase)) if args.fase else [1, 2, 3]
    headless = True if args.headless else (False if args.visible else None)
    print(f"[MAIN] Fases a ejecutar: {fases_a_ejecutar}\n")

    for fase in fases_a_ejecutar:
        if fase == 1:
            await ejecutar_fase_1(solo_descargar=args.solo_descargar)
        elif fase == 2:
            ejecutar_fase_2()
        elif fase == 3:
            await ejecutar_fase_3(plataforma=args.plataforma, headless=headless)
        if fase != fases_a_ejecutar[-1]:
            print("\n" + "—"*60 + "\n")

    print("\n[MAIN] Ejecución finalizada.")


if __name__ == "__main__":
    asyncio.run(main())
