#!/usr/bin/env bash
# =============================================================================
# release_helper.sh — Genera version.json con SHA256 reales para NeoTcg
#
# Uso:
#   ./release_helper.sh 1.2.0
#   ./release_helper.sh 1.2.0 /ruta/a/zips
# =============================================================================
set -euo pipefail

REPO="Mouzeh/launcher"

# --- Argumentos ---
VERSION="${1:-}"
SEARCH_DIR="${2:-.}"

if [ -z "$VERSION" ]; then
    echo "Uso: $0 <versión> [directorio_con_zips]"
    echo "Ej:  $0 1.2.0"
    echo "     $0 1.2.0 /Users/mouzeh/builds"
    exit 1
fi

# Normalizar versión (quitar 'v' si existe)
VERSION="${VERSION#v}"

WIN_ZIP="neo-tcg-${VERSION}-win.zip"
MAC_ZIP="neo-tcg-${VERSION}-mac.zip"

echo ""
echo "============================================================"
echo "  NeoTcg Release Helper (bash)"
echo "  Repo: ${REPO}"
echo "  Versión: v${VERSION}"
echo "  Buscando en: ${SEARCH_DIR}"
echo "============================================================"
echo ""

# --- Buscar ZIPs ---
WIN_PATH="${SEARCH_DIR}/${WIN_ZIP}"
MAC_PATH="${SEARCH_DIR}/${MAC_ZIP}"

MISSING=0

if [ ! -f "$WIN_PATH" ]; then
    echo "  ✗ No encontrado: ${WIN_ZIP}"
    MISSING=1
else
    echo "  ✓ Encontrado: ${WIN_ZIP}"
fi

if [ ! -f "$MAC_PATH" ]; then
    echo "  ✗ No encontrado: ${MAC_ZIP}"
    MISSING=1
else
    echo "  ✓ Encontrado: ${MAC_ZIP}"
fi

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "  Coloca los ZIPs en: ${SEARCH_DIR}"
    echo "  Nombres esperados:"
    echo "    - ${WIN_ZIP}"
    echo "    - ${MAC_ZIP}"
    exit 1
fi

echo ""
echo "[1] Calculando SHA256..."

# --- Calcular SHA256 ---
if command -v shasum &> /dev/null; then
    WIN_SHA=$(shasum -a 256 "$WIN_PATH" | awk '{print $1}')
    MAC_SHA=$(shasum -a 256 "$MAC_PATH" | awk '{print $1}')
elif command -v sha256sum &> /dev/null; then
    WIN_SHA=$(sha256sum "$WIN_PATH" | awk '{print $1}')
    MAC_SHA=$(sha256sum "$MAC_PATH" | awk '{print $1}')
else
    echo "  ✗ No se encontró shasum ni sha256sum. Instala uno de ellos."
    exit 1
fi

# --- Calcular tamaños ---
if command -v stat &> /dev/null; then
    # macOS stat
    WIN_SIZE=$(stat -f%z "$WIN_PATH" 2>/dev/null || stat -c%s "$WIN_PATH" 2>/dev/null || echo 0)
    MAC_SIZE=$(stat -f%z "$MAC_PATH" 2>/dev/null || stat -c%s "$MAC_PATH" 2>/dev/null || echo 0)
fi

WIN_MB=$((WIN_SIZE / 1024 / 1024))
MAC_MB=$((MAC_SIZE / 1024 / 1024))

echo "  ✓ win: ${WIN_SHA:0:16}...  (${WIN_MB} MB)"
echo "  ✓ mac: ${MAC_SHA:0:16}...  (${MAC_MB} MB)"

# --- Generar version.json ---
echo ""
echo "[2] Generando version.json..."

cat > version.json <<EOF
{
  "version": "${VERSION}",
  "builds": {
    "windows": {
      "url": "https://github.com/${REPO}/releases/download/v${VERSION}/${WIN_ZIP}",
      "sha256": "${WIN_SHA}"
    },
    "macos": {
      "url": "https://github.com/${REPO}/releases/download/v${VERSION}/${MAC_ZIP}",
      "sha256": "${MAC_SHA}"
    }
  }
}
EOF

echo "  ✓ version.json generado"

# --- Mostrar instrucciones ---
echo ""
echo "============================================================"
echo "  Comandos para publicar"
echo "============================================================"
echo ""

if command -v gh &> /dev/null; then
    echo "# Con GitHub CLI:"
    echo ""
    echo "gh release create \"v${VERSION}\" \\"
    echo "    --title \"NeoTcg v${VERSION}\" \\"
    echo "    --generate-notes \\"
    echo "    \"${WIN_ZIP}\" \"${MAC_ZIP}\" \"version.json\""
    echo ""
else
    echo "# Instala GitHub CLI: https://cli.github.com/"
    echo ""
    echo "# O manualmente vía web:"
    echo "  1. Ve a: https://github.com/${REPO}/releases/new"
    echo "  2. Tag: v${VERSION}"
    echo "  3. Sube: ${WIN_ZIP}, ${MAC_ZIP}, version.json"
    echo "  4. Publica"
fi

echo ""
echo "============================================================"
