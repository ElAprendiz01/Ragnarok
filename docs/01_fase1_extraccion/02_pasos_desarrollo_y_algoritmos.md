# Pasos de Desarrollo y Algoritmos Detallados - Fase 1

Este documento establece la hoja de ruta de desarrollo, firmas de funciones, pseudocódigo y especificaciones de implementación paso a paso para los cuatro módulos Python que conforman la **Fase 1: Extracción & Descarga**.

---

## 1. Módulo: `fase1_extraccion/padre_control_de_estados_txt.py`

### 1.1 Responsabilidad
Administrar de manera atómica las operaciones de entrada/salida (E/S) en disco para los archivos de texto de la carpeta `datos_persistencia/`. Garantiza que ninguna colección crezca en memoria RAM.

### 1.2 Firmas y Contratos de Métodos

```python
class PadreControlDeEstadosTXT:
    def __init__(self, ruta_base_datos: str = "datos_persistencia"): ...
    def inicializar_archivos_si_no_existen(self) -> None: ...
    def existe_en_historial_global(self, url: str) -> bool: ...
    def agregar_a_historial_global(self, url: str) -> bool: ...
    def agregar_a_cola_pendientes(self, url: str) -> bool: ...
    def obtener_siguiente_pendiente(self) -> Optional[str]: ...
    def remover_de_cola_pendientes(self, url: str) -> bool: ...
    def registrar_completado(self, id_video: str, url: str) -> None: ...
    def registrar_error(self, url: str, modulo: str, error_msg: str) -> None: ...
```

### 1.3 Algoritmo de Búsqueda Anti-Duplicados en ROM (Sin Cargar Archivo en RAM)
```text
ALGORITMO existe_en_historial_global(url_normalizada):
    1. Abrir historial_global_enlaces.txt en modo lectura ('r', encoding='utf-8').
    2. Para cada linea en el archivo:
        a. Limpiar espacios y saltos de linea de la linea.
        b. Si linea == url_normalizada:
            Cerrar archivo.
            RETORNAR True.
    3. Cerrar archivo.
    4. RETORNAR False.
```

---

## 2. Módulo: `fase1_extraccion/nieto_auditor_de_duplicados.py`

### 2.1 Responsabilidad
Recibir un lote de URLs obtenidas del DOM de Playwright, normalizarlas (eliminando parámetros tracking como `ref=share`, `fbclid=...`), eliminar duplicados internos del lote mediante `set` temporal en memoria y auditar contra el `padre_control_de_estados_txt`.

### 2.2 Firmas y Contratos de Métodos

```python
class NietoAuditorDeDuplicados:
    def __init__(self, gestor_estados: PadreControlDeEstadosTXT): ...
    def normalizar_url_facebook(self, url_raw: str) -> Optional[str]: ...
    def filtrar_lote_nuevo(self, lista_urls_raw: List[str]) -> List[str]: ...
```

### 2.3 Algoritmo de Normalización y Filtrado de Lote
```text
ALGORITMO normalizar_url_facebook(url_raw):
    1. Si url_raw no contiene "facebook.com" o ("watch" y "reel" y "videos"):
        RETORNAR None
    2. Parsear URL con urllib.parse.urlparse.
    3. Extraer el parametro 'v' o la ruta numerica del ID del video.
    4. Reconstruir URL canónica: "https://www.facebook.com/watch/?v=" + ID_VIDEO
    5. RETORNAR url_canonica

ALGORITMO filtrar_lote_nuevo(lista_urls_raw):
    1. Crear conjunto_lote_visto = set()
    2. Crear lista_unicos_nuevos = []
    3. Para cada url_raw en lista_urls_raw:
        a. url_clean = normalizar_url_facebook(url_raw)
        b. Si url_clean es None: CONTINUAR
        c. Si url_clean esta en conjunto_lote_visto: CONTINUAR
        d. Agregar url_clean a conjunto_lote_visto
        e. Si NO gestor_estados.existe_en_historial_global(url_clean):
            Agregar url_clean a lista_unicos_nuevos
    4. Liberar conjunto_lote_visto (garantiza 0 retencion)
    5. RETORNAR lista_unicos_nuevos
```

---

## 3. Módulo: `fase1_extraccion/nieto_gestor_scroll_dinamico.py`

### 3.1 Responsabilidad
Gestionar el ciclo de vida del navegador Playwright (modo headless stealth), aplicar intercepción de peticiones (bloquear `image`, `stylesheet`, `font`, `other`), realizar scroll incremental simulando movimiento humano y extraer los nodos `<a>` con URLs de video.

### 3.2 Banderas Chromium de Rendimiento y Memoria
El módulo debe arrancar Chromium con los siguientes argumentos estrictos:
```python
CHROMIUM_FLAGS = [
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
    "--blink-settings=imagesEnabled=false"
]
```

### 3.3 Firmas de Métodos
```python
class NietoGestorScrollDinamico:
    def __init__(self, ruta_cookies: str, headless: bool = True): ...
    async def inicializar_browser((self) -> None: ...
    async def interceptar_y_bloquear_recursos(self, route: Route) -> None: ...
    async def simular_scroll_humano(self, pasos: int = 3) -> int: ...
    async def extraer_enlaces_visibles(self) -> List[str]: ...
    async def cerrar(self) -> None: ...
```

---

## 4. Módulo: `fase1_extraccion/orquestador_descargas_principal.py`

### 4.1 Responsabilidad
Punto de entrada general de la Fase 1. Instancia los tres submódulos anteriores, coordina el bucle de scraping, traslada las URLs aprobadas a `cola_pendientes.txt` y ejecuta la descarga secuencial utilizando el ejecutor binario de `yt-dlp`.

### 4.2 Lógica de Invocación a `yt-dlp` vía Subprocess
Para mantener cero consumo de memoria en Python y máxima estabilidad de descarga:

```python
def ejecutar_descarga_ytdlp(url: str, dir_salida: str) -> Tuple[bool, dict]:
    """
    Ejecuta el binario yt-dlp mediante subprocess limitando la descarga a H.264 / AAC.
    """
    comando = [
        "yt-dlp",
        "--format", "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--no-playlist",
        "--output", f"{dir_salida}/video_original.%(ext)s",
        url
    ]
    # Ejecución con subprocess.run capturando stdout/stderr
```

---

## 5. Pasos Ordenados de Desarrollo (Checklist de Construcción)

1. **Paso 1**: Implementar `padre_control_de_estados_txt.py` y crear pruebas unitarias para validar creación de archivos, detección de duplicados en `.txt` y escritura atómica.
2. **Paso 2**: Implementar `nieto_auditor_de_duplicados.py` con expresiones regulares para normalizar URLs de Facebook Reels y Videos.
3. **Paso 3**: Implementar `nieto_gestor_scroll_dinamico.py` utilizando Playwright Async, validando el bloqueo de recursos CSS/Imágenes y la inyección de cookies de `config/cookies_facebook.json`.
4. **Paso 4**: Implementar `orquestador_descargas_principal.py` integrando la llamada a `yt-dlp` y el empaquetado de `metadata.json`.
5. **Paso 5**: Ejecutar prueba end-to-end con 5 enlaces objetivo y verificar que el uso de RAM de Python permanezca menor a **80 MB** durante todo el ciclo.
