# NeoTcg Launcher

Auto-updater and game launcher for **NeoTcg** — works on **Windows** and **macOS**.  
Downloads the latest release from GitHub Releases, verifies integrity via SHA256, backs up the current version, extracts the new build, and launches the game.

---

## 📁 Project Structure

| File | Purpose |
|---|---|
| `launcher.py` | Main launcher script (no GUI, console-only) |
| `version_template.json` | Template for `version.json` uploaded with each release |
| `requirements.txt` | Python dependencies (PyInstaller for building) |
| `build_mac.sh` | Build script for macOS |
| `build_win.bat` | Build script for Windows |
| `.gitignore` | Standard ignores for build artifacts |

---

## 🚀 Setup — GitHub Releases Repository

1. **Create a new public repository** on GitHub: `neo-tcg-builds`
2. In `launcher.py`, replace the placeholder:
   ```python
   GITHUB_REPO = "TU_USUARIO/neo-tcg-builds"
   ```
   with your actual username and repo:
   ```python
   GITHUB_REPO = "myusername/neo-tcg-builds"
   ```

---

## 📦 How to Publish a Release

### 1. Prepare `version.json`

Copy `version_template.json` and fill in real values:

```json
{
  "version": "1.0.0",
  "builds": {
    "windows": {
      "url": "https://github.com/TU_USUARIO/neo-tcg-builds/releases/download/v1.0.0/neo-tcg-1.0.0-win.zip",
      "sha256": "<sha256-of-win-zip>"
    },
    "macos": {
      "url": "https://github.com/TU_USUARIO/neo-tcg-builds/releases/download/v1.0.0/neo-tcg-1.0.0-mac.zip",
      "sha256": "<sha256-of-mac-zip>"
    }
  }
}
```

### 2. Calculate SHA256 Hashes

```bash
# macOS / Linux
shasum -a 256 neo-tcg-1.0.0-win.zip
shasum -a 256 neo-tcg-1.0.0-mac.zip

# Windows (PowerShell)
Get-FileHash neo-tcg-1.0.0-win.zip -Algorithm SHA256
Get-FileHash neo-tcg-1.0.0-mac.zip -Algorithm SHA256
```

### 3. Create the Release

1. Go to **GitHub → Releases → Draft a new release**
2. Tag: `v1.0.0`
3. Upload as **assets**:
   - `neo-tcg-1.0.0-win.zip`
   - `neo-tcg-1.0.0-mac.zip`
   - `version.json`
4. Publish the release.

> The launcher reads `version.json` from the release assets to get platform-specific URLs and SHA256 hashes.

---

## 🛠️ Compile the Launcher

### Prerequisites
- Python 3.10+ installed
- (Optional but recommended) create a virtual environment

### macOS

```bash
chmod +x build_mac.sh
./build_mac.sh
```

Output: `dist/NeoTcgLauncher.app`

### Windows

```bat
build_win.bat
```

Output: `dist\NeoTcgLauncher.exe`

---

## 🧪 Local Testing (without GitHub)

You can test the launcher with a local ZIP file before publishing:

1. Create a test ZIP of your game folder: `test-build.zip`
2. Calculate its SHA256 and add a `version.json` (you can serve it via a local HTTP server or a temporary GitHub draft).
3. Point `GITHUB_REPO` to a test repo or modify `launcher.py` temporarily to use a local file path instead of the GitHub API.
4. Run:
   ```bash
   python launcher.py
   ```

---

## ⚠️ Important Notes

### macOS Gatekeeper & Notarization

The PyInstaller-built `.app` is **not notarized** by default. Users may see a Gatekeeper warning. To avoid this:

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/)
2. Codesign the app:
   ```bash
   codesign --deep --force --sign "Your Developer ID" dist/NeoTcgLauncher.app
   ```
3. Notarize and staple:
   ```bash
   xcrun notarytool submit dist/NeoTcgLauncher.app --keychain-profile "AC_PASSWORD" --wait
   xcrun stapler staple dist/NeoTcgLauncher.app
   ```

For internal/test builds you can instruct users to right-click → Open to bypass Gatekeeper.

### Godot Project — Disable AutoUpdater

The NeoTcg game project (Godot) may have its own auto-update logic. **Disable it** to avoid conflicts with the launcher:

- Open your Godot project
- Find `AutoUpdater.gd` (or equivalent)
- Comment out or remove the auto-update calls
- Rebuild the game binaries

---

## 🔧 Customization Points

| What | Where |
|---|---|
| GitHub repo | `GITHUB_REPO` in `launcher.py` |
| Executable name | `launch_game()` function — change `NeoTcg.exe` / `NeoTcg.app` |
| Data directory | `get_data_dir()` (uses appdirs convention) |
| Chunk size / timeout | Top-level constants `CHUNK_SIZE`, `DOWNLOAD_TIMEOUT` |
| Logging level | `logging.basicConfig(level=logging.INFO, ...)` |

---

## 📄 License

MIT — feel free to adapt for your own projects.
