# Guía de Instalación y Ejecución de FaceDPeli

Esta guía explica las formas disponibles para instalar dependencias y levantar el sistema **FaceDPeli**.

---

## 🚀 Opción 1: Arranque Automático (Recomendada)

### En Windows (Doble Clic)
Haz doble clic en el archivo [iniciar.bat](file:///c:/Users/gmayc/OneDrive/Escritorio/facedpeli/iniciar.bat). Este script realizará todo de forma automática:
1. Instala/actualiza las librerías desde `requirements.txt`.
2. Instala Chromium para Playwright.
3. Abre el navegador en `http://127.0.0.1:5757`.
4. Mantiene el servidor web activo.

### Con Python Directo
Ejecuta en tu consola:
```powershell
python iniciar_sistema.py
```
Este script ([iniciar_sistema.py](file:///c:/Users/gmayc/OneDrive/Escritorio/facedpeli/iniciar_sistema.py)) verifica las dependencias, descarga Chromium si hace falta y levanta la interfaz visual.

---

## 🛠️ Opción 2: Ejecución Manual Paso a Paso

### Paso 1: Instalación de Dependencias
```powershell
pip install -r requirements.txt
playwright install chromium
```

### Paso 2A: Modo Interfaz Web (Panel de Control Visual)
```powershell
python interfaz/servidor_logs.py
```
Luego abre tu navegador en `http://127.0.0.1:5757`. Desde allí podrás:
* Iniciar sesión en Telegram Web (`/auth/telegram`).
* Agregar fuentes URL de Facebook.
* Agregar o eliminar tareas de la cola de pendientes.
* Ejecutar la Fase 1, Fase 2, Fase 3 o Fase 4 (Telegram HD) con un clic.
* Ver logs de ejecución en tiempo real y estadísticas del sistema.

### Paso 2B: Modo Consola CLI (Terminal)
```powershell
python main.py                     # Ejecuta las 3 fases secuenciales
python main.py --fase 1            # Solo Fase 1 (Extracción)
python main.py --fase 2            # Solo Fase 2 (Edición FFmpeg)
python main.py --fase 3            # Solo Fase 3 (Publicación Multicanal)
python main.py --fase 3 --plataforma telegram  # Solo Telegram HD
```
