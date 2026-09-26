He plasmado toda la visión arquitectónica de la Fase 1 en el documento. En él se abordan todos los puntos clave que faltaban:
 * Gestión de la Sesión y Cookies: Para que el sistema entre automáticamente sin ser detectado como bot ni requerir inicios de sesión constantes.
 * Manejo de Errores y Fallbacks: Qué hace el sistema si Facebook cambia su estructura o si un video guardado fue puesto en privado (para que el ciclo no se rompa).
 * Extracción de Metadatos Originales: Guardar el título y descripción original en un .json junto al video para usarlo más adelante en la Fase 3 (Publicación).
 * Ajustes Estrictos de Hardware: Las banderas exactas (--disable-gpu, --no-sandbox) y la intercepción de red para evitar que imágenes y CSS se carguen en memoria.
 * Formato de Descarga: La configuración ideal para lograr la más alta calidad con el menor peso (H.264 mp4).
Revisa el documento. Si el plan está alineado con lo que buscas, podemos empezar a escribir el código en Python, comenzando por el orquestador_descargas_principal.py o los módulos de nivel inferior
Tienes toda la razón. Es una omisión importante. Un sistema "livianito" no puede depender de guardar miles de enlaces en la memoria RAM para filtrarlos o imprimirlos al final de la ejecución; eso mataría el propósito de la optimización. Todo debe ser persistente, en tiempo real y basado en archivos de texto plano para mantener el consumo de recursos al mínimo.
Aquí tienes el Anexo del Plan de la Fase 1, estructurado exactamente bajo la misma arquitectura de Responsabilidad Única (archivos pequeños) y abordando el scroll, los duplicados y el control de estados. Puedes agregar esto directamente al final del documento .md anterior.
Anexo: Control de Estado, Paginación y Memoria Persistente
Para garantizar que la memoria RAM y la caché no se saturen durante la extracción masiva y descarga de videos, implementaremos un sistema de persistencia en tiempo real basado en archivos .txt. Ningún dato transaccional (enlaces exitosos, fallidos o pendientes) se retendrá en la memoria del programa para hacer resúmenes finales; todo se escribirá en disco al vuelo.
4. Nuevos Módulos Estructurales (Control de Estado y Paginación)
Se anexan los siguientes módulos a la jerarquía para manejar los nuevos requerimientos sin romper la regla de las 300 líneas:
 * padre_control_de_estados_txt.py
   * Responsabilidad: Administrar la creación, lectura y escritura en tiempo real de los archivos de registro (pendientes.txt, completados.txt, errores.txt). Si el archivo no existe, este módulo lo crea automáticamente al iniciar el sistema.
 * nieto_gestor_scroll_dinamico.py
   * Responsabilidad: Controlar la página de Playwright para hacer scroll down simulando comportamiento humano. Detecta cuándo no hay más contenido nuevo cargando en el DOM para detener el ciclo y evitar bucles infinitos, liberando los nodos viejos del DOM si es posible.
 * nieto_auditor_de_duplicados.py
   * Responsabilidad: Antes de enviar un enlace a descarga o a la lista de pendientes, verifica rápidamente si ya existe en los registros históricos. Utiliza estructuras de datos eficientes en Python (como sets en memoria solo para el lote actual con complejidad de búsqueda O(1)) respaldadas por los archivos de texto.
5. Lógica de Paginación y Carga (Infinite Scroll)
 * Facebook no carga todos los videos de una vez. El nieto_gestor_scroll_dinamico hará un scroll incremental.
 * Por cada lote de videos que aparezca en pantalla, el sistema extraerá los enlaces inmediatamente, los auditará y los guardará en disco, en lugar de esperar a llegar al final de la página para recolectar todo de golpe.
