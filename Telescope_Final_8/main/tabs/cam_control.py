#!/usr/bin/env python3
"""
Camera & Motor Controls Tab
- Row 1: Camera controls from hardware/cam.py (50% height)
- Row 2: Motor controls from hardware/motor.py (50% height)
- Fits perfectly in Tab 4 of the application
- No title rows - just the camera and motor widgets directly
- UPDATED: Proper theme propagation to child widgets
- FIXED: Correct method name for theme_manager (get_colors, not get_current_colors)
- FIXED: Initialize splitter before using it in resizeEvent
"""

import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMessageBox, QFrame, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, QProcess, QSize, QEvent, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QImage, QPalette, QColor

# Add parent directory to path to find hardware folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.dirname(CURRENT_DIR)
HARDWARE_DIR = os.path.join(MAIN_DIR, "hardware")
SETTINGS_DIR = os.path.join(MAIN_DIR, "settings")
UI_FOLDER = os.path.join(MAIN_DIR, "ui")

# Add directories to path
for path in [HARDWARE_DIR, SETTINGS_DIR, UI_FOLDER, MAIN_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import theme manager with fallback
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
    print("✅ cam_control.py - Using global theme manager from config folder")
except ImportError as e:
    print(f"⚠️ Warning: Could not import theme_manager - using fallback theme system. Error: {e}")
    THEME_AVAILABLE = False
    # Create fallback theme manager to prevent crashes
    class FallbackThemeManager:
        def __init__(self):
            self.current_theme = "dark_blue"
            self.theme_changed = pyqtSignal(str, dict)
        
        def get_colors(self):
            return {
                "window_bg": "#0f172a",
                "bg_secondary": "#1e293b",
                "bg_tertiary": "#334155",
                "text_color": "#f8fafc",
                "text_secondary": "#cbd5e1",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8",
                "button_text": "#ffffff",
                "text_size": 10,
                "accent": "#38bdf8",
                "accent_gold": "#fca311",
                "border": "#475569",
                "success": "#10b981",
                "warning": "#f59e0b",
                "error": "#ef4444",
                "border_color": "#38bdf8"
            }
        
        def get_current_theme(self):
            return self.current_theme
    
    theme_manager = FallbackThemeManager()

# Settings paths
SETTINGS_JSON_PATH = os.path.join(MAIN_DIR, "settings.json")
CAMERA_SETTINGS_PATH = os.path.join(SETTINGS_DIR, "camera_settings.py")
MOTOR_SETTINGS_PATH = os.path.join(SETTINGS_DIR, "motor_settings.py")

# Create directories for captures and records
CAPTURE_DIR = os.path.join(MAIN_DIR, "captures")
RECORD_DIR = os.path.join(MAIN_DIR, "records")
os.makedirs(CAPTURE_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

# ==================== LAZY IMPORTS FOR HARDWARE ====================
CAM_AVAILABLE = False
MOTOR_AVAILABLE = False
CameraControlWidget = None
MotorControlWidget = None

# Import Camera widget
try:
    from hardware.cam import CameraControlWidget
    CAM_AVAILABLE = True
    print("✅ [SUCCESS] Imported CameraControlWidget from hardware/cam.py")
except ImportError as e:
    print(f"⚠️ [WARNING] Camera Import Failed: {e}")
    # Create fallback camera widget
    class CameraControlWidget(QWidget):
        def __init__(self, theme=None, parent=None):
            super().__init__(parent)
            self.theme = theme or {}
            self._setup_ui()
            self._apply_theme()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            layout.setAlignment(Qt.AlignCenter)
            error_label = QLabel("⚠️ Camera Module Unavailable")
            error_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(error_label)

        def _apply_theme(self):
            bg = self.theme.get("window_bg", "#0f172a") if isinstance(self.theme, dict) else "#0f172a"
            text = self.theme.get("text_color", "#f8fafc") if isinstance(self.theme, dict) else "#f8fafc"
            self.setStyleSheet(f"""
                QWidget {{ background-color: {bg}; color: {text}; border: none; }}
                QLabel {{ border: none; }}
            """)

        def update_theme(self, new_theme):
            self.theme = new_theme
            self._apply_theme()

        def closeEvent(self, event):
            event.accept()

# Import Motor widget
try:
    from hardware.motor import MotorControlWidget
    MOTOR_AVAILABLE = True
    print("✅ [SUCCESS] Imported MotorControlWidget from hardware/motor.py")
except ImportError as e:
    print(f"⚠️ [ERROR] Motor Import Failed: {e}")
    # Create fallback motor widget
    class MotorControlWidget(QWidget):
        def __init__(self, theme=None, parent=None):
            super().__init__(parent)
            self.theme = theme or {}
            self._setup_ui()
            self._apply_theme()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            header = QLabel("⚠️ Motor Module Failed to Load")
            header.setAlignment(Qt.AlignCenter)
            layout.addWidget(header)
            debug_text = QTextEdit()
            debug_text.setReadOnly(True)
            debug_text.setMinimumHeight(200)
            layout.addWidget(debug_text, stretch=1)

        def _apply_theme(self):
            bg = self.theme.get("window_bg", "#0f172a") if isinstance(self.theme, dict) else "#0f172a"
            text = self.theme.get("text_color", "#f8fafc") if isinstance(self.theme, dict) else "#f8fafc"
            row = self.theme.get("row_bg", "rgba(30,41,59,0.8)") if isinstance(self.theme, dict) else "rgba(30,41,59,0.8)"
            self.setStyleSheet(f"""
                QWidget {{ background-color: {bg}; color: {text}; border: none; }}
                QTextEdit {{ background-color: {row}; color: {text}; border: none; border-radius:6px; padding:8px; }}
                QLabel {{ border: none; }}
            """)

        def update_theme(self, new_theme):
            self.theme = new_theme
            self._apply_theme()

        def closeEvent(self, event):
            event.accept()


# ==================== MAIN CAMERA/MOTOR CONTROL TAB ====================

class CameraMotorControlTab(QWidget):
    """Main tab for camera and motor controls (Tab 4) - EXACT FIT - No title rows"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Controls"
        self.is_embedded = parent is not None
        
        # Initialize splitter attribute BEFORE using it
        self.splitter = None
        
        # Get theme from manager - FIXED: Use get_colors() not get_current_colors()
        if hasattr(theme_manager, 'get_colors'):
            self.theme = theme_manager.get_colors()
        else:
            # Fallback for older theme manager versions
            self.theme = theme_manager.get_current_colors() if hasattr(theme_manager, 'get_current_colors') else {}
        
        self.camera_widget = None
        self.motor_widget = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self._setup_theme()
        self._build_layout()

        # Connect to theme manager - THIS IS THE ONLY CONNECTION TO GLOBAL THEME MANAGER
        if THEME_AVAILABLE and hasattr(theme_manager, 'theme_changed'):
            theme_manager.theme_changed.connect(self.on_global_theme_changed)

    def on_global_theme_changed(self, theme_name, theme_colors):
        """Handle global theme changes - propagate to child widgets"""
        self.theme = theme_colors
        self._setup_theme()
        
        # Propagate theme to child widgets using update_theme() method
        if self.camera_widget and hasattr(self.camera_widget, 'update_theme'):
            self.camera_widget.update_theme(theme_colors)
        if self.motor_widget and hasattr(self.motor_widget, 'update_theme'):
            self.motor_widget.update_theme(theme_colors)
        print(f"✅ [SUCCESS] CameraMotorControlTab theme synced to {theme_name}")

    def _setup_theme(self):
        """Setup theme styling"""
        bg_color     = self.theme.get("window_bg", "#0f172a")
        text_color   = self.theme.get("text_color", "#f8fafc")
        btn_bg       = self.theme.get("button_bg", "#2563eb")
        btn_hover    = self.theme.get("button_hover", "#38bdf8")
        btn_text     = self.theme.get("button_text", "#ffffff")
        text_size    = self.theme.get("text_size", 10)  # Slightly smaller for fitting

        style_sheet = f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Monospace', monospace;
                font-size: {text_size}px;
                border: none;
            }}
            QPushButton {{
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: {text_size - 1}px;
                font-weight: bold;
                margin: 1px 0;
                min-height: 24px;
                background-color: {btn_bg};
                color: {btn_text};
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                color: {btn_text};
            }}
            QPushButton:disabled {{
                background-color: #475569;
                color: #94a3b8;
            }}
            QLabel {{
                border: none;
                font-size: {text_size - 1}px;
                background-color: transparent;
                padding: 1px;
            }}
            QGroupBox {{
                border: 1px solid {self.theme.get("border_color", "#38bdf8")};
                border-radius: 4px;
                margin-top: 4px;
                padding-top: 8px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {self.theme.get("accent", "#38bdf8")};
            }}
        """
        self.setStyleSheet(style_sheet)

    def _build_layout(self):
        """Build the tab layout with 50/50 split - EXACT FIT - No titles"""
        # Main layout with ZERO margins to fill tab completely
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins - use full space
        main_layout.setSpacing(1)  # Minimal spacing between frames

        # Create a splitter for resizable rows (better for user experience)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(4)  # Thin handle
        self.splitter.setChildrenCollapsible(False)  # Prevent complete collapse
        
        # Camera section (top half) - DIRECT widget, no title
        self.camera_widget = CameraControlWidget(theme=self.theme, parent=self)
        self.camera_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.camera_widget)

        # Motor section (bottom half) - DIRECT widget, no title
        self.motor_widget = MotorControlWidget(theme=self.theme, parent=self)
        self.motor_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.motor_widget)

        # Set initial 50/50 split
        self.splitter.setSizes([500, 500])  # Will be proportionally scaled
        
        main_layout.addWidget(self.splitter)

    def update_theme(self, theme_input):
        """Update theme with colors dictionary"""
        if isinstance(theme_input, dict):
            self.theme = theme_input
        else:
            self.theme = theme_manager.get_colors() if hasattr(theme_manager, 'get_colors') else {}
        self._setup_theme()
        
        # Propagate to child widgets
        if self.camera_widget and hasattr(self.camera_widget, 'update_theme'):
            self.camera_widget.update_theme(self.theme)
        if self.motor_widget and hasattr(self.motor_widget, 'update_theme'):
            self.motor_widget.update_theme(self.theme)
        
        print(f"✅ [SUCCESS] CameraMotorControlTab theme updated")

    def resizeEvent(self, event):
        """Handle resize events to maintain splitter proportions"""
        super().resizeEvent(event)
        # Ensure splitter is initialized before using it
        if self.splitter is not None:
            total_height = self.height()
            self.splitter.setSizes([total_height // 2, total_height // 2])

    def on_tab_selected(self):
        """Called when tab is selected"""
        # Could refresh status here
        pass
    
    def on_tab_deselected(self):
        """Called when tab is deselected - pause hardware updates"""
        # Could pause updates here
        pass
    
    def closeEvent(self, event):
        """Clean up resources when tab is closed"""
        if self.motor_widget and hasattr(self.motor_widget, 'closeEvent'):
            self.motor_widget.closeEvent(event)
        if self.camera_widget and hasattr(self.camera_widget, 'closeEvent'):
            self.camera_widget.closeEvent(event)
        try:
            import cv2
            cv2.destroyAllWindows()
        except:
            pass
        print(f"✅ [SUCCESS] CameraMotorControlTab cleaned up")
        event.accept()


if __name__ == "__main__":
    # For testing
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    test_theme = theme_manager.get_colors() if hasattr(theme_manager, 'get_colors') else {}
    window = CameraMotorControlTab()
    window.setWindowTitle("Camera + Motor Control - No Titles")
    window.resize(830, 540)  # Test with tab dimensions
    window.show()
    
    sys.exit(app.exec_())