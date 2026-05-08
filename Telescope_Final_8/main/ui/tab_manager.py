# ui/tab_manager.py
#!/usr/bin/env python3
"""
Tab Manager with Lazy Loading
- Tabs 1 (Home) and 5 (Logs) are permanent (load at startup)
- Tabs 2, 3, 4 are lazy-loaded (load on first click)
- Home tab uses WeatherTab for weather and astronomy data
- AI Chat tab uses AIChatWidget for AI assistant
- Detection tab uses DetectTab from tabs/detect
- Controls tab uses CameraMotorControlTab from cam_control.py
- Propagates theme changes to all tabs using global theme manager
- Supports worker registration for cleanup
"""

import sys
import os

# Add the parent directory to path to find the tabs folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.dirname(CURRENT_DIR)
TABS_DIR = os.path.join(MAIN_DIR, "tabs")
CONFIG_DIR = os.path.join(MAIN_DIR, "config")

# Add directories to path
if TABS_DIR not in sys.path:
    sys.path.insert(0, TABS_DIR)
if CONFIG_DIR not in sys.path:
    sys.path.insert(0, CONFIG_DIR)
if MAIN_DIR not in sys.path:
    sys.path.insert(0, MAIN_DIR)

from PyQt5.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QLabel,
    QFrame, QTextEdit, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

# Import global theme manager
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
    print("✅ Tab Manager - Using global theme manager")
except ImportError as e:
    print(f"⚠️ Tab Manager - Could not import global theme manager: {e}")
    THEME_AVAILABLE = False
    theme_manager = None

# ==================== IMPORT ALL TAB WIDGETS ====================

# Import Weather Tab
try:
    from tabs.home.weather import WeatherTab
    print("✅ Successfully imported WeatherTab")
except ImportError as e:
    print(f"⚠️ Could not import WeatherTab: {e}")
    class WeatherTab(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("⚠️ Weather Tab Failed to Load"))
            layout.addWidget(QLabel(str(e)))
        def cleanup(self):
            pass

# Import AI Chat Tab
try:
    from tabs.chat.ai_chat import AIChatTab as AIChatWidget
    print("✅ Successfully imported AIChatWidget from tabs/chat/ai_chat.py")
except ImportError as e:
    print(f"⚠️ Could not import AIChatTab from tabs.chat: {e}")
    try:
        from ai_chat import AIChatTab as AIChatWidget
        print("✅ Successfully imported AIChatWidget from old location")
    except ImportError as e2:
        print(f"⚠️ Could not import AIChatTab: {e2}")
        class AIChatWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel("⚠️ AI Chat Tab Failed to Load"))
                layout.addWidget(QLabel(str(e2)))
            def cleanup(self):
                pass

# Import Detection Tab - FIXED: Use DetectTab from tabs.detect
try:
    from tabs.detect import DetectTab as DetectionWidget
    DETECTION_AVAILABLE = True
    print("✅ Successfully imported DetectTab from tabs/detect/__init__.py")
except ImportError as e:
    print(f"⚠️ Could not import DetectTab: {e}")
    DETECTION_AVAILABLE = False
    class DetectionWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("⚠️ Detection Tab Failed to Load"))
            layout.addWidget(QLabel(str(e)))
        def cleanup(self):
            pass

# Import Camera/Motor Controls Tab
try:
    from cam_control import CameraMotorControlTab as ControlsWidget
    print("✅ Successfully imported CameraMotorControlTab from cam_control.py")
except ImportError as e:
    print(f"⚠️ Could not import CameraMotorControlTab: {e}")
    try:
        from tabs.cam_control import CameraMotorControlTab as ControlsWidget
        print("✅ Successfully imported CameraMotorControlTab via tabs.cam_control")
    except ImportError as e2:
        print(f"⚠️ Alternative import also failed: {e2}")
        class ControlsWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel("⚠️ Camera/Motor Controls Tab Failed to Load"))
                layout.addWidget(QLabel(str(e2)))
            def cleanup(self):
                pass


# ==================== BASE TAB CLASS ====================