6. Sistema de Archivos Livianos (Persistencia y Cero Caché)
El orquestador se apoyará en los siguientes archivos de texto plano para manejar la lógica sin consumir RAM:
 * historial_global_enlaces.txt (El Registro Maestro):
   * Almacena absolutamente todos los enlaces que el sistema ha visto en su historia.
   * Uso: Sirve para la lógica anti-duplicados. Si el scraper detecta un enlace que ya está aquí, lo ignora al instante.
 * cola_pendientes.txt (El Gestor de Tareas):
   * Los enlaces nuevos y únicos se escriben aquí en tiempo real (modo append).
   * Uso: El motor de descarga lee de aquí. Si el sistema se apaga o se corta la luz, al reiniciar solo lee este archivo y retoma el trabajo exactamente donde se quedó.
 * enlaces_completados.txt (Control de Éxito):
   * Tan pronto como yt-dlp termina de procesar un video y empaquetar sus metadatos, el enlace se mueve de pendientes a este archivo.
   * Uso: Evita redescargas. Funciona como una confirmación de transacción exitosa.
 * registro_errores.txt (Manejo de Fallos sin Sobrecarga):
   * Si un video da error (fue borrado, es privado, falla la red), se guarda inmediatamente aquí con un código de error y la fecha.
   * Uso: Evita guardar los errores en una variable de tipo matriz (array) en la memoria caché para imprimirlos al final de la ejecución. El log se mantiene en disco, manteniendo el consumo de RAM estático.


Fase 2: Manejo de Edición y Procesamiento de Video
El objetivo de esta fase es procesar los archivos de la Fase 1 dividiéndolos en fragmentos de 8 minutos, ajustando velocidades (1.25x, 1.50x) y organizándolos en carpetas individuales. Para mantener el sistema ligero y no consumir la memoria RAM procesando píxeles directamente en Python, el trabajo pesado se delegará a binarios de bajo nivel.
1. Herramientas Open Source Seleccionadas
 * Motor de Edición: FFmpeg (Llamado a través de la librería ffmpeg-python o el módulo nativo subprocess). Es el estándar open-source absoluto. Funciona ejecutando comandos en la terminal, lo que significa que el video nunca se carga en la memoria RAM de Python.
 * Aceleración por Hardware: Se configurará FFmpeg para usar decodificación y codificación por hardware (NVENC si hay tarjeta NVIDIA, o QSV para Intel) para liberar el procesador central (CPU).
2. Estructura Jerárquica de Archivos
Respetando la regla de archivos menores a 300 líneas y nombres en español:
 * orquestador_edicion_principal.py (El Director)
   * Lee la lista de videos listos desde enlaces_completados.txt (creado en la Fase 1) y coordina el flujo de creación de carpetas, cálculo de tiempos y ejecución de cortes.
 * abuelo_gestor_de_carpetas_por_video.py (El Organizador)
   * Lee los metadatos (el título original de la publicación).
   * Crea una carpeta única para ese video específico dentro de un directorio principal predeterminado.
 * padre_calculadora_de_segmentos.py (El Matemático)
   * Lee la duración total del video sin cargarlo visualmente (usando ffprobe).
   * Calcula los puntos de corte exactos. Si el video dura 17 minutos, calcula: Parte 1 (0-8 min) y Parte 2 (8-17 min). Si el sobrante final es menor a 9 minutos, lo fusiona con el último bloque o lo deja íntegro según la regla de negocio.
 * hijo_procesador_de_velocidad.py (El Modificador)
   * Recibe el comando de si el video debe ir normal (1.0x), rápido (1.25x) o muy rápido (1.50x).
   * Ajusta los parámetros de FFmpeg (filtros setpts para video y atempo para audio).
 * nieto_ejecutor_ffmpeg_optimizado.py (El Obrero)
   * Recibe las instrucciones finales y lanza el proceso de edición directo en el disco (ROM). Emplea comandos de copia de flujo (-c copy) cuando la velocidad es normal (1.0x) para cortar el video en 1 segundo sin renderizar de nuevo.
