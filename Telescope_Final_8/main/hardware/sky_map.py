#!/usr/bin/env python3
"""
Sky Map Widget - Enhanced with smooth animations and correct coordinate mapping
- Proper altitude mapping (0° at horizon, 90° at zenith)
- Smooth animations with throttled updates
- Caching for performance
- Thread-safe position updates
- Fixed celestial object positioning (full graph utilization)
- Zoom in/out functionality with + and - buttons
- FIXED: Below horizon objects stay within graph with 80% transparency
- UPDATED: Default zoom set to 0.8x for better fit
- REDESIGNED: Size 640×260 with proper paddings
- FIXED: Theme handling with proper QColor conversion
- FIXED: All color accesses use _get_qcolor() to prevent QPen errors
"""

import sys
import os
import math
import json
import socket
import threading
import time
from datetime import datetime, timezone
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QLabel, QPushButton, 
    QMenu, QAction, QVBoxLayout, QMainWindow, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QPointF, pyqtSignal, QSize, QThread, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient, QPainterPath
import ephem

# --------------------------
# Path Setup (Same as other files)
# --------------------------
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.dirname(CURRENT_FILE_DIR)
CONFIG_DIR = os.path.join(MAIN_DIR, "config")
UI_DIR = os.path.join(MAIN_DIR, "ui")

# Add directories to path
for path in [MAIN_DIR, CONFIG_DIR, UI_DIR, CURRENT_FILE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Constants for sky map
HORIZON_RADIUS_FACTOR = 0.45  # Increased from 0.342 to 0.45 for better graph utilization
MAX_ZOOM = 2.0
MIN_ZOOM = 0.5
ZOOM_STEP = 0.1
DEFAULT_ZOOM = 0.8
BELOW_HORIZON_OPACITY = 80  # 80% transparency (0-255, where 0 is fully transparent, 255 is opaque)

# REDESIGNED: New dimensions with proper padding
WIDGET_WIDTH = 640
WIDGET_HEIGHT = 250
CONTROL_BAR_HEIGHT = 28
TIME_DISPLAY_WIDTH = 100
TIME_DISPLAY_HEIGHT = 38
LOCATION_DISPLAY_WIDTH = 140
STATUS_DISPLAY_WIDTH = 220
PADDING_TOP = 6
PADDING_LEFT = 8
PADDING_RIGHT = 8
PADDING_BOTTOM = 6
CONTROL_PADDING = 4
BUTTON_SPACING = 2

# Try to import theme manager from config folder (same as other files)
try:
    from config.themes import theme_manager
    THEME_MANAGER_AVAILABLE = True
    print("✅ sky_map.py - Using global theme manager from config folder")
except ImportError as e:
    print(f"⚠️ Could not import theme_manager from config - trying ui.themes_sessions. Error: {e}")
    try:
        from ui.themes_sessions import theme_manager
        THEME_MANAGER_AVAILABLE = True
        print("✅ sky_map.py - Using theme manager from ui folder")
    except ImportError as e2:
        print(f"⚠️ Could not import theme_manager - using fallback. Error: {e2}")
        THEME_MANAGER_AVAILABLE = False
        # Create fallback theme manager
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
                    "text_size": 11,
                    "accent": "#38bdf8",
                    "accent_gold": "#fca311",
                    "border": "#475569",
                    "success": "#10b981",
                    "warning": "#f59e0b",
                    "error": "#ef4444",
                    "bg_top": QColor(10, 20, 40),
                    "bg_mid": QColor(20, 30, 50),
                    "bg_bottom": QColor(30, 40, 60),
                    "grid": QColor(100, 150, 200, 80),
                    "text": QColor(200, 220, 255),
                    "below_horizon": QColor(100, 120, 150, 100)
                }
            
            def get_current_theme(self):
                return self.current_theme
        
        theme_manager = FallbackThemeManager()

# Helper function to safely get theme colors
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
                "error": "#ef4444",
                "bg_top": QColor(10, 20, 40),
                "bg_mid": QColor(20, 30, 50),
                "bg_bottom": QColor(30, 40, 60),
                "grid": QColor(100, 150, 200, 80),
                "text": QColor(200, 220, 255),
                "below_horizon": QColor(100, 120, 150, 100)
            }
    except Exception as e:
        print(f"⚠️ Error getting theme colors: {e}")
        return {}

# Path configuration
SETTINGS_JSON_PATH = os.path.join(MAIN_DIR, "settings.json")
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 65432

# Cache for celestial calculations
_CELESTIAL_CACHE = {}
_CACHE_DURATION = 300  # 5 minutes

class MotorPosition:
    """Represents current motor position from delta values - optimized"""
    def __init__(self):
        self.az_delta = 0.0
        self.alt_delta = 0.0
        self.x = 0.5
        self.y = 0.5
        self.visible = True
        self.last_update = time.time()
        self.above_horizon = True
        self.in_range = True
        self.range_status = "In Range"
        self.display_altitude = 0.0
        self.raw_altitude = 0.0
        self._cached_screen_pos = (0.5, 0.5)
        
    def update_position(self, az_delta, alt_delta):
        self.az_delta = az_delta
        self.alt_delta = alt_delta
        self.raw_altitude = alt_delta
        self.last_update = time.time()
        self._cached_screen_pos = self.calculate_screen_position()
        return self._cached_screen_pos
        
    def calculate_screen_position(self):
        """Calculate screen position with proper altitude mapping"""
        az_rad = math.radians(self.az_delta)
        
        # FIXED: Proper altitude mapping with full graph utilization
        # 0° at horizon (edge), 90° at zenith (center)
        max_radius = HORIZON_RADIUS_FACTOR
        
        if self.alt_delta < -5:  # Below horizon
            self.above_horizon = False
            self.in_range = False
            self.range_status = "Below Horizon"
            self.display_altitude = 360 + self.alt_delta
            # FIXED: Map below horizon positions inside the circle but closer to edge
            # Negative altitudes map to positions just inside the horizon circle
            # altitude -1° → just inside the circle, altitude -90° → at the very edge
            below_angle = min(90, abs(self.alt_delta + 5))
            # Map to positions between 95% and 100% of horizon radius
            distance = max_radius * (0.95 + (below_angle / 90.0) * 0.05)
        elif self.alt_delta > 95:  # Beyond zenith
            self.above_horizon = True
            self.in_range = False
            self.range_status = "Beyond Zenith"
            self.display_altitude = self.alt_delta
            # Map beyond zenith to just below center
            # altitude 91° → very close to center, altitude 180° → further out
            above_angle = min(90, self.alt_delta - 90)
            distance = max_radius * (above_angle / 90.0) * 0.1  # 0-10% of radius
        else:
            self.above_horizon = True
            self.in_range = True
            self.range_status = "In Range"
            self.display_altitude = self.alt_delta
            
            # FIXED: Linear mapping from altitude to distance from center
            # altitude 90° → distance 0 (center)
            # altitude 0° → distance max_radius (horizon)
            altitude_normalized = max(0, min(90, self.alt_delta)) / 90.0
            distance = max_radius * (1.0 - altitude_normalized)
        
        x = 0.5 + math.sin(az_rad) * distance
        y = 0.5 - math.cos(az_rad) * distance
        
        return (x, y)
    
    def get_screen_position(self):
        """Get cached screen position"""
        return self._cached_screen_pos
    
    def get_altitude_display(self):
        if not self.in_range:
            return f"{self.display_altitude:.1f}° ({self.range_status})"
        else:
            return f"{self.alt_delta:.1f}° above horizon"


