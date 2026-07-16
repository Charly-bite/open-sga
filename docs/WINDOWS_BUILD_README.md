# Building SGA for Windows

This guide explains how to create a standalone Windows executable (.exe) for the GHS Label System.

## 📋 Prerequisites

### On Windows (Recommended)
1. **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation
2. **pip** (included with Python)

### On Linux (Cross-platform prep)
You can prepare the build package on Linux, then build on Windows.

## 🚀 Quick Build (Windows)

### Option 1: Using the Batch File
```batch
# Open Command Prompt in the project folder
build_windows.bat
```

### Option 2: Using Python Script
```batch
# Check prerequisites
python build_windows.py --check

# Build the executable
python build_windows.py --build
```

### Option 3: Manual PyInstaller
```batch
pip install pyinstaller pillow pandas reportlab openpyxl
pyinstaller sga_app.spec --clean
```

## 📁 Output

After a successful build:
- `dist/SGA_GHS_Labels.exe` - The standalone executable (~50-80 MB)
- `SGA_GHS_Labels.exe` - Copy in root folder for convenience

## 🐧 Building from Linux

If you're developing on Linux and need to prepare for Windows:

```bash
# Create a package folder with all necessary files
python build_windows.py --package

# Transfer 'windows_build_package' folder to Windows
# Then run build_windows.bat on Windows
```

## 📦 What's Included in the EXE

The executable bundles:
- ✅ All Python source code
- ✅ GHS pictogram images (`assets/pictograms/`)
- ✅ Company logo (`assets/logo.png`)
- ✅ Database files (`unified_db/`)
- ✅ Original data files (`original_data/`)
- ✅ Configuration templates
- ✅ Python runtime and libraries

## ⚠️ Important Notes

### SAP HANA Connection
The SAP HANA driver (`hdbcli`) is **NOT** included in the build because:
- It requires a separate SAP license
- It's platform-specific

**For SAP connectivity on Windows:**
1. Install the SAP HANA Client from SAP
2. The app will automatically detect and use it if available

### First Run
On first run, the app creates:
- `generated_labels/` - Output folder for PDF labels
- `history.json` - Label generation history
- `users.json` - User accounts (if not present)

### Antivirus Warning
Some antivirus software may flag PyInstaller executables as suspicious. This is a false positive. You may need to:
- Add an exception in your antivirus
- Sign the executable with a code signing certificate (for distribution)

## 🔧 Troubleshooting

### "Python not found"
- Reinstall Python with "Add to PATH" checked
- Or add manually: `set PATH=%PATH%;C:\Python311`

### Build fails with missing module
```batch
pip install <module_name>
```

### EXE crashes on startup
Build with console enabled for debugging:
1. Edit `sga_app.spec`
2. Change `console=False` to `console=True`
3. Rebuild

### Missing pictograms/data
Ensure all folders exist before building:
- `assets/pictograms/` (9 PNG files)
- `unified_db/` (CSV database files)
- `original_data/` (backup data)

## 📝 Customization

### Change App Icon
1. Create a `.ico` file (Windows icon format)
2. Edit `sga_app.spec`:
   ```python
   icon='path/to/your/icon.ico'
   ```
3. Rebuild

### Include Additional Files
Edit the `datas` list in `sga_app.spec`:
```python
datas = [
    ...
    ('my_file.txt', '.'),  # Copy to root
    ('my_folder', 'my_folder'),  # Copy entire folder
]
```

## 📊 Build Size Optimization

The default build is ~50-80 MB. To reduce size:

1. **Use UPX compression** (already enabled in spec)
2. **Exclude unused modules** in the `excludes` list
3. **Use `--onedir` instead of `--onefile`** for faster startup (creates a folder instead of single exe)

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `build_windows.bat` | One-click Windows build |
| `python build_windows.py --check` | Verify prerequisites |
| `python build_windows.py --package` | Create transfer package |
| `python build_windows.py --build` | Build executable |
| `pyinstaller sga_app.spec --clean` | Manual build |
