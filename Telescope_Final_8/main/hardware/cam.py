#!/usr/bin/env python3
"""
Enhanced Camera Control with Advanced Image Processing
UPDATED: Connected to global theme manager from config folder
FIXED: Proper theme propagation - no direct connection to theme manager
OPTIMIZED: Using config/ themes and global_settings (same as detect.py)
"""

import sys
import os
import json
import cv2
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMessageBox, QSlider, QSpacerItem,
    QStackedWidget, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QProcess, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QColor

# --------------------------
# Critical Path Setup (Same as detect.py)
# --------------------------
# Get absolute path of current file (main/hardware/cam.py)
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
# Get path to main folder (parent of hardware/)
MAIN_DIR = os.path.dirname(CURRENT_FILE_DIR)
# Path to config folder (same level as hardware/)
CONFIG_DIR = os.path.join(MAIN_DIR, "config")
# Path to ui folder (for themes_sessions.py if needed)
UI_DIR = os.path.join(MAIN_DIR, "ui")
# Path to tabs folder (for any shared resources)
TABS_DIR = os.path.join(MAIN_DIR, "tabs")

# Add directories to Python's search path
for path in [MAIN_DIR, CONFIG_DIR, UI_DIR, TABS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# --------------------------
# Import Theme Manager from config folder (same as detect.py)
# --------------------------
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
    print("✅ cam.py - Using global theme manager from config folder")
    
except ImportError as e:
    print(f"⚠️ Warning: Could not import theme_manager from config - using fallback theme. Error: {e}")
    THEME_AVAILABLE = False
    # Create fallback theme manager
    class FallbackThemeManager:
        def __init__(self):
            self.current_theme = "dark_blue"
            self.theme_changed = pyqtSignal(str, dict)
        
        def get_current_theme(self):
            return self.current_theme
        
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
                "text_size": 11,
                "accent": "#38bdf8",
                "accent_gold": "#fca311",
                "border": "#475569",
                "success": "#10b981",
                "warning": "#f59e0b",
                "error": "#ef4444"
            }
    
    theme_manager = FallbackThemeManager()

# --------------------------
# Import Global Settings from config folder (same as detect.py)
# --------------------------
try:
    from config.global_settings import global_settings
    GLOBAL_SETTINGS_AVAILABLE = True
    print("✅ cam.py - Using global settings from config folder")
    
except ImportError as e:
    print(f"⚠️ Warning: Could not import global_settings - using defaults. Error: {e}")
    GLOBAL_SETTINGS_AVAILABLE = False
    # Create fallback global settings
    class FallbackGlobalSettings:
        def __init__(self):
            self.settings_path = os.path.join(MAIN_DIR, "settings.json")
        
        def get_camera_settings(self):
            return {
                "default_resolution": "1920x1080",
                "default_fps": 30,
                "default_exposure": 1.0,
                "capture_format": "jpg",
                "capture_quality": 95
            }
        
        def get_all_settings(self):
            return {}
    
    global_settings = FallbackGlobalSettings()

# --------------------------
# Import SkyMapWidget from the same directory
# --------------------------
try:
    # Add current directory to path if not already there
    if CURRENT_FILE_DIR not in sys.path:
        sys.path.insert(0, CURRENT_FILE_DIR)
    
    from sky_map import SkyMapWidget
    SKY_MAP_AVAILABLE = True
    print("✅ SkyMapWidget imported successfully from hardware directory")
except ImportError as e:
    print(f"❌ Failed to import SkyMapWidget: {e}")
    SKY_MAP_AVAILABLE = False
    
    class SkyMapWidget(QWidget):
        time_updated = pyqtSignal(str)
        view_changed = pyqtSignal(dict)
        celestial_selected = pyqtSignal(str)
        motor_connection_changed = pyqtSignal(bool)
        
        def __init__(self, parent=None, show_controls=True, theme=None):
            super().__init__(parent)
            self.setMinimumSize(600, 250)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            
            label = QLabel("🌌 Sky Map Placeholder")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #888;")
            layout.addWidget(label)
            
            info_label = QLabel("Sky map module not available - check that sky_map.py exists in the hardware directory")
            info_label.setAlignment(Qt.AlignCenter)
            info_label.setStyleSheet("font-size: 12px; color: #ff6b6b;")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            print("⚠️ Using placeholder SkyMapWidget")
        
        def set_theme(self, theme):
            pass
        
        def set_time_format(self, time_format="%H:%M:%S", date_format="%Y-%m-%d"):
            pass
        
        def set_grid_settings(self, altitude_circles=8, azimuth_lines=16):
            pass
        
        def update_theme(self, theme):
            pass

