#!/usr/bin/env python3
"""
NeoTcg Launcher — GUI Edition (UI Mejorada + Robusta)
Flujo estilo Valorant/Riot: comprobar → actualizar → jugar.
Interfaz oscura, moderna y limpia. 100% autocontenido.

Compatibilidad: Python 3.10+ | macOS Sonoma/Ventura | Windows 10/11

Dependencias: customtkinter, requests, psutil
Sin appdirs. Rutas nativas con pathlib + os.
"""

import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from pathlib import Path

import customtkinter as ctk
import psutil
import requests

# =============================================================================
#  CONFIGURACIÓN — personaliza estos valores antes de compilar
# =============================================================================
GITHUB_REPO = "Mouzeh/launcher"
APP_NAME = "NeoTcg"
LAUNCHER_VERSION = "2.1.0"

# Colores y estilo visual
COLOR_BG = "#121212"
COLOR_ACCENT = "#0096ff"
COLOR_ACCENT_HOVER = "#0077cc"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#22c55e"
COLOR_WARNING = "#cc7a00"
COLOR_ERROR = "#ef4444"
COLOR_SURFACE = "#1e1e1e"
COLOR_DISCORD = "#5865F2"      # [UI MEJORADA] Color oficial Discord
COLOR_WEB = "#2a2a2a"          # [UI MEJORADA] Color botón web oficial

# [UI MEJORADA] URLs externas — edita estas URLs según necesidad
URL_DISCORD = "https://discord.gg/QQdgeba4"
URL_WEB = "https://www.neotcg.cl"
URL_INSTAGRAM = "https://instagram.com/NEOTCG.cl"

# Umbrales de red
REQUEST_TIMEOUT = 15          # segundos para peticiones API pequeñas
DOWNLOAD_TIMEOUT = 600         # segundos para descarga del ZIP (~700 MB)
CHUNK_SIZE = 131072            # 128 KB por chunk de streaming

# Nombres de ejecutables por plataforma
EXE_NAME_WIN = "Pokemon Tcg.exe"
APP_NAME_MAC = "Pokemon Tcg.app"

# =============================================================================
#  FUNCIONES AUXILIARES DE RUTAS (sin appdirs)
# =============================================================================
def get_data_dir() -> Path:
    """
    Devuelve el directorio de datos nativo de cada plataforma.
    macOS → ~/Library/Application Support/NeoTcg
    Windows → %APPDATA%\\NeoTcg
    Linux → ~/.local/share/NeoTcg (fallback)
    """
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / ".local" / "share"
    return base / APP_NAME


def validate_tkinter_available():
    """
    Valida que Tkinter esté disponible antes de iniciar la UI.
    En macOS con Homebrew, python-tk debe instalarse por separado.
    """
    try:
        import tkinter
        import _tkinter  # noqa: F401
    except ImportError:
        system = platform.system()
        msg = "ERROR: Tkinter no está disponible.\n\n"
        if system == "Darwin":
            msg += (
                "En macOS con Homebrew, Python no incluye Tk por defecto.\n"
                "Ejecuta en terminal:\n    brew install python-tk\n\n"
                "O ejecuta ./setup.sh que lo hará automáticamente."
            )
        elif system == "Linux":
            msg += (
                "En Linux, instala el paquete correspondiente:\n"
                "    sudo apt install python3-tk    (Debian/Ubuntu)\n"
                "    sudo dnf install python3-tkinter  (Fedora)\n"
            )
        else:
            msg += "Asegúrate de que Python se instaló con soporte Tkinter."

        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            from tkinter import messagebox
            messagebox.showerror("NeoTcg Launcher — Error Crítico", msg)
            root.destroy()
        except Exception:
            print(msg, file=sys.stderr)
        sys.exit(1)


