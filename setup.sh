#!/usr/bin/env bash
# =============================================================================
# setup.sh — Configuración automática del entorno para NeoTcg Launcher
# =============================================================================
# Compatibilidad: macOS (Homebrew + system Python) + Linux
# Python 3.10+ requerido.
# =============================================================================
set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=========================================="
echo -e "  NeoTcg Launcher — Setup"
echo -e "==========================================${NC}"
echo ""

# --- 1. Detectar sistema operativo ---
OS="$(uname -s)"
echo -e "[1/7] Sistema operativo detectado: ${GREEN}${OS}${NC}"

# --- 2. Detectar Python ---
# Prioridad: Preferir versiones estables (3.12, 3.13) sobre bleeding-edge (3.14+)
# 3.14 de Homebrew tiene bugs conocidos con pyexpat
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3.14 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}[ERROR] No se encontró Python 3.10+ en el PATH.${NC}"
    echo "Instala Python desde https://www.python.org/downloads/ o con:"
    if [ "$OS" = "Darwin" ]; then
        echo "  brew install python"
    else
        echo "  sudo apt install python3    (Debian/Ubuntu)"
        echo "  sudo dnf install python3    (Fedora)"
    fi
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1)
echo -e "[2/7] Python encontrado: ${GREEN}${PYTHON_VERSION}${NC}"

# Validar versión mínima (3.10)
PY_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}[ERROR] Python 3.10+ es requerido. Versión encontrada: ${PYTHON_VERSION}${NC}"
    exit 1
fi

# Validar que módulos críticos funcionen (detectar Python de Homebrew roto)
echo -e "[2.5/7] Validando integridad de Python..."
PYTHON_OK=$("$PYTHON_CMD" -c "
import sys
try:
    # Módulos esenciales para venv y pip
    import pyexpat
    import zipimport
    import zlib
    import ssl
    print('OK')
except ImportError as e:
    print(f'FAIL: {e}')
" 2>&1) || true

if [[ "$PYTHON_OK" != "OK" ]]; then
    echo -e "${RED}[ERROR] Tu instalación de Python está dañada: ${PYTHON_OK}${NC}"
    echo ""
    if [ "$OS" = "Darwin" ]; then
        echo "Esto ocurre frecuentemente con Homebrew tras actualizaciones de macOS."
        echo "La causa más común es un conflicto entre libexpat del sistema y la de Homebrew."
        echo ""

        # Primero: buscar un Python alternativo que SÍ funcione
        for alt_cmd in python3.12 python3.11 python3.10; do
            if command -v "$alt_cmd" &>/dev/null; then
                ALT_OK=$("$alt_cmd" -c "import pyexpat, zlib, ssl; print('OK')" 2>&1) || true
                if [[ "$ALT_OK" == "OK" ]]; then
                    echo -e "${GREEN}[✓] Encontrado Python funcional: $alt_cmd ($("$alt_cmd" --version 2>&1))${NC}"
                    echo -e "${YELLOW}[*] Usando $alt_cmd en lugar de $PYTHON_CMD${NC}"
                    PYTHON_CMD="$alt_cmd"
                    PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1)
                    PY_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
                    PY_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")
                    echo -e "[2/7] Python encontrado: ${GREEN}${PYTHON_VERSION}${NC}"
                    echo -e "${GREEN}[✓] Python íntegro, todos los módulos OK.${NC}"
                    # Saltar a la sección de Tkinter
                    goto_tkinter=1
                    break
                fi
            fi
        done

        if [ "${goto_tkinter:-0}" -ne 1 ]; then
            # No hay alternativa funcional, intentar reparar
            if command -v brew &>/dev/null; then
                echo -e "${YELLOW}[*] Intentando reparar: reinstalando expat + Python desde Homebrew...${NC}"
                
                brew reinstall expat 2>/dev/null || brew install expat 2>/dev/null || true
                brew reinstall python@${PY_MAJOR}.${PY_MINOR} 2>/dev/null || true

                PYTHON_OK2=$("$PYTHON_CMD" -c "import pyexpat, zipimport, zlib, ssl; print('OK')" 2>&1) || true

                if [[ "$PYTHON_OK2" == "OK" ]]; then
                    echo -e "${GREEN}[✓] Reparación exitosa. Python funciona correctamente.${NC}"
                else
                    echo -e "${RED}[ERROR] La reparación automática no funcionó.${NC}"
                    echo ""
                    echo "Ejecuta manualmente:"
                    echo "  brew reinstall expat"
                    echo "  brew reinstall python@${PY_MAJOR}.${PY_MINOR}"
                    echo ""
                    echo "O usa el instalador oficial: https://www.python.org/downloads/"
                    exit 1
                fi
            else
                echo "Instala Homebrew (https://brew.sh) o Python oficial."
                exit 1
            fi
        fi
    else
        echo "Reinstala Python desde tu gestor de paquetes."
        exit 1
    fi
else
    echo -e "${GREEN}[✓] Python íntegro, todos los módulos OK.${NC}"
fi

