"""
================================================================================
MÓDULO: fase1_extraccion/__init__.py
PROYECTO: FaceDPeli
DESCRIPCIÓN: Inicializador del paquete de la Fase 1 - Extracción & Descarga.
             Expone los módulos principales para importación limpia.
================================================================================
"""

from fase1_extraccion.orquestador_descargas_principal import OrquestadorDescargasPrincipal
from fase1_extraccion.padre_control_de_estados_txt import PadreControlDeEstadosTXT
from fase1_extraccion.hijo_gestor_de_fuentes_url import HijoGestorDeFuentesURL
from fase1_extraccion.nieto_auditor_de_duplicados import NietoAuditorDeDuplicados
from fase1_extraccion.nieto_gestor_scroll_dinamico import NietoGestorScrollDinamico

__all__ = [
    "OrquestadorDescargasPrincipal",
    "PadreControlDeEstadosTXT",
    "HijoGestorDeFuentesURL",
    "NietoAuditorDeDuplicados",
    "NietoGestorScrollDinamico",
]