class BaseTab(QWidget):
    """Base class for all tabs with common functionality"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Base"
        self.running_workers = []
    
    def register_worker(self, worker):
        """Register a worker thread for cleanup"""
        self.running_workers.append(worker)
        # Also register with main window if available
        parent = self.parent()
        while parent:
            if hasattr(parent, 'register_worker'):
                parent.register_worker(worker)
                break
            parent = parent.parent()
    
    def unregister_worker(self, worker):
        """Unregister a worker thread"""
        if worker in self.running_workers:
            self.running_workers.remove(worker)
    
    def stop_all_workers(self):
        """Stop all running worker threads in this tab"""
        for worker in self.running_workers[:]:
            try:
                if hasattr(worker, 'stop'):
                    worker.stop()
                if hasattr(worker, 'wait'):
                    worker.wait(1000)
            except Exception as e:
                print(f"⚠️ Error stopping worker in {self.tab_title}: {e}")
        self.running_workers.clear()
    
    def setup_ui(self):
        """Setup basic tab UI - to be overridden by subclasses"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignCenter)
        
        placeholder = QLabel(f"📌 {self.tab_title} Tab Content")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 14px; font-weight: bold; opacity: 0.5;")
        layout.addWidget(placeholder)
    
    def on_tab_selected(self):
        """Called when tab is selected - useful for lazy loading"""
        pass
    
    def on_tab_deselected(self):
        """Called when tab is deselected - useful for cleanup"""
        pass
    
    def cleanup(self):
        """Clean up resources when tab is closed"""
        self.stop_all_workers()
    
    def update_theme(self, theme_colors):
        """Update tab theme - to be overridden by subclasses"""
        pass


# ==================== HOME TAB (TAB 1) ====================

class HomeTab(BaseTab):
    """Home tab (Tab 1) - Permanent - Weather & Astronomy"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Home"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup home tab with weather widget"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        try:
            self.weather_widget = WeatherTab(self)
            if hasattr(self.weather_widget, 'register_worker'):
                self.weather_widget.register_worker = self.register_worker
            layout.addWidget(self.weather_widget)
        except Exception as e:
            print(f"⚠️ Error creating WeatherTab: {e}")
            error_label = QLabel(f"⚠️ Weather Tab Error:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            layout.addWidget(error_label)
    
    def on_tab_selected(self):
        """Called when tab is selected"""
        if hasattr(self, 'weather_widget'):
            try:
                if hasattr(self.weather_widget, 'refresh_regular_data'):
                    self.weather_widget.refresh_regular_data()
            except:
                pass
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'weather_widget'):
            try:
                if hasattr(self.weather_widget, 'cleanup'):
                    self.weather_widget.cleanup()
            except:
                pass
        super().cleanup()
    
    def update_theme(self, theme_colors):
        """Update theme for home tab and its weather widget"""
        if hasattr(self, 'weather_widget'):
            try:
                if hasattr(self.weather_widget, 'update_theme'):
                    self.weather_widget.update_theme(theme_colors)
            except Exception as e:
                print(f"⚠️ Error updating weather widget theme: {e}")


# ==================== AI CHAT TAB (TAB 2) ====================

class AIChatTab(BaseTab):
    """AI Chat tab (Tab 2) - Lazy loaded"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "AI Chat"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup AI chat tab with the actual chat widget"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        try:
            self.chat_widget = AIChatWidget(self)
            if hasattr(self.chat_widget, 'register_worker'):
                self.chat_widget.register_worker = self.register_worker
            layout.addWidget(self.chat_widget)
        except Exception as e:
            print(f"⚠️ Error creating AIChatTab: {e}")
            error_label = QLabel(f"⚠️ AI Chat Error:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            layout.addWidget(error_label)
    
    def on_tab_selected(self):
        """Called when tab is selected"""
        pass
    
    def on_tab_deselected(self):
        """Called when tab is deselected - stop any running AI queries"""
        if hasattr(self, 'chat_widget'):
            try:
                if hasattr(self.chat_widget, 'stop_query'):
                    self.chat_widget.stop_query()
            except:
                pass
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'chat_widget'):
            try:
                if hasattr(self.chat_widget, 'cleanup'):
                    self.chat_widget.cleanup()
            except:
                pass
        super().cleanup()
    
    def update_theme(self, theme_colors):
        """Update theme for chat widget"""
        if hasattr(self, 'chat_widget'):
            try:
                if hasattr(self.chat_widget, 'update_theme'):
                    self.chat_widget.update_theme(theme_colors)
            except Exception as e:
                print(f"⚠️ Error updating chat widget theme: {e}")


