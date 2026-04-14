#!/usr/bin/env bash
# =============================================================================
# build_mac.sh — Compilar NeoTcg Launcher para macOS con PyInstaller
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  NeoTcg Launcher — macOS Build"
echo "=========================================="

# --- Verificar que el venv exista ---
if [ ! -d "venv" ]; then
    echo "[!] Virtual environment no encontrado."
    echo "[*] Ejecuta ./setup.sh primero."
    exit 1
fi

# --- Activar venv si no está activo ---
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "[*] Activando venv..."
    source venv/bin/activate
fi

# --- Instalar/actualizar dependencias ---
echo "[*] Verificando dependencias..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# --- Limpiar builds anteriores ---
echo "[*] Limpiando builds anteriores..."
rm -rf build/ dist/ *.spec

# --- Compilar con PyInstaller ---
echo "[*] Compilando NeoTcgLauncher.app..."
pyinstaller \
    --onefile \
    --windowed \
    --name NeoTcgLauncher \
    --bundle-id com.neotcg.launcher \
    --hidden-import=tkinter \
    --hidden-import=_tkinter \
    launcher_gui.py

echo ""
echo "=========================================="
echo "  Build completado!"
echo "  Output: dist/NeoTcgLauncher.app"
echo "=========================================="
