@echo off
setlocal

REM Ir a la carpeta donde está este BAT
cd /d "%~dp0"

REM Crear el entorno virtual si no existe
if not exist "venv" (
    echo Creando entorno virtual...
    py -m venv "%~dp0venv"
)

REM Activar el entorno virtual
call "%~dp0venv\Scripts\activate.bat"

REM Instalar dependencias
pip install -q -r "%~dp0requirements.txt"

echo.
echo ============================================================
echo   Playlist Manager iniciando en http://127.0.0.1:5000
echo   Ctrl+C para detener
echo ============================================================
echo.

python "%~dp0app.py"

pause