# ==================== DETECTION TAB (TAB 3) ====================

class DetectionTab(BaseTab):
    """Object Detection tab (Tab 3) - Lazy loaded"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Detection"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup object detection tab UI"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        try:
            # FIXED: Use DetectionWidget imported from tabs.detect
            self.detection_widget = DetectionWidget(self)
            if hasattr(self.detection_widget, 'register_worker'):
                self.detection_widget.register_worker = self.register_worker
            layout.addWidget(self.detection_widget)
            print("✅ DetectionTab loaded successfully from tabs.detect")
        except Exception as e:
            print(f"⚠️ Error creating DetectionTab: {e}")
            import traceback
            traceback.print_exc()
            error_label = QLabel(f"⚠️ Detection Tab Error:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            layout.addWidget(error_label)
    
    def on_tab_selected(self):
        """Called when tab is selected"""
        if hasattr(self, 'detection_widget'):
            try:
                if hasattr(self.detection_widget, 'on_tab_selected'):
                    self.detection_widget.on_tab_selected()
            except:
                pass
    
    def on_tab_deselected(self):
        """Called when tab is deselected - stop any running detections"""
        if hasattr(self, 'detection_widget'):
            try:
                if hasattr(self.detection_widget, 'stop_detection'):
                    self.detection_widget.stop_detection()
            except:
                pass
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'detection_widget'):
            try:
                if hasattr(self.detection_widget, 'cleanup'):
                    self.detection_widget.cleanup()
            except:
                pass
        super().cleanup()
    
    def update_theme(self, theme_colors):
        """Update theme for detection widget"""
        if hasattr(self, 'detection_widget'):
            try:
                if hasattr(self.detection_widget, 'update_theme'):
                    self.detection_widget.update_theme(theme_colors)
            except Exception as e:
                print(f"⚠️ Error updating detection widget theme: {e}")


# ==================== CONTROLS TAB (TAB 4) ====================

class ControlsTab(BaseTab):
    """Camera & Motor Controls tab (Tab 4) - Lazy loaded"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Controls"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup camera and motor controls tab UI"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        try:
            self.controls_widget = ControlsWidget(self)
            if hasattr(self.controls_widget, 'register_worker'):
                self.controls_widget.register_worker = self.register_worker
            layout.addWidget(self.controls_widget)
            print("✅ ControlsTab loaded successfully from cam_control.py")
        except Exception as e:
            print(f"⚠️ Error creating ControlsTab: {e}")
            import traceback
            traceback.print_exc()
            error_label = QLabel(f"⚠️ Controls Tab Error:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            layout.addWidget(error_label)
    
    def on_tab_selected(self):
        """Called when tab is selected"""
        if hasattr(self, 'controls_widget'):
            try:
                if hasattr(self.controls_widget, 'on_tab_selected'):
                    self.controls_widget.on_tab_selected()
            except:
                pass
    
    def on_tab_deselected(self):
        """Called when tab is deselected - pause hardware updates"""
        if hasattr(self, 'controls_widget'):
            try:
                if hasattr(self.controls_widget, 'on_tab_deselected'):
                    self.controls_widget.on_tab_deselected()
            except:
                pass
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'controls_widget'):
            try:
                if hasattr(self.controls_widget, 'cleanup'):
                    self.controls_widget.cleanup()
            except:
                pass
        super().cleanup()
    
    def update_theme(self, theme_colors):
        """Update theme for controls widget"""
        if hasattr(self, 'controls_widget'):
            try:
                if hasattr(self.controls_widget, 'update_theme'):
                    self.controls_widget.update_theme(theme_colors)
            except Exception as e:
                print(f"⚠️ Error updating controls widget theme: {e}")