3. Estrategias de Optimización (Hardware y Memoria)
Cortes sin Re-codificación (Velocidad 1.0x)
Si el usuario elige velocidad normal, el nieto_ejecutor usará el parámetro -c copy de FFmpeg. Esto simplemente "corta" el contenedor del archivo sin procesar los píxeles. Dividir un video de 1 hora en partes de 8 minutos tomará apenas un par de segundos y 0% de sobrecarga en la CPU o RAM.
Perfil de Renderizado Liviano (Velocidad 1.25x o 1.50x)
Alterar la velocidad obliga a re-codificar el video. Para que esto no consuma recursos masivos:
 * Se usará el preset ultrafast de FFmpeg.
 * Se limitará el consumo de hilos (-threads) para dejar capacidad al sistema operativo.
 * Se aplicará un bitrate controlado para mantener los archivos divididos tan livianos como el original de la Fase 1.
Nomenclatura Automática
El orquestador_edicion generará los nombres concatenando el título original limpiado y el contador de partes. Ejemplo: El_Mejor_Video_Del_Mundo_Parte_1.mp4.
Limpieza Continua (Garbage Collection Físico)
Opcionalmente, a nivel de orquestador, una vez que todas las partes de 8 minutos han sido generadas y verificadas exitosamente, se puede incluir una función que elimine el archivo del video original pesado de 1 hora para recuperar espacio inmediatamente en el disco (ROM), dejando solo las partes listas para publicar.


El objetivo de esta fase final es distribuir los clips procesados en las distintas plataformas (Facebook, TikTok, YouTube, Instagram) utilizando los metadatos originales, y asegurar que el disco duro quede completamente limpio tras confirmar el éxito de cada transacción.
Herramientas Open Source Seleccionadas
 * Automatización Web: Playwright (Reutilizado de la Fase 1). El uso de automatización web en lugar de las APIs oficiales evita los largos procesos de aprobación, cuotas estrictas y limitaciones de tokens que imponen plataformas como TikTok o Instagram.
Estructura Jerárquica de Archivos
 * orquestador_publicaciones_principal.py
   * Lee las carpetas de videos procesados y sus archivos metadatos.json. Delega el archivo a los publicadores y espera la confirmación para ordenar su eliminación.
 * abuelo_gestor_plataformas_multiplex.py
   * Instancia navegadores aislados para cada red social, asegurando que las sesiones (cookies) de TikTok no interfieran con las de YouTube, manteniendo perfiles independientes y ligeros.
 * padre_publicador_tiktok.py (y homólogos para YouTube, Instagram, Facebook)
   * Contiene la lógica específica de navegación para llegar al portal de subida de la red social correspondiente. Recibe la ruta del video y el texto del encabezado original.
 * hijo_inyector_de_metadatos_y_carga.py
   * Se encarga de arrastrar o subir el archivo .mp4, escribir el título original recuperado de la Fase 1 (añadiendo el sufijo de la parte) y pulsar los botones de publicación, utilizando selectores de accesibilidad (ARIA) y XPath relativos para evadir clases dinámicas.
 * nieto_auditor_y_limpiador_rom.py
   * Monitorea la confirmación visual de la plataforma (ej. mensaje de "Video publicado"). Solo tras validar la publicación, ejecuta la orden a nivel de sistema operativo para eliminar el clip local.
Gestión de Estados y Prevención de Pérdidas
 * Control de Subidas Asíncrono: Se implementará un registro estado_publicaciones.txt. Si el sistema publica un clip exitosamente en YouTube pero la conexión falla al subir a TikTok, el registro evita que ese mismo clip se duplique en YouTube al reiniciar el proceso.
 * Retención de Archivos ante Fallos: Si un publicador detecta un error de red o un cambio drástico en el portal de la red social, se aborta la carga y el video se marca como "Pendiente". El módulo limpiador tiene estrictamente prohibido borrar el archivo físico hasta recolectar el código de éxito de todas las plataformas elegidas por el usuario.
 * Eliminación en Cascada: Una vez que todos los clips de 8 minutos derivados de un video original han sido publicados y eliminados de forma individual, el sistema procede a eliminar la carpeta raíz que los contenía, recuperando el 100% de la capacidad de almacenamiento (ROM) para el siguiente ciclo.



