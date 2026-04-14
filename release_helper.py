#!/usr/bin/env python3
"""
release_helper.py — Genera version.json con SHA256 reales y muestra
los comandos exactos para publicar el release en GitHub.

Uso:
    python release_helper.py 1.2.0
    python release_helper.py 1.2.0 --dir /ruta/a/zips
    python release_helper.py 1.2.0 --publish   # requiere gh CLI autenticado
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# =============================================================================
#  CONFIG
# =============================================================================
GITHUB_REPO = "Mouzeh/launcher"
GITHUB_BASE = f"https://github.com/{GITHUB_REPO}/releases/download"
ZIP_PATTERN = "neo-tcg-{version}-{platform}.zip"  # e.g. neo-tcg-1.2.0-win.zip

# =============================================================================
#  FUNCIONES
# =============================================================================
def sha256_file(path: Path) -> str:
    """Calcula SHA256 hex de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_zip(version: str, platform_suffix: str, search_dir: Path) -> Path | None:
    """
    Busca un ZIP del juego. Prioriza estos patrones (en orden):
      1. neo-tcg-{version}-{suffix}.zip   (convention release)
      2. NeoTcg{Suffix}.zip                (Godot default export)
      3. Cualquier .zip que contenga version + suffix
    """
    # Patrón 1: convención de releases
    filename = f"neo-tcg-{version}-{platform_suffix}.zip"
    candidate = search_dir / filename
    if candidate.exists():
        return candidate

    # Patrón 2: nombre directo de export Godot (ej: NeoTcgMac.zip)
    suffix_cap = platform_suffix.upper()  # "win" → "WIN", "mac" → "MAC"
    filename2 = f"NeoTcg{suffix_cap}.zip"
    candidate2 = search_dir / filename2
    if candidate2.exists():
        return candidate2

    # Patrón 3: búsqueda flexible
    for f in search_dir.iterdir():
        if f.is_file() and f.suffix == ".zip" and platform_suffix.lower() in f.name.lower():
            return f

    return None


def build_version_json(version: str, search_dir: Path) -> dict | None:
    """
    Busca los ZIPs, calcula SHA256 y genera version.json.
    Devuelve el dict generado o None si falta algún archivo.
    """
    result = {
        "version": version,
        "builds": {}
    }

    platforms = {
        "windows": "win",
        "macos": "mac",
    }

    all_found = True
    for plat, suffix in platforms.items():
        zip_path = find_zip(version, suffix, search_dir)
        if not zip_path:
            print(f"  ✗ No se encontró ZIP para {plat} (buscando *{suffix}* en {search_dir})")
            all_found = False
            continue

        file_size = zip_path.stat().st_size
        sha = sha256_file(zip_path)
        download_url = f"{GITHUB_BASE}/v{version}/{zip_path.name}"

        result["builds"][plat] = {
            "url": download_url,
            "sha256": sha,
            "filename": zip_path.name,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 1)
        }
        print(f"  ✓ {plat}: {zip_path.name}  ({result['builds'][plat]['size_mb']} MB)  SHA256: {sha[:16]}...")

    if not all_found:
        return None

    return result


def print_gh_commands(version: str):
    """Muestra los comandos gh CLI para crear y subir el release."""
    win_zip = f"neo-tcg-{version}-win.zip"
    mac_zip = f"neo-tcg-{version}-mac.zip"

    print(f"""
{'=' * 60}
  Comandos para publicar con GitHub CLI (gh)
{'=' * 60}

# 1. Crear el release (tag v{version}):
gh release create "v{version}" \\
    --title "NeoTcg v{version}" \\
    --generate-notes \\
    --draft

# 2. Subir los assets:
gh release upload "v{version}" \\
    "{win_zip}" \\
    "{mac_zip}" \\
    "version.json"

# 3. Publicar (quitar draft):
gh release edit "v{version}" --draft=false

# O todo en un solo comando si los archivos ya existen:
gh release create "v{version}" \\
    --title "NeoTcg v{version}" \\
    --generate-notes \\
    "{win_zip}" "{mac_zip}" "version.json"
""")


def print_manual_instructions(version: str):
    """Instrucciones manuales si no se tiene gh CLI."""
    print(f"""
{'=' * 60}
  Instrucciones manuales (GitHub Web)
{'=' * 60}

1. Ve a: https://github.com/{GITHUB_REPO}/releases/new

2. Tag version:  v{version}

3. Release title: NeoTcg v{version}

4. Sube como archivos adjuntos:
   - neo-tcg-{version}-win.zip
   - neo-tcg-{version}-mac.zip
   - version.json  (generado en este directorio)

5. Marca "Set as the latest release" si corresponde.

6. Publica.
""")


