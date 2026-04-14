#!/usr/bin/env python3
"""
NeoTcg Launcher - Auto-updater and game launcher for Windows and macOS.
Downloads the latest release from GitHub, verifies integrity, and launches the game.

No GUI — lightweight console-only design for maximum stability.
"""

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

GITHUB_REPO = "Mouzeh/launcher"

LAUNCHER_VERSION = "1.0.0"
CHUNK_SIZE = 8192  # 8 KB read chunks for download
DOWNLOAD_TIMEOUT = 300  # 5 minutes total download timeout
REQUEST_TIMEOUT = 15  # seconds for API / small requests

# Configure logging with [NeoTcg] prefix
logging.basicConfig(
    level=logging.INFO,
    format="[NeoTcg] %(message)s",
)
log = logging.getLogger("NeoTcgLauncher")


def get_data_dir() -> Path:
    """
    Return the platform-appropriate data directory using appdirs logic.
    Windows → %APPDATA%/NeoTcg
    macOS   → ~/Library/Application Support/NeoTcg
    Linux   → ~/.local/share/NeoTcg (fallback)
    """
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "NeoTcg"


def github_api_latest_release(repo: str) -> dict:
    """
    Query the GitHub Releases API and return the latest (top) release JSON.
    Raises on HTTP error or malformed response.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "NeoTcgLauncher")

    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"GitHub API request failed: {e.code} {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Network error contacting GitHub API: {e.reason}") from e


def find_asset(release: dict, name_suffix: str) -> dict:
    """
    Find a release asset whose filename ends with *name_suffix*.
    e.g. name_suffix="-win.zip" or "-mac.zip"
    """
    for asset in release.get("assets", []):
        if asset["name"].endswith(name_suffix):
            return asset
    raise RuntimeError(
        f"No release asset ending with '{name_suffix}' found. "
        f"Available: {[a['name'] for a in release.get('assets', [])]}"
    )


def download_file_with_resume(url: str, dest: Path, sha256_expected: str):
    """
    Download *url* to *dest* supporting resume (Range header).
    Shows a console progress bar. Aborts if SHA256 mismatches.
    """
    dest = Path(dest)
    existing_size = dest.stat().st_size if dest.exists() else 0

    req = Request(url)
    req.add_header("User-Agent", "NeoTcgLauncher")
    if existing_size > 0:
        req.add_header("Range", f"bytes={existing_size}-")

    try:
        with urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            status_code = resp.status
            content_length = int(resp.headers.get("Content-Length", 0))
            total = content_length + existing_size if status_code == 206 else content_length

            mode = "ab" if status_code == 206 else "wb"
            downloaded = existing_size if status_code == 206 else 0

            with open(dest, mode) as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    _print_progress(downloaded, total)

            print()  # newline after progress
    except HTTPError as e:
        raise RuntimeError(f"Download failed: {e.code} {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Network error during download: {e.reason}") from e
    except KeyboardInterrupt:
        log.info("Download interrupted by user.")
        raise

    # --- SHA256 verification ---
    log.info("Verifying SHA256 integrity...")
    sha256_actual = _sha256_file(dest)
    if sha256_actual != sha256_expected:
        raise RuntimeError(
            f"SHA256 mismatch!\n"
            f"  Expected: {sha256_expected}\n"
            f"  Got:      {sha256_actual}\n"
            f"The download may be corrupted. Delete {dest} and retry."
        )
    log.info("SHA256 verified OK.")


def _sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _print_progress(downloaded: int, total: int):
    """Render a simple console progress bar."""
    if total == 0:
        return
    pct = min(downloaded / total, 1.0)
    bar_len = 40
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    mb_dl = downloaded / (1024 * 1024)
    mb_total = total / (1024 * 1024)
    print(f"\r  [{bar}] {pct:5.1%}  {mb_dl:7.1f}/{mb_total:7.1f} MB", end="", flush=True)


def check_disk_space(path: Path, required_bytes: int):
    """Raise RuntimeError if not enough free disk space."""
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        needed_mb = required_bytes / (1024 * 1024)
        free_mb = usage.free / (1024 * 1024)
        raise RuntimeError(
            f"Insufficient disk space. Need ~{needed_mb:.0f} MB, free: {free_mb:.0f} MB"
        )


def create_backup(game_dir: Path, backup_dir: Path):
    """Copy current game directory to .backup/ before updating."""
    if game_dir.exists() and any(game_dir.iterdir()):
        log.info("Creating backup of current version...")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(game_dir, backup_dir)
        log.info(f"Backup saved to {backup_dir}")


def restore_backup(backup_dir: Path, game_dir: Path):
    """Restore from .backup/ after a failed extraction."""
    if backup_dir.exists():
        log.warning("Restoring from backup...")
        if game_dir.exists():
            shutil.rmtree(game_dir)
        shutil.copytree(backup_dir, game_dir)
        log.info("Backup restored successfully.")


def extract_zip(zip_path: Path, dest: Path):
    """
    Extract *zip_path* into *dest*, overwriting existing files.
    Raises on corrupt/invalid ZIP.
    """
    log.info(f"Extracting {zip_path.name}...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad_file = zf.testzip()
            if bad_file is not None:
                raise RuntimeError(f"Corrupt file inside ZIP: {bad_file}")
            zf.extractall(dest)
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"ZIP file is corrupt or incomplete: {e}") from e
    log.info("Extraction complete.")


def save_installed_version(game_dir: Path, version: str):
    """Write the installed version string to a file."""
    version_file = game_dir / "installed_version.txt"
    version_file.write_text(version.strip())
    log.info(f"Installed version recorded: {version}")


def get_installed_version(game_dir: Path) -> str:
    """Read the installed version string, or return 'none'."""
    version_file = game_dir / "installed_version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    return "none"


def launch_game(game_dir: Path):
    """
    Launch the game binary.
    Windows → Pokemon Tcg.exe
    macOS   → open -a Pokemon Tcg.app
    """
    system = platform.system()
    log.info("Launching game...")

    if system == "Windows":
        exe = game_dir / "Pokemon Tcg.exe"
        if not exe.exists():
            raise RuntimeError(f"Game executable not found: {exe}")
        subprocess.Popen([str(exe)], cwd=str(game_dir))
    elif system == "Darwin":
        app_bundle = game_dir / "Pokemon Tcg.app"
        if app_bundle.exists():
            subprocess.Popen(["open", "-a", str(app_bundle)])
        else:
            # Fallback: try to find any .app bundle
            apps = list(game_dir.glob("*.app"))
            if apps:
                subprocess.Popen(["open", "-a", str(apps[0])])
            else:
                raise RuntimeError(
                    f"Pokemon Tcg.app not found in {game_dir}. "
                    "Make sure the macOS build is packaged as a .app bundle."
                )
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    log.info("Game launched successfully!")


def main():
    """Main entry point for the NeoTcg Launcher."""
    print(f"========================================")
    print(f"  NeoTcg Launcher v{LAUNCHER_VERSION}")
    print(f"========================================")
    print()

    try:
        # 1. Determine data directory
        data_dir = get_data_dir()
        game_dir = data_dir / "game"
        backup_dir = data_dir / ".backup"
        data_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"Game directory: {game_dir}")

        installed_ver = get_installed_version(game_dir)
        log.info(f"Currently installed: {installed_ver}")

        # 2. Fetch latest release from GitHub
        log.info("Checking for updates on GitHub...")
        release = github_api_latest_release(GITHUB_REPO)
        remote_version = release.get("tag_name", "unknown")

        if remote_version == installed_ver:
            log.info(f"Already up to date (v{remote_version}). Launching...")
            if game_dir.exists():
                launch_game(game_dir)
            else:
                log.error("Game directory missing despite version record. Please re-run launcher.")
            return

        log.info(f"New version available: {remote_version} (you have {installed_ver})")

        # 3. Determine platform suffix and find the correct asset
        system = platform.system()
        if system == "Windows":
            suffix = "-win.zip"
        elif system == "Darwin":
            suffix = "-mac.zip"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

        asset = find_asset(release, suffix)
        download_url = asset["browser_download_url"]
        file_size = asset.get("size", 0)

        # 4. Fetch version.json from assets to get SHA256
        log.info("Fetching version.json for build metadata...")
        version_json_asset = None
        for a in release.get("assets", []):
            if a["name"] == "version.json":
                version_json_asset = a
                break

        sha256_expected = ""
        if version_json_asset:
            try:
                with urlopen(version_json_asset["browser_download_url"], timeout=REQUEST_TIMEOUT) as vresp:
                    vdata = json.loads(vresp.read().decode("utf-8"))
                    plat_key = "windows" if system == "Windows" else "macos"
                    sha256_expected = vdata.get("builds", {}).get(plat_key, {}).get("sha256", "")
            except Exception as e:
                log.warning(f"Could not fetch version.json: {e}")

        # Fallback: use tag-based naming convention for the local zip
        zip_filename = f"neo-tcg-{remote_version.lstrip('v')}-{suffix.replace('.zip', '').lstrip('-')}.zip"
        zip_path = data_dir / zip_filename

        # 5. Check disk space
        check_disk_space(data_dir, file_size * 2)  # need room for zip + extraction

        # 6. Download
        if sha256_expected:
            log.info(f"Downloading {asset['name']} ({file_size / (1024*1024):.1f} MB)...")
            download_file_with_resume(download_url, zip_path, sha256_expected)
        else:
            log.warning("No SHA256 found in version.json — skipping integrity check (not recommended).")
            # Still download, but without hash verification
            download_file_with_resume(download_url, zip_path, "")

        # 7. Backup current version
        if game_dir.exists():
            create_backup(game_dir, backup_dir)

        # 8. Extract
        game_dir.mkdir(parents=True, exist_ok=True)
        try:
            extract_zip(zip_path, game_dir)
        except RuntimeError as e:
            log.error(f"Extraction failed: {e}")
            restore_backup(backup_dir, game_dir)
            raise

        # 9. Save installed version
        save_installed_version(game_dir, remote_version)

        # 10. Clean up
        if zip_path.exists():
            zip_path.unlink()
            log.info("Temporary ZIP file removed.")

        # 11. Launch
        launch_game(game_dir)

    except KeyboardInterrupt:
        log.info("\nOperation cancelled by user.")
        _wait_on_error()
        sys.exit(130)
    except RuntimeError as e:
        log.error(f"Error: {e}")
        _wait_on_error()
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        _wait_on_error()
        sys.exit(1)


def _wait_on_error():
    """On Windows, wait for Enter before closing the console window."""
    if platform.system() == "Windows":
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