class CelestialObject:
    """Represents a celestial object with position and appearance using ephem - with caching"""
    
    def __init__(self, name, obj_id, obj_type, magnitude, color, ephem_name, ra=None, dec=None):
        self.name = name
        self.obj_id = obj_id
        self.obj_type = obj_type
        self.magnitude = magnitude
        self.color = color if isinstance(color, QColor) else QColor(color)
        self.ephem_name = ephem_name
        self.ra = ra
        self.dec = dec
        
        # Cache for positions
        self.last_cache_time = 0
        self.cached_azimuth = 0.0
        self.cached_altitude = 0.0
        self.cached_x = 0.0
        self.cached_y = 0.0
        self.cached_visible = False
        self._cache_key = None
        
        # Create ephem object
        self._create_ephem_object()
        
    def _create_ephem_object(self):
        """Create the appropriate ephem object"""
        try:
            if self.obj_type == "planet":
                if self.ephem_name == "sun":
                    self.ephem_obj = ephem.Sun()
                elif self.ephem_name == "moon":
                    self.ephem_obj = ephem.Moon()
                elif self.ephem_name == "mercury":
                    self.ephem_obj = ephem.Mercury()
                elif self.ephem_name == "venus":
                    self.ephem_obj = ephem.Venus()
                elif self.ephem_name == "mars":
                    self.ephem_obj = ephem.Mars()
                elif self.ephem_name == "jupiter":
                    self.ephem_obj = ephem.Jupiter()
                elif self.ephem_name == "saturn":
                    self.ephem_obj = ephem.Saturn()
                elif self.ephem_name == "uranus":
                    self.ephem_obj = ephem.Uranus()
                elif self.ephem_name == "neptune":
                    self.ephem_obj = ephem.Neptune()
                else:
                    self.ephem_obj = ephem.FixedBody()
                    if self.ra and self.dec:
                        self.ephem_obj._ra = self.ra
                        self.ephem_obj._dec = self.dec
            elif self.obj_type == "star":
                try:
                    self.ephem_obj = getattr(ephem, self.ephem_name)()
                except AttributeError:
                    self.ephem_obj = ephem.FixedBody()
                    if self.ra and self.dec:
                        self.ephem_obj._ra = self.ra
                        self.ephem_obj._dec = self.dec
            else:
                self.ephem_obj = ephem.FixedBody()
                if self.ra and self.dec:
                    self.ephem_obj._ra = self.ra
                    self.ephem_obj._dec = self.dec
        except Exception as e:
            print(f"Error creating ephem object for {self.name}: {e}")
            self.ephem_obj = None
    
    def calculate_position(self, latitude, longitude, current_time, force_recalc=False):
        """Calculate position with caching to improve performance"""
        # Create cache key with date to prevent cross-day caching issues
        cache_key = f"{latitude}_{longitude}_{current_time.strftime('%Y%m%d_%H_%M')}"
        
        # Check if cache is still valid (60 seconds)
        if not force_recalc and hasattr(self, '_cache_key') and self._cache_key == cache_key:
            time_since_update = time.time() - self.last_cache_time
            if time_since_update < 60:  # Cache valid for 60 seconds
                return (self.cached_azimuth, self.cached_altitude, 
                        self.cached_x, self.cached_y, self.cached_visible)
        
        try:
            if self.ephem_obj:
                observer = ephem.Observer()
                observer.lat = str(latitude)
                observer.lon = str(longitude)
                observer.elevation = 0
                observer.date = current_time.strftime('%Y/%m/%d %H:%M:%S')
                
                self.ephem_obj.compute(observer)
                self.cached_altitude = float(self.ephem_obj.alt) * 180.0 / math.pi
                self.cached_azimuth = float(self.ephem_obj.az) * 180.0 / math.pi
                
                if hasattr(self.ephem_obj, 'mag'):
                    self.magnitude = float(self.ephem_obj.mag)
            else:
                self._simplified_calculation(latitude, longitude, current_time)
            
            self.cached_visible = self.cached_altitude > 0
            az_rad = math.radians(self.cached_azimuth)
            
            # FIXED: Proper altitude mapping with full graph utilization
            max_radius = HORIZON_RADIUS_FACTOR
            
            if self.cached_altitude >= 0:
                # altitude 90° → distance 0 (center)
                # altitude 0° → distance max_radius (horizon)
                norm_alt = self.cached_altitude / 90.0
                distance = max_radius * (1.0 - norm_alt)
            else:
                # FIXED: Below horizon - map inside the circle near the edge
                # Negative altitudes map to positions between 95% and 100% of horizon radius
                # altitude -1° → just inside the circle (95% radius)
                # altitude -90° → at the very edge (100% radius)
                abs_alt = min(90, abs(self.cached_altitude))
                norm_alt = abs_alt / 90.0
                # Map to positions between 95% and 100% of radius
                distance = max_radius * (0.95 + norm_alt * 0.05)
            
            self.cached_x = 0.5 + math.sin(az_rad) * distance
            self.cached_y = 0.5 - math.cos(az_rad) * distance
            
            # Update cache
            self._cache_key = cache_key
            self.last_cache_time = time.time()
            
        except Exception as e:
            print(f"Error calculating position for {self.name}: {e}")
            self._simplified_calculation(latitude, longitude, current_time)
        
        return (self.cached_azimuth, self.cached_altitude, 
                self.cached_x, self.cached_y, self.cached_visible)
    
    def _simplified_calculation(self, latitude, longitude, current_time):
        """Simplified calculation for fallback"""
        day_of_year = current_time.timetuple().tm_yday
        hour_of_day = current_time.hour + current_time.minute / 60.0 + current_time.second / 3600.0
        
        if hasattr(self, 'ra') and self.ra and hasattr(self, 'dec') and self.dec:
            ra_hours = self.ra
            dec_deg = self.dec
        else:
            ra_hours = 10.5
            dec_deg = 15.0
            
        lst = (hour_of_day * 15 + longitude) % 360
        ha = lst - (ra_hours * 15)
        
        ha_rad = math.radians(ha)
        dec_rad = math.radians(dec_deg)
        lat_rad = math.radians(latitude)
        
        sin_alt = (math.sin(dec_rad) * math.sin(lat_rad) + 
                   math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad))
        self.cached_altitude = math.degrees(math.asin(sin_alt))
        
        cos_az = (math.sin(dec_rad) - math.sin(lat_rad) * sin_alt) / (math.cos(lat_rad) * math.cos(math.asin(sin_alt)))
        cos_az = max(-1, min(1, cos_az))
        self.cached_azimuth = math.degrees(math.acos(cos_az))
        
        if math.sin(ha_rad) > 0:
            self.cached_azimuth = 360 - self.cached_azimuth
            
        self.cached_visible = self.cached_altitude > 0


