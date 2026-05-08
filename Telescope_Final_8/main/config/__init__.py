"""
Global Configuration Package
Single source of truth for settings and themes
"""

from config.global_settings import GlobalSettings, global_settings
from config.themes import GlobalThemeManager, theme_manager

__all__ = [
    'GlobalSettings',
    'global_settings',
    'GlobalThemeManager',
    'theme_manager'
]