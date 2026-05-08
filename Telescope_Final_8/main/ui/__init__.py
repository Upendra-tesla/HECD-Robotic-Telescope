# ui/__init__.py
"""
UI Package for AI Telescope Control
Contains main window, theme manager, and tab manager
"""

# Import from config instead of ui.themes
from config.themes import theme_manager
from ui.tab_manager import TabManager, BaseTab, HomeTab, AIChatTab, DetectionTab, ControlsTab, LogsTab
from ui.main_window import MainWindow

__all__ = [
    'theme_manager',
    'TabManager',
    'BaseTab',
    'HomeTab',
    'AIChatTab',
    'DetectionTab',
    'ControlsTab',
    'LogsTab',
    'MainWindow'
]