# --------------------------
# Helper function to get theme colors safely
# --------------------------
def get_theme_colors():
    """Safely get theme colors from theme manager"""
    try:
        if hasattr(theme_manager, 'get_colors'):
            return theme_manager.get_colors()
        elif hasattr(theme_manager, 'get_current_colors'):
            return theme_manager.get_current_colors()
        elif hasattr(theme_manager, 'get_theme_colors'):
            return theme_manager.get_theme_colors()
        else:
            # Fallback colors
            return {
                "window_bg": "#0f172a",
                "bg_secondary": "#1e293b",
                "bg_tertiary": "#334155",
                "text_color": "#f8fafc",
                "text_secondary": "#cbd5e1",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8",
                "button_text": "#ffffff",
                "text_size": 11,
                "accent": "#38bdf8",
                "accent_gold": "#fca311",
                "border": "#475569",
                "success": "#10b981",
                "warning": "#f59e0b",
                "error": "#ef4444"
            }
    except Exception as e:
        print(f"⚠️ Error getting theme colors: {e}")
        return {}

# --------------------------
# Path Configuration
# --------------------------
CAM_PY_DIR = CURRENT_FILE_DIR
SETTINGS_JSON_PATH = os.path.join(MAIN_DIR, "settings.json")
SETTINGS_FOLDER = os.path.join(MAIN_DIR, "settings")
CAMERA_SETTINGS_PATH = os.path.join(SETTINGS_FOLDER, "camera_settings.py")

