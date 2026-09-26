@echo off
TITLE FaceDPeli — Instalador y Lanzador Automático
COLOR 0A

echo ============================================================
echo   FaceDPeli — Instalador y Lanzador del Sistema
echo ============================================================
echo.

echo [1/3] Instalando dependencias de Python desde requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo al instalar dependencias de pip.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Instalando navegador Chromium para Playwright...
python -m playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo [ADVERTENCIA] Ocurrio un aviso al instalar Chromium. Continuando...
)

echo.
echo [3/3] Iniciando Servidor Web del Panel de Control...
echo Abriendo navegador en http://127.0.0.1:5757 ...
start http://127.0.0.1:5757

python interfaz/servidor_logs.py

pause
