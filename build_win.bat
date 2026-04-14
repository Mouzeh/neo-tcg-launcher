@echo off
REM =============================================================================
REM build_win.bat — Compilar NeoTcg Launcher para Windows con PyInstaller
REM =============================================================================
setlocal enabledelayedexpansion

echo ==========================================
echo   NeoTcg Launcher — Windows Build
echo ==========================================

REM --- Verificar que el venv exista ---
if not exist "venv" (
    echo [!] Virtual environment no encontrado.
    echo [*] Ejecuta setup.bat primero.
    pause
    exit /b 1
)

REM --- Activar venv si no esta activo ---
if not defined VIRTUAL_ENV (
    echo [*] Activando venv...
    call venv\Scripts\activate.bat
)

REM --- Instalar/actualizar dependencias ---
echo [*] Verificando dependencias...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

REM --- Limpiar builds anteriores ---
echo [*] Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del /q /s *.spec 2>nul

REM --- Compilar con PyInstaller ---
echo [*] Compilando NeoTcgLauncher.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name NeoTcgLauncher ^
    launcher_gui.py

echo.
echo ==========================================
echo   Build completado!
echo   Output: dist\NeoTcgLauncher.exe
echo ==========================================
pause
