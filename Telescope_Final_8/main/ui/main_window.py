# ui/main_window.py
#!/usr/bin/env python3
"""
Main Window for AI-Powered Robotic Telescope Control
- Size loaded from global settings
- Borderless design with drag to move
- Lazy loading tabs (1 and 5 active, 2,3,4 lazy)
- Integrated global theme manager with cycling themes
- Proper theme propagation to all tabs
- Keyboard shortcuts for common operations
- FIXED: Proper handling of QColor objects from theme manager
"""

import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QApplication, QShortcut
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QFont, QColor, QKeySequence

from config.themes import theme_manager
from ui.tab_manager import TabManager


# ==================== HELPER FUNCTIONS FOR COLOR HANDLING ====================

def ensure_hex_color(color):
    """
    Convert any color input to hex string format
    Handles QColor objects, hex strings, and other formats
    """
    if color is None:
        return "#000000"
    
    if isinstance(color, QColor):
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"
    
    if isinstance(color, str):
        # If it's already a hex string, return as is
        if color.startswith('#'):
            return color
        # Try to parse as RGB tuple string? For now, return default
        return "#000000"
    
    # If it's a tuple/list of RGB values
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    
    return "#000000"


def get_contrasting_color(color_input):
    """
    Return black or white based on background luminance for maximum contrast
    Uses WCAG relative luminance formula
    Handles both string colors and QColor objects
    """
    # Convert input to QColor if it's a string
    if isinstance(color_input, str):
        color = QColor(color_input)
    elif isinstance(color_input, QColor):
        color = color_input
    else:
        # Default to black if invalid
        return "#000000"
    
    # Get RGB values normalized to 0-1
    r = color.red() / 255.0
    g = color.green() / 255.0
    b = color.blue() / 255.0
    
    # Calculate luminance (WCAG formula)
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    # Return black for light backgrounds, white for dark backgrounds
    return "#000000" if luminance > 0.5 else "#ffffff"


def rgba_color(color_input, opacity=0.10):
    """Convert color to rgba with opacity - handles QColor and strings"""
    if isinstance(color_input, QColor):
        return f"rgba({color_input.red()}, {color_input.green()}, {color_input.blue()}, {opacity})"
    elif isinstance(color_input, str):
        color_input = color_input.lstrip('#')
        if len(color_input) == 3:
            color_input = ''.join([c*2 for c in color_input])
        if len(color_input) >= 6:
            r = int(color_input[0:2], 16)
            g = int(color_input[2:4], 16)
            b = int(color_input[4:6], 16)
            return f"rgba({r}, {g}, {b}, {opacity})"
    return f"rgba(0, 0, 0, {opacity})"


def get_color_value(color_dict, key, default="#000000"):
    """Safely get a color value from a dictionary, converting QColor to hex if needed"""
    value = color_dict.get(key, default)
    return ensure_hex_color(value)