# =============================================================================
#  CLASE PRINCIPAL DEL LAUNCHER
# =============================================================================
class NeoTcgLauncher(ctk.CTk):
    """Ventana principal del launcher con todo el flujo integrado."""

    def __init__(self):
        super().__init__()
        validate_tkinter_available()

        # --- Configuración de ventana [UI MEJORADA: tamaño 560x480] ---
        self.title(f"NEOTCG — Launcher v{LAUNCHER_VERSION}")
        self.geometry("560x480")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        # Centrar ventana en pantalla
        self.update_idletasks()
        w, h = 560, 480
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # --- Rutas ---
        self.data_dir = get_data_dir()
        self.game_dir = self.data_dir / "game"
        self.backup_dir = self.data_dir / ".backup"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # --- Estado interno ---
        self.is_updating = False
        self.game_process = None
        self.latest_release = None
        self.remote_version = "unknown"
        self.installed_version = "none"

        # [UI MEJORADA] Estado del efecto de pulso en la barra de progreso
        self._pulse_active = False
        self._pulse_after_id = None

        # [UI MEJORADA] Timestamp de inicio de descarga para calcular velocidad
        self._download_start_time = 0.0
        self._download_bytes_so_far = 0

        # --- Construir UI ---
        self._build_ui()
        self.update_status()
        self.after(200, self._start_check_update_thread)

    # =========================================================================
    #  CONSTRUCCIÓN DE UI [UI MEJORADA]
    # =========================================================================
    def _build_ui(self):
        """Construye todos los widgets con estilo Valorant/Riot."""

        # --- Frame contenedor principal ---
        main_frame = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # --- [UI MEJORADA] Header / Banner superior con línea decorativa ---
        header_frame = ctk.CTkFrame(main_frame, fg_color=COLOR_SURFACE, corner_radius=0)
        header_frame.pack(fill="x", padx=0, pady=(0, 0))
        header_frame.pack_propagate(False)
        header_frame.configure(height=72)

        self.lbl_title = ctk.CTkLabel(
            header_frame, text="NEOTCG",
            font=ctk.CTkFont(size=30, weight="bold", family="Arial"),
            text_color=COLOR_ACCENT
        )
        self.lbl_title.pack(pady=(10, 0))

        self.lbl_subtitle = ctk.CTkLabel(
            header_frame, text=f"Launcher v{LAUNCHER_VERSION}",
            font=ctk.CTkFont(size=11, family="Arial"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_subtitle.pack(pady=(2, 10))

        # Línea separadora inferior del header
        separator = ctk.CTkFrame(main_frame, fg_color=COLOR_ACCENT, corner_radius=0, height=2)
        separator.pack(fill="x", padx=0, pady=0)
        separator.configure(height=2)

        # --- Cuerpo principal con padding generoso ---
        body_frame = ctk.CTkFrame(main_frame, fg_color=COLOR_BG, corner_radius=0)
        body_frame.pack(fill="both", expand=True, padx=30, pady=(18, 10))

        # --- [UI MEJORADA] Label de estado con emoji y color dinámico ---
        self.lbl_status = ctk.CTkLabel(
            body_frame, text="⏳  Comprobando actualizaciones...",
            font=ctk.CTkFont(size=13, family="Arial"),
            text_color=COLOR_TEXT
        )
        self.lbl_status.pack(pady=(0, 12))

        # --- [UI MEJORADA] Barra de progreso mejorada ---
        self.progress = ctk.CTkProgressBar(
            body_frame, width=480, height=22,
            progress_color=COLOR_ACCENT, corner_radius=11
        )
        self.progress.set(0)
        self.progress.pack(pady=(0, 4))

        # [UI MEJORADA] Porcentaje grande + velocidad estimada
        self.lbl_pct = ctk.CTkLabel(
            body_frame, text="0%",
            font=ctk.CTkFont(size=22, weight="bold", family="Arial"),
            text_color=COLOR_ACCENT
        )
        self.lbl_pct.pack(pady=(2, 0))

        self.lbl_progress_detail = ctk.CTkLabel(
            body_frame, text="0.0 / 0.0 MB  ·  0.0 MB/s",
            font=ctk.CTkFont(size=11, family="Arial"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_progress_detail.pack(pady=(0, 18))

        # --- [UI MEJORADA] Botón principal grande ---
        self.btn_main = ctk.CTkButton(
            body_frame, text="CARGANDO...",
            width=340, height=50,
            font=ctk.CTkFont(size=16, weight="bold", family="Arial"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=14,
            state="disabled",
            command=self.on_main_button
        )
        self.btn_main.pack(pady=(0, 10))

        # --- Versión instalada ---
        self.lbl_installed = ctk.CTkLabel(
            body_frame, text="",
            font=ctk.CTkFont(size=11, family="Arial"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_installed.pack(pady=(0, 0))

        # --- Botones sociales [UI MEJORADA] ---
        social_frame = ctk.CTkFrame(body_frame, fg_color="transparent", corner_radius=0)
        social_frame.pack(pady=(14, 0))

        self.btn_discord = ctk.CTkButton(
            social_frame, text="🎮  Discord",
            width=150, height=36,
            font=ctk.CTkFont(size=12, weight="bold", family="Arial"),
            fg_color=COLOR_DISCORD,
            hover_color="#4752c4",
            corner_radius=10,
            command=lambda: webbrowser.open(URL_DISCORD)
        )
        self.btn_discord.pack(side="left", padx=(0, 10))

        self.btn_web = ctk.CTkButton(
            social_frame, text="🌐  Web Oficial",
            width=150, height=36,
            font=ctk.CTkFont(size=12, weight="bold", family="Arial"),
            fg_color=COLOR_WEB,
            hover_color="#3a3a3a",
            corner_radius=10,
            command=lambda: webbrowser.open(URL_WEB)
        )
        self.btn_web.pack(side="left", padx=(0, 10))

        # --- Footer ---
        self.lbl_footer = ctk.CTkLabel(
            self,
            text="Launcher oficial de NeoTcg  ·  www.neotcg.cl  ·  @NEOTCG.cl",
            font=ctk.CTkFont(size=9, family="Arial"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_footer.pack(side="bottom", pady=(0, 12))

    # =========================================================================
    #  ACTUALIZACIÓN SEGURA DE UI (thread-safe)
    # =========================================================================
    def set_status(self, text: str, color: str = COLOR_TEXT):
        """[UI MEJORADA] Cambia texto de estado con color dinámico."""
        self.lbl_status.configure(text=text, text_color=color)

    def set_progress(self, value: float, detail_text: str, pct_text: str = None):
        """
        [UI MEJORADA] Actualiza barra, porcentaje grande y detalle.
        pct_text: porcentaje grande (e.g. "45%"). Si None, se extrae de detail_text.
        """
        self.progress.set(value)
        self.lbl_progress_detail.configure(text=detail_text)
        if pct_text:
            self.lbl_pct.configure(text=pct_text)

    def set_button(self, text: str, enabled: bool = True, fg: str = COLOR_ACCENT):
        """Configura el botón principal con color según estado."""
        self.btn_main.configure(text=text, state=("normal" if enabled else "disabled"), fg_color=fg)

    def reset_progress(self):
        """Resetea la barra de progreso a cero."""
        self.progress.set(0)
        self.lbl_pct.configure(text="0%", text_color=COLOR_ACCENT)
        self.lbl_progress_detail.configure(text="0.0 / 0.0 MB  ·  0.0 MB/s")
        # Detener efecto de pulso si está activo
        self._stop_pulse()

    # =========================================================================
    #  [UI MEJORADA] EFECTO DE PULSO EN BARRA DE PROGRESO
    # =========================================================================
    def _start_pulse(self):
        """Inicia animación de pulso suave en la barra mientras descarga."""
        if self._pulse_active:
            return
        self._pulse_active = True
        self._pulse_cycle(0)

    def _pulse_cycle(self, step: int):
        """Ciclo de animación: oscila opacidad de la barra sutilmente."""
        if not self._pulse_active:
            return
        # Pulso sutil: varía progress_color entre 60% y 100% de opacidad visual
        # Simulado vía variar ligeramente el valor set
        # Como CTkProgressBar no permite animar color directamente, usamos un
        # "wiggle" en el texto del porcentaje para dar sensación de actividad
        phase = (step % 20) / 20.0  # 0..1 cíclico
        alpha = 0.7 + 0.3 * (0.5 + 0.5 * __import__('math').sin(phase * 2 * __import__('math').pi))

        # Actualizar color del texto de porcentaje para efecto visual
        r = int(0x00 * alpha + 0x00 * (1 - alpha))
        g = int(0x96 * alpha + 0x88 * (1 - alpha))
        b = int(0xff * alpha + 0x88 * (1 - alpha))
        pulse_color = f"#{r:02x}{g:02x}{b:02x}"
        self.lbl_pct.configure(text_color=pulse_color)

        self._pulse_after_id = self.after(120, lambda: self._pulse_cycle(step + 1))

    def _stop_pulse(self):
        """Detiene la animación de pulso."""
        self._pulse_active = False
        if self._pulse_after_id:
            self.after_cancel(self._pulse_after_id)
            self._pulse_after_id = None
        # Restaurar color original
        self.lbl_pct.configure(text_color=COLOR_ACCENT)

    # =========================================================================
    #  [UI MEJORADA] TRANSICIÓN SUAVE DE ESTADO
    # =========================================================================
    def _fade_status(self, old_text: str, new_text: str, color: str = COLOR_TEXT, delay: int = 300):
        """
        Transición suave: parpadea brevemente el texto de estado
        para evitar cambios bruscos.
        """
        def _do():
            self.lbl_status.configure(text="", text_color=COLOR_TEXT_DIM)
            self.after(80, lambda: self.lbl_status.configure(text=new_text, text_color=color))
        self.after(delay, _do)

    # =========================================================================
    #  LECTURA DE VERSIÓN INSTALADA
    # =========================================================================
    def read_installed_version(self) -> str:
        vf = self.game_dir / "installed_version.txt"
        if vf.exists():
            try:
                return vf.read_text().strip()
            except Exception:
                return "none"
        return "none"

    def update_status(self):
        self.installed_version = self.read_installed_version()
        self.lbl_installed.configure(text=f"Versión instalada: {self.installed_version}")

    def _game_executable_exists(self) -> bool:
        if platform.system() == "Windows":
            return (self.game_dir / EXE_NAME_WIN).exists()
        else:
            return (self.game_dir / APP_NAME_MAC).exists()

    # =========================================================================
    #  COMPROBACIÓN DE ACTUALIZACIONES (THREAD)
    # =========================================================================
    def _start_check_update_thread(self):
        threading.Thread(target=self.check_update, daemon=True).start()

    def check_update(self):
        """
        Consulta la API de GitHub para obtener el último release.
        Compara con la versión instalada y actualiza la UI.
        """
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NeoTcgLauncher"}
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            self.latest_release = resp.json()
            self.remote_version = self.latest_release.get("tag_name", "unknown")
            self.installed_version = self.read_installed_version()

            has_exe = self._game_executable_exists()
            needs_update = self.remote_version != self.installed_version or not has_exe

            if needs_update:
                btn_text = "📥  ACTUALIZAR" if self.installed_version != "none" else "📥  INSTALAR"
                self.after(0, lambda: self.set_status(
                    f"🔔  Nueva versión disponible: {self.remote_version}",
                    color=COLOR_WARNING
                ))
                self.after(0, lambda t=btn_text: self.set_button(t, enabled=True, fg=COLOR_ACCENT))
            else:
                self.after(0, lambda: self.set_status(
                    "✅  ¡Estás en la última versión!",
                    color=COLOR_SUCCESS
                ))
                self.after(0, lambda: self.set_button("🎮  JUGAR", enabled=True, fg=COLOR_SUCCESS))

            self.after(0, lambda: self.lbl_installed.configure(
                text=f"Instalada: {self.installed_version}  |  Disponible: {self.remote_version}"
            ))

        except requests.exceptions.Timeout:
            self.after(0, lambda: self.set_status(
                "⚠️  Timeout al consultar GitHub. Revisa tu conexión.",
                color=COLOR_WARNING
            ))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))
        except requests.exceptions.ConnectionError:
            self.after(0, lambda: self.set_status(
                "⚠️  Sin conexión a Internet.",
                color=COLOR_ERROR
            ))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))
        except requests.exceptions.RequestException as e:
            self.after(0, lambda err=str(e): self.set_status(
                f"⚠️  Error de red: {err}",
                color=COLOR_ERROR
            ))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))
        except Exception as e:
            self.after(0, lambda err=str(e): self.set_status(
                f"❌  Error inesperado: {err}",
                color=COLOR_ERROR
            ))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))

    # =========================================================================
    #  ACCIÓN DEL BOTÓN PRINCIPAL
    # =========================================================================
    def on_main_button(self):
        text = self.btn_main.cget("text").strip()
        if "ACTUALIZAR" in text or "INSTALAR" in text:
            self._start_download_thread()
        elif "JUGAR" in text:
            self._launch_game()
        elif "REINTENTAR" in text:
            self.reset_progress()
            self.set_status("⏳  Reintentando...", color=COLOR_TEXT)
            self.set_button("CARGANDO...", enabled=False)
            self._start_check_update_thread()

    # =========================================================================
    #  DESCARGA E INSTALACIÓN (THREAD)
    # =========================================================================
    def _start_download_thread(self):
        if self.is_updating:
            return
        self.is_updating = True
        self._download_start_time = time.time()
        self._download_bytes_so_far = 0
        self._start_pulse()  # [UI MEJORADA] Activar efecto visual
        self.after(0, lambda: self.set_button("⏳  DESCARGANDO...", enabled=False, fg=COLOR_ACCENT))
        threading.Thread(target=self._download_and_install, daemon=True).start()

    def _find_platform_asset(self, release: dict) -> dict:
        """Busca el asset ZIP correcto para la plataforma actual."""
        system = platform.system()
        for asset in release.get("assets", []):
            name = asset["name"]
            if system == "Windows":
                if name == "NeoTcg.zip" or (name.endswith(".zip") and "mac" not in name.lower()):
                    return asset
            else:
                if "mac" in name.lower() and name.endswith(".zip"):
                    return asset
        available = [a["name"] for a in release.get("assets", [])]
        raise RuntimeError(f"No se encontró el asset para {system}. Disponibles: {available}")

    def _download_and_install(self):
        """Flujo completo: descarga → verifica SHA256 → backup → extrae → limpia."""
        try:
            release = self.latest_release
            if not release:
                raise RuntimeError("No hay información del release. Reintenta.")

            asset = self._find_platform_asset(release)
            download_url = asset["browser_download_url"]
            file_size = asset.get("size", 0)
            asset_name = asset["name"]
            sha256_expected = self._fetch_sha256(release)
            self._check_disk_space(file_size)

            zip_path = self.data_dir / "temp_update.zip"
            self.after(0, lambda: self.set_status(f"📥  Descargando {asset_name}...", color=COLOR_TEXT))
            self._download_with_resume(download_url, zip_path, sha256_expected, file_size)

            if self.game_dir.exists() and any(self.game_dir.iterdir()):
                self.after(0, lambda: self.set_status("💾  Creando copia de seguridad...", color=COLOR_TEXT))
                self._create_backup()

            self.after(0, lambda: self.set_status("📦  Extrayendo archivos...", color=COLOR_TEXT))
            try:
                self._extract_zip(zip_path)
            except RuntimeError as e:
                self.after(0, lambda err=str(e): self.set_status(f"❌  Error al extraer: {err}", color=COLOR_ERROR))
                self._restore_backup()
                raise

            version_tag = self.remote_version
            (self.game_dir / "installed_version.txt").write_text(version_tag.strip())
            self.installed_version = version_tag

            if zip_path.exists():
                zip_path.unlink()

            self._stop_pulse()  # [UI MEJORADA] Detener pulso
            self.after(0, lambda: self.set_status("🎉  ¡Actualización completada!", color=COLOR_SUCCESS))
            self.after(0, lambda: self.set_button("🎮  JUGAR", enabled=True, fg=COLOR_SUCCESS))
            self.after(0, lambda: self.reset_progress())
            self.after(0, lambda: self.lbl_installed.configure(
                text=f"Versión instalada: {self.installed_version}"
            ))

        except RuntimeError as e:
            self._stop_pulse()
            self.after(0, lambda err=str(e): self.set_status(f"❌  Error: {err}", color=COLOR_ERROR))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))
            self.after(0, lambda: self.reset_progress())
        except Exception as e:
            self._stop_pulse()
            self.after(0, lambda err=str(e): self.set_status(f"❌  Error inesperado: {err}", color=COLOR_ERROR))
            self.after(0, lambda: self.set_button("🔄  REINTENTAR", enabled=True, fg=COLOR_WARNING))
            self.after(0, lambda: self.reset_progress())
        finally:
            self.is_updating = False

    def _fetch_sha256(self, release: dict) -> str:
        """Descarga version.json del release y extrae el SHA256 de la plataforma."""
        version_asset = None
        for a in release.get("assets", []):
            if a["name"] == "version.json":
                version_asset = a
                break
        if not version_asset:
            return ""
        try:
            resp = requests.get(version_asset["browser_download_url"], timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            vdata = resp.json()
            plat_key = "windows" if platform.system() == "Windows" else "macos"
            return vdata.get("builds", {}).get(plat_key, {}).get("sha256", "")
        except Exception:
            return ""

    def _check_disk_space(self, required_bytes: int):
        """Valida espacio libre en disco (necesita al menos el doble del ZIP)."""
        try:
            usage = shutil.disk_usage(self.data_dir)
            needed = required_bytes * 2
            if usage.free < needed:
                need_mb = needed / (1024 * 1024)
                free_mb = usage.free / (1024 * 1024)
                raise RuntimeError(f"Espacio insuficiente. Se necesitan ~{need_mb:.0f} MB, disponibles: {free_mb:.0f} MB")
        except OSError as e:
            print(f"[NeoTcg] Aviso: No se pudo verificar espacio en disco: {e}", file=sys.stderr)

    def _download_with_resume(self, url: str, dest: Path, sha256_expected: str, total_size: int):
        """
        Descarga con streaming + header Range para reanudación.
        [UI MEJORADA] Muestra velocidad estimada (MB/s) + porcentaje grande.
        Verifica SHA256 al finalizar.
        """
        dest = Path(dest)
        existing = dest.stat().st_size if dest.exists() else 0

        headers = {"User-Agent": "NeoTcgLauncher"}
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"

        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError("Timeout durante la descarga. Comprueba tu conexión.")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Sin conexión a Internet. Comprueba tu red.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error de red: {e}")

        if resp.status_code == 206:
            mode = "ab"
            downloaded = existing
        else:
            mode = "wb"
            downloaded = 0
            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > 0:
                total_size = content_length

        # [UI MEJORADA] Resetear tracking de velocidad
        self._download_start_time = time.time()
        self._download_bytes_so_far = downloaded

        try:
            with open(dest, mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    self._download_bytes_so_far = downloaded

                    # [UI MEJORADA] Calcular velocidad y actualizar UI enriquecida
                    elapsed = time.time() - self._download_start_time
                    speed_mbps = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0.0

                    pct = min(downloaded / total_size, 1.0) if total_size else 0
                    mb_dl = downloaded / (1024 * 1024)
                    mb_tot = total_size / (1024 * 1024)
                    pct_str = f"{pct:.0%}"

                    # Detalle: tamaño + velocidad
                    detail = f"{mb_dl:.1f} / {mb_tot:.1f} MB  ·  {speed_mbps:.1f} MB/s"

                    self.after(0, lambda p=pct, d=detail, ps=pct_str: self.set_progress(p, d, ps))
        except OSError as e:
            raise RuntimeError(f"Error de escritura en disco: {e}")

        # --- Verificación SHA256 ---
        if sha256_expected:
            self.after(0, lambda: self.set_status("🔒  Verificando integridad SHA256...", color=COLOR_TEXT))
            actual = self._sha256_file(dest)
            if actual != sha256_expected:
                raise RuntimeError(f"SHA256 incorrecto.\nEsperado: {sha256_expected}\nObtenido: {actual}")
            self.after(0, lambda: self.set_status("🔒  SHA256 verificado ✓", color=COLOR_SUCCESS))

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calcula el hash SHA256 de un archivo."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    # =========================================================================
    #  BACKUP / RESTAURACIÓN
    # =========================================================================
    def _create_backup(self):
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            shutil.copytree(self.game_dir, self.backup_dir)
        except OSError as e:
            print(f"[NeoTcg] Warning: No se pudo crear backup: {e}", file=sys.stderr)

    def _restore_backup(self):
        try:
            if self.backup_dir.exists():
                if self.game_dir.exists():
                    shutil.rmtree(self.game_dir)
                shutil.copytree(self.backup_dir, self.game_dir)
        except OSError as e:
            print(f"[NeoTcg] ERROR: No se pudo restaurar backup: {e}", file=sys.stderr)

    # =========================================================================
    #  EXTRACCIÓN
    # =========================================================================
    def _extract_zip(self, zip_path: Path):
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise RuntimeError("El archivo ZIP no existe.")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise RuntimeError(f"ZIP corrupto: primer archivo dañado es '{bad}'")
                self.game_dir.mkdir(parents=True, exist_ok=True)
                zf.extractall(self.game_dir)
        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Archivo ZIP inválido o corrupto: {e}")
        except OSError as e:
            raise RuntimeError(f"Error al extraer: {e}")

    # =========================================================================
    #  LANZAMIENTO DEL JUEGO
    # =========================================================================
    def _launch_game(self):
        if not self._game_executable_exists():
            self.set_status("❌  No se encontró el ejecutable del juego.", color=COLOR_ERROR)
            return

        if self._is_game_running():
            self.set_status("⚠️  El juego ya se está ejecutando. Lanzando de todos modos...", color=COLOR_WARNING)

        session_file = self.game_dir / ".launcher_session"
        try:
            session_file.write_text(str(time.time()))
        except OSError:
            pass

        try:
            if platform.system() == "Windows":
                exe_path = self.game_dir / EXE_NAME_WIN
                self.game_process = subprocess.Popen([str(exe_path)], cwd=str(self.game_dir))
            else:
                app_path = self.game_dir / APP_NAME_MAC
                if app_path.exists():
                    self.game_process = subprocess.Popen(["open", "-a", str(app_path)])
                else:
                    apps = list(self.game_dir.glob("*.app"))
                    if apps:
                        self.game_process = subprocess.Popen(["open", "-a", str(apps[0])])
                    else:
                        raise RuntimeError("No se encontró Pokemon Tcg.app en el directorio del juego.")
        except FileNotFoundError:
            self.set_status("❌  Ejecutable no encontrado. Reinstala el juego.", color=COLOR_ERROR)
            return
        except PermissionError:
            self.set_status("❌  Permiso denegado al ejecutar el juego.", color=COLOR_ERROR)
            return
        except Exception as e:
            self.set_status(f"❌  Error al lanzar el juego: {e}", color=COLOR_ERROR)
            return

        self.set_status("🎮  Juego en ejecución...", color=COLOR_SUCCESS)
        self.set_button("🎮  EN JUEGO", enabled=False, fg="#555555")
        threading.Thread(target=self._monitor_game, daemon=True).start()

    def _is_game_running(self) -> bool:
        target = EXE_NAME_WIN if platform.system() == "Windows" else "Pokemon Tcg"
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                name = proc.info.get("name", "") or ""
                cmdline = " ".join(proc.info.get("cmdline", []) or [])
                if target.lower() in name.lower() or target.lower() in cmdline.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def _monitor_game(self):
        if self.game_process:
            try:
                self.game_process.wait()
            except Exception:
                pass
        session_file = self.game_dir / ".launcher_session"
        if session_file.exists():
            try:
                session_file.unlink()
            except OSError:
                pass
        self.after(0, lambda: self.set_status("🏁  Juego cerrado. ¡Hasta la próxima!", color=COLOR_TEXT))
        self.after(0, lambda: self.set_button("🎮  JUGAR", enabled=True, fg=COLOR_SUCCESS))
        self.after(0, lambda: self.reset_progress())

    # =========================================================================
    #  UTILIDADES
    # =========================================================================
    def _open_game_folder(self):
        if self.game_dir.exists():
            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(str(self.game_dir))
                elif system == "Darwin":
                    subprocess.Popen(["open", str(self.game_dir)])
                else:
                    subprocess.Popen(["xdg-open", str(self.game_dir)])
            except Exception as e:
                self.set_status(f"No se pudo abrir la carpeta: {e}", color=COLOR_WARNING)
        else:
            self.set_status("La carpeta del juego aún no existe.", color=COLOR_WARNING)

    # =========================================================================
    #  CIERRE LIMPIO
    # =========================================================================
    def on_closing(self):
        self._stop_pulse()
        self.destroy()


# =============================================================================
#  PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    try:
        app = NeoTcgLauncher()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except KeyboardInterrupt:
        print("\nLauncher cerrado por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"[NeoTcg] Error crítico: {e}", file=sys.stderr)
        if platform.system() == "Windows":
            input("Presiona Enter para salir...")
        sys.exit(1)


"""
================================================================================
  COMPILACIÓN Y DISTRIBUCIÓN — PyInstaller + Empaquetado
================================================================================

  ─────────────────────────────────────────────────────────
  1. COMPILACIÓN CON PYINSTALLER
  ─────────────────────────────────────────────────────────

  A) macOS (genera .app):
  ────────────────────────
     # Desde el directorio del proyecto, con el venv activado:
     source venv/bin/activate

     pyinstaller \
         --onefile \
         --windowed \
         --name NeoTcgLauncher \
         --bundle-id com.neotcg.launcher \
         --hidden-import=customtkinter \
         --hidden-import=tkinter \
         --hidden-import=_tkinter \
         --icon=icon_mac.icns \
         launcher_gui.py

     Output: dist/NeoTcgLauncher.app

  B) Windows (genera .exe):
  ─────────────────────────
     REM Desde CMD o PowerShell, con el venv activado:
     call venv\\Scripts\\activate.bat

     pyinstaller ^
         --onefile ^
         --windowed ^
         --name NeoTcgLauncher ^
         --icon=icon_win.ico ^
         --hidden-import=customtkinter ^
         --hidden-import=tkinter ^
         --hidden-import=_tkinter ^
         launcher_gui.py

     Output: dist\\NeoTcgLauncher.exe

  ─────────────────────────────────────────────────────────
  2. GENERAR ICONOS DESDE PNG
  ─────────────────────────────────────────────────────────

  A) macOS (.icns):
     # Necesitas una imagen PNG de 1024x1024 px
     # Instala iconutil (viene con Xcode) o usa online converter:
     mkdir icon.iconset
     sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
     sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
     sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
     sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
     sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
     sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
     sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
     sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
     sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
     cp icon.png icon.iconset/icon_512x512@2x.png
     iconutil -c icns icon.iconset -o icon_mac.icns

     Alternativa rápida: usa https://cloudconvert.com/png-to-icns

  B) Windows (.ico):
     # Necesitas PNG de 256x256 px
     pip install Pillow
     python -c "
     from PIL import Image
     img = Image.open('icon.png')
     img.save('icon_win.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
     "

     Alternativa: https://convertio.co/png-ico/

  ─────────────────────────────────────────────────────────
  3. EMPAQUETAR PARA DISTRIBUCIÓN
  ─────────────────────────────────────────────────────────

  A) Windows → ZIP:
     cd dist
     zip -r NeoTcgLauncher-v2.1.0-win.zip NeoTcgLauncher.exe

  B) macOS → DMG:
     # Crear DMG arrastrable:
     hdiutil create -volname "NeoTcgLauncher" -srcfolder dist/NeoTcgLauncher.app -ov -format UDZO NeoTcgLauncher-v2.1.0-mac.dmg

  C) Subir a MediaFire / Google Drive / cualquier hosting:
     1. Ve a https://www.mediafire.com/ → Inicia sesión → Upload
     2. Sube el .zip o .dmg generado
     3. Copia el enlace público de descarga
     4. Comparte el enlace en Discord / Web / redes

  ─────────────────────────────────────────────────────────
  4. NOTAS DE SEGURIDAD DE PLATAFORMA
  ─────────────────────────────────────────────────────────

  A) macOS Gatekeeper:
     Los binarios no firmados muestran: "No se puede verificar"
     Soluciones:
     - Rápida: clic derecho → Abrir → Abrir de todos modos
     - Terminal: xattr -d com.apple.quarantine NeoTcgLauncher.app
     - Profesional: Firma y notariza con Developer ID de Apple
       (requiere cuenta Apple Developer, $99/año)

  B) Windows SmartScreen:
     Aparece "Windows protected your PC" en primeras descargas
     Soluciones:
     - Usuario: clic en "More info" → "Run anyway"
     - Desarrollador: Compra certificado de firma de código EV
       (~$150-400/año) para eliminar SmartScreen permanentemente
     - Alternativa: sube el archivo a VirusTotal; tras suficientes
       análisis positivos, SmartScreen lo whitelisteará

  ─────────────────────────────────────────────────────────
  5. RUTAS DE INSTALACIÓN DEL JUEGO
  ─────────────────────────────────────────────────────────

  El launcher descarga y extrae el juego en:

  macOS:   ~/Library/Application Support/NeoTcg/game/
  Windows: %APPDATA%\\NeoTcg\\game\\

  Dentro de game/ encontrarás:
  - installed_version.txt  (versión instalada)
  - Pokemon Tcg.exe        (Windows)
  - Pokemon Tcg.app/       (macOS)
  - .launcher_session      (temporal, se crea al lanzar)

  Para desinstalar: borra la carpeta NeoTcg completa del directorio
  correspondiente a tu plataforma.

================================================================================
"""
