@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM   Playlist Manager - Lanzador para Windows
REM   Exportify CSV -> Nuclear Player JSON
REM ============================================================

REM Ir a la carpeta donde est este BAT
cd /d "%~dp0"

echo.
echo ============================================================
echo   Playlist Manager - Iniciando...
echo   Carpeta: %CD%
echo ============================================================
echo.

REM Verificar que existe app.py
if not exist "app.py" (
    echo [ERROR] No se encuentra app.py en esta carpeta.
    echo Asegurate de haber descomprimido TODO el proyecto en una sola carpeta.
    echo.
    pause
    exit /b 1
)

REM Crear el entorno virtual si no existe
if not exist "venv" (
    echo [1/3] Creando entorno virtual...
    py -m venv "%~dp0venv"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual con 'py'.
        echo Intentando con 'python'...
        python -m venv "%~dp0venv"
        if errorlevel 1 (
            echo [ERROR] No se encontro Python instalado.
            echo Descargalo desde: https://www.python.org/downloads/
            echo.
            pause
            exit /b 1
        )
    )
) else (
    echo [1/3] Entorno virtual ya existe.
)

REM Activar el entorno virtual
echo [2/3] Activando entorno virtual...
call "%~dp0venv\Scripts\activate.bat"

REM Instalar dependencias
echo [3/3] Verificando dependencias...
pip install -q -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Falla al instalar dependencias.
    echo.
    pause
    exit /b 1
)

REM Matar cualquier instancia previa de Python que tenga el puerto 5000 ocupado
REM (a veces queda colgada de una ejecucion anterior)
echo.
echo Limpiando instancias previas...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Abrir el navegador en segundo plano despus de 4 segundos
REM (damos tiempo a que Flask arranque)
echo Abriendo navegador...
start "" /b cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:5000"

echo.
echo ============================================================
echo   Playlist Manager iniciando...
echo.
echo   Se abrira automaticamente tu navegador en:
echo     http://127.0.0.1:5000
echo.
echo   Si no se abre, copia esa URL manualmente.
echo.
echo   Ctrl+C para detener el servidor.
echo ============================================================
echo.

python "%~dp0app.py"

REM Si llegamos aqui, el servidor se cerr. Preguntar antes de salir.
echo.
echo Servidor detenido.
pause