class MainWindow(QMainWindow):
    """Main application window with borderless design and theme support"""
    
    def __init__(self, width=850, height=570):
        super().__init__()
        
        # Window properties - size from settings
        self.window_width = width
        self.window_height = height
        self.setWindowTitle("AI Telescope Control")
        self.setFixedSize(self.window_width, self.window_height)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Track running processes
        self.running_workers = []
        self.cleanup_in_progress = False
        
        print(f"🏠 Main window size: {self.window_width}x{self.window_height}")
        print(f"🎨 Using global theme manager")
        
        # Get current theme from global theme manager
        self.current_theme = theme_manager.get_current_theme()
        self.current_colors = theme_manager.get_colors()
        
        # Drag window variables
        self.drag_position = None
        
        # Setup UI
        self.setup_ui()
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Apply initial theme
        self.apply_theme()
        
        # Connect theme changed signal from global theme manager
        theme_manager.theme_changed.connect(self.on_theme_changed)
    
    def register_worker(self, worker):
        """Register a running worker thread for cleanup"""
        if worker not in self.running_workers:
            self.running_workers.append(worker)
    
    def unregister_worker(self, worker):
        """Unregister a completed worker thread"""
        if worker in self.running_workers:
            self.running_workers.remove(worker)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+Q - Quit
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.quit_shortcut.activated.connect(self.close_application)
        
        # Ctrl+R - Restart
        self.restart_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.restart_shortcut.activated.connect(self.restart_application)
        
        # Ctrl+T - Cycle theme
        self.theme_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.theme_shortcut.activated.connect(self.cycle_theme)
        
        # F5 - Refresh all data
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.refresh_all_data)
        
        # Ctrl+1 through Ctrl+5 - Switch tabs
        self.tab1_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        self.tab1_shortcut.activated.connect(lambda: self.switch_to_tab(0))
        
        self.tab2_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        self.tab2_shortcut.activated.connect(lambda: self.switch_to_tab(1))
        
        self.tab3_shortcut = QShortcut(QKeySequence("Ctrl+3"), self)
        self.tab3_shortcut.activated.connect(lambda: self.switch_to_tab(2))
        
        self.tab4_shortcut = QShortcut(QKeySequence("Ctrl+4"), self)
        self.tab4_shortcut.activated.connect(lambda: self.switch_to_tab(3))
        
        self.tab5_shortcut = QShortcut(QKeySequence("Ctrl+5"), self)
        self.tab5_shortcut.activated.connect(lambda: self.switch_to_tab(4))
        
        # F1 - Help
        self.help_shortcut = QShortcut(QKeySequence("F1"), self)
        self.help_shortcut.activated.connect(self.show_help)
        
        # Ctrl+S - Save current settings
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save_current_settings)
        
        # Space - Emergency stop (if implemented)
        self.emergency_stop_shortcut = QShortcut(QKeySequence("Space"), self)
        self.emergency_stop_shortcut.activated.connect(self.emergency_stop)
    
    def switch_to_tab(self, index):
        """Switch to a specific tab by index"""
        if hasattr(self, 'tab_widget'):
            if 0 <= index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(index)
                self.update_status(f"Switched to tab {index + 1}")
    
    def refresh_all_data(self):
        """Refresh all data in current tab"""
        self.update_status("Refreshing data...")
        current_index = self.tab_widget.currentIndex()
        current_tab = self.tab_widget.widget(current_index)
        
        # Try to call refresh method if exists
        if hasattr(current_tab, 'refresh_all_data'):
            current_tab.refresh_all_data()
        elif hasattr(current_tab, 'refresh_regular_data'):
            current_tab.refresh_regular_data()
        elif hasattr(current_tab, 'refresh'):
            current_tab.refresh()
        else:
            self.update_status("No refresh method available")
    
    def show_help(self):
        """Show help dialog"""
        help_text = """
        <h3>AI Telescope Control - Keyboard Shortcuts</h3>
        <table>
        <tr><td><b>Ctrl+Q</b></td><td>Quit application</td></tr>
        <tr><td><b>Ctrl+R</b></td><td>Restart application</td></tr>
        <tr><td><b>Ctrl+T</b></td><td>Cycle themes</td></tr>
        <tr><td><b>F5</b></td><td>Refresh current tab</td></tr>
        <tr><td><b>Ctrl+1-5</b></td><td>Switch to tab 1-5</td></tr>
        <tr><td><b>F1</b></td><td>Show this help</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Save settings</td></tr>
        <tr><td><b>Space</b></td><td>Emergency stop</td></tr>
        </table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", help_text)
    
    def save_current_settings(self):
        """Save current settings"""
        self.update_status("Settings saved")
        # This would connect to actual save functionality
    
    def emergency_stop(self):
        """Emergency stop all motors (placeholder)"""
        self.update_status("⚠️ EMERGENCY STOP ACTIVATED")
        # This would connect to motor control
    
    def update_status(self, message):
        """Update status bar message"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"✅ {message}")
    
    def setup_ui(self):
        """Setup the main user interface"""
        # Central widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Top bar with window controls and theme button
        top_bar = self.create_top_bar()
        main_layout.addLayout(top_bar)
        
        # Tab manager - handles lazy loading
        self.tab_manager = TabManager()
        self.tab_widget = self.tab_manager.get_tab_widget()
        
        # Connect tab manager to this window for worker registration
        if hasattr(self.tab_manager, 'set_main_window'):
            self.tab_manager.set_main_window(self)
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar at bottom
        status_bar = self.create_status_bar()
        main_layout.addLayout(status_bar)
    
    def create_top_bar(self):
        """Create the top bar with window controls and theme button"""
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(5, 2, 5, 2)
        top_layout.setSpacing(8)
        
        # Window title/logo area
        title_label = QLabel("🔭 AI Telescope Control")
        title_label.setObjectName("windowTitle")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        # Theme toggle button
        self.theme_btn = QPushButton("🎨 Theme (Ctrl+T)")
        self.theme_btn.setFixedSize(120, 26)
        self.theme_btn.clicked.connect(self.cycle_theme)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("Cycle themes (Ctrl+T)")
        top_layout.addWidget(self.theme_btn)
        
        # Restart button
        self.restart_btn = QPushButton("🔄 Restart (Ctrl+R)")
        self.restart_btn.setFixedSize(120, 26)
        self.restart_btn.clicked.connect(self.restart_application)
        self.restart_btn.setCursor(Qt.PointingHandCursor)
        self.restart_btn.setToolTip("Restart application (Ctrl+R)")
        top_layout.addWidget(self.restart_btn)
        
        # Minimize button
        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(40, 26)
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setToolTip("Minimize window")
        top_layout.addWidget(self.min_btn)
        
        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(40, 26)
        self.close_btn.clicked.connect(self.close_application)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Close application (Ctrl+Q)")
        top_layout.addWidget(self.close_btn)
        
        return top_layout
    
    def create_status_bar(self):
        """Create status bar at bottom of window"""
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(8, 2, 8, 2)
        
        self.status_label = QLabel("✅ System Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("font-size: 9px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Shortcut hint
        shortcut_hint = QLabel("F1 for help | Ctrl+T theme | Ctrl+R restart | Ctrl+Q quit")
        shortcut_hint.setObjectName("shortcutHint")
        shortcut_hint.setStyleSheet("font-size: 8px; opacity: 0.7;")
        status_layout.addWidget(shortcut_hint)
        
        self.theme_indicator = QLabel(theme_manager.get_theme_name())
        self.theme_indicator.setObjectName("themeIndicator")
        self.theme_indicator.setStyleSheet("font-size: 9px; font-style: italic;")
        status_layout.addWidget(self.theme_indicator)
        
        return status_layout
    
    def cycle_theme(self):
        """Cycle to next theme using global theme manager"""
        theme_manager.cycle_theme()
    
    def on_theme_changed(self, theme_name, colors):
        """Handle theme change - propagate to all tabs"""
        self.current_theme = theme_name
        self.current_colors = colors
        self.apply_theme()
        self.theme_indicator.setText(theme_manager.get_theme_name())
        
        # Propagate theme to tab manager (which will update all tabs)
        if hasattr(self, 'tab_manager'):
            self.tab_manager.update_theme(theme_name, colors)
    
    def apply_theme(self):
        """Apply current theme stylesheet to the main window with proper contrast"""
        # Safely get color values as hex strings
        bg_color = get_color_value(self.current_colors, 'bg', '#0f172a')
        bg_secondary = get_color_value(self.current_colors, 'bg_secondary', '#1e293b')
        bg_tertiary = get_color_value(self.current_colors, 'bg_tertiary', '#334155')
        accent = get_color_value(self.current_colors, 'accent', '#38bdf8')
        accent_success = get_color_value(self.current_colors, 'accent_success', '#10b981')
        accent_warning = get_color_value(self.current_colors, 'accent_warning', '#f59e0b')
        accent_error = get_color_value(self.current_colors, 'accent_error', '#ef4444')
        border = get_color_value(self.current_colors, 'border', '#475569')
        button_bg = get_color_value(self.current_colors, 'button_bg', '#2563eb')
        
        # Calculate contrasting text colors
        text_color = get_contrasting_color(bg_color)
        text_secondary = get_contrasting_color(bg_secondary)
        
        # Get font family from global theme manager
        font_family = theme_manager.get_font_family()
        
        # Apply main stylesheet
        self.setStyleSheet(f"""
            /* Main window */
            QMainWindow, QDialog {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                font-family: {font_family};
            }}
            
            /* Central widget */
            QWidget#centralWidget {{
                background-color: transparent;
            }}
            
            /* Tab widget */
            QTabWidget::pane {{
                border: 1px solid {border};
                border-radius: 6px;
                background-color: {bg_secondary};
                padding: 2px;
            }}
            
            QTabBar::tab {{
                background-color: {bg_tertiary};
                color: {text_color};
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
                background-color: {accent};
                color: {bg_color};
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {accent};
                opacity: 0.7;
                color: {bg_color};
            }}
            
            /* Labels */
            QLabel {{
                color: {text_color};
                background-color: transparent;
                border: none;
                padding: 2px;
                font-size: 10px;
                font-family: {font_family};
            }}
            
            QLabel#windowTitle {{
                font-size: 13px;
                font-weight: bold;
                color: {accent};
            }}
            
            QLabel#statusLabel, QLabel#themeIndicator, QLabel#shortcutHint {{
                color: {text_secondary};
                background-color: {bg_secondary};
                border-radius: 3px;
                padding: 3px 8px;
            }}
            
            /* Buttons - general */
            QPushButton {{
                background-color: {button_bg};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
                font-family: {font_family};
            }}
            
            QPushButton:hover {{
                background-color: {accent};
                color: {bg_color};
            }}
            
            QPushButton:pressed {{
                opacity: 0.6;
            }}
            
            QPushButton:disabled {{
                background-color: {bg_tertiary};
                color: {text_secondary};
            }}
            
            /* Group boxes */
            QGroupBox {{
                color: {text_color};
                border: 1px solid {border};
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
                color: {accent};
            }}
            
            /* Scroll areas */
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            /* Sliders */
            QSlider::groove:horizontal {{
                height: 6px;
                background: {bg_tertiary};
                border-radius: 3px;
            }}
            
            QSlider::handle:horizontal {{
                background: {accent};
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            
            QSlider::groove:vertical {{
                width: 6px;
                background: {bg_tertiary};
                border-radius: 3px;
            }}
            
            QSlider::handle:vertical {{
                background: {accent};
                height: 14px;
                margin: 0 -4px;
                border-radius: 7px;
            }}
            
            /* Progress bars */
            QProgressBar {{
                border: 1px solid {border};
                border-radius: 3px;
                text-align: center;
                color: {text_color};
                background-color: {bg_secondary};
                font-size: 8px;
                font-family: {font_family};
            }}
            
            QProgressBar::chunk {{
                background-color: {accent_success};
                border-radius: 2px;
            }}
            
            /* Line edits / Spin boxes */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {bg_secondary};
                color: {text_color};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 3px;
                font-size: 9px;
                font-family: {font_family};
            }}
            
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {accent};
            }}
            
            /* Check boxes */
            QCheckBox {{
                color: {text_color};
                font-size: 9px;
                spacing: 4px;
                font-family: {font_family};
            }}
            
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
            }}
            
            QCheckBox::indicator:unchecked {{
                border: 1px solid {border};
                background: {bg_secondary};
            }}
            
            QCheckBox::indicator:checked {{
                border: 1px solid {accent};
                background: {accent};
            }}
            
            /* Radio buttons */
            QRadioButton {{
                color: {text_color};
                font-size: 9px;
                spacing: 4px;
                font-family: {font_family};
            }}
            
            QRadioButton::indicator {{
                width: 12px;
                height: 12px;
            }}
            
            QRadioButton::indicator:unchecked {{
                border: 1px solid {border};
                background: {bg_secondary};
                border-radius: 6px;
            }}
            
            QRadioButton::indicator:checked {{
                border: 1px solid {accent};
                background: {accent};
                border-radius: 6px;
            }}
            
            /* Tooltips */
            QToolTip {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 3px;
                padding: 4px;
                font-size: 9px;
                font-family: {font_family};
            }}
        """)
        
        # Update button text colors individually to ensure proper contrast
        self.update_button_colors()
    
    def update_button_colors(self):
        """Update button colors to ensure proper contrast"""
        # Safely get color values
        bg_color = get_color_value(self.current_colors, 'bg', '#0f172a')
        accent = get_color_value(self.current_colors, 'accent', '#38bdf8')
        
        # Calculate contrasting color for accent buttons
        accent_contrast = get_contrasting_color(accent)
        
        # Theme button
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {accent_contrast};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
                padding: 5px 8px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)
        
        # Restart button
        self.restart_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {accent_contrast};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
                padding: 5px 8px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)
        
        # Minimize button
        self.min_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {accent_contrast};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 0px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)
        
        # Close button
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {accent_contrast};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 0px;
            }}
            QPushButton:hover {{
                background-color: #ef4444;
                color: {accent_contrast};
            }}
        """)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging"""
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def cleanup_all_workers(self):
        """Stop all running worker threads and clean up cache"""
        if self.cleanup_in_progress:
            return
        
        self.cleanup_in_progress = True
        self.update_status("Cleaning up resources...")
        
        # Stop all registered workers
        for worker in self.running_workers[:]:  # Copy list to avoid modification during iteration
            try:
                if hasattr(worker, 'stop'):
                    worker.stop()
                if hasattr(worker, 'wait'):
                    worker.wait(2000)  # Wait up to 2 seconds
            except Exception as e:
                print(f"⚠️ Error stopping worker: {e}")
        
        self.running_workers.clear()
        
        # Clean up tab manager
        if hasattr(self, 'tab_manager'):
            try:
                self.tab_manager.cleanup()
            except Exception as e:
                print(f"⚠️ Error cleaning up tab manager: {e}")
        
        # Clear any cached data
        self.cleanup_cache()
    
    def cleanup_cache(self):
        """Clear any cached data"""
        # Clear QPixmap cache
        from PyQt5.QtGui import QPixmapCache
        QPixmapCache.clear()
        
        # Clear application cache if needed
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        if os.path.exists(cache_dir):
            try:
                import shutil
                shutil.rmtree(cache_dir, ignore_errors=True)
                os.makedirs(cache_dir, exist_ok=True)
            except Exception as e:
                print(f"⚠️ Error clearing cache: {e}")
    
    def restart_application(self):
        """Restart the application with proper cleanup"""
        reply = QMessageBox.question(
            self, 
            "Confirm Restart", 
            "Are you sure you want to restart the application?\nAll running processes will be stopped.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.update_status("Restarting application...")
            
            # Clean up all workers and cache
            self.cleanup_all_workers()
            
            # Get the path to main.py
            main_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
            
            # Small delay to ensure cleanup completes
            QTimer.singleShot(500, lambda: self._perform_restart(main_py))
    
    def _perform_restart(self, main_py):
        """Actually perform the restart after cleanup"""
        # Restart the application
        QApplication.quit()
        subprocess.Popen([sys.executable, main_py])
    
    def close_application(self):
        """Close application with confirmation and proper cleanup"""
        reply = QMessageBox.question(
            self, 
            "Confirm Exit", 
            "Are you sure you want to exit?\nAll running processes will be stopped.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.update_status("Shutting down...")
            
            # Clean up all workers and cache
            self.cleanup_all_workers()
            
            # Small delay to ensure cleanup completes
            QTimer.singleShot(500, QApplication.quit)
    
    def closeEvent(self, event):
        """Handle close event for proper cleanup"""
        # If user clicks X, do proper cleanup
        self.cleanup_all_workers()
        event.accept()