class SocketClient(QThread):
    """Socket client to receive motor delta values - optimized"""
    position_received = pyqtSignal(float, float)
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.connected = False
        self.socket = None
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0
        self._lock = threading.Lock()
        
    def run(self):
        while self.running:
            try:
                if not self.connected:
                    self._connect()
                
                if self.connected and self.socket:
                    self._receive_data()
                    
                time.sleep(0.05)  # Reduced sleep for better responsiveness
            except Exception as e:
                print(f"Socket client error: {e}")
                time.sleep(self.reconnect_delay)
    
    def _connect(self):
        """Connect to server with exponential backoff"""
        try:
            with self._lock:
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(0.2)
                self.socket.connect((SOCKET_HOST, SOCKET_PORT))
                self.connected = True
                self.connection_changed.emit(True)
                print("✅ Connected to motor.py socket server")
                self.reconnect_delay = 1.0
        except ConnectionRefusedError:
            if self.connected:
                with self._lock:
                    self.connected = False
                self.connection_changed.emit(False)
                print("⚠️ Disconnected from motor.py socket server")
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        except Exception as e:
            print(f"Socket connect error: {e}")
    
    def _receive_data(self):
        """Receive and process data"""
        try:
            with self._lock:
                if not self.socket:
                    return
                self.socket.settimeout(0.05)
                data = self.socket.recv(1024).decode().strip()
            
            if data:
                if data.startswith("SENSOR,"):
                    parts = data.split(",")
                    if len(parts) >= 3:
                        try:
                            az_delta = float(parts[1])
                            alt_delta = float(parts[2])
                            self.position_received.emit(az_delta, alt_delta)
                        except ValueError:
                            pass
            else:
                with self._lock:
                    self.connected = False
                self.connection_changed.emit(False)
                print("⚠️ Connection closed by motor.py")
        except socket.timeout:
            pass
        except (BrokenPipeError, ConnectionResetError) as e:
            with self._lock:
                self.connected = False
            self.connection_changed.emit(False)
            print(f"⚠️ Connection lost: {e}")
    
    def stop(self):
        self.running = False
        with self._lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass


