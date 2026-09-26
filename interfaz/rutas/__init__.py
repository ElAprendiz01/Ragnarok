"""
================================================================================
PAQUETE: interfaz/rutas
PROYECTO: Ragnarok
DESCRIPCIÓN: Registro centralizado de Blueprints para el servidor Flask.
LÍNEAS: < 40
================================================================================
"""

from flask import Flask

from interfaz.rutas.rutas_publicacion import bp_publicacion
from interfaz.rutas.rutas_videos import bp_videos
from interfaz.rutas.rutas_fuentes import bp_fuentes
from interfaz.rutas.rutas_configuracion import bp_configuracion
from interfaz.rutas.rutas_pipeline import bp_pipeline
from interfaz.rutas.rutas_auth import bp_auth


def registrar_rutas(app: Flask) -> None:
    """Registra todos los Blueprints modulares en la aplicación Flask."""
    app.register_blueprint(bp_publicacion)
    app.register_blueprint(bp_videos)
    app.register_blueprint(bp_fuentes)
    app.register_blueprint(bp_configuracion)
    app.register_blueprint(bp_pipeline)
    app.register_blueprint(bp_auth)
