#!/usr/bin/env python3
"""
Global Settings Manager
Single source of truth for all application settings
Handles loading/saving settings.json from a single location
"""

import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


class GlobalSettings:
    """Global settings manager - single instance for entire application"""
    
    _instance = None
    _settings = None
    _settings_path = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the settings manager"""
        # Determine the config directory path
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.config_dir)  # main folder
        self.settings_path = os.path.join(self.config_dir, "settings.json")
        
        # Load or create settings
        self._settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file or create defaults"""
        default_settings = {
            "window_size": {
                "width": 880,
                "height": 570
            },
            "default_theme": "Dark",
            "longitude": 118.7878,
            "latitude": 32.0415,
            "camera_settings": {
                "resolution": "1920x1080",
                "fps": 30,
                "exposure": 1.0
            },
            "tabs": {
                "count": 5,
                "row_count": 1,
                "column_count": 5
            },
            "detection_settings": {
                "default_confidence": 0.25,
                "max_detections": 1000,
                "auto_save_results": True,  # Fixed: true -> True
                "default_method": "astro_parallel_net",
                "star_detection": {
                    "min_area": 1,
                    "max_area": 200,
                    "min_circularity": 0.2,
                    "min_contrast": 40
                },
                "galaxy_detection": {
                    "min_area": 3,
                    "max_area": 50,
                    "min_aspect_ratio": 1.5,
                    "confidence": 0.55
                },
                "nebula_detection": {
                    "min_area": 50,
                    "max_area": 5000,
                    "min_gradient": 5,
                    "confidence": 0.65
                }
            },
            "ai_settings": {
                "default_model": "deepseek-r1:1.5b",
                "recommended_models": [
                    "deepseek-r1:1.5b",
                    "deepseek-coder:1.3b",
                    "tinyllama:latest",
                    "phi3:mini"
                ],
                "ollama_host": "http://localhost:11434",
                "keep_alive_seconds": 600
            }
        }
        
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all fields exist
                    merged = self._merge_settings(default_settings, loaded)
                    print(f"✅ Loaded global settings from: {self.settings_path}")
                    return merged
            except Exception as e:
                print(f"⚠️ Error loading settings: {e}")
                print(f"📝 Creating default settings at: {self.settings_path}")
                self._save_settings(default_settings)
                return default_settings
        else:
            print(f"📝 Creating default settings at: {self.settings_path}")
            self._save_settings(default_settings)
            return default_settings
    
    def _merge_settings(self, defaults: Dict, loaded: Dict) -> Dict:
        """Recursively merge loaded settings with defaults"""
        result = defaults.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _save_settings(self, settings: Dict = None) -> bool:
        """Save settings to file"""
        if settings is None:
            settings = self._settings
        
        try:
            # Ensure config directory exists
            os.makedirs(self.config_dir, exist_ok=True)
            
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            print(f"✅ Saved global settings to: {self.settings_path}")
            return True
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'window_size.width')"""
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """Set a setting value using dot notation"""
        keys = key.split('.')
        target = self._settings
        
        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        # Set the value
        target[keys[-1]] = value
        
        # Save to file
        return self._save_settings()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        return self._settings.copy()
    
    def get_window_size(self) -> tuple:
        """Get window size as (width, height)"""
        width = self.get('window_size.width', 850)
        height = self.get('window_size.height', 570)
        return width, height
    
    def get_coordinates(self) -> tuple:
        """Get coordinates as (longitude, latitude)"""
        lon = self.get('longitude', 118.7878)
        lat = self.get('latitude', 32.0415)
        return lon, lat
    
    def get_theme(self) -> str:
        """Get current theme"""
        return self.get('default_theme', 'Dark')
    
    def set_theme(self, theme_name: str) -> bool:
        """Set current theme"""
        return self.set('default_theme', theme_name)
    
    # ==================== DETECTION SETTINGS ====================
    
    def get_detection_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a detection setting using dot notation
        Example: get_detection_setting('star_detection.min_area')
        """
        return self.get(f'detection_settings.{key}', default)
    
    def set_detection_setting(self, key: str, value: Any) -> bool:
        """Set a detection setting using dot notation"""
        return self.set(f'detection_settings.{key}', value)
    
    def get_detection_settings(self) -> Dict[str, Any]:
        """Get all detection settings"""
        return self.get('detection_settings', {})
    
    def get_detection_default_confidence(self) -> float:
        """Get default confidence threshold for detection"""
        return self.get_detection_setting('default_confidence', 0.25)
    
    def get_detection_max_detections(self) -> int:
        """Get maximum number of detections per image"""
        return self.get_detection_setting('max_detections', 1000)
    
    def get_detection_auto_save(self) -> bool:
        """Get auto-save results setting"""
        return self.get_detection_setting('auto_save_results', True)
    
    def get_detection_default_method(self) -> str:
        """Get default detection method"""
        return self.get_detection_setting('default_method', 'astro_parallel_net')
    
    def get_star_detection_settings(self) -> Dict[str, Any]:
        """Get star detection specific settings"""
        return self.get_detection_setting('star_detection', {})
    
    def get_galaxy_detection_settings(self) -> Dict[str, Any]:
        """Get galaxy detection specific settings"""
        return self.get_detection_setting('galaxy_detection', {})
    
    def get_nebula_detection_settings(self) -> Dict[str, Any]:
        """Get nebula detection specific settings"""
        return self.get_detection_setting('nebula_detection', {})
    
    # ==================== AI SETTINGS ====================
    
    def get_ai_setting(self, key: str, default: Any = None) -> Any:
        """
        Get an AI setting using dot notation
        Example: get_ai_setting('recommended_models')
        """
        return self.get(f'ai_settings.{key}', default)
    
    def set_ai_setting(self, key: str, value: Any) -> bool:
        """Set an AI setting using dot notation"""
        return self.set(f'ai_settings.{key}', value)
    
    def get_ai_settings(self) -> Dict[str, Any]:
        """Get all AI settings"""
        return self.get('ai_settings', {})
    
    def get_ai_default_model(self) -> str:
        """Get default AI model"""
        return self.get_ai_setting('default_model', 'deepseek-r1:1.5b')
    
    def get_ai_recommended_models(self) -> list:
        """Get list of recommended AI models"""
        return self.get_ai_setting('recommended_models', [
            "deepseek-r1:1.5b",
            "deepseek-coder:1.3b",
            "tinyllama:latest",
            "phi3:mini"
        ])
    
    def get_ollama_host(self) -> str:
        """Get Ollama host URL"""
        return self.get_ai_setting('ollama_host', 'http://localhost:11434')
    
    def get_ai_keep_alive_seconds(self) -> int:
        """Get keep-alive time for loaded models (seconds)"""
        return self.get_ai_setting('keep_alive_seconds', 600)
    
    # ==================== CAMERA SETTINGS ====================
    
    def get_camera_setting(self, key: str, default: Any = None) -> Any:
        """Get a camera setting using dot notation"""
        return self.get(f'camera_settings.{key}', default)
    
    def set_camera_setting(self, key: str, value: Any) -> bool:
        """Set a camera setting using dot notation"""
        return self.set(f'camera_settings.{key}', value)
    
    def get_camera_settings(self) -> Dict[str, Any]:
        """Get all camera settings"""
        return self.get('camera_settings', {})
    
    def get_camera_resolution(self) -> str:
        """Get camera resolution"""
        return self.get_camera_setting('resolution', '1920x1080')
    
    def get_camera_fps(self) -> int:
        """Get camera FPS"""
        return self.get_camera_setting('fps', 30)
    
    def get_camera_exposure(self) -> float:
        """Get camera exposure"""
        return self.get_camera_setting('exposure', 1.0)
    
    # ==================== TAB SETTINGS ====================
    
    def get_tab_setting(self, key: str, default: Any = None) -> Any:
        """Get a tab setting using dot notation"""
        return self.get(f'tabs.{key}', default)
    
    def set_tab_setting(self, key: str, value: Any) -> bool:
        """Set a tab setting using dot notation"""
        return self.set(f'tabs.{key}', value)
    
    def get_tab_count(self) -> int:
        """Get number of tabs"""
        return self.get_tab_setting('count', 5)
    
    def get_tab_row_count(self) -> int:
        """Get tab row count"""
        return self.get_tab_setting('row_count', 1)
    
    def get_tab_column_count(self) -> int:
        """Get tab column count"""
        return self.get_tab_setting('column_count', 5)
    
    # ==================== UTILITY METHODS ====================
    
    def reload(self) -> bool:
        """Reload settings from file"""
        try:
            self._settings = self._load_settings()
            return True
        except Exception as e:
            print(f"❌ Error reloading settings: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset settings to defaults and save"""
        self._settings = {
            "window_size": {
                "width": 850,
                "height": 570
            },
            "default_theme": "Dark",
            "longitude": 118.7878,
            "latitude": 32.0415,
            "camera_settings": {
                "resolution": "1920x1080",
                "fps": 30,
                "exposure": 1.0
            },
            "tabs": {
                "count": 5,
                "row_count": 1,
                "column_count": 5
            },
            "detection_settings": {
                "default_confidence": 0.25,
                "max_detections": 1000,
                "auto_save_results": True,
                "default_method": "astro_parallel_net",
                "star_detection": {
                    "min_area": 1,
                    "max_area": 200,
                    "min_circularity": 0.2,
                    "min_contrast": 40
                },
                "galaxy_detection": {
                    "min_area": 3,
                    "max_area": 50,
                    "min_aspect_ratio": 1.5,
                    "confidence": 0.55
                },
                "nebula_detection": {
                    "min_area": 50,
                    "max_area": 5000,
                    "min_gradient": 5,
                    "confidence": 0.65
                }
            },
            "ai_settings": {
                "default_model": "deepseek-r1:1.5b",
                "recommended_models": [
                    "deepseek-r1:1.5b",
                    "deepseek-coder:1.3b",
                    "tinyllama:latest",
                    "phi3:mini"
                ],
                "ollama_host": "http://localhost:11434",
                "keep_alive_seconds": 600
            }
        }
        return self._save_settings()
    
    def export_settings(self, filepath: str) -> bool:
        """Export settings to a different file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4)
            print(f"✅ Exported settings to: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Error exporting settings: {e}")
            return False
    
    def import_settings(self, filepath: str, merge: bool = True) -> bool:
        """Import settings from a file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            
            if merge:
                self._settings = self._merge_settings(self._settings, imported)
            else:
                self._settings = imported
            
            return self._save_settings()
        except Exception as e:
            print(f"❌ Error importing settings: {e}")
            return False
    
    def validate(self) -> list:
        """Validate settings structure and return list of issues"""
        issues = []
        
        # Check required top-level keys
        required_keys = ['window_size', 'default_theme', 'longitude', 'latitude']
        for key in required_keys:
            if key not in self._settings:
                issues.append(f"Missing required key: {key}")
        
        # Check window_size structure
        if 'window_size' in self._settings:
            ws = self._settings['window_size']
            if not isinstance(ws, dict):
                issues.append("window_size must be a dictionary")
            else:
                if 'width' not in ws or not isinstance(ws['width'], (int, float)):
                    issues.append("window_size.width missing or invalid")
                if 'height' not in ws or not isinstance(ws['height'], (int, float)):
                    issues.append("window_size.height missing or invalid")
        
        # Check coordinates range
        lon = self._settings.get('longitude')
        lat = self._settings.get('latitude')
        if lon is not None and not (-180 <= lon <= 180):
            issues.append(f"Longitude {lon} out of range (-180 to 180)")
        if lat is not None and not (-90 <= lat <= 90):
            issues.append(f"Latitude {lat} out of range (-90 to 90)")
        
        return issues


# Create global instance
global_settings = GlobalSettings()