# --- 3. macOS: verificar e instalar python-tk si es necesario ---
if [ "$OS" = "Darwin" ]; then
    echo -e "[3/7] Verificando Tkinter en macOS..."

    # Probar import de tkinter y _tkinter
    TKINTER_OK=$("$PYTHON_CMD" -c "
import sys
try:
    import tkinter
    import _tkinter
    print('OK')
except ImportError as e:
    print(f'FAIL: {e}')
" 2>&1) || true

    if [[ "$TKINTER_OK" != "OK" ]]; then
        echo -e "${YELLOW}[!] Tkinter no está disponible: ${TKINTER_OK}${NC}"
        echo -e "[*] Intentando instalar python-tk vía Homebrew..."

        if command -v brew &>/dev/null; then
            # Instalar la versión de python-tk que coincida con el Python activo
            # python-tk@3.13 para Python 3.13, python-tk@3.12 para Python 3.12, etc.
            # 'python-tk' sin versión instala para la última versión de Homebrew
            TK_PACKAGE="python-tk@${PY_MAJOR}.${PY_MINOR}"
            echo -e "[*] Instalando: ${TK_PACKAGE}..."
            brew install "$TK_PACKAGE" 2>/dev/null || {
                # Fallback: intentar sin versión
                echo -e "[*] ${TK_PACKAGE} no encontrado, probando python-tk genérico..."
                brew install python-tk
            }

            # Re-validar Tkinter tras la instalación
            TKINTER_OK2=$("$PYTHON_CMD" -c "
import sys
try:
    import tkinter
    import _tkinter
    print('OK')
except ImportError as e:
    print(f'FAIL: {e}')
" 2>&1) || true

            if [[ "$TKINTER_OK2" == "OK" ]]; then
                echo -e "${GREEN}[✓] python-tk instalado y funcional.${NC}"
            else
                echo -e "${RED}[ERROR] Tkinter sigue sin funcionar tras la instalación.${NC}"
                echo "Intenta: brew reinstall python-tk@${PY_MAJOR}.${PY_MINOR}"
                echo "O reinstala Python completo: brew reinstall python@${PY_MAJOR}.${PY_MINOR}"
                exit 1
            fi
        else
            echo -e "${RED}[ERROR] Homebrew no está instalado.${NC}"
            echo "Instala Homebrew primero: https://brew.sh"
            echo "O instala Python desde python.org que incluye Tkinter."
            exit 1
        fi
    else
        echo -e "${GREEN}[✓] Tkinter disponible.${NC}"
    fi
else
    echo -e "[3/7] Tkinter: ${GREEN}verificado (Linux)${NC}"
fi

# --- 4. Crear/actualizar venv ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo -e "[4/7] Venv existente: ${YELLOW}${VENV_DIR}${NC}"
    echo -e "[*] Eliminando venv anterior para crear uno limpio..."
    rm -rf "$VENV_DIR"
fi

echo -e "[4/7] Creando entorno virtual limpio..."

# Intentar crear venv con pip. En Python 3.14+, ensurepip puede fallar.
"$PYTHON_CMD" -m venv "$VENV_DIR" || {
    echo -e "${YELLOW}[!] venv sin pip detectado. Instalando pip manualmente...${NC}"
    "$PYTHON_CMD" -m venv --without-pip "$VENV_DIR" 2>/dev/null || {
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    }
    # Descargar get-pip.py como fallback
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    "$VENV_DIR/bin/python" /tmp/get-pip.py -q
    rm -f /tmp/get-pip.py
}

# --- 5. Activar venv e instalar dependencias ---
echo -e "[5/7] Activando venv e instalando dependencias..."

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Si pip no está disponible, instalarlo con get-pip.py
if ! command -v pip &>/dev/null; then
    echo -e "${YELLOW}[!] pip no disponible. Instalando con get-pip.py...${NC}"
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    "$PYTHON_CMD" /tmp/get-pip.py -q
    rm -f /tmp/get-pip.py
fi

pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q

echo -e "${GREEN}[✓] Dependencias instaladas correctamente.${NC}"

# --- 6. Validar imports ---
echo -e "[6/7] Validando imports críticos..."

VALIDATION_ERRORS=$("$PYTHON_CMD" -c "
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
" 2>&1) || VALIDATION_EXIT=$?

if [ "${VALIDATION_EXIT:-0}" -ne 0 ]; then
    echo -e "${RED}[ERROR] Validación de imports fallida:${NC}"
    echo "$VALIDATION_ERRORS"
    echo ""
    echo -e "${YELLOW}[*] Intentando resolver dependencias nuevamente...${NC}"
    pip install --upgrade --force-reinstall -r "$SCRIPT_DIR/requirements.txt"

    # Re-validar
    if ! "$PYTHON_CMD" -c "import customtkinter, requests, psutil, tkinter, _tkinter"; then
        echo -e "${RED}[ERROR] No se pudieron resolver las dependencias.${NC}"
        echo "Revisa el output de pip y tu conexión a Internet."
        exit 1
    fi
    echo -e "${GREEN}[✓] Reinstalación exitosa.${NC}"
else
    echo -e "${GREEN}[✓] ${VALIDATION_ERRORS}${NC}"
fi

# --- Resumen final ---
echo ""
echo -e "${CYAN}=========================================="
echo -e "  Setup completado correctamente"
echo -e "==========================================${NC}"
echo ""
echo -e "Para iniciar el launcher:"
echo -e "  ${GREEN}source venv/bin/activate${NC}"
echo -e "  ${GREEN}python launcher_gui.py${NC}"
echo ""
echo -e "O simplemente ejecuta:"
echo -e "  ${GREEN}./launcher_gui.py${NC} (si el venv ya está creado)"
echo ""