# ==================== LOGS TAB (TAB 5) ====================

class LogsTab(BaseTab):
    """Logs tab (Tab 5) - Permanent"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_title = "Logs"
        self.setup_ui()
    
    def setup_ui(self):
        """Setup logs tab with scrollable log viewer"""
        if self.layout() is not None:
            QWidget().setLayout(self.layout())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title = QLabel("📋 System Logs")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 5px;")
        layout.addWidget(title)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Monospace", 9))
        self.log_display.setMinimumHeight(350)
        layout.addWidget(self.log_display)
        
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignCenter)
        button_row.setSpacing(15)
        
        self.clear_btn = QPushButton("🗑️ Clear Logs")
        self.clear_btn.setFixedSize(120, 30)
        self.clear_btn.clicked.connect(self.clear_logs)
        button_row.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton("💾 Export Logs")
        self.export_btn.setFixedSize(120, 30)
        self.export_btn.clicked.connect(self.export_logs)
        button_row.addWidget(self.export_btn)
        
        layout.addLayout(button_row)
        
        self.add_log("System initialized")
    
    def add_log(self, message, level="INFO"):
        """Add a log message"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if level == "INFO":
            prefix = "ℹ️"
        elif level == "WARNING":
            prefix = "⚠️"
        elif level == "ERROR":
            prefix = "❌"
        elif level == "SUCCESS":
            prefix = "✅"
        else:
            prefix = "📌"
        
        self.log_display.append(f"[{timestamp}] {prefix} {message}")
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.End)
        self.log_display.setTextCursor(cursor)
    
    def clear_logs(self):
        """Clear all logs"""
        reply = QMessageBox.question(
            None,
            "Clear Logs",
            "Are you sure you want to clear all logs?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.log_display.clear()
            self.add_log("Logs cleared")
    
    def export_logs(self):
        """Export logs to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Logs",
            "telescope_logs.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.log_display.toPlainText())
                self.add_log(f"Logs exported to {file_path}")
                QMessageBox.information(None, "Success", "Logs exported successfully!")
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to export logs: {str(e)}")
    
    def on_tab_selected(self):
        """Called when tab is selected"""
        self.add_log("Logs tab viewed")
    
    def cleanup(self):
        """Clean up resources"""
        self.log_display.clear()
        super().cleanup()
    
    def update_theme(self, theme_colors):
        """Update theme for logs tab"""
        if theme_colors:
            bg_color = theme_colors.get('bg_secondary', '#1e293b')
            text_color = theme_colors.get('text', '#f8fafc')
            border = theme_colors.get('border', '#475569')
            
            self.log_display.setStyleSheet(f"""
                QTextEdit {{
                    border: 1px solid {border};
                    border-radius: 4px;
                    padding: 8px;
                    background-color: rgba(30, 41, 59, 0.15);
                    color: {text_color};
                }}
            """)


# ==================== TAB MANAGER ====================

class TabManager:
    """Manages tabs with lazy loading for tabs 2, 3, 4"""
    
    # Tab definitions: index, title, tab_class, is_permanent
    TAB_CONFIG = [
        (0, "🏠 Home", HomeTab, True),
        (1, "🤖 AI Chat", AIChatTab, False),
        (2, "🔍 Detection", DetectionTab, False),
        (3, "🎮 Controls", ControlsTab, False),
        (4, "📋 Logs", LogsTab, True),
    ]
    
    def __init__(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabBar().setCursor(Qt.PointingHandCursor)
        
        # Track loaded tabs
        self.loaded_tabs = {}  # index -> widget
        self.tab_instances = {}  # index -> tab object
        self._loading = False
        self.main_window = None
        
        self._create_tabs()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
    
    def set_main_window(self, main_window):
        """Set reference to main window for worker registration"""
        self.main_window = main_window
    
    def _create_tabs(self):
        """Create all tabs (permanent ones are loaded, lazy ones are placeholders)"""
        for idx, title, tab_class, is_permanent in self.TAB_CONFIG:
            if is_permanent:
                tab = tab_class(self.tab_widget)
                self.tab_widget.addTab(tab, title)
                self.loaded_tabs[idx] = tab
                self.tab_instances[idx] = tab
                
                if self.main_window and hasattr(tab, 'set_main_window'):
                    tab.set_main_window(self.main_window)
            else:
                placeholder = QWidget(self.tab_widget)
                placeholder.setObjectName(f"placeholder_{idx}")
                self.tab_widget.addTab(placeholder, title)
    
    def on_tab_changed(self, index):
        """Handle tab change - load lazy tab if needed"""
        if self._loading:
            return
        
        self._loading = True
        
        try:
            # Call on_tab_deselected for previously selected tab
            for idx, tab in self.tab_instances.items():
                if idx != index and hasattr(tab, 'on_tab_deselected'):
                    tab.on_tab_deselected()
            
            # Load lazy tab if needed
            for idx, title, tab_class, is_permanent in self.TAB_CONFIG:
                if idx == index and not is_permanent and idx not in self.loaded_tabs:
                    self._load_lazy_tab(idx, tab_class, title)
                    break
            
            # Call on_tab_selected for newly selected tab
            if index in self.tab_instances and hasattr(self.tab_instances[index], 'on_tab_selected'):
                self.tab_instances[index].on_tab_selected()
                
        finally:
            self._loading = False
    
    def _load_lazy_tab(self, index, tab_class, title):
        """Load a lazy tab and replace its placeholder"""
        tab = tab_class(self.tab_widget)
        
        if self.main_window and hasattr(tab, 'set_main_window'):
            tab.set_main_window(self.main_window)
        
        self.loaded_tabs[index] = tab
        self.tab_instances[index] = tab
        
        self.tab_widget.removeTab(index)
        self.tab_widget.insertTab(index, tab, title)
        self.tab_widget.setCurrentIndex(index)
    
    def get_tab_widget(self):
        """Get the tab widget"""
        return self.tab_widget
    
    def get_tab(self, index):
        """Get tab instance by index (loads if necessary)"""
        if index in self.loaded_tabs:
            return self.loaded_tabs[index]
        
        for idx, title, tab_class, is_permanent in self.TAB_CONFIG:
            if idx == index:
                self._load_lazy_tab(index, tab_class, title)
                return self.loaded_tabs[index]
        
        return None
    
    def cleanup(self):
        """Clean up all tabs"""
        for tab in self.tab_instances.values():
            try:
                tab.cleanup()
            except Exception as e:
                print(f"⚠️ Error cleaning up tab: {e}")
        
        if 4 in self.tab_instances and hasattr(self.tab_instances[4], 'log_display'):
            try:
                self.tab_instances[4].log_display.clear()
            except:
                pass
        
        self.tab_instances.clear()
        self.loaded_tabs.clear()
    
    def update_theme(self, theme_name, theme_colors):
        """Update theme for all loaded tabs"""
        for idx, tab in self.tab_instances.items():
            try:
                if hasattr(tab, 'update_theme'):
                    tab.update_theme(theme_colors)
                elif hasattr(tab, 'weather_widget') and hasattr(tab.weather_widget, 'update_theme'):
                    tab.weather_widget.update_theme(theme_colors)
                elif hasattr(tab, 'chat_widget') and hasattr(tab.chat_widget, 'update_theme'):
                    tab.chat_widget.update_theme(theme_colors)
                elif hasattr(tab, 'detection_widget') and hasattr(tab.detection_widget, 'update_theme'):
                    tab.detection_widget.update_theme(theme_colors)
                elif hasattr(tab, 'controls_widget') and hasattr(tab.controls_widget, 'update_theme'):
                    tab.controls_widget.update_theme(theme_colors)
            except Exception as e:
                print(f"⚠️ Error updating theme for tab {idx}: {e}")