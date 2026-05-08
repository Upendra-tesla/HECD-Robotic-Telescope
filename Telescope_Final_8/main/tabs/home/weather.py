"""
Weather Tab for AI Telescope Control - Home Tab
Main widget that combines UI and features
"""

import sys
import os
from PyQt5.QtWidgets import QWidget, QApplication, QDialog, QMessageBox, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QProcess, QDateTime
from PyQt5.QtGui import QPixmap

# Add parent directories to path for proper imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # main/tabs/home
TABS_DIR = os.path.dirname(CURRENT_DIR)  # main/tabs
MAIN_DIR = os.path.dirname(TABS_DIR)  # main/
CONFIG_DIR = os.path.join(MAIN_DIR, "config")

# Add directories to path
for path in [MAIN_DIR, CONFIG_DIR, TABS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Handle direct execution vs module import
try:
    # When running as module (imported by tab_manager)
    from .weather_features import WeatherFeatures
    from .weather_ui import WeatherUI
    print("✅ Weather tab - Imported as module")
except ImportError as e:
    print(f"⚠️ Module import failed: {e}, trying direct import...")
    try:
        # When running as standalone script
        from weather_features import WeatherFeatures
        from weather_ui import WeatherUI
        print("✅ Weather tab - Imported directly")
    except ImportError as e2:
        print(f"❌ Both imports failed: {e2}")
        # Fallback: try absolute imports
        try:
            from tabs.home.weather_features import WeatherFeatures
            from tabs.home.weather_ui import WeatherUI
            print("✅ Weather tab - Imported via absolute path")
        except ImportError as e3:
            print(f"❌ All import attempts failed: {e3}")
            raise

# Import theme manager
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
    print("✅ Weather tab - Theme manager imported")
except ImportError as e:
    print(f"⚠️ Could not import theme_manager: {e}")
    THEME_AVAILABLE = False
    # Create fallback theme manager
    class FallbackThemeManager:
        def __init__(self):
            self.current_theme = "Dark"
        def get_colors(self):
            return {
                "bg": "#0f172a",
                "bg_secondary": "#1e293b",
                "bg_tertiary": "#334155",
                "text": "#f8fafc",
                "text_secondary": "#cbd5e1",
                "accent": "#38bdf8",
                "border": "#475569",
                "button_bg": "#2563eb",
                "button_hover": "#38bdf8"
            }
        def get_current_theme(self):
            return self.current_theme
        def theme_changed(self):
            pass
    theme_manager = FallbackThemeManager()

# Import location settings
try:
    from settings.location_settings import LocationSettingsDialog
    LOCATION_DIALOG_AVAILABLE = True
    print("✅ Weather tab - Location settings imported")
except ImportError as e:
    print(f"⚠️ Could not import LocationSettingsDialog: {e}")
    LOCATION_DIALOG_AVAILABLE = False


class WeatherTab(QWidget):
    """Weather and astronomy information tab for Home"""
    
    def __init__(self, parent=None, log_text_ref=None):
        super().__init__(parent)
        
        print(f"📁 Weather tab initialized from tabs/home/")
        print(f"   Current dir: {CURRENT_DIR}")
        print(f"   Main dir: {MAIN_DIR}")
        
        # Set fixed size for tab content area (850×510)
        self.setFixedSize(850, 510)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        self.log_text = log_text_ref
        self.process = QProcess(self)
        self.image_loader = None
        
        # Initialize features module
        self.features = WeatherFeatures(self)
        
        # Get theme from global theme manager
        self.theme = theme_manager.get_colors() if THEME_AVAILABLE else {}
        self.current_theme = theme_manager.get_current_theme() if THEME_AVAILABLE else "Dark"
        
        # Setup UI
        self.setup_ui()
        
        # Connect signals
        self.features.data_updated.connect(self.refresh_display)
        self.features.apod_updated.connect(self.on_apod_updated)
        
        # Setup timers
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_regular_data)
        self.refresh_timer.start(60000)  # 1 minute
        
        self.apod_timer = QTimer(self)
        self.apod_timer.timeout.connect(self.refresh_apod_data)
        self.apod_timer.start(30 * 60 * 1000)  # 30 minutes
        
        # Initial data load
        self.refresh_regular_data()
        self.refresh_apod_data()
        
        # Connect to global theme manager
        if THEME_AVAILABLE and hasattr(theme_manager, 'theme_changed'):
            try:
                theme_manager.theme_changed.connect(self.on_theme_changed)
                print("✅ Weather tab - Connected to theme manager signals")
            except Exception as e:
                print(f"⚠️ Could not connect to theme signals: {e}")
    
    def setup_ui(self):
        """Setup the user interface using WeatherUI builder"""
        try:
            (self.w_fields, self.o_fields, self.planets_label, self.fact_label,
             self.update_label, self.space_image_label, self.moon_widget,
             self.loc_label, self.refresh_btn, self.loc_btn) = WeatherUI.setup_ui(
                self, self.features.latitude, self.features.longitude
            )
            
            # Connect buttons
            self.refresh_btn.clicked.connect(self.refresh_all_data)
            self.loc_btn.clicked.connect(self.open_location_settings)
            
            # Apply initial theme
            WeatherUI.apply_theme(self, self.theme)
            print("✅ Weather tab - UI setup complete")
        except Exception as e:
            print(f"❌ Error setting up UI: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_display(self):
        """Refresh display when data changes"""
        self.refresh_regular_data()
    
    def on_theme_changed(self, theme_name, theme_colors):
        """Handle theme changes from global theme manager"""
        print(f"🎨 Weather tab - Theme changed to: {theme_name}")
        self.current_theme = theme_name
        self.theme = theme_colors
        WeatherUI.apply_theme(self, self.theme)
    
    def update_theme(self, theme_colors):
        """Update widget theme with new colors (called from tab manager)"""
        self.theme = theme_colors
        WeatherUI.apply_theme(self, self.theme)
    
    def refresh_all_data(self):
        """Refresh all data manually"""
        self.log_message("🔄 Manual refresh triggered")
        self.refresh_regular_data()
        self.refresh_apod_data()
        self.log_message("✅ Manual refresh completed")
    
    def refresh_regular_data(self):
        """Refresh data that updates every minute"""
        try:
            self.loc_label.setText(f"📍 Lat: {self.features.latitude:.4f}°, Lon: {self.features.longitude:.4f}°")
            self.fact_label.setText(self.features.get_space_fact())
            
            weather_data = self.features.get_weather_data()
            self.w_fields["sky_quality"].setText(weather_data["sky_quality"])
            self.w_fields["temperature"].setText(weather_data["temperature"])
            self.w_fields["humidity"].setText(weather_data["humidity"])
            
            obs_data = self.features.get_observation_data()
            self.o_fields["sun_position"].setText(obs_data["sun_position"])
            self.o_fields["sky_visibility"].setText(obs_data["sky_visibility"])
            self.o_fields["recommendation"].setText(obs_data["recommendation"])
            
            self.update_label.setText(self.features.get_space_tech_update())
            
            # Update planets visibility
            visible_planets = self.features.get_visible_planets()
            if visible_planets:
                planet_text = "\n".join([self.features.get_planet_display_text(p) for p in visible_planets[:6]])
                self.planets_label.setText(planet_text)
                self.log_message(f"👁️ Visible planets: {len(visible_planets)}")
            else:
                self.planets_label.setText("  No planets visible at this time")
            
            # Update moon phase with image (now using 0-27 index)
            moon_info = self.features.get_moon_phase_info()
            self.moon_widget.set_phase(
                moon_info['image_index'],  # Now 0-27 instead of 0-7
                moon_info['phase_name'],
                moon_info['illumination'],
                moon_info['age_days']
            )
        except Exception as e:
            print(f"⚠️ Error refreshing data: {e}")
            self.log_message(f"⚠️ Error refreshing data: {str(e)}")
    
    def refresh_apod_data(self):
        """Refresh APOD data"""
        self.log_message("🔄 Fetching fresh APOD data")
        self.features.fetch_apod_data()
    
    def on_apod_updated(self, apod_data):
        """Handle APOD data update"""
        self.update_label.setText(self.features.get_space_tech_update())
        self.load_apod_image()
    
    def load_apod_image(self):
        """Load APOD image from URL"""
        if not self.features.current_apod_data:
            self.space_image_label.setText("No Image")
            return
        
        # Simple image loading (you can implement threading if needed)
        try:
            import requests
            image_url = None
            
            if self.features.current_apod_data["media_type"] == "video" and self.features.current_apod_data.get("thumbnail_url"):
                image_url = self.features.current_apod_data["thumbnail_url"]
            elif self.features.current_apod_data["media_type"] == "image" and self.features.current_apod_data.get("image_url"):
                image_url = self.features.current_apod_data["image_url"]
            
            if image_url:
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(320, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.space_image_label.setPixmap(scaled_pixmap)
                        self.space_image_label.setText("")
                        return
            self.space_image_label.setText("Image\nFailed")
        except Exception as e:
            print(f"⚠️ Error loading APOD image: {e}")
            self.space_image_label.setText("Image\nFailed")
    
    def open_location_settings(self):
        """Open the location settings dialog"""
        if LOCATION_DIALOG_AVAILABLE:
            try:
                dialog = LocationSettingsDialog(self)
                if dialog.exec_() == QDialog.Accepted:
                    self.reload_coordinates()
                return
            except Exception as e:
                print(f"❌ Error opening LocationSettingsDialog: {e}")
        
        # Fallback - try to find location_settings.py
        location_script = os.path.join(MAIN_DIR, "settings", "location_settings.py")
        if os.path.exists(location_script):
            self.process.startDetached(sys.executable, [location_script])
            self.log_message("⚠️ Location settings opened in separate window.")
            QTimer.singleShot(2000, self.reload_coordinates)
        else:
            self.log_message("⚠️ Location settings script not found!")
            QMessageBox.warning(self, "Error", "Location settings module not found!")
    
    def reload_coordinates(self):
        """Reload coordinates from features"""
        if self.features.reload_coordinates():
            self.loc_label.setText(f"📍 Lat: {self.features.latitude:.4f}°, Lon: {self.features.longitude:.4f}°")
            self.log_message(f"📍 Coordinates updated: {self.features.latitude:.4f}°, {self.features.longitude:.4f}°")
            self.refresh_regular_data()
    
    def log_message(self, msg):
        """Log message"""
        if self.log_text:
            ts = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.log_text.append(f"[{ts}] {msg}")
        else:
            print(f"[Weather] {msg}")
    
    def register_worker(self, worker):
        """Register a worker thread for cleanup"""
        if not hasattr(self, 'running_workers'):
            self.running_workers = []
        self.running_workers.append(worker)
        parent = self.parent()
        if parent and hasattr(parent, 'register_worker'):
            parent.register_worker(worker)
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Weather tab - Cleaning up...")
        if self.refresh_timer:
            self.refresh_timer.stop()
        if self.apod_timer:
            self.apod_timer.stop()
        if hasattr(self, 'features'):
            try:
                self.features.quit()
                self.features.wait()
            except:
                pass
    
    def closeEvent(self, e):
        """Clean up threads on close"""
        self.cleanup()
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WeatherTab()
    window.setWindowTitle("Weather Tab Test")
    window.show()
    sys.exit(app.exec_())