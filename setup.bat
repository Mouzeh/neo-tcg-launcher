@echo off
REM =============================================================================
REM setup.bat — Configuración automática del entorno para NeoTcg Launcher (Windows)
REM =============================================================================
REM Compatibilidad: Windows 10/11 con Python 3.10+
REM =============================================================================
setlocal enabledelayedexpansion

echo ==========================================
echo   NeoTcg Launcher — Setup (Windows)
echo ==========================================
echo.

REM --- 1. Detectar Python ---
set PYTHON_CMD=
for %%i in (python3.14 python3.13 python3.12 python3.11 python3.10 python) do (
    where %%i >nul 2>&1 && set PYTHON_CMD=%%i
)

if "!PYTHON_CMD!"=="" (
    echo [ERROR] No se encontro Python 3.10+ en el PATH.
    echo Instala Python desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('!PYTHON_CMD! --version 2^>^&1') do set PYTHON_VERSION=%%v
echo [1/5] Python encontrado: !PYTHON_VERSION!

REM --- 2. Crear/actualizar venv ---
set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv

if exist "%VENV_DIR%" (
    echo [2/5] Venv existente: !VENV_DIR!
    echo [*] Eliminando venv anterior para crear uno limpio...
    rmdir /s /q "%VENV_DIR%"
)

echo [2/5] Creando entorno virtual limpio...
!PYTHON_CMD! -m venv "%VENV_DIR%"

REM --- 3. Activar venv ---
echo [3/5] Activando venv...
call "%VENV_DIR%\Scripts\activate.bat"

REM --- 4. Instalar dependencias ---
echo [4/5] Instalando dependencias...
python -m pip install --upgrade pip -q
pip install -r "%SCRIPT_DIR%requirements.txt" -q

if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias.
    echo Comprueba tu conexion a Internet.
    pause
    exit /b 1
)

echo [✓] Dependencias instaladas correctamente.

REM --- 5. Validar imports ---
echo [5/5] Validando imports criticos...

python -c "
import sys
errors = []

try:
    import customtkinter
except ImportError as e:
    errors.append(f'customtkinter: {e}')

try:
    import requests
except ImportError as e:
    errors.append(f'requests: {e}')

try:
    import psutil
except ImportError as e:
    errors.append(f'psutil: {e}')

try:
    import tkinter
    import _tkinter
except ImportError as e:
    errors.append(f'tkinter/_tkinter: {e}')

if errors:
    for err in errors:
        print(f'FAIL: {err}', file=sys.stderr)
    sys.exit(1)
else:
    print('Todos los imports OK')
    sys.exit(0)
"

if errorlevel 1 (
    echo.
    echo [!] Reintentando instalacion de dependencias...
    pip install --upgrade --force-reinstall -r "%SCRIPT_DIR%requirements.txt" -q

    python -c "import customtkinter, requests, psutil, tkinter, _tkinter"
    if errorlevel 1 (
        echo [ERROR] No se pudieron resolver las dependencias.
        echo Revisa el output de pip y tu conexion a Internet.
        pause
        exit /b 1
    )
)

echo [✓] Todos los imports validados correctamente.

REM --- Resumen final ---
echo.
echo ==========================================
echo   Setup completado correctamente
echo ==========================================
echo.
echo Para iniciar el launcher:
echo   call venv\Scripts\activate.bat
echo   python launcher_gui.py
echo.
echo O simplemente ejecuta:
echo   launcher_gui.py  (si el venv ya esta creado)
echo.
pause
