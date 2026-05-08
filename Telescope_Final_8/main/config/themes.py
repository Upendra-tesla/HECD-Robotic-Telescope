#!/usr/bin/env python3
"""
Global Theme Manager for AI Telescope Control
Single source of truth for all themes
"""

import os
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFontDatabase


class GlobalThemeManager(QObject):
    """Global theme manager - single instance for entire application"""
    
    theme_changed = pyqtSignal(str, dict)  # (theme_name, colors_dict)
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the theme manager"""
        super().__init__()
        self._font_family = None
        self.themes = self._define_themes()
        self.theme_names = list(self.themes.keys())
        self.current_index = 0  # Start with Dark
        
        # Try to load saved theme from global settings
        try:
            from config.global_settings import global_settings
            saved_theme = global_settings.get_theme()
            if saved_theme in self.theme_names:
                self.current_index = self.theme_names.index(saved_theme)
        except:
            pass
    
    def _define_themes(self):
        """Define all four themes with proper contrast"""
        return {
            "Dark": {
                "name": "🌑 Dark",
                "bg": "#0f172a",          # Very dark blue
                "bg_secondary": "#1e293b",
                "bg_tertiary": "#334155",
                "text": "#f8fafc",         # Off-white
                "text_secondary": "#cbd5e1",
                "accent": "#38bdf8",        # Bright blue
                "accent_success": "#10b981",
                "accent_warning": "#f59e0b",
                "accent_error": "#ef4444",
                "border": "#475569",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8"
            },
            "Dark Blue": {
                "name": "🔵 Dark Blue",
                "bg": "#0c4a6e",          # Deep blue
                "bg_secondary": "#0f5b8c",
                "bg_tertiary": "#1e6f9f",
                "text": "#f0f9ff",         # Light cyan
                "text_secondary": "#bae6fd",
                "accent": "#fbbf24",        # Amber/gold for contrast
                "accent_success": "#34d399",
                "accent_warning": "#fbbf24",
                "accent_error": "#f87171",
                "border": "#7dd3fc",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8"
            },
            "Dark Red": {
                "name": "🔴 Dark Red",
                "bg": "#7f1d1d",          # Deep red
                "bg_secondary": "#991b1b",
                "bg_tertiary": "#b91c1c",
                "text": "#fee2e2",         # Light pink/red
                "text_secondary": "#fecaca",
                "accent": "#fde047",        # Bright yellow for contrast
                "accent_success": "#4ade80",
                "accent_warning": "#fde047",
                "accent_error": "#fca5a5",
                "border": "#f87171",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8"
            },
            "White": {
                "name": "⚪ White",
                "bg": "#ffffff",           # White
                "bg_secondary": "#f8fafc",
                "bg_tertiary": "#f1f5f9",
                "text": "#0f172a",          # Very dark blue for contrast
                "text_secondary": "#334155",
                "accent": "#2563eb",        # Bright blue
                "accent_success": "#059669",
                "accent_warning": "#d97706",
                "accent_error": "#dc2626",
                "border": "#cbd5e1",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8"
            }
        }
    
    def get_font_family(self):
        """Get the best available font family"""
        if self._font_family is None:
            try:
                available_fonts = QFontDatabase().families()
                
                preferred_fonts = [
                    'Noto Sans',
                    'DejaVu Sans',
                    'Liberation Sans',
                    'FreeSans',
                    'Arial',
                    'Helvetica',
                    'sans-serif'
                ]
                
                available_fallbacks = []
                
                for font in preferred_fonts:
                    if font in available_fonts or font == 'sans-serif':
                        if font == 'sans-serif':
                            available_fallbacks.append(font)
                        else:
                            available_fallbacks.append(f"'{font}'")
                
                if available_fallbacks:
                    self._font_family = ', '.join(available_fallbacks)
                else:
                    self._font_family = 'sans-serif'
            except:
                self._font_family = 'sans-serif'
        
        return self._font_family
    
    def get_current_theme(self):
        """Get current theme name"""
        return self.theme_names[self.current_index]
    
    def get_theme_name(self):
        """Get display name of current theme"""
        return self.themes[self.get_current_theme()]["name"]
    
    def get_colors(self, theme_name=None):
        """Get colors dictionary for specified or current theme"""
        if theme_name is None:
            theme_name = self.get_current_theme()
        return self.themes[theme_name]
    
    def get_color(self, key):
        """Get specific color value from current theme"""
        return self.themes[self.get_current_theme()].get(key, "#000000")
    
    def cycle_theme(self):
        """Cycle to next theme and save to settings"""
        self.current_index = (self.current_index + 1) % len(self.theme_names)
        theme_name = self.get_current_theme()
        colors = self.get_colors()
        
        # Save to global settings
        try:
            from config.global_settings import global_settings
            global_settings.set_theme(theme_name)
        except:
            pass
        
        self.theme_changed.emit(theme_name, colors)
    
    def set_theme(self, theme_name):
        """Set specific theme by name"""
        if theme_name in self.theme_names:
            self.current_index = self.theme_names.index(theme_name)
            colors = self.get_colors()
            
            # Save to global settings
            try:
                from config.global_settings import global_settings
                global_settings.set_theme(theme_name)
            except:
                pass
            
            self.theme_changed.emit(theme_name, colors)
            return True
        return False
    
    def get_stylesheet(self, theme_name=None):
        """Generate complete stylesheet for current theme"""
        colors = self.get_colors(theme_name)
        font_family = self.get_font_family()
        
        return f"""
            /* Main window */
            QMainWindow, QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
                border: none;
                font-family: {font_family};
            }}
            
            /* Central widget */
            QWidget#centralWidget {{
                background-color: transparent;
            }}
            
            /* Tab widget */
            QTabWidget::pane {{
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background-color: {colors['bg_secondary']};
                padding: 2px;
            }}
            
            QTabBar::tab {{
                background-color: {colors['bg_tertiary']};
                color: {colors['text']};
                padding: 6px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 10px;
                border: none;
                font-family: {font_family};
            }}
            
            QTabBar::tab:selected {{
                background-color: {colors['accent']};
                color: {colors['bg']};
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {colors['accent']};
                opacity: 0.7;
                color: {colors['bg']};
            }}
            
            /* Labels */
            QLabel {{
                color: {colors['text']};
                background-color: transparent;
                border: none;
                padding: 2px;
                font-size: 10px;
                font-family: {font_family};
            }}
            
            QLabel#windowTitle {{
                font-size: 13px;
                font-weight: bold;
                color: {colors['accent']};
            }}
            
            QLabel#statusLabel, QLabel#themeIndicator {{
                color: {colors['text_secondary']};
                background-color: {colors['bg_secondary']};
                border-radius: 3px;
                padding: 3px 8px;
            }}
            
            /* Buttons - general */
            QPushButton {{
                background-color: {colors['button_bg']};
                color: {colors['text']};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
                font-family: {font_family};
            }}
            
            QPushButton:hover {{
                background-color: {colors['button_hover']};
            }}
            
            QPushButton:pressed {{
                opacity: 0.6;
            }}
            
            QPushButton:disabled {{
                background-color: {colors['bg_tertiary']};
                color: {colors['text_secondary']};
            }}
            
            /* Group boxes */
            QGroupBox {{
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                margin-top: 8px;
                font-weight: bold;
                font-size: 10px;
                font-family: {font_family};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {colors['accent']};
            }}
            
            /* Scroll areas */
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            /* Sliders */
            QSlider::groove:horizontal {{
                height: 6px;
                background: {colors['bg_tertiary']};
                border-radius: 3px;
            }}
            
            QSlider::handle:horizontal {{
                background: {colors['accent']};
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            
            QSlider::groove:vertical {{
                width: 6px;
                background: {colors['bg_tertiary']};
                border-radius: 3px;
            }}
            
            QSlider::handle:vertical {{
                background: {colors['accent']};
                height: 14px;
                margin: 0 -4px;
                border-radius: 7px;
            }}
            
            /* Progress bars */
            QProgressBar {{
                border: 1px solid {colors['border']};
                border-radius: 3px;
                text-align: center;
                color: {colors['text']};
                background-color: {colors['bg_secondary']};
                font-size: 8px;
                font-family: {font_family};
            }}
            
            QProgressBar::chunk {{
                background-color: {colors['accent_success']};
                border-radius: 2px;
            }}
            
            /* Line edits / Spin boxes */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {colors['bg_secondary']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 3px;
                font-size: 9px;
                font-family: {font_family};
            }}
            
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {colors['accent']};
            }}
            
            /* Check boxes */
            QCheckBox {{
                color: {colors['text']};
                font-size: 9px;
                spacing: 4px;
                font-family: {font_family};
            }}
            
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
            }}
            
            QCheckBox::indicator:unchecked {{
                border: 1px solid {colors['border']};
                background: {colors['bg_secondary']};
            }}
            
            QCheckBox::indicator:checked {{
                border: 1px solid {colors['accent']};
                background: {colors['accent']};
            }}
            
            /* Radio buttons */
            QRadioButton {{
                color: {colors['text']};
                font-size: 9px;
                spacing: 4px;
                font-family: {font_family};
            }}
            
            QRadioButton::indicator {{
                width: 12px;
                height: 12px;
            }}
            
            QRadioButton::indicator:unchecked {{
                border: 1px solid {colors['border']};
                background: {colors['bg_secondary']};
                border-radius: 6px;
            }}
            
            QRadioButton::indicator:checked {{
                border: 1px solid {colors['accent']};
                background: {colors['accent']};
                border-radius: 6px;
            }}
            
            /* Tooltips */
            QToolTip {{
                background-color: {colors['bg']};
                color: {colors['text']};
                border: 1px solid {colors['accent']};
                border-radius: 3px;
                padding: 4px;
                font-size: 9px;
                font-family: {font_family};
            }}
        """


# Create global instance
theme_manager = GlobalThemeManager()