# main.py
#!/usr/bin/env python3
"""
Main Application Entry Point
- Sets up high DPI attributes
- Checks system requirements (fonts, icons)
- Launches main window with size from global settings
- Uses global configuration system
"""

import sys
import os
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase

# Add config directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'config'))
# Add ui directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ui'))

from ui.main_window import MainWindow
from config.global_settings import global_settings


def check_system_requirements():
    """Check if required fonts and icons are installed"""
    missing = []
    
    # Check for basic fonts that should be available on any system
    available_fonts = QFontDatabase().families()
    
    # Common fonts available on most Linux systems
    common_fonts = [
        'Noto Sans', 'DejaVu Sans', 'Liberation Sans', 
        'FreeSans', 'Arial', 'Helvetica', 'sans-serif'
    ]
    
    font_found = False
    for font in common_fonts:
        if font in available_fonts or font == 'sans-serif':
            font_found = True
            break
    
    if not font_found:
        missing.append("No suitable fonts found (install fonts-noto or fonts-dejavu)")
    
    # Check for common icon themes
    icon_themes = ['hicolor', 'Adwaita', 'gnome', 'Papirus']
    icon_paths = ['/usr/share/icons', '/usr/share/pixmaps', str(Path.home() / '.local/share/icons')]
    
    has_icons = False
    for theme in icon_themes:
        for path in icon_paths:
            if os.path.exists(os.path.join(path, theme)):
                has_icons = True
                break
        if has_icons:
            break
    
    if not has_icons:
        missing.append("Icon theme (install adwaita-icon-theme or papirus-icon-theme)")
    
    return missing


def install_missing_packages(missing_items):
    """Attempt to install missing packages"""
    packages = []
    
    # Map missing items to package names
    if any('Icon theme' in item for item in missing_items):
        packages.append('adwaita-icon-theme')
        packages.append('papirus-icon-theme')
    
    if any('fonts' in item for item in missing_items):
        packages.append('fonts-noto')
        packages.append('fonts-dejavu-core')
        packages.append('fonts-liberation')
        packages.append('fonts-freefont-ttf')
    
    return packages


def get_preferred_font():
    """Get the best available font"""
    available_fonts = QFontDatabase().families()
    
    # Fonts in order of preference
    preferred_fonts = [
        'Noto Sans',
        'DejaVu Sans',
        'Liberation Sans',
        'FreeSans',
        'Arial',
        'Helvetica',
        'sans-serif'
    ]
    
    for font in preferred_fonts:
        if font in available_fonts:
            return QFont(font, 10)
        if font == 'sans-serif':
            return QFont('sans-serif', 10)
    
    # Ultimate fallback
    return QFont('sans-serif', 10)


def main():
    """Main entry point"""
    # Set high DPI attributes BEFORE creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Print global settings location for debugging
    print(f"📁 Using global settings from: {global_settings.settings_path}")
    
    # Load window size from global settings
    window_width, window_height = global_settings.get_window_size()
    print(f"📐 Loaded window size: {window_width}x{window_height}")
    
    # Check for required fonts and icons
    missing = check_system_requirements()
    
    if missing:
        print("⚠️ Missing system dependencies:")
        for item in missing:
            print(f"   - {item}")
        
        # Offer to install missing packages
        packages = install_missing_packages(missing)
        if packages:
            pkg_list = ' '.join(packages)
            reply = QMessageBox.question(
                None,
                "Install Missing Packages?",
                f"The following packages are missing:\n\n{chr(10).join(missing)}\n\n"
                f"Would you like to install them?\n\n"
                f"Packages: {pkg_list}\n"
                f"(Note: This requires sudo privileges)",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    cmd = ['sudo', 'apt-get', 'install', '-y'] + packages
                    process = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if process.returncode == 0:
                        QMessageBox.information(None, "Success", "Packages installed successfully!")
                    else:
                        QMessageBox.critical(None, "Error", f"Failed to install packages:\n{process.stderr}")
                except Exception as e:
                    QMessageBox.critical(None, "Error", f"Installation failed: {str(e)}")
    
    # Set default font for the application
    default_font = get_preferred_font()
    app.setFont(default_font)
    
    # Create and show main window with loaded size
    window = MainWindow(window_width, window_height)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()