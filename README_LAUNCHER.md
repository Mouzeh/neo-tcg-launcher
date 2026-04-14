# NeoTcg Launcher — Guía Completa

Launcher GUI robusto con flujo tipo Valorant: **verificar → actualizar → jugar**.

Compatibilidad: **Python 3.10+** | **macOS Sonoma/Ventura** | **Windows 10/11**

---

## 🚀 Primer Uso (Configuración Inicial)

### macOS / Linux

```bash
# 1. Ejecutar setup automático
chmod +x setup.sh
./setup.sh

# 2. Iniciar el launcher
source venv/bin/activate
python launcher_gui.py
```

> `setup.sh` detecta tu SO, instala `python-tk` si falta (Homebrew), crea un venv limpio y valida todos los imports.

### Windows

```batch
REM 1. Ejecutar setup automático
setup.bat

REM 2. Iniciar el launcher
call venv\Scripts\activate.bat
python launcher_gui.py
```

---

## 📁 Estructura de Archivos

```
NeoTcg-Launcher/
├── launcher_gui.py      # UI + lógica completa del launcher
├── launcher.py           # Versión console-only (legacy, mantener por compatibilidad)
├── requirements.txt      # Dependencias esenciales (sin appdirs)
├── setup.sh              # Setup automático para Mac/Linux
├── setup.bat             # Setup automático para Windows
├── build_mac.sh          # Compilación PyInstaller para macOS
├── build_win.bat         # Compilación PyInstaller para Windows
├── release_helper.py     # Genera version.json con SHA256
└── release_helper.sh     # Versión bash del helper
```

---

## 🔧 Compilación (PyInstaller)

### macOS
```bash
./build_mac.sh
# Output: dist/NeoTcgLauncher.app
```

### Windows
```batch
build_win.bat
REM Output: dist\NeoTcgLauncher.exe
```

> Los build scripts detectan el venv automáticamente. Si no existe, te indican que ejecutes `setup.sh`/`setup.bat` primero.

---

## 🛡️ Robustez contra Errores Comunes

### `ModuleNotFoundError: No module named '_tkinter'`

**Causa:** Homebrew en macOS no incluye Tkinter por defecto en Python.

**Solución automática:** `./setup.sh` ejecuta `brew install python-tk` si detecta que falta.

**Solución manual:**
```bash
brew install python-tk
```

### Conflictos con `appdirs`

Este launcher **NO usa appdirs**. Las rutas se calculan con `pathlib` + `os` nativo:
- **macOS:** `~/Library/Application Support/NeoTcg`
- **Windows:** `%APPDATA%\NeoTcg`
- **Linux:** `~/.local/share/NeoTcg`

### Venv roto tras actualizar Python

`setup.sh`/`setup.bat` eliminan el venv anterior y crean uno limpio cada vez. No hay residuos de versiones previas.

---

## 🎮 Flujo del Launcher

1. **Comprobar:** Consulta `https://api.github.com/repos/Mouzeh/launcher/releases/latest`
2. **Comparar:** Versión local (`installed_version.txt`) vs remota (`tag_name`)
3. **Botón dinámico:**
   - `📥 INSTALAR` — primera instalación
   - `📥 ACTUALIZAR` — hay nueva versión
   - `✅ JUGAR` — todo al día
4. **Descarga:** Streaming con header `Range` (reanudación), barra de progreso real
5. **Verificación:** SHA256 obligatorio (desde `version.json` en los assets)
6. **Backup:** Copia automática de la versión actual antes de extraer
7. **Rollback:** Si la extracción falla, restaura desde backup
8. **Lanzamiento:** `Pokemon Tcg.exe` (Win) / `Pokemon Tcg.app` (Mac)
9. **Monitor:** Detecta proceso duplicado con `psutil` (advertencia, no bloqueo)

---

## 🔴 Threading

TODO el trabajo de red/descarga/monitoreo se ejecuta en `threading.Thread`. La UI se actualiza exclusivamente con `self.after(0, ...)`. **Cero bloqueos** en la interfaz.

---

## 📋 Flujo de Publicación (Godot → GitHub → Launcher)

```
Godot Export → .exe / .app
       ↓
Crear ZIPs (win + mac)
       ↓
python release_helper.py 1.2.0 --dir ~/builds/v1.2.0  →  version.json con SHA256
       ↓
gh release create "v1.2.0" --repo "Mouzeh/launcher" *.zip version.json
       ↓
Usuarios descargan desde el launcher ✅
```

> Ver `README_LAUNCHER.md` (si existe) para el flujo completo de publicación.

---

## ⚠️ Notas Importantes

### Espacio en disco
El launcher requiere ~2x el tamaño del ZIP (descarga + extracción). Para un juego de 700 MB: necesita ~1.4 GB libres.

### Reanudación de descargas
Si la conexión se corta, el launcher reanuda desde donde quedó (header `Range`). No necesita borrar archivos parciales.

### Gatekeeper en macOS
Los builds de Godot no están firmados por defecto. Los usuarios verán: *"No se puede verificar"*. Solución: **Click derecho → Abrir → Abrir de todos modos**. Para builds oficiales: firma y notariza con tu Developer ID de Apple.

### Ejecución manual del juego
El launcher **permite ejecución manual** del juego. La detección de proceso duplicado es solo una advertencia, no un bloqueo. Filosofía: *"Launcher recomendado, pero permite ejecución manual"*.

---

## 🧪 Validación Post-Setup

Tras ejecutar `./setup.sh && python launcher_gui.py`:

1. ✅ La UI debe abrir sin `ModuleNotFoundError`
2. ✅ El estado debe mostrar "Comprobando actualizaciones..."
3. ✅ El botón debe cambiar a `📥 INSTALAR`, `📥 ACTUALIZAR` o `✅ JUGAR`
4. ✅ Si no hay conexión a Internet, muestra `⚠️ REINTENTAR`

Si algo falla, el setup re-intenta la instalación de dependencias automáticamente antes de salir.