class SkyMapWidget(QWidget):
    """Sky map widget with altitude circles and azimuth lines - optimized for smoothness"""
    
    # Define signals normally
    time_updated = pyqtSignal(str)
    view_changed = pyqtSignal(dict)
    celestial_selected = pyqtSignal(str)
    motor_connection_changed = pyqtSignal(bool)
    zoom_changed = pyqtSignal(float)
    
    def __init__(self, parent=None, show_controls=True, theme=None):
        super().__init__(parent)
        
        # REDESIGNED: Set new dimensions with proper padding
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.setMinimumSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self.setMaximumSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        
        # Set margins for proper padding
        self.setContentsMargins(PADDING_LEFT, PADDING_TOP, PADDING_RIGHT, PADDING_BOTTOM)
        
        # Load location
        self.latitude, self.longitude = self.load_location()
        
        # Get theme safely
        if theme is None:
            self.theme = get_theme_colors()
        elif isinstance(theme, dict):
            self.theme = theme
        else:
            self.theme = get_theme_colors()
        
        # Convert color strings to QColor objects where needed
        self._prepare_theme_colors()
        
        # Zoom level set to default
        self.zoom_level = DEFAULT_ZOOM
        
        self.show_grid = True
        self.show_labels = True
        self.show_controls = show_controls
        self.altitude_circles = 8
        self.azimuth_lines = 16
        self.show_celestial = True
        self.show_below_horizon = True
        self.show_motor_position = True
        self.selected_celestial = None
        
        self.motor_pos = MotorPosition()
        self.motor_connected = False
        
        self.celestial_objects = []
        self.setup_celestial_objects()
        
        self.current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        self.time_format = "%H:%M:%S"
        self.date_format = "%Y-%m-%d"
        
        # Throttled update timer for smoother animation
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(33)  # ~30 FPS for smooth animation
        
        # Celestial update timer (every minute)
        self.celestial_update_timer = QTimer()
        self.celestial_update_timer.timeout.connect(self.update_celestial_positions)
        self.celestial_update_timer.start(60000)  # Update every minute
        
        # Time update timer (1 second)
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)
        
        self.socket_client = SocketClient()
        self.socket_client.position_received.connect(self.on_motor_position)
        self.socket_client.connection_changed.connect(self.on_motor_connection)
        self.socket_client.start()
        
        if self.show_controls:
            self.setup_buttons()
        
        # Connect to theme manager if available
        if THEME_MANAGER_AVAILABLE and hasattr(theme_manager, 'theme_changed'):
            try:
                theme_manager.theme_changed.connect(self.on_global_theme_changed)
            except:
                pass
    
    def _get_qcolor(self, color_key, default=None):
        """Get a color from theme as QColor object - FIXED: converts strings to QColor"""
        if color_key not in self.theme:
            if default is not None:
                return default if isinstance(default, QColor) else QColor(default)
            return QColor(200, 200, 200)  # Default gray
        
        color = self.theme[color_key]
        if isinstance(color, QColor):
            return color
        elif isinstance(color, str):
            return QColor(color)
        elif isinstance(color, (tuple, list)) and len(color) >= 3:
            if len(color) >= 4:
                return QColor(color[0], color[1], color[2], color[3])
            else:
                return QColor(color[0], color[1], color[2])
        else:
            if default is not None:
                return default if isinstance(default, QColor) else QColor(default)
            return QColor(200, 200, 200)
    
    def update_celestial_positions(self):
        """Force recalculation of celestial positions"""
        for obj in self.celestial_objects:
            obj.calculate_position(
                self.latitude, self.longitude, self.current_time_utc, force_recalc=True
            )
    
    def _prepare_theme_colors(self):
        """Convert color strings to QColor objects where needed"""
        # Helper function to ensure color is QColor
        def ensure_qcolor(color):
            if isinstance(color, QColor):
                return color
            elif isinstance(color, str):
                return QColor(color)
            elif isinstance(color, (tuple, list)) and len(color) >= 3:
                if len(color) >= 4:
                    return QColor(color[0], color[1], color[2], color[3])
                else:
                    return QColor(color[0], color[1], color[2])
            else:
                return QColor(200, 200, 200)  # Default gray
        
        # Convert all color entries to QColor
        for key in ['bg_top', 'bg_mid', 'bg_bottom', 'grid', 'text', 'accent', 
                    'below_horizon', 'motor_position_above', 'motor_position_below', 
                    'motor_position_out_of_range', 'success_color', 'error_color', 
                    'warning_color', 'button_bg_transparent', 'button_text_color']:
            if key in self.theme:
                self.theme[key] = ensure_qcolor(self.theme[key])
    
    def on_global_theme_changed(self, theme_name, theme_colors):
        """Handle global theme changes"""
        if isinstance(theme_colors, dict):
            self.theme = theme_colors
        else:
            self.theme = get_theme_colors()
        self._prepare_theme_colors()
        self.update()
    
    def load_location(self):
        """Load location from settings file"""
        default_lon, default_lat = 118.7878, 32.0415
        try:
            if os.path.exists(SETTINGS_JSON_PATH):
                with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    longitude = settings.get("longitude", default_lon)
                    latitude = settings.get("latitude", default_lat)
                    return latitude, longitude
            else:
                return default_lat, default_lon
        except Exception as e:
            print(f"Error loading settings: {e}")
            return default_lat, default_lon
        
    def setup_celestial_objects(self):
        """Initialize celestial objects list"""
        self.celestial_objects = [
            CelestialObject("Sun", "sun", "planet", -26.7, QColor(255, 200, 50), "sun"),
            CelestialObject("Moon", "moon", "planet", -12.6, QColor(200, 200, 200), "moon"),
            CelestialObject("Mercury", "mercury", "planet", 0.5, QColor(169, 169, 169), "mercury"),
            CelestialObject("Venus", "venus", "planet", -4.6, QColor(255, 220, 180), "venus"),
            CelestialObject("Mars", "mars", "planet", -2.0, QColor(255, 100, 100), "mars"),
            CelestialObject("Jupiter", "jupiter", "planet", -2.9, QColor(255, 200, 150), "jupiter"),
            CelestialObject("Saturn", "saturn", "planet", -0.5, QColor(240, 220, 150), "saturn"),
            CelestialObject("Uranus", "uranus", "planet", 5.3, QColor(180, 220, 255), "uranus"),
            CelestialObject("Neptune", "neptune", "planet", 7.7, QColor(100, 150, 255), "neptune"),
            CelestialObject("Sirius", "sirius", "star", -1.46, QColor(255, 255, 255), "Sirius"),
            CelestialObject("Canopus", "canopus", "star", -0.72, QColor(255, 255, 200), "Canopus"),
            CelestialObject("Arcturus", "arcturus", "star", -0.05, QColor(255, 200, 150), "Arcturus"),
            CelestialObject("Vega", "vega", "star", 0.03, QColor(255, 255, 255), "Vega"),
            CelestialObject("Capella", "capella", "star", 0.08, QColor(255, 255, 200), "Capella"),
            CelestialObject("Rigel", "rigel", "star", 0.18, QColor(200, 200, 255), "Rigel"),
            CelestialObject("Betelgeuse", "betelgeuse", "star", 0.45, QColor(255, 150, 150), "Betelgeuse"),
            CelestialObject("Aldebaran", "aldebaran", "star", 0.87, QColor(255, 150, 100), "Aldebaran"),
            CelestialObject("Antares", "antares", "star", 1.06, QColor(255, 100, 100), "Antares"),
            CelestialObject("Spica", "spica", "star", 1.04, QColor(200, 200, 255), "Spica"),
            CelestialObject("Polaris", "polaris", "star", 1.98, QColor(255, 255, 200), "Polaris"),
            CelestialObject("Andromeda", "andromeda", "deepsky", 3.4, QColor(200, 150, 255), "M31", 0.71, 41.27),
            CelestialObject("Pleiades", "pleiades", "deepsky", 1.6, QColor(200, 200, 255), "M45", 3.78, 24.11),
            CelestialObject("Orion Nebula", "orion", "deepsky", 4.0, QColor(255, 150, 200), "M42", 5.62, -5.38),
            CelestialObject("Beehive", "beehive", "deepsky", 3.1, QColor(200, 200, 150), "M44", 8.68, 19.98),
            CelestialObject("Hercules", "hercules", "deepsky", 5.8, QColor(150, 200, 255), "M13", 16.08, 18.02),
        ]
    
    def _update_time(self):
        """Update time (called every second)"""
        self.current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        time_str = self.get_time_string()
        self.time_updated.emit(time_str)
        # No need to call update() directly - the update timer will handle it
        
    def on_motor_position(self, az_delta, alt_delta):
        """Handle motor position updates"""
        self.motor_pos.update_position(az_delta, alt_delta)
        self.motor_connected = True
        
    def on_motor_connection(self, connected):
        self.motor_connected = connected
        self.motor_connection_changed.emit(connected)
        if connected:
            print("✅ Motor connected - showing position indicator")
        else:
            print("⚠️ Motor disconnected")
    
    def zoom_in(self):
        """Zoom in on the sky map"""
        self.zoom_level = min(MAX_ZOOM, self.zoom_level + ZOOM_STEP)
        self.zoom_changed.emit(self.zoom_level)
        self.update()
    
    def zoom_out(self):
        """Zoom out of the sky map"""
        self.zoom_level = max(MIN_ZOOM, self.zoom_level - ZOOM_STEP)
        self.zoom_changed.emit(self.zoom_level)
        self.update()
    
    def reset_zoom(self):
        """Reset zoom to default level"""
        self.zoom_level = DEFAULT_ZOOM
        self.zoom_changed.emit(self.zoom_level)
        self.update()
        
    def setup_buttons(self):
        """Setup control buttons with proper padding"""
        # REDESIGNED: Button container with proper positioning
        self.button_container = QWidget(self)
        # Position at top with padding
        self.button_container.setGeometry(
            PADDING_LEFT, 
            PADDING_TOP, 
            WIDGET_WIDTH - PADDING_LEFT - PADDING_RIGHT, 
            CONTROL_BAR_HEIGHT
        )
        
        button_layout = QHBoxLayout(self.button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(BUTTON_SPACING)
        button_layout.setAlignment(Qt.AlignCenter)
        
        # Zoom controls
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.zoom_out_btn)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_reset_btn = QPushButton("↺")
        self.zoom_reset_btn.setToolTip(f"Reset Zoom ({DEFAULT_ZOOM:.1f}x)")
        self.zoom_reset_btn.clicked.connect(self.reset_zoom)
        self.zoom_reset_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.zoom_reset_btn)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(2)
        separator.setStyleSheet("background-color: rgba(255,255,255,30); margin: 2px 4px;")
        button_layout.addWidget(separator)
        
        self.celestial_btn = QPushButton("✨ ▼")
        self.celestial_btn.setToolTip("Select celestial object")
        self.celestial_btn.setStyleSheet(self.get_button_style())
        
        self.celestial_menu = QMenu()
        
        # Get accent color for menu border
        accent_color = "#fca311"
        if hasattr(self.theme, 'get') and callable(self.theme.get):
            accent_color = self.theme.get('accent_gold', '#fca311')
        elif isinstance(self.theme, dict):
            accent_color = self.theme.get('accent_gold', '#fca311')
        
        self.celestial_menu.setStyleSheet(f"""
            QMenu {{
                background-color: rgba(30, 40, 60, 200);
                color: white;
                border: 1px solid {accent_color};
                font-size: 8px;
                padding: 2px;
                border-radius: 3px;
            }}
            QMenu::item {{
                padding: 2px 12px;
                margin: 1px;
            }}
            QMenu::item:selected {{
                background-color: {accent_color};
                color: #0f172a;
                border-radius: 2px;
            }}
        """)
        
        categories = {
            "☀️ Solar System": ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"],
            "⭐ Bright Stars": ["sirius", "canopus", "arcturus", "vega", "capella", "rigel", "betelgeuse", "aldebaran", "antares", "spica", "polaris"],
            "🌌 Deep Sky": ["andromeda", "pleiades", "orion", "beehive", "hercules"]
        }
        
        for category_name, obj_ids in categories.items():
            category_menu = QMenu(category_name, self.celestial_menu)
            category_menu.setStyleSheet(self.celestial_menu.styleSheet())
            
            for obj in self.celestial_objects:
                if obj.obj_id in obj_ids:
                    if obj.obj_type == "star":
                        emoji = "⭐"
                    elif obj.obj_type == "planet":
                        if obj.obj_id == "sun":
                            emoji = "☀️"
                        elif obj.obj_id == "moon":
                            emoji = "🌙"
                        else:
                            emoji = "🪐"
                    else:
                        emoji = "🌌"
                        
                    action = QAction(f"{emoji} {obj.name}", category_menu)
                    action.triggered.connect(lambda checked, o=obj.obj_id, n=obj.name: self.select_celestial(o, n))
                    category_menu.addAction(action)
            
            self.celestial_menu.addMenu(category_menu)
        
        self.celestial_btn.setMenu(self.celestial_menu)
        button_layout.addWidget(self.celestial_btn)
        
        self.show_celestial_btn = QPushButton("Obj")
        self.show_celestial_btn.setToolTip("Toggle celestial objects")
        self.show_celestial_btn.setCheckable(True)
        self.show_celestial_btn.setChecked(True)
        self.show_celestial_btn.clicked.connect(self.toggle_celestial)
        self.show_celestial_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.show_celestial_btn)
        
        self.show_below_btn = QPushButton("Blw")
        self.show_below_btn.setToolTip("Show objects below horizon")
        self.show_below_btn.setCheckable(True)
        self.show_below_btn.setChecked(True)
        self.show_below_btn.clicked.connect(self.toggle_below_horizon)
        self.show_below_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.show_below_btn)
        
        self.show_motor_btn = QPushButton("Mot")
        self.show_motor_btn.setToolTip("Show motor position")
        self.show_motor_btn.setCheckable(True)
        self.show_motor_btn.setChecked(True)
        self.show_motor_btn.clicked.connect(self.toggle_motor_position)
        self.show_motor_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.show_motor_btn)
        
        self.grid_btn = QPushButton("Grd")
        self.grid_btn.setToolTip("Toggle grid")
        self.grid_btn.setCheckable(True)
        self.grid_btn.setChecked(True)
        self.grid_btn.clicked.connect(self.toggle_grid)
        self.grid_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.grid_btn)
        
        self.labels_btn = QPushButton("Lbl")
        self.labels_btn.setToolTip("Toggle labels")
        self.labels_btn.setCheckable(True)
        self.labels_btn.setChecked(True)
        self.labels_btn.clicked.connect(self.toggle_labels)
        self.labels_btn.setStyleSheet(self.get_button_style())
        button_layout.addWidget(self.labels_btn)
        
        button_layout.addStretch()
        
        self.button_container.setStyleSheet("background-color: transparent;")
        
    def get_button_style(self):
        # REDESIGNED: Slightly smaller buttons for tighter layout
        return """
            QPushButton {
                background-color: rgba(30, 40, 60, 180);
                color: white;
                border: 1px solid rgba(255,255,255,30);
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 8px;
                font-weight: bold;
                min-width: 26px;
                max-width: 26px;
                height: 16px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #fca311;
                color: #0f172a;
                border: 1px solid #fca311;
            }
            QPushButton:checked {
                background-color: #fca311;
                color: #0f172a;
                border: 1px solid #fca311;
            }
            QPushButton::menu-indicator { 
                image: none;
                width: 0px;
            }
        """
        
    def select_celestial(self, obj_id, name):
        self.selected_celestial = obj_id
        self.celestial_btn.setText("✨ ▼")
        self.celestial_btn.setToolTip(f"Selected: {name}")
        self.celestial_selected.emit(obj_id)
        self.update()
        
    def toggle_celestial(self):
        self.show_celestial = self.show_celestial_btn.isChecked()
        self.view_changed.emit({"show_celestial": self.show_celestial})
        self.update()
        
    def toggle_below_horizon(self):
        self.show_below_horizon = self.show_below_btn.isChecked()
        self.view_changed.emit({"show_below_horizon": self.show_below_horizon})
        self.update()
        
    def toggle_motor_position(self):
        self.show_motor_position = self.show_motor_btn.isChecked()
        self.view_changed.emit({"show_motor_position": self.show_motor_position})
        self.update()
        
    def get_time_string(self):
        local_time = datetime.now()
        return local_time.strftime(f"{self.date_format} {self.time_format}")
        
    def toggle_grid(self):
        self.show_grid = self.grid_btn.isChecked()
        self.view_changed.emit({"show_grid": self.show_grid})
        self.update()
        
    def toggle_labels(self):
        self.show_labels = self.labels_btn.isChecked()
        self.view_changed.emit({"show_labels": self.show_labels})
        self.update()
        
    def set_time_format(self, time_format="%H:%M:%S", date_format="%Y-%m-%d"):
        self.time_format = time_format
        self.date_format = date_format
        
    def set_theme(self, theme):
        if isinstance(theme, dict):
            self.theme = theme
            self._prepare_theme_colors()
        if self.show_controls:
            self.zoom_out_btn.setStyleSheet(self.get_button_style())
            self.zoom_in_btn.setStyleSheet(self.get_button_style())
            self.zoom_reset_btn.setStyleSheet(self.get_button_style())
            self.celestial_btn.setStyleSheet(self.get_button_style())
            self.show_celestial_btn.setStyleSheet(self.get_button_style())
            self.show_below_btn.setStyleSheet(self.get_button_style())
            self.show_motor_btn.setStyleSheet(self.get_button_style())
            self.grid_btn.setStyleSheet(self.get_button_style())
            self.labels_btn.setStyleSheet(self.get_button_style())
        self.update()
        
    def update_theme(self, theme):
        self.set_theme(theme)
        
    def set_grid_settings(self, altitude_circles=8, azimuth_lines=16):
        self.altitude_circles = max(4, min(16, altitude_circles))
        self.azimuth_lines = max(8, min(32, azimuth_lines))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        self.draw_background(painter)
        
        if self.show_grid:
            self.draw_sky_grid(painter)
        
        if self.show_celestial:
            self.draw_celestial_objects(painter)
        
        if self.show_motor_position and self.motor_connected:
            self.draw_motor_position(painter)
        
        self.draw_time_display(painter)
        
        if self.show_labels:
            self.draw_labels(painter)
        
        if self.selected_celestial:
            self.draw_selected_highlight(painter)
        
        self.draw_location_info(painter)
        
        self.draw_motor_status(painter)
        self.draw_zoom_indicator(painter)
        
    def draw_background(self, painter):
        """Draw gradient background - FIXED: uses _get_qcolor for color conversion"""
        # Get colors as QColor objects
        bg_top = self._get_qcolor('bg_top', QColor(10, 20, 40))
        bg_mid = self._get_qcolor('bg_mid', QColor(20, 30, 50))
        bg_bottom = self._get_qcolor('bg_bottom', QColor(30, 40, 60))
        
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, bg_top)
        gradient.setColorAt(0.5, bg_mid)
        gradient.setColorAt(1.0, bg_bottom)
        painter.fillRect(self.rect(), gradient)
        
    def draw_time_display(self, painter):
        """Draw time display with proper padding"""
        time_str = datetime.now().strftime(self.time_format)
        date_str = datetime.now().strftime(self.date_format)
        
        # REDESIGNED: Position with proper padding
        x = PADDING_LEFT
        y = self.height() - TIME_DISPLAY_HEIGHT - PADDING_BOTTOM
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(x, y, TIME_DISPLAY_WIDTH, TIME_DISPLAY_HEIGHT, 4, 4)
        
        # Get text color as QColor
        text_color = self._get_qcolor('text', QColor(200, 220, 255))
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(x + 7, y + 17, time_str)
        
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x + 7, y + 32, date_str)
        
    def draw_location_info(self, painter):
        """Draw location information with proper padding"""
        location_str = f"Lat: {self.latitude:.2f}°  Lon: {self.longitude:.2f}°"
        
        # REDESIGNED: Position with proper padding
        x = PADDING_LEFT
        y = PADDING_TOP + CONTROL_BAR_HEIGHT + 4
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawRoundedRect(x, y, LOCATION_DISPLAY_WIDTH, 16, 4, 4)
        
        # Get text color as QColor
        text_color = self._get_qcolor('text', QColor(200, 220, 255))
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x + 5, y + 11, location_str)
        
    def draw_zoom_indicator(self, painter):
        """Draw zoom level indicator"""
        if self.zoom_level != DEFAULT_ZOOM:
            zoom_str = f"Zoom: {self.zoom_level:.1f}x"
            
            # REDESIGNED: Position with proper padding
            x = self.width() - 90 - PADDING_RIGHT
            y = PADDING_TOP + CONTROL_BAR_HEIGHT + 4
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 80))
            painter.drawRoundedRect(x, y, 60, 16, 4, 4)
            
            # Get accent color as QColor
            accent_color = self._get_qcolor('accent', QColor(252, 163, 17))
            painter.setPen(QPen(accent_color))
            painter.setFont(QFont("Arial", 6, QFont.Bold))
            painter.drawText(x + 5, y + 11, zoom_str)
        
    def draw_motor_status(self, painter):
        """Draw motor connection status with proper padding"""
        if self.motor_connected:
            if hasattr(self.motor_pos, 'in_range') and not self.motor_pos.in_range:
                if self.motor_pos.alt_delta < 0:
                    status_str = f"Motor: ↓ {self.motor_pos.display_altitude:.1f}° (Below)"
                    color = QColor(255, 100, 100)
                else:
                    status_str = f"Motor: ↑ {self.motor_pos.display_altitude:.1f}° (Beyond)"
                    color = QColor(255, 100, 100)
            elif self.motor_pos.above_horizon:
                status_str = f"Motor: ✓ ({self.motor_pos.az_delta:.1f}°, {self.motor_pos.alt_delta:.1f}°)"
                color = QColor(100, 255, 100)
            else:
                status_str = f"Motor: ⚠ Below ({self.motor_pos.az_delta:.1f}°, {self.motor_pos.alt_delta:.1f}°)"
                color = QColor(255, 165, 0)
        else:
            status_str = "Motor: ✗ Disconnected"
            color = QColor(255, 100, 100)
        
        # REDESIGNED: Position with proper padding
        x = self.width() - STATUS_DISPLAY_WIDTH - PADDING_RIGHT
        y = self.height() - 25 - PADDING_BOTTOM
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawRoundedRect(x, y, STATUS_DISPLAY_WIDTH, 18, 4, 4)
        
        painter.setPen(QPen(color))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(x + 5, y + 12, status_str)
        
    def draw_sky_grid(self, painter):
        """Draw the sky grid with correct altitude mapping and zoom - FIXED: uses _get_qcolor"""
        # REDESIGNED: Center based on available space
        center_x = self.width() // 2
        center_y = self.height() // 2 + 5  # Slight adjustment for balance
        
        base_max_radius = min(self.width(), self.height()) * HORIZON_RADIUS_FACTOR
        max_radius = base_max_radius * self.zoom_level
        
        # Get colors as QColor objects
        grid_color = self._get_qcolor('grid', QColor(100, 150, 200, 80))
        text_color = self._get_qcolor('text', QColor(200, 220, 255))
        
        grid_pen = QPen(grid_color)
        grid_pen.setWidth(1)
        text_pen = QPen(text_color)
        
        painter.setPen(grid_pen)
        
        # Draw altitude circles (distance from center represents altitude)
        for i in range(1, self.altitude_circles + 1):
            altitude = 90 * (1 - i / self.altitude_circles)
            radius = max_radius * (i / self.altitude_circles)
            
            painter.drawEllipse(QPointF(center_x, center_y), radius, radius)
            
            if self.show_labels:
                label_x = center_x + radius * 0.7
                label_y = center_y - radius * 0.7
                
                if 0 <= label_x <= self.width() and 0 <= label_y <= self.height():
                    painter.setPen(text_pen)
                    painter.setFont(QFont("Arial", 5))
                    painter.drawText(int(label_x), int(label_y), f"{altitude:.0f}°")
                    painter.setPen(grid_pen)
        
        # Draw azimuth lines
        for i in range(self.azimuth_lines):
            angle = i * (2 * math.pi / self.azimuth_lines)
            end_x = center_x + math.sin(angle) * max_radius
            end_y = center_y - math.cos(angle) * max_radius
            painter.drawLine(int(center_x), int(center_y), int(end_x), int(end_y))
            
            if self.show_labels:
                deg_angle = (i * 360 / self.azimuth_lines) % 360
                
                if deg_angle % 30 < 0.1:
                    label_x = center_x + math.sin(angle) * (max_radius + 12)
                    label_y = center_y - math.cos(angle) * (max_radius + 12)
                    
                    if 0 <= label_x <= self.width() and 0 <= label_y <= self.height():
                        painter.setPen(text_pen)
                        painter.setFont(QFont("Arial", 5, QFont.Bold))
                        
                        if abs(deg_angle) < 5 or abs(deg_angle - 360) < 5:
                            painter.drawText(int(label_x - 5), int(label_y - 2), "N")
                        elif abs(deg_angle - 90) < 5:
                            painter.drawText(int(label_x - 5), int(label_y - 2), "E")
                        elif abs(deg_angle - 180) < 5:
                            painter.drawText(int(label_x - 5), int(label_y - 2), "S")
                        elif abs(deg_angle - 270) < 5:
                            painter.drawText(int(label_x - 5), int(label_y - 2), "W")
                        else:
                            painter.setFont(QFont("Arial", 4))
                            painter.drawText(int(label_x - 8), int(label_y - 2), f"{int(deg_angle)}°")
                        
                        painter.setPen(grid_pen)
        
        # Draw horizon circle (0° altitude)
        horizon_pen = QPen(text_color, 1)
        horizon_pen.setStyle(Qt.DashLine)
        painter.setPen(horizon_pen)
        painter.drawEllipse(QPointF(center_x, center_y), max_radius, max_radius)
        
    def draw_motor_position(self, painter):
        """Draw motor position indicator with zoom - FIXED: uses proper color handling"""
        center_x = self.width() // 2
        center_y = self.height() // 2 + 5
        base_max_radius = min(self.width(), self.height()) * HORIZON_RADIUS_FACTOR
        max_radius = base_max_radius * self.zoom_level
        
        x, y = self.motor_pos.get_screen_position()
        
        screen_x = center_x + (x - 0.5) * 2 * max_radius
        screen_y = center_y + (y - 0.5) * 2 * max_radius
        
        # Determine color based on position
        if hasattr(self.motor_pos, 'in_range') and not self.motor_pos.in_range:
            if self.motor_pos.alt_delta < 0:
                color = QColor(255, 100, 100, 200)
                status_text = "↓"
            else:
                color = QColor(255, 0, 0, 200)
                status_text = "↑"
        elif self.motor_pos.above_horizon:
            color = QColor(0, 255, 0, 200)
            status_text = ""
        else:
            color = QColor(255, 165, 0, 200)
            status_text = "↓"
        
        # Draw main dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(screen_x, screen_y), 5, 5)
        
        # Draw labels
        if self.show_labels:
            text_color = self._get_qcolor('text', QColor(200, 220, 255))
            painter.setPen(QPen(text_color))
            painter.setFont(QFont("Arial", 5, QFont.Bold))
            
            label_x = min(max(int(screen_x + 8), 10), self.width() - 40)
            label_y = min(max(int(screen_y - 8), 15), self.height() - 15)
            
            az_text = f"{self.motor_pos.az_delta:.0f}°"
            alt_text = f"{self.motor_pos.alt_delta:.0f}°"
            
            painter.drawText(label_x, label_y, az_text)
            painter.drawText(label_x, label_y + 8, alt_text + status_text)
        
    def draw_celestial_objects(self, painter):
        """Draw celestial objects with correct altitude mapping and zoom - FIXED: color handling"""
        center_x = self.width() // 2
        center_y = self.height() // 2 + 5
        base_max_radius = min(self.width(), self.height()) * HORIZON_RADIUS_FACTOR
        max_radius = base_max_radius * self.zoom_level
        
        for obj in self.celestial_objects:
            az, alt, x, y, visible = obj.calculate_position(
                self.latitude, self.longitude, self.current_time_utc
            )
            
            screen_x = center_x + (x - 0.5) * 2 * max_radius
            screen_y = center_y + (y - 0.5) * 2 * max_radius
            
            margin = 30
            if screen_x < -margin or screen_x > self.width() + margin or \
               screen_y < -margin or screen_y > self.height() + margin:
                continue
            
            if obj.obj_id == "sun":
                base_size = 6
            elif obj.obj_id == "moon":
                base_size = 5
            elif obj.obj_type == "planet":
                base_size = 4
            elif obj.magnitude < 0:
                base_size = 4
            elif obj.magnitude < 2:
                base_size = 3
            else:
                base_size = 2
            
            size = base_size * min(1.3, max(0.8, self.zoom_level))
            
            # Ensure obj.color is QColor
            obj_color = obj.color
            if isinstance(obj_color, str):
                obj_color = QColor(obj_color)
            
            if not visible:
                if self.show_below_horizon:
                    transparent_color = QColor(
                        obj_color.red(), 
                        obj_color.green(), 
                        obj_color.blue(), 
                        BELOW_HORIZON_OPACITY
                    )
                    
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(transparent_color))
                    painter.drawEllipse(QPointF(screen_x, screen_y), size, size)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(obj_color))
                painter.drawEllipse(QPointF(screen_x, screen_y), size, size)
        
    def draw_selected_highlight(self, painter):
        """Highlight selected celestial object with zoom - FIXED: uses _get_qcolor"""
        center_x = self.width() // 2
        center_y = self.height() // 2 + 5
        base_max_radius = min(self.width(), self.height()) * HORIZON_RADIUS_FACTOR
        max_radius = base_max_radius * self.zoom_level
        
        for obj in self.celestial_objects:
            if obj.obj_id == self.selected_celestial:
                az, alt, x, y, visible = obj.calculate_position(
                    self.latitude, self.longitude, self.current_time_utc
                )
                
                if visible:
                    screen_x = center_x + (x - 0.5) * 2 * max_radius
                    screen_y = center_y + (y - 0.5) * 2 * max_radius
                    
                    accent_color = self._get_qcolor('accent', QColor(252, 163, 17))
                    painter.setPen(QPen(accent_color, 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(screen_x, screen_y), 8, 8)
                    
                    painter.setPen(QPen(accent_color))
                    painter.setFont(QFont("Arial", 5, QFont.Bold))
                    label_x = min(max(int(screen_x + 8), 10), self.width() - 40)
                    label_y = min(max(int(screen_y - 8), 15), self.height() - 15)
                    painter.drawText(label_x, label_y, obj.name[:6])
                    break
        
    def draw_labels(self, painter):
        """Draw static labels with zoom - FIXED: uses _get_qcolor"""
        center_x = self.width() // 2
        center_y = self.height() // 2 + 5
        base_max_radius = min(self.width(), self.height()) * HORIZON_RADIUS_FACTOR
        max_radius = base_max_radius * self.zoom_level
        
        text_color = self._get_qcolor('text', QColor(200, 220, 255))
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 5))
        
        # Zenith label
        zenith_x = center_x
        zenith_y = center_y - 10
        if 0 <= zenith_x <= self.width() and 0 <= zenith_y <= self.height():
            painter.drawText(zenith_x + 10, zenith_y, "Zenith")
        
        # Horizon label
        horizon_x = center_x + int(max_radius) + 15
        horizon_y = center_y - 3
        if 0 <= horizon_x <= self.width() and 0 <= horizon_y <= self.height():
            painter.drawText(horizon_x, horizon_y, "Horizon")
        
    def resizeEvent(self, event):
        if self.show_controls:
            self.button_container.setGeometry(
                PADDING_LEFT, 
                PADDING_TOP, 
                WIDGET_WIDTH - PADDING_LEFT - PADDING_RIGHT, 
                CONTROL_BAR_HEIGHT
            )
        self.update()
        
    def sizeHint(self):
        return QSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        
    def minimumSizeHint(self):
        return QSize(WIDGET_WIDTH, WIDGET_HEIGHT)
    
    def closeEvent(self, event):
        self.update_timer.stop()
        self.celestial_update_timer.stop()
        self.time_timer.stop()
        self.socket_client.stop()
        self.socket_client.wait()
        super().closeEvent(event)