def publish_release(version: str, version_json_path: Path, search_dir: Path, vdata: dict):
    """Intenta crear y publicar el release automáticamente con gh CLI."""
    # Usar los nombres reales de los archivos encontrados en vdata
    files_to_upload = [str(version_json_path)]

    for plat_key in ("windows", "macos"):
        plat_data = vdata.get("builds", {}).get(plat_key, {})
        fname = plat_data.get("filename")
        if fname:
            fpath = search_dir / fname
            if fpath.exists():
                files_to_upload.append(str(fpath))
            else:
                print(f"  ⚠ {fname} no encontrado en {search_dir}")

    # Verificar que gh está disponible y autenticado
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print("  ✗ gh CLI no está autenticado. Ejecuta: gh auth login")
            return False
    except FileNotFoundError:
        print("  ✗ gh CLI no está instalado. Instálalo: https://cli.github.com/")
        return False

    # Crear release
    cmd = [
        "gh", "release", "create", f"v{version}",
        "--title", f"NeoTcg v{version}",
        "--generate-notes",
    ] + files_to_upload

    print(f"  → Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"  ✗ Error al crear release: {result.stderr}")
        return False

    print(f"  ✓ Release v{version} creado y publicado en https://github.com/{GITHUB_REPO}/releases/tag/v{version}")
    return True


# =============================================================================
#  MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Genera version.json con SHA256 y ayuda a publicar releases de NeoTcg."
    )
    parser.add_argument("version", help="Número de versión, ej: 1.2.0")
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default=".",
        help="Directorio donde están los ZIPs del juego (por defecto: directorio actual)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="version.json",
        help="Ruta del archivo version.json de salida (por defecto: version.json)"
    )
    parser.add_argument(
        "--publish", "-p",
        action="store_true",
        help="Publicar automáticamente con gh CLI"
    )
    parser.add_argument(
        "--copy-to-project",
        action="store_true",
        help="Copiar version.json al directorio del launcher"
    )

    args = parser.parse_args()

    version = args.version
    search_dir = Path(args.dir).resolve()
    output_path = Path(args.output)

    if not version.startswith("v"):
        version_tag = f"v{version}"
    else:
        version_tag = version
        version = version[1:]  # strip 'v' para nombres de archivo

    print(f"""
{'=' * 60}
  NeoTcg Release Helper
  Repo: {GITHUB_REPO}
  Versión: {version_tag}
  Buscando ZIPs en: {search_dir}
{'=' * 60}
""")

    # Generar version.json
    print("[1] Buscando ZIPs y calculando SHA256...")
    vdata = build_version_json(version, search_dir)

    if not vdata:
        print("\n  ✗ No se encontraron todos los ZIPs necesarios.")
        print(f"  Asegúrate de tener en {search_dir}:")
        print(f"    - neo-tcg-{version}-win.zip")
        print(f"    - neo-tcg-{version}-mac.zip")
        print()
        print("  Puedes exportar desde Godot y crear los ZIPs manualmente,")
        print("  o usar este script con --dir apuntando al directorio correcto.")
        sys.exit(1)

    # Escribir version.json
    print(f"\n[2] Escribiendo {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vdata, f, indent=2, ensure_ascii=False)
    print(f"  ✓ {output_path} generado ({output_path.stat().st_size} bytes)")

    # Copiar al proyecto del launcher si se solicita
    if args.copy_to_project:
        launcher_dir = Path(__file__).parent
        dest = launcher_dir / "version_template.json"
        shutil.copy2(output_path, dest)
        print(f"  ✓ Copiado a {dest}")

    # Publicar o mostrar instrucciones
    if args.publish:
        print("\n[3] Publicando release con gh CLI...")
        success = publish_release(version, output_path, search_dir, vdata)
        if not success:
            print("\n  Fallo automático. Usa las instrucciones manuales de abajo.")
            print_gh_commands(version)
    else:
        print("\n[3] Listo. Usa uno de estos métodos para publicar:\n")

        # Detectar si gh CLI está disponible
        if shutil.which("gh"):
            print_gh_commands(version)
        else:
            print_manual_instructions(version)

    print(f"{'=' * 60}")
    print(f"  Recuerda: actualiza LAUNCHER_VERSION en launcher_gui.py")
    print(f"  si haces cambios en el propio launcher.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