CAPTURE_DIR = os.path.join(MAIN_DIR, "captures")
RECORD_DIR = os.path.join(MAIN_DIR, "records")
os.makedirs(CAPTURE_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

DEFAULT_HSV_LOW = np.array([0, 120, 70])
DEFAULT_HSV_HIGH = np.array([10, 255, 255])

DEFAULT_SHARPEN_STRENGTH = 0
DEFAULT_NOISE_REDUCTION = 0
DEFAULT_CLAHE_CLIP = 2.0
DEFAULT_CLAHE_GRID = 8

START_BTN_COLOR = "#10b981"
START_BTN_HOVER = "#059669"
STOP_BTN_COLOR = "#ef4444"
STOP_BTN_HOVER = "#dc2626"

BUTTON_WIDTH_SMALL = 80
BUTTON_WIDTH_MEDIUM = 100
BUTTON_WIDTH_LARGE = 160
BUTTON_HEIGHT = 24
FILTER_BUTTON_WIDTH = 112

class CameraControlWidget(QWidget):
    settings_updated = pyqtSignal(dict)

    def __init__(self, theme=None, parent=None):
        super().__init__(parent)
        
        # Get theme from manager if not provided
        if theme is None:
            self.theme = get_theme_colors()
        elif isinstance(theme, dict):
            self.theme = theme
        else:
            self.theme = get_theme_colors()

        # Ensure all required keys exist with proper QColor conversion
        self._ensure_theme_complete()

        self.camera_active = False
        self.recording = False
        self.cap = None
        self.video_writer = None

        self.mouse_x = 0
        self.mouse_y = 0
        self.image_w = 0
        self.image_h = 0

        self.filter_mode = "RGB"
        self.hsv_low = DEFAULT_HSV_LOW
        self.hsv_high = DEFAULT_HSV_HIGH

        self.sharpen_strength = DEFAULT_SHARPEN_STRENGTH
        self.noise_reduction = DEFAULT_NOISE_REDUCTION
        self.clahe_clip = DEFAULT_CLAHE_CLIP
        self.clahe_grid = DEFAULT_CLAHE_GRID

        self.camera_settings = self.load_camera_settings()
        self.resolution = self._parse_resolution(self.camera_settings["resolution"])
        self.fps = self.camera_settings["fps"]
        self.exposure = self.camera_settings["exposure"]

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._setup_style()
        self._build_ui()
        self._setup_camera_timer()
        self._update_start_stop_button_style(start_mode=True)

        # DO NOT connect to theme manager here - updates come from parent tab
        # Theme updates will be handled via update_theme() method

    def _ensure_theme_complete(self):
        """Ensure theme has all required keys with QColor conversion"""
        # Add default QColor values if missing
        if 'bg_top' not in self.theme:
            self.theme['bg_top'] = QColor(10, 20, 40)
        if 'bg_mid' not in self.theme:
            self.theme['bg_mid'] = QColor(20, 30, 50)
        if 'bg_bottom' not in self.theme:
            self.theme['bg_bottom'] = QColor(30, 40, 60)
        if 'grid' not in self.theme:
            self.theme['grid'] = QColor(100, 150, 200, 80)
        if 'text' not in self.theme:
            self.theme['text'] = QColor(200, 220, 255)
        if 'accent' not in self.theme:
            self.theme['accent'] = QColor(252, 163, 17)
        if 'button_bg_transparent' not in self.theme:
            self.theme['button_bg_transparent'] = QColor(30, 41, 59, 180)
        if 'button_text_color' not in self.theme:
            self.theme['button_text_color'] = QColor(248, 250, 252)
        if 'below_horizon' not in self.theme:
            self.theme['below_horizon'] = QColor(255, 100, 100)
        if 'motor_position_above' not in self.theme:
            self.theme['motor_position_above'] = QColor(0, 255, 0, 200)
        if 'motor_position_below' not in self.theme:
            self.theme['motor_position_below'] = QColor(255, 165, 0, 200)
        if 'motor_position_out_of_range' not in self.theme:
            self.theme['motor_position_out_of_range'] = QColor(255, 0, 0, 200)
        if 'success_color' not in self.theme:
            self.theme['success_color'] = QColor(16, 185, 129)
        if 'error_color' not in self.theme:
            self.theme['error_color'] = QColor(239, 68, 68)

    def _parse_resolution(self, res_text):
        if "x" in res_text:
            return res_text.split(" ")[0]
        return "1280x720"

    def load_camera_settings(self):
        default_settings = {
            "resolution": "1920x1080 (Full HD)",
            "fps": 30,
            "exposure": 1.0
        }

        # Try to load from global settings first
        if GLOBAL_SETTINGS_AVAILABLE:
            try:
                if hasattr(global_settings, 'get_camera_settings'):
                    cam_settings = global_settings.get_camera_settings()
                    default_settings.update(cam_settings)
            except:
                pass

        try:
            if os.path.exists(SETTINGS_JSON_PATH):
                with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                    all_settings = json.load(f)
                    camera_settings = all_settings.get("camera_settings", default_settings)

                    camera_settings["resolution"] = camera_settings.get("resolution", default_settings["resolution"])
                    if "x" not in camera_settings["resolution"]:
                        camera_settings["resolution"] = default_settings["resolution"]
                    camera_settings["fps"] = max(1, min(60, int(camera_settings.get("fps", default_settings["fps"]))))
                    camera_settings["exposure"] = max(0.1, min(10.0, float(camera_settings.get("exposure", default_settings["exposure"]))))

                    print(f"[Cam.py] Loaded settings: {camera_settings}")
                    return camera_settings
            else:
                self.save_camera_settings(default_settings)
                return default_settings
        except Exception as e:
            QMessageBox.warning(self, "Settings Error", f"Failed to load camera settings:\n{str(e)}\nUsing default values.")
            return default_settings

    def save_camera_settings(self, settings):
        try:
            if os.path.exists(SETTINGS_JSON_PATH):
                with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}

            all_settings["camera_settings"] = settings

            with open(SETTINGS_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(all_settings, f, indent=4)

            print(f"[Cam.py] Saved settings to JSON: {settings}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", "Failed to save camera settings")

    def _setup_style(self):
        bg_color = self.theme.get("window_bg", "#0f172a")
        text_color = self.theme.get("text_color", "#f8fafc")
        btn_bg = self.theme.get("button_bg", "#2563eb")
        btn_hover = self.theme.get("button_hover", "#38bdf8")
        btn_text = self.theme.get("button_text", "#ffffff")
        text_size = self.theme.get("text_size", 11)
        accent = self.theme.get("accent_gold", "#fca311")
        border = self.theme.get("border", "#475569")

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
                border-radius: 4px;
                padding: 4px 8px;
                font-size: {text_size - 1}px;
                font-weight: bold;
                margin: 2px;
                min-height: {BUTTON_HEIGHT}px;
                max-height: {BUTTON_HEIGHT + 4}px;
            }}
            QPushButton#start_stop_btn {{
                min-width: {BUTTON_WIDTH_LARGE}px;
                max-width: {BUTTON_WIDTH_LARGE + 20}px;
            }}
            QPushButton#capture_btn, QPushButton#record_btn, 
            QPushButton#cam_btn, QPushButton#filter_btn {{
                background-color: {btn_bg};
                color: {btn_text};
                min-width: {BUTTON_WIDTH_SMALL}px;
                max-width: {FILTER_BUTTON_WIDTH}px;
            }}
            QPushButton#capture_btn:hover, QPushButton#record_btn:hover,
            QPushButton#cam_btn:hover, QPushButton#filter_btn:hover {{
                background-color: {btn_hover};
                color: {btn_text};
            }}
            QPushButton#filter_btn.active {{
                background-color: #d946ef;
            }}
            QPushButton:disabled {{
                background-color: #475569;
                color: #94a3b8;
            }}
            QLabel {{
                border: none;
                font-size: {text_size - 2}px;
                background-color: transparent;
                padding: 2px;
            }}
            QLabel#feed_label {{
                border: 1px solid {border};
                border-radius: 4px;
                background-color: #1e293b;
            }}
            QStackedWidget {{
                border: 1px solid {border};
                border-radius: 4px;
                background-color: #1e293b;
            }}
            QSlider {{
                background-color: transparent;
                height: 20px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #334155;
                border-radius: 3px;
                border: none;
            }}
            QSlider::handle:horizontal {{
                background: {btn_bg};
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
                border: none;
            }}
            QSlider::handle:horizontal:hover {{
                background: {btn_hover};
            }}
        """
        self.setStyleSheet(style_sheet)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)

        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(0)

        self.display_stack = QStackedWidget()
        
        self.sky_map = SkyMapWidget(theme=self.theme)
        self.sky_map.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.display_stack.addWidget(self.sky_map)
        
        self.feed_label = QLabel("📹 Camera Feed")
        self.feed_label.setObjectName("feed_label")
        self.feed_label.setAlignment(Qt.AlignCenter)
        self.feed_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.feed_label.setScaledContents(True)
        self.feed_label.setMouseTracking(True)
        self.display_stack.addWidget(self.feed_label)
        
        self.display_stack.setCurrentIndex(0)
        
        display_layout.addWidget(self.display_stack, stretch=1)
        main_layout.addLayout(display_layout, stretch=7)

        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(4, 4, 4, 4)
        control_layout.setSpacing(4)
        control_layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        self.start_stop_btn = QPushButton("Start Camera")
        self.start_stop_btn.setObjectName("start_stop_btn")
        self.start_stop_btn.clicked.connect(self.toggle_camera)
        control_layout.addWidget(self.start_stop_btn, alignment=Qt.AlignCenter)

        capture_record_layout = QHBoxLayout()
        capture_record_layout.setSpacing(4)
        capture_record_layout.setAlignment(Qt.AlignCenter)

        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setObjectName("capture_btn")
        self.capture_btn.clicked.connect(self.capture_image)
        self.capture_btn.setEnabled(False)
        capture_record_layout.addWidget(self.capture_btn)

        self.record_btn = QPushButton("Record")
        self.record_btn.setObjectName("record_btn")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(False)
        capture_record_layout.addWidget(self.record_btn)

        control_layout.addLayout(capture_record_layout)

        settings_filter_layout = QHBoxLayout()
        settings_filter_layout.setSpacing(4)
        settings_filter_layout.setAlignment(Qt.AlignCenter)

        self.cam_btn = QPushButton("Settings")
        self.cam_btn.setObjectName("cam_btn")
        self.cam_btn.clicked.connect(self.open_cam_settings)
        settings_filter_layout.addWidget(self.cam_btn)

        self.filter_btn = QPushButton("RGB")
        self.filter_btn.setObjectName("filter_btn")
        self.filter_btn.clicked.connect(self.toggle_filter_mode)
        self.filter_btn.setEnabled(False)
        settings_filter_layout.addWidget(self.filter_btn)

        control_layout.addLayout(settings_filter_layout)

        clahe_layout = QVBoxLayout()
        clahe_layout.setSpacing(1)
        clahe_layout.setAlignment(Qt.AlignCenter)
        
        self.clahe_label = QLabel(f"CLAHE: {self.clahe_clip:.1f}")
        self.clahe_label.setAlignment(Qt.AlignCenter)
        clahe_layout.addWidget(self.clahe_label)
        
        self.clahe_slider = QSlider(Qt.Horizontal)
        self.clahe_slider.setRange(10, 50)
        self.clahe_slider.setValue(int(self.clahe_clip * 10))
        self.clahe_slider.setMinimumWidth(150)
        self.clahe_slider.setMaximumWidth(200)
        self.clahe_slider.setEnabled(False)
        self.clahe_slider.valueChanged.connect(self.on_clahe_change)
        clahe_layout.addWidget(self.clahe_slider)
        
        control_layout.addLayout(clahe_layout)

        sharpen_layout = QVBoxLayout()
        sharpen_layout.setSpacing(1)
        sharpen_layout.setAlignment(Qt.AlignCenter)
        
        self.sharpen_label = QLabel(f"Sharpen: {self.sharpen_strength}%")
        self.sharpen_label.setAlignment(Qt.AlignCenter)
        sharpen_layout.addWidget(self.sharpen_label)
        
        self.sharpen_slider = QSlider(Qt.Horizontal)
        self.sharpen_slider.setRange(0, 100)
        self.sharpen_slider.setValue(self.sharpen_strength)
        self.sharpen_slider.setMinimumWidth(150)
        self.sharpen_slider.setMaximumWidth(200)
        self.sharpen_slider.setEnabled(False)
        self.sharpen_slider.valueChanged.connect(self.on_sharpen_change)
        sharpen_layout.addWidget(self.sharpen_slider)
        
        control_layout.addLayout(sharpen_layout)

        noise_layout = QVBoxLayout()
        noise_layout.setSpacing(1)
        noise_layout.setAlignment(Qt.AlignCenter)
        
        self.noise_label = QLabel(f"Noise: {self.noise_reduction}%")
        self.noise_label.setAlignment(Qt.AlignCenter)
        noise_layout.addWidget(self.noise_label)
        
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(0, 100)
        self.noise_slider.setValue(self.noise_reduction)
        self.noise_slider.setMinimumWidth(150)
        self.noise_slider.setMaximumWidth(200)
        self.noise_slider.setEnabled(False)
        self.noise_slider.valueChanged.connect(self.on_noise_change)
        noise_layout.addWidget(self.noise_slider)
        
        control_layout.addLayout(noise_layout)

        control_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        main_layout.addLayout(control_layout, stretch=3)

    def _update_start_stop_button_style(self, start_mode):
        text_size = self.theme.get("text_size", 11) - 1
        if start_mode:
            self.start_stop_btn.setText("Start Camera")
            self.start_stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {START_BTN_COLOR};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: {text_size}px;
                    font-weight: bold;
                    margin: 2px;
                    min-height: {BUTTON_HEIGHT}px;
                    min-width: {BUTTON_WIDTH_LARGE}px;
                    max-width: {BUTTON_WIDTH_LARGE + 20}px;
                }}
                QPushButton:hover {{
                    background-color: {START_BTN_HOVER};
                }}
            """)
        else:
            self.start_stop_btn.setText("Stop Camera")
            self.start_stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {STOP_BTN_COLOR};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: {text_size}px;
                    font-weight: bold;
                    margin: 2px;
                    min-height: {BUTTON_HEIGHT}px;
                    min-width: {BUTTON_WIDTH_LARGE}px;
                    max-width: {BUTTON_WIDTH_LARGE + 20}px;
                }}
                QPushButton:hover {{
                    background-color: {STOP_BTN_HOVER};
                }}
            """)

    def on_clahe_change(self, value):
        self.clahe_clip = value / 10.0
        self.clahe_label.setText(f"CLAHE: {self.clahe_clip:.1f}")

    def on_sharpen_change(self, value):
        self.sharpen_strength = value
        self.sharpen_label.setText(f"Sharpen: {value}%")

    def on_noise_change(self, value):
        self.noise_reduction = value
        self.noise_label.setText(f"Noise: {value}%")

    def toggle_filter_mode(self):
        if self.filter_mode == "RGB":
            self.filter_mode = "HSV"
            self.filter_btn.setText("HSV")
            self.filter_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d946ef;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10px;
                    font-weight: bold;
                    margin: 2px;
                    min-height: 22px;
                    min-width: 70px;
                    max-width: 100px;
                }
                QPushButton:hover {
                    background-color: #c026d3;
                }
            """)
        else:
            self.filter_mode = "RGB"
            self.filter_btn.setText("RGB")
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.theme.get('button_bg', '#2563eb')};
                    color: {self.theme.get('button_text', '#ffffff')};
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10px;
                    font-weight: bold;
                    margin: 2px;
                    min-height: 22px;
                    min-width: 70px;
                    max-width: 100px;
                }}
                QPushButton:hover {{
                    background-color: {self.theme.get('button_hover', '#38bdf8')};
                }}
            """)
        print(f"Filter mode switched to: {self.filter_mode}")

    def _apply_clahe(self, frame):
        if len(frame.shape) == 3:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=self.clahe_clip, tileGridSize=(self.clahe_grid, self.clahe_grid))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=self.clahe_clip, tileGridSize=(self.clahe_grid, self.clahe_grid))
            return clahe.apply(frame)

    def _apply_sharpen(self, frame):
        if self.sharpen_strength <= 0:
            return frame
        
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        strength = self.sharpen_strength / 50.0
        sharpened = cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)
        return sharpened

    def _apply_noise_reduction(self, frame):
        if self.noise_reduction <= 0:
            return frame
        
        h = self.noise_reduction / 5.0
        if len(frame.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(frame, None, h, h, 7, 21)
        else:
            return cv2.fastNlMeansDenoising(frame, None, h, 7, 21)

    def _apply_hsv_filter(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_low, self.hsv_high)
        return cv2.bitwise_and(frame, frame, mask=mask)

    def _apply_image_enhancements(self, frame):
        if self.noise_reduction > 0:
            frame = self._apply_noise_reduction(frame)
        
        frame = self._apply_clahe(frame)
        
        if self.sharpen_strength > 0:
            frame = self._apply_sharpen(frame)
        
        return frame

    def _setup_camera_timer(self):
        self.timer = QTimer()
        interval = max(10, int(1000 / self.fps))
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self.update_feed)

    def mouseMoveEvent(self, event):
        if self.camera_active and self.feed_label.rect().contains(self.feed_label.mapFromParent(event.pos())):
            label_pos = self.feed_label.mapFromParent(event.pos())
            label_w = self.feed_label.width()
            label_h = self.feed_label.height()

            if label_w > 0 and label_h > 0 and self.image_w > 0 and self.image_h > 0:
                scale_x = self.image_w / label_w
                scale_y = self.image_h / label_h
                self.mouse_x = int(label_pos.x() * scale_x)
                self.mouse_y = int(label_pos.y() * scale_y)

    def toggle_camera(self):
        if not self.camera_active:
            if self.start_camera():
                self._update_start_stop_button_style(start_mode=False)
                self.capture_btn.setEnabled(True)
                self.record_btn.setEnabled(True)
                self.filter_btn.setEnabled(True)
                self.sharpen_slider.setEnabled(True)
                self.noise_slider.setEnabled(True)
                self.clahe_slider.setEnabled(True)
                self.camera_active = True
                self.display_stack.setCurrentIndex(1)
        else:
            if self.recording:
                self.toggle_recording()
            self.stop_camera()
            self._update_start_stop_button_style(start_mode=True)
            self.capture_btn.setEnabled(False)
            self.record_btn.setEnabled(False)
            self.filter_btn.setEnabled(False)
            self.sharpen_slider.setEnabled(False)
            self.noise_slider.setEnabled(False)
            self.clahe_slider.setEnabled(False)
            self.camera_active = False
            self.display_stack.setCurrentIndex(0)

    def start_camera(self):
        try:
            w, h = map(int, self.resolution.split("x"))
            self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise Exception("Could not open USB camera")

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure * 100)

            self.image_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.image_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.timer.start()
            return True

        except Exception as e:
            QMessageBox.critical(self, "Camera Error", str(e))
            if self.cap:
                self.cap.release()
            return False

    def stop_camera(self):
        if self.cap:
            self.timer.stop()
            self.cap.release()
            self.cap = None

    def update_feed(self):
        if not self.cap or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if ret:
            self.image_h, self.image_w = frame.shape[:2]

            display_frame = frame.copy()
            display_frame = self._apply_image_enhancements(display_frame)

            if self.filter_mode == "HSV":
                display_frame = self._apply_hsv_filter(display_frame)

            if self.mouse_x > 0 and self.mouse_y > 0:
                cv2.line(display_frame, (self.mouse_x, 0), (self.mouse_x, self.image_h), (0, 255, 0), 1)
                cv2.line(display_frame, (0, self.mouse_y), (self.image_w, self.mouse_y), (0, 255, 0), 1)
                overlay_text = (
                    f"X:{self.mouse_x} Y:{self.mouse_y} | {self.filter_mode} "
                    f"| S:{self.sharpen_strength}% N:{self.noise_reduction}% C:{self.clahe_clip:.1f}"
                )
                cv2.putText(display_frame, overlay_text, (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.feed_label.setPixmap(QPixmap.fromImage(qt_image))

            if self.recording and self.video_writer:
                self.video_writer.write(frame)

    def capture_image(self):
        if not self.camera_active or not self.cap:
            QMessageBox.warning(self, "Error", "Camera not active")
            return

        ret, frame = self.cap.read()
        if ret:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            enhanced_frame = self._apply_image_enhancements(frame)
            if self.filter_mode == "HSV":
                enhanced_frame = self._apply_hsv_filter(enhanced_frame)
            
            save_path = os.path.join(CAPTURE_DIR, f"capture_{timestamp}_{self.filter_mode}.jpg")
            cv2.imwrite(save_path, enhanced_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            QMessageBox.information(self, "Success", f"Saved:\n{save_path}")

    def toggle_recording(self):
        if not self.camera_active or not self.cap:
            return

        if not self.recording:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(RECORD_DIR, f"record_{timestamp}.avi")
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self.video_writer = cv2.VideoWriter(save_path, fourcc, self.fps, (w, h))

            if self.video_writer.isOpened():
                self.recording = True
                self.record_btn.setText("Stop Recording")
        else:
            self.recording = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.record_btn.setText("Record")
            QMessageBox.information(self, "Saved", "Video saved")

    def open_cam_settings(self):
        if not os.path.exists(CAMERA_SETTINGS_PATH):
            QMessageBox.critical(self, "Error", "Camera settings file not found")
            return
        QProcess.startDetached(sys.executable, [CAMERA_SETTINGS_PATH], MAIN_DIR)
        QMessageBox.information(self, "Info", "Restart camera to apply settings")

    def update_theme(self, theme_input):
        """
        Update widget theme with new colors dictionary.
        This is called from the parent tab (cam_control.py) when theme changes.
        """
        if isinstance(theme_input, dict):
            self.theme = theme_input
            print(f"🎨 Camera widget updating theme with {len(self.theme)} colors")
        else:
            self.theme = get_theme_colors()
            print(f"⚠️ Camera widget received non-dict theme, using fallback")
        
        self._ensure_theme_complete()
        self._setup_style()
        
        # Update sky map if available
        if hasattr(self, 'sky_map') and hasattr(self.sky_map, 'update_theme'):
            self.sky_map.update_theme(self.theme)
        
        # Update button styles based on current camera state
        self._update_start_stop_button_style(start_mode=not self.camera_active)

    def closeEvent(self, event):
        if self.recording:
            self.toggle_recording()
        self.stop_camera()
        cv2.destroyAllWindows()
        event.accept()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Get theme colors safely
    test_theme = get_theme_colors()
    print(f"✅ Loaded theme colors: {list(test_theme.keys())}")

    window = CameraControlWidget(theme=test_theme)
    window.setWindowTitle("Camera Control - Compact UI")
    window.resize(850, 280)
    window.show()
    sys.exit(app.exec_())