class SkyMapApp(QMainWindow):
    """Standalone application for sky map"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Raspberry Pi 5 - Sky Map")
        self.setStyleSheet("background-color: #0a1428;")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.sky_map = SkyMapWidget(show_controls=True)
        layout.addWidget(self.sky_map)
        
        self.sky_map.time_updated.connect(self.on_time_updated)
        self.sky_map.view_changed.connect(self.on_view_changed)
        self.sky_map.celestial_selected.connect(self.on_celestial_selected)
        self.sky_map.motor_connection_changed.connect(self.on_motor_connected)
        self.sky_map.zoom_changed.connect(self.on_zoom_changed)
        
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        
    def on_time_updated(self, time_str):
        pass
        
    def on_view_changed(self, settings):
        pass
        
    def on_celestial_selected(self, obj_id):
        pass
        
    def on_motor_connected(self, connected):
        if connected:
            self.setWindowTitle("Raspberry Pi 5 - Sky Map (Motor Connected)")
        else:
            self.setWindowTitle("Raspberry Pi 5 - Sky Map")
    
    def on_zoom_changed(self, zoom_level):
        """Handle zoom level changes"""
        self.setWindowTitle(f"Raspberry Pi 5 - Sky Map (Zoom: {zoom_level:.1f}x)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = SkyMapApp()
    window.show()
    
    sys.exit(app.exec_())