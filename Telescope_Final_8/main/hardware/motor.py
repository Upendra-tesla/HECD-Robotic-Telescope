#!/usr/bin/env python3
"""
Motor Control - Manual Mode Only
UPDATED: Connected to global theme manager and config manager from config folder
UPDATED: Proper theme propagation - no direct connection to theme manager
UPDATED: Added safety monitoring
UPDATED: Fixed missing on_sensor_data method
UPDATED: GPIO cleanup and improved error handling
"""

# -----------------------------------------------------------------------------
# Import & Path Configuration
# -----------------------------------------------------------------------------
import sys
import os
import time
import json
import math
from threading import Lock
import subprocess
import socket
import threading
import select
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QMessageBox, QDoubleSpinBox, QSizePolicy,
    QApplication, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QObject
)
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --------------------------
# Critical Path Setup (Same as detect.py and cam.py)
# --------------------------
# Get absolute path of current file (main/hardware/motor.py)
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
# Get path to main folder (parent of hardware/)
MAIN_DIR = os.path.dirname(CURRENT_FILE_DIR)
# Path to config folder (same level as hardware/)
CONFIG_DIR = os.path.join(MAIN_DIR, "config")
# Path to ui folder (for themes_sessions.py if needed)
UI_DIR = os.path.join(MAIN_DIR, "ui")
# Path to tabs folder (for any shared resources)
TABS_DIR = os.path.join(MAIN_DIR, "tabs")
# Path to hardware/utils folder
UTILS_DIR = os.path.join(MAIN_DIR, "hardware", "utils")

# Add directories to Python's search path
for path in [MAIN_DIR, CONFIG_DIR, UI_DIR, TABS_DIR, UTILS_DIR, CURRENT_FILE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# --------------------------
# Import utilities with fallbacks
# --------------------------
try:
    from config.config_manager import config
    CONFIG_MANAGER_AVAILABLE = True
    print("✅ motor.py - Using config manager from config folder")
except ImportError as e:
    print(f"⚠️ Could not import config_manager - using fallback. Error: {e}")
    CONFIG_MANAGER_AVAILABLE = False
    # Fallback ConfigManager
    class ConfigManager:
        def get(self, key, default=None):
            # Try to parse nested keys like 'motor.current_position.azimuth'
            if '.' in key:
                parts = key.split('.')
                current = self._get_config_dict()
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part, {})
                    else:
                        return default
                return current if current != {} else default
            return default
        
        def set(self, key, value):
            print(f"Config set: {key} = {value}")
        
        def update(self, name, updates):
            print(f"Config update: {name} = {updates}")
        
        def reload(self, name):
            pass
        
        def _get_config_dict(self):
            try:
                config_path = os.path.join(MAIN_DIR, "settings.json")
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        return json.load(f)
            except:
                pass
            return {}
    
    config = ConfigManager()

# Import logger with fallback
try:
    from utils.logging import logger
    LOGGER_AVAILABLE = True
    print("✅ motor.py - Using logger from utils folder")
except ImportError as e:
    print(f"⚠️ Could not import logger - using fallback. Error: {e}")
    LOGGER_AVAILABLE = False
    
    class Logger:
        def info(self, msg): print(f"INFO: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def sensor_data(self, *args): pass
        def motor_command(self, *args): pass
    
    logger = Logger()

# --------------------------
# Import Theme Manager from config folder (same as detect.py and cam.py)
# --------------------------
try:
    from config.themes import theme_manager
    THEME_AVAILABLE = True
    print("✅ motor.py - Using global theme manager from config folder")
except ImportError as e:
    print(f"⚠️ Warning: Could not import theme_manager from config - trying ui.themes_sessions. Error: {e}")
    try:
        from ui.themes_sessions import theme_manager
        THEME_AVAILABLE = True
        print("✅ motor.py - Using theme manager from ui folder")
    except ImportError as e2:
        print(f"⚠️ Warning: Could not import theme_manager - using fallback theme. Error: {e2}")
        THEME_AVAILABLE = False
        from PyQt5.QtCore import QObject, pyqtSignal
        
        class FallbackThemeManager(QObject):
            theme_changed = pyqtSignal(str, dict)
            
            def __init__(self):
                super().__init__()
                self.current_theme = "dark_blue"
            
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
                    "slider_bg": "#1e293b",
                    "slider_handle": "#38bdf8",
                    "steel_blue": "#2a4365",
                    "row_bg": "rgba(30, 41, 59, 0.8)",
                    "text_size_small": 9,
                    "border_radius": 5,
                    "button_disabled_bg": "#475569",
                    "button_disabled_text": "#94a3b8"
                }
            
            def get_current_theme(self):
                return self.current_theme
        
        theme_manager = FallbackThemeManager()

# --------------------------
# Helper function to get theme colors safely (same as cam.py)
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
                "text_size": 10,
                "accent": "#38bdf8",
                "accent_gold": "#fca311",
                "border": "#475569",
                "success": "#10b981",
                "warning": "#f59e0b",
                "error": "#ef4444",
                "slider_bg": "#1e293b",
                "slider_handle": "#38bdf8",
                "steel_blue": "#2a4365",
                "row_bg": "rgba(30, 41, 59, 0.8)",
                "text_size_small": 9,
                "border_radius": 5,
                "button_disabled_bg": "#475569",
                "button_disabled_text": "#94a3b8"
            }
    except Exception as e:
        print(f"⚠️ Error getting theme colors: {e}")
        return {}

# --------------------------
# Import calibration dialog
# --------------------------
try:
    from hardware.calibration import CalibrateDialog
    logger.info("Successfully imported CalibrateDialog")
except ImportError as e:
    logger.warning(f"calibration module not found: {e}")
    class CalibrateDialog(QDialog):
        calibration_saved = pyqtSignal(float, float)
        
        def __init__(self, current_az, current_alt, theme, parent=None, 
                     sensor_az_delta=None, sensor_alt_delta=None, both_connected=False):
            super().__init__(parent)
            self.current_az = current_az
            self.current_alt = current_alt
            self.sensor_az_delta = sensor_az_delta
            self.sensor_alt_delta = sensor_alt_delta
            self.both_connected = both_connected
            self.setModal(True)
            self.setWindowTitle("Motor Calibration (Mock)")
            self.setFixedSize(400, 300)
            
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel(f"Current Azimuth: {current_az:.1f}°"))
            layout.addWidget(QLabel(f"Current Altitude: {current_alt:.1f}°"))
            if sensor_az_delta is not None:
                az_text = f"{sensor_az_delta:+.1f}°"
                if sensor_az_delta > 0:
                    az_text = f"↻{az_text}"
                elif sensor_az_delta < 0:
                    az_text = f"↺{az_text}"
                layout.addWidget(QLabel(f"Azimuth Delta: {az_text}"))
            if sensor_alt_delta is not None:
                layout.addWidget(QLabel(f"Altitude Delta: {sensor_alt_delta:.1f}°"))
            
            buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                Qt.Horizontal, self
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
            
        def exec_(self):
            return QDialog.Accepted
            
        def get_values(self):
            return self.current_az, self.current_alt

# GPIO initialization with cleanup
GPIO_AVAILABLE = False
try:
    from gpiozero import Motor, Device
    from gpiozero.pins.native import NativeFactory
    GPIO_AVAILABLE = True
    logger.info("gpiozero imported successfully")
except ImportError:
    logger.warning("gpiozero not found - running in simulation mode")
    class Motor:
        def __init__(self, forward, backward): 
            logger.debug(f"Simulation: Motor created with forward={forward}, backward={backward}")
            pass
        def forward(self, speed=1): 
            logger.debug(f"Simulation: Motor.forward({speed}) called")
            pass
        def backward(self, speed=1): 
            logger.debug(f"Simulation: Motor.backward({speed}) called")
            pass
        def stop(self): 
            logger.debug(f"Simulation: Motor.stop() called")
            pass

# GPIO cleanup function
def cleanup_gpio_pins():
    """Attempt to clean up any stale GPIO pins"""
    if not GPIO_AVAILABLE:
        return
    
    try:
        # Close all gpiozero devices
        Device.close_all()
        logger.info("✅ Cleaned up gpiozero devices")
    except Exception as e:
        logger.debug(f"gpiozero cleanup: {e}")
    
    try:
        # Try to unexport any stuck pins via sysfs
        pins_to_clean = [17, 18, 22, 23, 27, 19]
        for pin in pins_to_clean:
            try:
                if os.path.exists(f'/sys/class/gpio/gpio{pin}'):
                    with open('/sys/class/gpio/unexport', 'w') as f:
                        f.write(str(pin))
                    logger.debug(f"Unexported GPIO{pin} via sysfs")
            except (PermissionError, IOError):
                # May need root - ignore
                pass
            except Exception as e:
                logger.debug(f"Could not unexport GPIO{pin}: {e}")
    except Exception as e:
        logger.debug(f"GPIO sysfs cleanup error: {e}")

# Import unified sensor controller
try:
    from hardware.sensor_controller import UnifiedSensorController
    logger.info("Successfully imported UnifiedSensorController")
except ImportError:
    logger.warning("sensor_controller module not found - using mock")
    class UnifiedSensorController(QObject):
        connection_status = pyqtSignal(int, bool, str)
        sensor_data = pyqtSignal(int, dict)
        error_msg = pyqtSignal(str)
        def __init__(self):
            super().__init__()
        def start(self): pass
        def stop(self): pass

# Import safety monitor
try:
    from hardware.safety import SafetyMonitor, SafetyCondition, SafetyLevel
    SAFETY_AVAILABLE = True
    logger.info("Safety monitor imported successfully")
except ImportError:
    logger.warning("Safety monitor not available")
    SAFETY_AVAILABLE = False
    class SafetyLevel:
        NORMAL = 0; WARNING = 1; CRITICAL = 2; EMERGENCY = 3
    class SafetyCondition: pass
    class SafetyMonitor:
        def __init__(self, check_interval=0.1): pass
        def start(self): pass
        def stop(self): pass
        def add_condition(self, cond): pass
        def register_callback(self, level, cb): pass

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
LOCKED_AZ_PINS = {"left": 22, "right": 23}
LOCKED_ALT_PINS = {"up": 17, "down": 18}

UI_SPACING = 4
UI_MARGIN = 2
MIN_BUTTON_SIZE = (55, 25)

AZ_MIN = 0.0
AZ_MAX = 360.0

DEFAULT_HORIZON_ANGLE = 0.0
DEFAULT_ZENITH_ANGLE = 90.0

MANUAL_SPEED_MIN = 1.0
MANUAL_SPEED_MAX = 10.0

SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 65432
INITIAL_AZIMUTH = 0.0
INITIAL_ALTITUDE = 90.0

SENSOR_UPDATE_INTERVAL = 0.3
SOCKET_SEND_INTERVAL = 0.1


# -----------------------------------------------------------------------------
# Continuous Angle Tracker
# -----------------------------------------------------------------------------
class ContinuousAngleTracker:
    """Tracks angle continuously, handling wrap-around smoothly for 0-360° display"""
    
    def __init__(self, initial_value=0.0, initial_crossings=0):
        self.continuous_value = float(initial_value) if initial_value is not None else 0.0
        self.last_raw_value = float(initial_value) if initial_value is not None else 0.0
        self.crossings = int(initial_crossings) if initial_crossings is not None else 0
        self.total_wraps = int(initial_crossings) if initial_crossings is not None else 0
        logger.debug(f"AngleTracker initialized: value={self.continuous_value:.1f}, crossings={self.crossings}")
        
    def update(self, raw_value):
        if raw_value is None:
            return self.continuous_value
            
        diff = raw_value - self.last_raw_value
        
        if diff > 180:
            diff -= 360
            self.crossings += 1
            self.total_wraps += 1
            logger.debug(f"AngleTracker: wrap +1 (crossings={self.crossings})")
        elif diff < -180:
            diff += 360
            self.crossings -= 1
            self.total_wraps -= 1
            logger.debug(f"AngleTracker: wrap -1 (crossings={self.crossings})")
        
        self.continuous_value += diff
        self.last_raw_value = raw_value
        
        return self.continuous_value
    
    def get_display_value(self, reset_reference=None):
        if reset_reference is not None:
            relative = reset_reference - self.continuous_value
        else:
            relative = self.continuous_value
        
        display = relative % 360.0
        return display
    
    def get_direction_symbol(self, reset_reference=None):
        if reset_reference is None:
            return ""
        
        current_display = self.get_display_value(reset_reference)
        
        earlier_continuous = self.continuous_value - 1.0
        earlier_display = (reset_reference - earlier_continuous) % 360.0
        
        if abs(current_display - earlier_display) > 180:
            if current_display < earlier_display:
                return "↻"
            else:
                return "↺"
        elif current_display > earlier_display:
            return "↻"
        elif current_display < earlier_display:
            return "↺"
        else:
            return ""
    
    def reset_reference(self, raw_value):
        if raw_value is None:
            return self.continuous_value
            
        self.continuous_value = float(raw_value)
        self.last_raw_value = float(raw_value)
        self.crossings = 0
        logger.debug(f"AngleTracker: reset to {raw_value:.1f}")
        return self.continuous_value
    
    def get_raw_delta(self, reset_reference):
        if reset_reference is None:
            return None
        
        relative = reset_reference - self.continuous_value
        raw_delta = relative % 360.0
        if raw_delta > 180:
            raw_delta -= 360
        return raw_delta


# -----------------------------------------------------------------------------
# Angle Conversion Functions
# -----------------------------------------------------------------------------
def sensor_to_motor_az(sensor_az):
    if sensor_az is None:
        return 0.0
    return float(sensor_az) % 360.0

def motor_to_sensor_az(motor_az):
    if motor_az is None:
        return 0.0
    sensor_az = float(motor_az) % 360.0
    if sensor_az > 180:
        sensor_az -= 360
    return sensor_az

def safe_normalize(angle):
    if angle is None:
        return 0.0
    return float(angle) % 360.0

def sensor_to_motor_alt(sensor_alt, horizon_angle, zenith_angle):
    if sensor_alt is None:
        return INITIAL_ALTITUDE
    
    h_norm = safe_normalize(horizon_angle if horizon_angle is not None else DEFAULT_HORIZON_ANGLE)
    z_norm = safe_normalize(zenith_angle if zenith_angle is not None else DEFAULT_ZENITH_ANGLE)
    s_norm = safe_normalize(sensor_alt)
    
    dist_to_horizon = min(abs(s_norm - h_norm), 360 - abs(s_norm - h_norm))
    dist_to_zenith = min(abs(s_norm - z_norm), 360 - abs(s_norm - z_norm))
    
    if dist_to_horizon < dist_to_zenith:
        motor_alt = 0.0
        if dist_to_horizon < 10:
            motor_alt = 0.0
        else:
            motor_alt = min(45.0, dist_to_horizon * 4.5)
    else:
        motor_alt = 90.0
        if dist_to_zenith < 10:
            motor_alt = 90.0
        else:
            motor_alt = max(45.0, 90.0 - (dist_to_zenith * 4.5))
    
    return motor_alt

def motor_to_sensor_alt(motor_alt, horizon_angle, zenith_angle):
    if motor_alt is None:
        return 0.0
        
    motor_norm = safe_normalize(motor_alt)
    
    h = float(horizon_angle) if horizon_angle is not None else DEFAULT_HORIZON_ANGLE
    z = float(zenith_angle) if zenith_angle is not None else DEFAULT_ZENITH_ANGLE
    
    if motor_norm < 45:
        factor = motor_norm / 45.0
        z_norm = safe_normalize(z)
        h_norm = safe_normalize(h)
        
        if h_norm <= z_norm:
            interp = h_norm + factor * (z_norm - h_norm)
        else:
            interp = h_norm + factor * ((z_norm + 360) - h_norm)
            if interp >= 360:
                interp -= 360
        
        if interp > 180:
            interp -= 360
        return interp
    elif motor_norm < 135:
        factor = (motor_norm - 45.0) / 90.0
        z_norm = safe_normalize(z)
        h_norm = safe_normalize(h)
        
        if z_norm <= h_norm:
            interp = z_norm + factor * ((h_norm + 360) - z_norm)
        else:
            interp = z_norm + factor * ((h_norm + 360) - z_norm)
            
        if interp >= 360:
            interp -= 360
        if interp > 180:
            interp -= 360
        return interp
    else:
        factor = (motor_norm - 135.0) / 225.0
        h_norm = safe_normalize(h)
        interp = h_norm + factor * 360.0
        interp %= 360.0
        if interp > 180:
            interp -= 360
        return interp

def is_altitude_within_limits(sensor_alt, horizon_angle, zenith_angle):
    if sensor_alt is None:
        return False
    
    s_norm = safe_normalize(sensor_alt)
    h_norm = safe_normalize(horizon_angle if horizon_angle is not None else DEFAULT_HORIZON_ANGLE)
    z_norm = safe_normalize(zenith_angle if zenith_angle is not None else DEFAULT_ZENITH_ANGLE)
    
    arc1_length = (z_norm - h_norm) % 360
    arc2_length = (h_norm - z_norm) % 360
    
    if arc1_length <= arc2_length:
        if h_norm <= z_norm:
            return h_norm <= s_norm <= z_norm
        else:
            return s_norm >= h_norm or s_norm <= z_norm
    else:
        if z_norm <= h_norm:
            return z_norm <= s_norm <= h_norm
        else:
            return s_norm >= z_norm or s_norm <= h_norm

def calculate_relative_angle(current, reference):
    if current is None or reference is None:
        return None, ""
    
    diff = float(current) - float(reference)
    
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    
    if abs(diff) < 0.1:
        direction = ""
    elif diff > 0:
        direction = "↻"
    else:
        direction = "↺"
    
    return diff, direction

def format_relative_angle(diff, direction):
    if diff is None:
        return "—"
    if abs(diff) < 0.1:
        return "0.0°"
    return f"{direction}{diff:+.1f}°"

def format_display_angle(angle, direction):
    if angle is None:
        return "—"
    if abs(angle) < 0.1 or abs(360 - angle) < 0.1:
        return "0.0°"
    return f"{direction}{angle:.1f}°"

def calculate_altitude_delta(sensor_alt, alt_reference):
    if sensor_alt is None or alt_reference is None:
        return None, ""
    
    raw_delta, direction = calculate_relative_angle(sensor_alt, alt_reference)
    if raw_delta is None:
        return None, ""
    
    if raw_delta >= 0:
        display_angle = raw_delta
        display_dir = "↻" if raw_delta > 0 else ""
    else:
        display_angle = 360.0 + raw_delta
        display_dir = "↺"
    
    display_angle = display_angle % 360.0
    return display_angle, display_dir


# -----------------------------------------------------------------------------
# Motor Thread
# -----------------------------------------------------------------------------
class MotorThread(QThread):
    position_signal = pyqtSignal(float, str)
    error_signal = pyqtSignal(str)

    def __init__(self, axis, pins):
        super().__init__()
        self.axis = axis
        self.pins = pins
        self.running = True
        self.lock = Lock()
        self.motor_initialized = False

        if axis == "az":
            self.current_position = INITIAL_AZIMUTH
        else:
            self.current_position = INITIAL_ALTITUDE
        self.target_position = self.current_position
        self.speed = 1.0
        self.emergency_stop = False
        
        self.sensor_connected = False
        self.sensor_angles = [0.0, 0.0, 0.0]
        self.last_sensor_update = time.time()
        self.sensor_timeout = 2.0

        # Initialize motor with cleanup
        self.motor = None
        try:
            if GPIO_AVAILABLE:
                # Attempt to clean up any stale pins first
                try:
                    Device.close_all()
                except:
                    pass
                
                if self.axis == "az":
                    self.motor = Motor(forward=pins["right"], backward=pins["left"])
                else:
                    self.motor = Motor(forward=pins["up"], backward=pins["down"])
                
                if self.motor:
                    self.motor.stop()
                    self.motor_initialized = True
                    logger.info(f"{self.axis.upper()} motor initialized successfully")
            else:
                logger.warning(f"{self.axis.upper()} motor: GPIO not available - simulation mode")
                self.motor_initialized = False
        except Exception as e:
            # Check if it's a pin-in-use error
            error_str = str(e)
            if "already in use" in error_str:
                logger.error(f"{self.axis.upper()} motor initialization failed: {error_str}")
                logger.warning("Attempting to clean up GPIO pins...")
                
                # Try to clean up and retry once
                try:
                    Device.close_all()
                    time.sleep(0.5)
                    
                    if self.axis == "az":
                        self.motor = Motor(forward=pins["right"], backward=pins["left"])
                    else:
                        self.motor = Motor(forward=pins["up"], backward=pins["down"])
                    
                    if self.motor:
                        self.motor.stop()
                        self.motor_initialized = True
                        logger.info(f"{self.axis.upper()} motor initialized successfully after cleanup")
                    else:
                        self.motor_initialized = False
                except Exception as retry_e:
                    logger.error(f"{self.axis.upper()} motor initialization failed even after cleanup: {retry_e}")
                    self.motor_initialized = False
                    self.motor = None
            else:
                logger.error(f"{self.axis.upper()} motor initialization failed: {e}")
                self.motor_initialized = False
                self.motor = None

    def set_sensor_status(self, connected, angles=None):
        with self.lock:
            self.sensor_connected = connected
            if angles and len(angles) >= 3:
                self.sensor_angles = [float(a) if a is not None else 0.0 for a in angles]
                self.last_sensor_update = time.time()

    def set_step(self, step):
        with self.lock:
            old_target = self.target_position
            if self.axis == "az":
                new_target = (self.current_position + step) % AZ_MAX
            else:
                new_target = self.current_position + step
                # Safety check for altitude
                if new_target < -5 or new_target > 95:
                    logger.warning(f"Altitude target {new_target:.1f}° outside safe range, clamping")
                    new_target = max(-5, min(95, new_target))
            
            self.target_position = new_target
            self.emergency_stop = False
            logger.debug(f"{self.axis.upper()} step: {step:.1f}° (from {old_target:.1f}° to {new_target:.1f}°)")

    def set_speed(self, speed):
        with self.lock:
            old_speed = self.speed
            self.speed = max(MANUAL_SPEED_MIN, min(MANUAL_SPEED_MAX, float(speed)))
            if abs(self.speed - old_speed) > 0.1:
                logger.debug(f"{self.axis.upper()} speed: {self.speed:.1f}°/s")

    def trigger_emergency_stop(self):
        with self.lock:
            self.emergency_stop = True
            if self.motor_initialized and self.motor:
                self.motor.stop()
            logger.warning(f"EMERGENCY STOP triggered for {self.axis.upper()}")

    def clear_emergency_stop(self):
        with self.lock:
            self.emergency_stop = False
            logger.info(f"{self.axis.upper()} emergency stop cleared")

    def run(self):
        logger.debug(f"{self.axis.upper()} motor thread started")
        while self.running:
            with self.lock:
                target = self.target_position
                speed = self.speed
                emergency_stop = self.emergency_stop
                current = self.current_position
                motor_ok = self.motor_initialized and self.motor is not None

            if emergency_stop:
                if motor_ok:
                    self.motor.stop()
                time.sleep(0.05)
                continue

            if self.axis == "az":
                cw = (target - current) % AZ_MAX
                ccw = (current - target) % AZ_MAX
                dist = min(cw, ccw)
                dir = 1 if cw <= ccw else -1
            else:
                error = target - current
                if abs(error) > 180:
                    if error > 0:
                        error = error - 360
                    else:
                        error = error + 360
                dir = 1 if error > 0 else -1
                dist = abs(error)

            if dist < 0.05:
                if motor_ok:
                    self.motor.stop()
                time.sleep(0.05)
                continue

            try:
                move_step = speed * 0.05
                move_step = min(move_step, dist)
                speed_norm = min(1.0, speed / 10.0)

                if self.axis == "az":
                    if dir > 0:
                        if motor_ok:
                            self.motor.forward(speed_norm)
                        new_pos = current + move_step
                        if new_pos >= AZ_MAX:
                            new_pos -= AZ_MAX
                    else:
                        if motor_ok:
                            self.motor.backward(speed_norm)
                        new_pos = current - move_step
                        if new_pos < 0:
                            new_pos += AZ_MAX
                else:
                    if dir > 0:
                        if motor_ok:
                            self.motor.forward(speed_norm)
                        new_pos = current + move_step
                    else:
                        if motor_ok:
                            self.motor.backward(speed_norm)
                        new_pos = current - move_step
                    
                    # Safety check
                    if new_pos < -5 or new_pos > 95:
                        logger.warning(f"Altitude position {new_pos:.1f}° outside safe range, stopping")
                        self.trigger_emergency_stop()
                        continue

                with self.lock:
                    self.current_position = new_pos
                self.position_signal.emit(new_pos, self.axis)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"{self.axis.upper()} Movement Error: {e}")
                self.error_signal.emit(f"{self.axis.upper()} Movement Error: {str(e)}")
                time.sleep(0.5)

    def stop(self):
        logger.info(f"Stopping {self.axis.upper()} motor")
        with self.lock:
            self.running = False
            self.emergency_stop = True
        if self.motor_initialized and self.motor:
            self.motor.stop()
        self.wait()


# -----------------------------------------------------------------------------
# Socket Server
# -----------------------------------------------------------------------------
class MotorSocketServer(QObject):
    client_connected = pyqtSignal(bool)

    def __init__(self, az_motor=None, alt_motor=None, parent=None):
        super().__init__(parent)
        self.running = True
        self.client_connection = None
        self.client_address = None
        self.lock = Lock()
        self.client_present = False
        self.server_socket = None
        self.thread = None
        
        self.current_az_delta = 0.0
        self.current_alt_delta = 0.0
        self.az_reset_reference = None
        self.alt_reset_reference = None
        self.sensor_az_connected = False
        self.sensor_alt_connected = False
        
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self.send_sensor_data)
        self.send_timer.start(int(SOCKET_SEND_INTERVAL * 1000))

        self.start_server()

    def start_server(self):
        self.stop_server()
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((SOCKET_HOST, SOCKET_PORT))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            self.running = True

            self.thread = threading.Thread(target=self.run_server, daemon=True)
            self.thread.start()
            print(f"✅ Socket server listening on {SOCKET_HOST}:{SOCKET_PORT}")
        except Exception as e:
            print(f"⚠️ Could not start socket server: {e}")

    def stop_server(self):
        self.running = False
        
        with self.lock:
            if self.client_connection:
                try:
                    self.client_connection.close()
                except:
                    pass
                self.client_connection = None
                self.client_present = False
            
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
                self.server_socket = None
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def update_delta_values(self, az_delta, alt_delta):
        with self.lock:
            self.current_az_delta = float(az_delta) if az_delta is not None else 0.0
            self.current_alt_delta = float(alt_delta) if alt_delta is not None else 0.0

    def update_sensor_status(self, az_connected, alt_connected, az_ref=None, alt_ref=None):
        with self.lock:
            self.sensor_az_connected = az_connected
            self.sensor_alt_connected = alt_connected
            if az_ref is not None:
                self.az_reset_reference = float(az_ref)
            if alt_ref is not None:
                self.alt_reset_reference = float(alt_ref)

    def send_sensor_data(self):
        if not self.client_present or not self.client_connection:
            return
        
        try:
            with self.lock:
                sensor_msg = f"SENSOR,{self.current_az_delta:.1f},{self.current_alt_delta:.1f}\n"
            
            self.client_connection.send(sensor_msg.encode())
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            with self.lock:
                if self.client_connection:
                    try:
                        self.client_connection.close()
                    except:
                        pass
                    self.client_connection = None
                    self.client_present = False
            self.client_connected.emit(False)
            print(f"⚠️ Client disconnected: {e}")

    def run_server(self):
        while self.running:
            try:
                if self.client_connection is None and self.server_socket:
                    try:
                        ready, _, _ = select.select([self.server_socket], [], [], 0.1)
                        if ready:
                            conn, addr = self.server_socket.accept()
                            with self.lock:
                                self.client_connection = conn
                                self.client_present = True
                                self.client_address = addr
                            self.client_connected.emit(True)
                            print(f"📡 Client connected from {addr}")
                    except (socket.timeout, select.error):
                        continue
                    except Exception as e:
                        if self.running:
                            print(f"⚠️ Socket accept error: {e}")

                if self.client_connection:
                    try:
                        self.client_connection.settimeout(0.1)
                        data = self.client_connection.recv(1024)
                        if not data:
                            raise ConnectionResetError("Client closed connection")
                    except socket.timeout:
                        continue
                    except (ConnectionResetError, BrokenPipeError, OSError) as e:
                        with self.lock:
                            if self.client_connection:
                                try:
                                    self.client_connection.close()
                                except:
                                    pass
                                self.client_connection = None
                                self.client_present = False
                        self.client_connected.emit(False)
                        print(f"⚠️ Client disconnected: {e}")
            except Exception as e:
                if self.running:
                    print(f"⚠️ Socket server error: {e}")
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.send_timer.stop()
        self.stop_server()


# -----------------------------------------------------------------------------
# File Watcher
# -----------------------------------------------------------------------------
class CalibrationFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
    
    def on_modified(self, event):
        if event.src_path.endswith('motor.json'):
            logger.info("Calibration file changed, reloading...")
            self.callback()


# -----------------------------------------------------------------------------
# Direction Mapping
# -----------------------------------------------------------------------------
class DirectionMapper:
    """Maps sensor values to cardinal directions using trained calibration"""
    
    def __init__(self):
        self.az_calibration = {}
        self.alt_calibration = {}
        self.horizon_angle = DEFAULT_HORIZON_ANGLE
        self.zenith_angle = DEFAULT_ZENITH_ANGLE
        self.load_calibration()
    
    def load_calibration(self):
        """Load calibration data from config manager"""
        try:
            # Get calibration from config
            calib = config.get('motor.calibration', {})
            
            self.az_calibration = calib.get("azimuth_calibration_delta_32", {})
            if not self.az_calibration:
                self.az_calibration = calib.get("azimuth_calibration_delta", {})
            if not self.az_calibration:
                self.az_calibration = calib.get("azimuth_calibration", {})
            
            self.alt_calibration = calib.get("altitude_calibration_delta_13", {})
            if not self.alt_calibration:
                self.alt_calibration = calib.get("altitude_calibration_delta", {})
            if not self.alt_calibration:
                self.alt_calibration = calib.get("altitude_calibration", {})
            
            if "horizon" in self.alt_calibration and self.alt_calibration["horizon"] is not None:
                self.horizon_angle = float(self.alt_calibration["horizon"])
            else:
                for key, value in self.alt_calibration.items():
                    if "horizon" in key.lower() and value is not None:
                        self.horizon_angle = float(value)
                        break
            
            if "zenith" in self.alt_calibration and self.alt_calibration["zenith"] is not None:
                self.zenith_angle = float(self.alt_calibration["zenith"])
            else:
                for key, value in self.alt_calibration.items():
                    if "zenith" in key.lower() and value is not None:
                        self.zenith_angle = float(value)
                        break
            
            az_count = len([v for v in self.az_calibration.values() if v is not None])
            alt_count = len([v for v in self.alt_calibration.values() if v is not None])
            
            logger.info(f"Loaded calibration: {az_count} directions, {alt_count} altitudes")
            logger.info(f"Horizon: {self.horizon_angle:.1f}°, Zenith: {self.zenith_angle:.1f}°")
            
        except Exception as e:
            logger.error(f"Could not load calibration: {e}")
            self.az_calibration = {}
            self.alt_calibration = {}
            self.horizon_angle = DEFAULT_HORIZON_ANGLE
            self.zenith_angle = DEFAULT_ZENITH_ANGLE
    
    def get_direction_from_delta(self, delta_az):
        """Get cardinal direction from delta azimuth angle"""
        if delta_az is None or not self.az_calibration:
            return None, 999
        
        closest_dir = None
        min_diff = float('inf')
        
        for direction, trained_delta in self.az_calibration.items():
            if trained_delta is None:
                continue
            diff = abs(delta_az - float(trained_delta))
            if diff > 180:
                diff = 360 - diff
            
            if diff < min_diff:
                min_diff = diff
                closest_dir = direction
        
        if min_diff < 10:
            return closest_dir.capitalize(), min_diff
        return None, min_diff
    
    def get_altitude_from_sensor(self, sensor_value):
        """Get altitude position from trained sensor value"""
        if sensor_value is None or not self.alt_calibration:
            return None, 999
        
        closest_pos = None
        min_diff = float('inf')
        
        for position, trained_value in self.alt_calibration.items():
            if trained_value is None:
                continue
            diff = abs(sensor_value - float(trained_value))
            if diff > 180:
                diff = 360 - diff
            
            if diff < min_diff:
                min_diff = diff
                closest_pos = position
        
        if min_diff < 10:
            return closest_pos.capitalize(), min_diff
        return None, min_diff


# Global direction mapper instance
direction_mapper = DirectionMapper()

def get_cardinal_direction(az_angle):
    """Get cardinal direction from motor azimuth angle"""
    if az_angle is None:
        return "Unknown"
    az = float(az_angle) % 360
    if 348.75 <= az < 360 or 0 <= az < 11.25:
        return "N"
    elif 11.25 <= az < 33.75:
        return "NbE"
    elif 33.75 <= az < 56.25:
        return "NNE"
    elif 56.25 <= az < 78.75:
        return "NEbN"
    elif 78.75 <= az < 101.25:
        return "NE"
    elif 101.25 <= az < 123.75:
        return "NEbE"
    elif 123.75 <= az < 146.25:
        return "ENE"
    elif 146.25 <= az < 168.75:
        return "EbN"
    elif 168.75 <= az < 191.25:
        return "E"
    elif 191.25 <= az < 213.75:
        return "EbS"
    elif 213.75 <= az < 236.25:
        return "ESE"
    elif 236.25 <= az < 258.75:
        return "SEbE"
    elif 258.75 <= az < 281.25:
        return "SE"
    elif 281.25 <= az < 303.75:
        return "SEbS"
    elif 303.75 <= az < 326.25:
        return "SSE"
    elif 326.25 <= az < 348.75:
        return "SbE"
    return "Unknown"

def get_full_direction(az_angle):
    """Get detailed direction (32-point compass) from motor azimuth"""
    if az_angle is None:
        return "Unknown"
    az = (float(az_angle) - 5.625) % 360
    
    compass_points = [
        (0, "North"), (11.25, "North by east"), (22.5, "North-northeast"),
        (33.75, "Northeast by north"), (45, "Northeast"), (56.25, "Northeast by east"),
        (67.5, "East-northeast"), (78.75, "East by north"), (90, "East"),
        (101.25, "East by south"), (112.5, "East-southeast"), (123.75, "Southeast by east"),
        (135, "Southeast"), (146.25, "Southeast by south"), (157.5, "South-southeast"),
        (168.75, "South by east"), (180, "South"), (191.25, "South by west"),
        (202.5, "South-southwest"), (213.75, "Southwest by south"), (225, "Southwest"),
        (236.25, "Southwest by west"), (247.5, "West-southwest"), (258.75, "West by south"),
        (270, "West"), (281.25, "West by north"), (292.5, "West-northwest"),
        (303.75, "Northwest by west"), (315, "Northwest"), (326.25, "Northwest by north"),
        (337.5, "North-northwest"), (348.75, "North by west")
    ]
    
    for i, (angle, name) in enumerate(compass_points):
        next_angle = compass_points[(i + 1) % 32][0] if i < 31 else 360
        if angle <= az < next_angle:
            return name
    return "North"

def get_altitude_name(alt_angle):
    """Get altitude position name from motor altitude"""
    if alt_angle is None:
        return "Unknown"
    alt = float(alt_angle) % 360
    
    altitude_points = [
        (0, "Horizon"), (7.5, "Very Low"), (15, "Low"), (22.5, "Low-Mid"),
        (30, "Mid-Low"), (37.5, "Mid"), (45, "Mid"), (52.5, "Mid-High"),
        (60, "Mid-High"), (67.5, "High-Mid"), (75, "High"), (82.5, "Very High"),
        (90, "Zenith")
    ]
    
    if alt > 90 and alt < 270:
        return "Below Horizon"
    elif alt > 270:
        alt = 360 - alt
    
    for i, (angle, name) in enumerate(altitude_points):
        next_angle = altitude_points[i + 1][0] if i < len(altitude_points) - 1 else 90
        if angle <= alt < next_angle:
            return name
        elif abs(alt - angle) < 1:
            return name
    return f"{alt:.0f}°"

def format_angle_with_sign(angle):
    """Format angle with explicit sign"""
    if angle is None:
        return "—"
    if angle >= 0:
        return f"+{angle:.1f}°"
    else:
        return f"{angle:.1f}°"


# -----------------------------------------------------------------------------
# Main Widget
# -----------------------------------------------------------------------------
class MotorControlWidget(QWidget):
    def __init__(self, theme=None, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(580, 200)
        self.setWindowTitle("Motor Control")

        # Get theme from manager if not provided
        if theme is None:
            self.theme = get_theme_colors()
        elif isinstance(theme, dict):
            self.theme = theme
        else:
            self.theme = get_theme_colors()

        # Ensure theme has all required keys
        self._ensure_theme_complete()

        # Initialize components
        self.sensor = UnifiedSensorController()
        self.sensor_az_connected = False
        self.sensor_alt_connected = False
        self.sensor_az_data = None
        self.sensor_alt_data = None
        
        self.az_tracker = None
        self.az_display_reference = None
        
        self.az_reset_reference = config.get('motor.delta_tracking.az_delta_reference')
        self.alt_reset_reference = config.get('motor.delta_tracking.alt_delta_reference')
        
        self.current_az_delta = config.get('motor.delta_tracking.current_az_delta', 0.0)
        self.current_alt_delta = config.get('motor.delta_tracking.current_alt_delta', 0.0)
        
        self.az_continuous = config.get('motor.delta_tracking.az_continuous', 0.0)
        self.az_crossings = config.get('motor.delta_tracking.az_crossings', 0)
        
        self.deltas_restored = False
        self.last_button_press_time = 0
        self.last_az_update = 0
        self.last_alt_update = 0

        # Initialize motors with GPIO cleanup
        self.az_motor = MotorThread("az", LOCKED_AZ_PINS)
        self.alt_motor = MotorThread("alt", LOCKED_ALT_PINS)

        # Connect motor signals
        self.az_motor.position_signal.connect(self.update_motor_display)
        self.alt_motor.position_signal.connect(self.update_motor_display)
        self.az_motor.error_signal.connect(self.show_error)
        self.alt_motor.error_signal.connect(self.show_error)

        # Connect sensor signals
        self.sensor.connection_status.connect(self.on_sensor_status)
        self.sensor.sensor_data.connect(self.on_sensor_data)
        self.sensor.error_msg.connect(self.on_sensor_error)

        # Load saved positions
        self.load_saved_positions()
        
        # Initialize angle tracker
        if self.az_tracker is None:
            self.az_tracker = ContinuousAngleTracker(
                initial_value=self.az_continuous,
                initial_crossings=self.az_crossings
            )
        
        # Socket server for track.py
        self.socket_server = MotorSocketServer(self.az_motor, self.alt_motor, self)
        self.socket_server.client_connected.connect(self.on_client_connected)

        # Timers
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.check_sensor_health)
        self.health_timer.start(1000)

        self.delta_update_timer = QTimer()
        self.delta_update_timer.timeout.connect(self.update_socket_delta_values)
        self.delta_update_timer.start(50)

        # Setup file watcher
        self.setup_file_watcher()

        # Initialize safety monitor
        self.safety = SafetyMonitor(check_interval=0.1)
        self._setup_safety_monitor()
        self.safety.start()

        # Build UI
        self._build_ui()
        self._apply_theme_styles()

        # Update button states
        self.update_button_states(
            self.az_motor.current_position,
            self.alt_motor.current_position
        )

        # Start motors
        self.az_motor.start()
        self.alt_motor.start()

        # DO NOT connect to theme manager here - updates come from parent tab
        # Theme updates will be handled via update_theme() method
        
        logger.info("MotorControlWidget initialized")

    def _setup_safety_monitor(self):
        """Setup safety monitoring conditions"""
        if not SAFETY_AVAILABLE:
            return
            
        # Azimuth range check
        self.safety.add_condition(SafetyCondition(
            name="azimuth_range",
            check_func=lambda: abs(self.az_motor.current_position) > 360,
            level=SafetyLevel.EMERGENCY,
            message="Azimuth outside safe range",
            auto_recover=False
        ))
        
        # Altitude range check
        self.safety.add_condition(SafetyCondition(
            name="altitude_range",
            check_func=lambda: (self.alt_motor.current_position < -5 or 
                                self.alt_motor.current_position > 95),
            level=SafetyLevel.EMERGENCY,
            message="Altitude outside safe range",
            auto_recover=False
        ))
        
        # Sensor timeout check
        self.safety.add_condition(SafetyCondition(
            name="sensor_timeout_az",
            check_func=lambda: (self.sensor_az_connected and 
                               time.time() - self.last_az_update > 5.0),
            level=SafetyLevel.WARNING,
            message="AZ sensor timeout",
            auto_recover=True
        ))
        
        self.safety.add_condition(SafetyCondition(
            name="sensor_timeout_alt",
            check_func=lambda: (self.sensor_alt_connected and 
                               time.time() - self.last_alt_update > 5.0),
            level=SafetyLevel.WARNING,
            message="ALT sensor timeout",
            auto_recover=True
        ))
        
        # Register callback for emergency stops
        self.safety.register_callback(SafetyLevel.EMERGENCY, 
                                      lambda c: self.emergency_stop_all())

    def _ensure_theme_complete(self):
        """Ensure theme dictionary has all required keys"""
        default_theme = {
            "window_bg": "#0f172a",
            "tab_pane": "#1e293b",
            "text_color": "#f8fafc",
            "button_bg": "#2563eb",
            "button_hover": "#38bdf8",
            "button_text": "#ffffff",
            "slider_bg": "#1e293b",
            "slider_handle": "#38bdf8",
            "accent_gold": "#fca311",
            "steel_blue": "#2a4365",
            "row_bg": "rgba(30, 41, 59, 0.8)",
            "text_size": 10,
            "text_size_small": 9,
            "border_radius": 5,
            "button_disabled_bg": "#475569",
            "button_disabled_text": "#94a3b8",
            "warning_color": "#f59e0b",
            "error_color": "#ef4444",
            "success_color": "#10b981"
        }
        
        for key, value in default_theme.items():
            if key not in self.theme:
                self.theme[key] = value

    def setup_file_watcher(self):
        try:
            self.observer = Observer()
            self.file_handler = CalibrationFileHandler(self.reload_calibration)
            
            # Check multiple possible locations for motor.json
            possible_paths = [
                os.path.join(MAIN_DIR, "motor.json"),
                os.path.join(CONFIG_DIR, "motor.json"),
                os.path.join(MAIN_DIR, "config", "motor.json")
            ]
            
            config_path = None
            for path in possible_paths:
                if os.path.exists(os.path.dirname(path)):
                    config_path = path
                    break
            
            if config_path is None:
                config_path = possible_paths[0]  # Default to main dir
            
            self.observer.schedule(self.file_handler, path=os.path.dirname(config_path), recursive=False)
            self.observer.start()
            logger.info(f"File watcher started for {config_path}")
        except Exception as e:
            logger.warning(f"Could not start file watcher: {e}")

    def reload_calibration(self):
        global direction_mapper
        if hasattr(config, 'reload'):
            config.reload('motor')
        direction_mapper.load_calibration()
        logger.info("Calibration reloaded from motor.json")

    def load_saved_positions(self):
        """Load saved positions from config manager"""
        az = config.get('motor.current_position.azimuth', INITIAL_AZIMUTH)
        alt = config.get('motor.current_position.altitude', INITIAL_ALTITUDE)
        self.az_motor.set_step(az - self.az_motor.current_position)
        self.alt_motor.set_step(alt - self.alt_motor.current_position)
        logger.info(f"Loaded positions: Az={az:.1f}°, Alt={alt:.1f}°")

    def save_positions(self):
        """Save current positions to config manager"""
        config.set('motor.current_position.azimuth', 
                   round(float(self.az_motor.current_position), 1))
        config.set('motor.current_position.altitude', 
                   round(float(self.alt_motor.current_position), 1))
        logger.debug("Saved motor positions")

    def save_delta_references(self):
        """Save delta references to config manager"""
        updates = {
            'delta_tracking': {
                'az_delta_reference': round(float(self.az_reset_reference), 1) if self.az_reset_reference else None,
                'alt_delta_reference': round(float(self.alt_reset_reference), 1) if self.alt_reset_reference else None,
                'current_az_delta': round(float(self.current_az_delta), 1),
                'current_alt_delta': round(float(self.current_alt_delta), 1)
            }
        }
        
        if self.az_tracker:
            updates['delta_tracking']['az_continuous'] = round(float(self.az_tracker.continuous_value), 1)
            updates['delta_tracking']['az_crossings'] = int(self.az_tracker.crossings)
        
        if hasattr(config, 'update'):
            config.update('motor', updates)
        logger.debug(f"Saved delta references: Az ref={self.az_reset_reference}")

    def update_socket_delta_values(self):
        if hasattr(self, 'socket_server') and self.socket_server:
            self.socket_server.update_delta_values(self.current_az_delta, self.current_alt_delta)
            self.socket_server.update_sensor_status(
                self.sensor_az_connected, 
                self.sensor_alt_connected,
                self.az_reset_reference,
                self.alt_reset_reference
            )

    def restore_delta_angles(self):
        """Restore delta angles and display in 0-360 range with smooth transitions"""
        if not (self.sensor_az_connected and self.sensor_alt_connected):
            return
        
        if self.deltas_restored:
            return
        
        az_raw = None
        alt_raw = None
        
        if self.sensor_az_data and "angle" in self.sensor_az_data:
            angles = self.sensor_az_data["angle"]
            if len(angles) > 2 and angles[2] is not None:
                az_raw = float(angles[2])
        
        if self.sensor_alt_data and "angle" in self.sensor_alt_data:
            angles = self.sensor_alt_data["angle"]
            if len(angles) > 0 and angles[0] is not None:
                alt_raw = float(angles[0])
        
        if az_raw is not None and alt_raw is not None:
            if self.az_reset_reference is not None and self.alt_reset_reference is not None:
                pass
            else:
                # Try to load from config
                self.az_reset_reference = config.get('motor.delta_tracking.az_delta_reference')
                self.alt_reset_reference = config.get('motor.delta_tracking.alt_delta_reference')
            
            if self.az_reset_reference is None:
                self.az_reset_reference = az_raw
                self.alt_reset_reference = alt_raw
                self.current_az_delta = 0.0
                self.current_alt_delta = 0.0
                self.az_tracker.reset_reference(az_raw)
                self.az_display_reference = self.az_tracker.continuous_value
                print(f"🔄 Set initial delta references: Az={az_raw:.1f}°, Alt={alt_raw:.1f}°")
            else:
                self.az_tracker.update(az_raw)
                
                if self.az_display_reference is None:
                    self.az_display_reference = self.az_tracker.continuous_value - self.current_az_delta
                    if self.az_display_reference < 0:
                        self.az_display_reference += 360
                
                self.current_az_delta = self.az_tracker.get_display_value(self.az_display_reference)
                
                az_dir = self.az_tracker.get_direction_symbol(self.az_display_reference)
                
                alt_display, alt_dir = calculate_altitude_delta(alt_raw, self.alt_reset_reference)
                self.current_alt_delta = alt_display
                
                self.az_sensor_change.setText(f"Δ: {az_dir}{self.current_az_delta:.1f}°")
                
                alt_text = f"Δ: {alt_dir}{alt_display:.1f}°" if alt_dir else f"Δ: {alt_display:.1f}°"
                self.alt_sensor_change.setText(alt_text)
                
                print(f"🔄 Restored delta angles: Az={self.current_az_delta:.1f}° (0-360), Alt={alt_display:.1f}°")
                print(f"   Tracker continuous: {self.az_tracker.continuous_value:.1f}°, reference: {self.az_display_reference:.1f}°")
            
            self.deltas_restored = True

    def reset_angles(self):
        """Reset angles to 0° reference"""
        if not (self.sensor_az_connected and self.sensor_alt_connected):
            QMessageBox.warning(self, "Sensors Required", 
                               "Both sensors must be connected to reset angles!")
            return
        
        az_raw = None
        alt_raw = None
        
        if self.sensor_az_data and "angle" in self.sensor_az_data:
            angles = self.sensor_az_data["angle"]
            if len(angles) > 2 and angles[2] is not None:
                az_raw = float(angles[2])
        
        if self.sensor_alt_data and "angle" in self.sensor_alt_data:
            angles = self.sensor_alt_data["angle"]
            if len(angles) > 0 and angles[0] is not None:
                alt_raw = float(angles[0])
        
        if az_raw is not None and alt_raw is not None:
            self.az_tracker.reset_reference(az_raw)
            self.az_display_reference = self.az_tracker.continuous_value
            
            self.az_reset_reference = az_raw
            self.alt_reset_reference = alt_raw
            
            self.current_az_delta = 0.0
            self.current_alt_delta = 0.0
            
            self.az_sensor_change.setText(f"Δ: 0.0°")
            self.alt_sensor_change.setText(f"Δ: 0.0°")
            
            self.save_delta_references()
            self.deltas_restored = True
            
            self.status_label.setText(f"Angles reset: Az Δ=0.0°, Alt Δ=0.0° (Horizon)")
            print(f"🔁 Angles reset - Az reference: {az_raw:.1f}°, Tracker continuous: {self.az_tracker.continuous_value:.1f}°")

    def check_sensor_health(self):
        current_time = time.time()
        
        if self.sensor_az_connected:
            time_since_az = current_time - self.last_az_update
            if time_since_az > 2.0:
                print(f"⚠️ Sensor-Az not updating for {time_since_az:.1f}s")
        
        if self.sensor_alt_connected:
            time_since_alt = current_time - self.last_alt_update
            if time_since_alt > 2.0:
                print(f"⚠️ Sensor-Alt not updating for {time_since_alt:.1f}s")
        
        if self.sensor_az_connected and self.sensor_alt_connected:
            self.update_rate_label.setText(f"Updates: 3.3/sec (300ms)")

    def on_client_connected(self, connected):
        if connected:
            self.status_label.setText("Status: Client Connected")
        else:
            self.status_label.setText("Status: Ready")

    def update_button_states(self, az_pos, alt_pos):
        if hasattr(self, 'halt_btn') and self.halt_btn.text() == "Move":
            return
            
        self.az_left_btn.setEnabled(True)
        self.az_right_btn.setEnabled(True)
        self.alt_up_btn.setEnabled(True)
        self.alt_down_btn.setEnabled(True)

    def _build_ui(self):
        """Build main UI layout with optimized spacing"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(UI_MARGIN, UI_MARGIN, UI_MARGIN, UI_MARGIN)
        main_layout.setSpacing(UI_SPACING)
        main_layout.setAlignment(Qt.AlignTop)

        motor_container = QWidget()
        motor_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        motor_layout = QVBoxLayout(motor_container)
        motor_layout.setContentsMargins(0, 0, 0, 0)
        motor_layout.setSpacing(UI_SPACING)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {self.theme['accent_gold']}; font-size: 9px;")
        motor_layout.addWidget(self.status_label)

        two_col_layout = QHBoxLayout()
        two_col_layout.setSpacing(UI_SPACING)

        az_column = self._build_az_column()
        alt_column = self._build_alt_column()

        az_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        alt_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        two_col_layout.addWidget(az_column, stretch=1)
        two_col_layout.addWidget(alt_column, stretch=1)

        motor_layout.addLayout(two_col_layout, stretch=1)

        sensor_container = self._build_sensor_column()
        sensor_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_layout.addWidget(motor_container, stretch=6)
        main_layout.addWidget(sensor_container, stretch=4)

    def _build_az_column(self):
        """Build azimuth control column"""
        container = QWidget()
        container.setMinimumHeight(220)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(UI_MARGIN, UI_MARGIN, UI_MARGIN, UI_MARGIN)
        layout.setSpacing(UI_SPACING)
        layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        title = QLabel("<b>Azimuth (0°–360°)</b>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 10px;")
        layout.addWidget(title)

        status_row = QHBoxLayout()
        status_row.setSpacing(2)
        self.az_display = QLabel("Current: 0.0°")
        self.az_display.setMinimumWidth(70)
        self.az_display.setStyleSheet("font-size: 9px;")
        
        self.az_sensor_change = QLabel("Δ: —")
        self.az_sensor_change.setMinimumWidth(70)
        self.az_sensor_change.setStyleSheet("font-size: 8px; color: #f39c12; font-weight: bold;")
        
        status_row.addWidget(self.az_display)
        status_row.addWidget(self.az_sensor_change)
        layout.addLayout(status_row)

        self.az_direction = QLabel("Dir: —")
        self.az_direction.setAlignment(Qt.AlignCenter)
        self.az_direction.setStyleSheet(f"color: {self.theme['success_color']}; font-size: 8px; font-weight: bold;")
        layout.addWidget(self.az_direction)

        self.az_slider = QSlider(Qt.Horizontal)
        self.az_slider.setRange(int(AZ_MIN), int(AZ_MAX))
        self.az_slider.setValue(int(INITIAL_AZIMUTH))
        self.az_slider.setMinimumHeight(20)
        self.az_slider.valueChanged.connect(lambda v: self.az_motor.set_step(v - self.az_motor.current_position))
        layout.addWidget(self.az_slider)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.az_left_btn = QPushButton("← Left")
        self.az_left_btn.setMinimumSize(55, 25)
        self.az_right_btn = QPushButton("Right →")
        self.az_right_btn.setMinimumSize(55, 25)
        btn_row.addWidget(self.az_left_btn)
        btn_row.addWidget(self.az_right_btn)
        
        self.az_left_btn.pressed.connect(lambda: self.on_az_manual_start(-1))
        self.az_left_btn.released.connect(self.on_az_manual_stop)
        self.az_right_btn.pressed.connect(lambda: self.on_az_manual_start(1))
        self.az_right_btn.released.connect(self.on_az_manual_stop)
        layout.addLayout(btn_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(4)

        self.calibrate_btn = QPushButton("Cal")
        self.calibrate_btn.setMinimumSize(45, 25)
        self.calibrate_btn.setStyleSheet("font-size: 8px;")
        self.calibrate_btn.clicked.connect(self.open_calibration)
        control_row.addWidget(self.calibrate_btn)
        
        self.sensor_btn = QPushButton("Connect")
        self.sensor_btn.setMinimumSize(65, 25)
        self.sensor_btn.setStyleSheet("font-size: 8px; background-color: #10b981;")
        self.sensor_btn.clicked.connect(self.toggle_sensor)
        control_row.addWidget(self.sensor_btn)
        
        self.reset_angle_btn = QPushButton("Reset")
        self.reset_angle_btn.setMinimumSize(55, 25)
        self.reset_angle_btn.setStyleSheet("font-size: 8px; background-color: #9b59b6;")
        self.reset_angle_btn.clicked.connect(self.reset_angles)
        self.reset_angle_btn.setEnabled(False)
        control_row.addWidget(self.reset_angle_btn)

        layout.addLayout(control_row)
        layout.addStretch()
        return container

    def _build_alt_column(self):
        """Build altitude control column"""
        container = QWidget()
        container.setMinimumHeight(220)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(UI_MARGIN, UI_MARGIN, UI_MARGIN, UI_MARGIN)
        layout.setSpacing(UI_SPACING)
        layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        self.alt_title = QLabel("<b>Altitude (0°–90°)</b>")
        self.alt_title.setAlignment(Qt.AlignCenter)
        self.alt_title.setStyleSheet("font-size: 10px;")
        layout.addWidget(self.alt_title)

        status_row = QHBoxLayout()
        status_row.setSpacing(2)
        self.alt_display = QLabel("Current: 90.0°")
        self.alt_display.setMinimumWidth(70)
        self.alt_display.setStyleSheet("font-size: 9px;")
        
        self.alt_sensor_change = QLabel("Δ: 0.0°")
        self.alt_sensor_change.setMinimumWidth(70)
        self.alt_sensor_change.setStyleSheet("font-size: 8px; color: #f39c12; font-weight: bold;")
        
        status_row.addWidget(self.alt_display)
        status_row.addWidget(self.alt_sensor_change)
        layout.addLayout(status_row)

        self.alt_position = QLabel("Pos: Zenith")
        self.alt_position.setAlignment(Qt.AlignCenter)
        self.alt_position.setStyleSheet(f"color: {self.theme['success_color']}; font-size: 8px; font-weight: bold;")
        layout.addWidget(self.alt_position)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)

        self.alt_slider = QSlider(Qt.Vertical)
        self.alt_slider.setRange(0, 360)
        self.alt_slider.setValue(int(INITIAL_ALTITUDE))
        self.alt_slider.setMinimumHeight(70)
        self.alt_slider.setMaximumHeight(90)
        self.alt_slider.valueChanged.connect(lambda v: self.alt_motor.set_step(v - self.alt_motor.current_position))
        control_layout.addWidget(self.alt_slider)

        self.alt_up_btn = QPushButton("↑ Up")
        self.alt_up_btn.setMinimumSize(55, 25)
        self.alt_up_btn.setStyleSheet("font-size: 9px;")
        self.alt_up_btn.pressed.connect(lambda: self.on_alt_manual_start(1))
        self.alt_up_btn.released.connect(self.on_alt_manual_stop)

        self.alt_down_btn = QPushButton("↓ Down")
        self.alt_down_btn.setMinimumSize(55, 25)
        self.alt_down_btn.setStyleSheet("font-size: 9px;")
        self.alt_down_btn.pressed.connect(lambda: self.on_alt_manual_start(-1))
        self.alt_down_btn.released.connect(self.on_alt_manual_stop)

        self.park_btn = QPushButton("Park")
        self.park_btn.setMinimumSize(50, 25)
        self.park_btn.setObjectName("ParkButton")
        self.park_btn.setStyleSheet("font-size: 8px; background-color: #d35400;")
        self.park_btn.clicked.connect(self.park_all)

        self.halt_btn = QPushButton("Halt")
        self.halt_btn.setMinimumSize(50, 25)
        self.halt_btn.setObjectName("HaltButton")
        self.halt_btn.setStyleSheet("font-size: 8px; background-color: #e74c3c;")
        self.halt_btn.clicked.connect(self.emergency_stop_all)

        button_panel = QVBoxLayout()
        button_panel.setSpacing(3)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(self.alt_up_btn)
        row1.addStretch()
        
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(2)
        speed_layout.addWidget(QLabel("Spd:"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(MANUAL_SPEED_MIN, MANUAL_SPEED_MAX)
        self.speed_spin.setSingleStep(0.5)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setMinimumWidth(50)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setStyleSheet("font-size: 8px;")
        self.speed_spin.valueChanged.connect(lambda v: self.on_speed_change(v))
        speed_layout.addWidget(self.speed_spin)
        speed_layout.addWidget(QLabel("°/s"))
        
        row1.addWidget(speed_widget)
        button_panel.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addWidget(self.alt_down_btn)
        row2.addStretch()
        row2.addWidget(self.park_btn)
        row2.addStretch()
        row2.addWidget(self.halt_btn)
        button_panel.addLayout(row2)

        control_layout.addLayout(button_panel)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        layout.addStretch()
        return container

    def _build_sensor_column(self):
        """Build sensor column - OPTIMIZED to remove empty space"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(UI_MARGIN, UI_MARGIN, UI_MARGIN, UI_MARGIN)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("<b>WT901 Sensors - Raw Angles</b>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 9px;")
        layout.addWidget(title)

        self.sensor_status = QLabel("Disconnected")
        self.sensor_status.setAlignment(Qt.AlignCenter)
        self.sensor_status.setStyleSheet("font-size: 7px;")
        layout.addWidget(self.sensor_status)

        self.update_rate_label = QLabel("Updates: 3.3/sec (300ms)")
        self.update_rate_label.setAlignment(Qt.AlignCenter)
        self.update_rate_label.setStyleSheet("font-size: 7px; color: #94a3b8;")
        layout.addWidget(self.update_rate_label)

        sensor_az_group = QWidget()
        sensor_az_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sensor_az_group.setStyleSheet(f"border: 1px solid {self.theme['steel_blue']}; border-radius: 3px; padding: 2px; margin: 2px 0;")
        sensor_az_layout = QVBoxLayout(sensor_az_group)
        sensor_az_layout.setContentsMargins(4, 4, 4, 4)
        sensor_az_layout.setSpacing(2)
        
        az_header = QHBoxLayout()
        self.sensor_az_name = QLabel("Sensor-Az (WTSDCL) - Angle Z")
        self.sensor_az_name.setAlignment(Qt.AlignCenter)
        self.sensor_az_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
        az_header.addWidget(self.sensor_az_name)
        sensor_az_layout.addLayout(az_header)
        
        az_angle_row = QHBoxLayout()
        az_angle_row.setSpacing(4)
        self.sensor_az_angle_x = QLabel("X: —°")
        self.sensor_az_angle_x.setAlignment(Qt.AlignCenter)
        self.sensor_az_angle_x.setStyleSheet("font-size: 8px;")
        
        self.sensor_az_angle_y = QLabel("Y: —°")
        self.sensor_az_angle_y.setAlignment(Qt.AlignCenter)
        self.sensor_az_angle_y.setStyleSheet("font-size: 8px;")
        
        self.sensor_az_angle_z = QLabel("Z: —°")
        self.sensor_az_angle_z.setAlignment(Qt.AlignCenter)
        self.sensor_az_angle_z.setStyleSheet("font-size: 8px; font-weight: bold; color: #10b981;")
        
        az_angle_row.addWidget(self.sensor_az_angle_x)
        az_angle_row.addWidget(self.sensor_az_angle_y)
        az_angle_row.addWidget(self.sensor_az_angle_z)
        sensor_az_layout.addLayout(az_angle_row)
        
        layout.addWidget(sensor_az_group, stretch=1)

        sensor_alt_group = QWidget()
        sensor_alt_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sensor_alt_group.setStyleSheet(f"border: 1px solid {self.theme['steel_blue']}; border-radius: 3px; padding: 2px; margin: 2px 0;")
        sensor_alt_layout = QVBoxLayout(sensor_alt_group)
        sensor_alt_layout.setContentsMargins(4, 4, 4, 4)
        sensor_alt_layout.setSpacing(2)
        
        alt_header = QHBoxLayout()
        self.sensor_alt_name = QLabel("Sensor-Alt (WT901BLE68) - Angle X")
        self.sensor_alt_name.setAlignment(Qt.AlignCenter)
        self.sensor_alt_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
        alt_header.addWidget(self.sensor_alt_name)
        sensor_alt_layout.addLayout(alt_header)
        
        alt_angle_row = QHBoxLayout()
        alt_angle_row.setSpacing(4)
        self.sensor_alt_angle_x = QLabel("X: —°")
        self.sensor_alt_angle_x.setAlignment(Qt.AlignCenter)
        self.sensor_alt_angle_x.setStyleSheet("font-size: 8px; font-weight: bold; color: #10b981;")
        
        self.sensor_alt_angle_y = QLabel("Y: —°")
        self.sensor_alt_angle_y.setAlignment(Qt.AlignCenter)
        self.sensor_alt_angle_y.setStyleSheet("font-size: 8px;")
        
        self.sensor_alt_angle_z = QLabel("Z: —°")
        self.sensor_alt_angle_z.setAlignment(Qt.AlignCenter)
        self.sensor_alt_angle_z.setStyleSheet("font-size: 8px;")
        
        alt_angle_row.addWidget(self.sensor_alt_angle_x)
        alt_angle_row.addWidget(self.sensor_alt_angle_y)
        alt_angle_row.addWidget(self.sensor_alt_angle_z)
        sensor_alt_layout.addLayout(alt_angle_row)
        
        layout.addWidget(sensor_alt_group, stretch=1)

        self.direction_display = QLabel("Dir: —")
        self.direction_display.setAlignment(Qt.AlignCenter)
        self.direction_display.setStyleSheet(f"color: {self.theme['accent_gold']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.direction_display)

        layout.addStretch()

        return container

    def _apply_theme_styles(self):
        disabled_style = f"""
            QPushButton:disabled {{
                background-color: {self.theme["button_disabled_bg"]};
                color: {self.theme["button_disabled_text"]};
                border: none;
                border-radius: {self.theme["border_radius"]}px;
                padding: 4px;
            }}
        """

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme["window_bg"]};
                color: {self.theme["text_color"]};
                font-size: {self.theme["text_size"]}px;
                font-family: Monospace;
            }}
            QPushButton {{
                background-color: {self.theme["button_bg"]};
                color: {self.theme["button_text"]};
                border: none;
                border-radius: {self.theme["border_radius"]}px;
                padding: 4px;
                font-size: 8px;
            }}
            QPushButton:hover {{
                background-color: {self.theme["button_hover"]};
            }}
            QPushButton#ParkButton {{
                background-color: #d35400;
                font-weight: bold;
            }}
            QPushButton#ParkButton:hover {{
                background-color: #e67e22;
            }}
            QPushButton#HaltButton {{
                background-color: #e74c3c;
                font-weight: bold;
            }}
            QPushButton#HaltButton:hover {{
                background-color: #c0392b;
            }}
            QSlider::groove:horizontal {{ background: {self.theme["slider_bg"]}; height:6px; border-radius:3px; }}
            QSlider::handle:horizontal {{ background: {self.theme["slider_handle"]}; width:14px; border-radius:7px; }}
            QSlider::groove:vertical {{ background: {self.theme["slider_bg"]}; width:6px; border-radius:3px; }}
            QSlider::handle:vertical {{ background: {self.theme["slider_handle"]}; height:14px; border-radius:7px; }}
            QGroupBox {{ color: {self.theme["accent_gold"]}; border:1px solid {self.theme["steel_blue"]}; border-radius:4px; padding:2px; }}
            QDoubleSpinBox {{
                background: {self.theme["row_bg"]};
                color: {self.theme["text_color"]};
                border: 1px solid {self.theme["accent_gold"]};
                border-radius: 3px;
                padding: 1px;
                font-size: 8px;
            }}
            QLabel {{ border: none; }}
            {disabled_style}
        """)

    def open_calibration(self):
        """Open calibration dialog"""
        sensor_az_delta = None
        sensor_alt_delta = None
        
        if self.sensor_az_connected and self.sensor_az_data:
            angles = self.sensor_az_data.get("angle", [0, 0, 0])
            if len(angles) > 2 and angles[2] is not None:
                sensor_az_raw = float(angles[2])
                if self.az_reset_reference is not None:
                    raw_delta = self.az_tracker.get_raw_delta(self.az_display_reference)
                    if raw_delta is not None:
                        sensor_az_delta = float(raw_delta)
                        direction = "↻" if raw_delta > 0 else "↺" if raw_delta < 0 else ""
                        print(f"📐 Azimuth delta for calibration: {raw_delta:+.1f}° {direction}")
                else:
                    sensor_az_delta = sensor_az_raw
        
        if self.sensor_alt_connected and self.sensor_alt_data:
            angles = self.sensor_alt_data.get("angle", [0, 0, 0])
            if len(angles) > 0 and angles[0] is not None:
                sensor_alt_raw = float(angles[0])
                if self.alt_reset_reference is not None:
                    display_angle, display_dir = calculate_altitude_delta(sensor_alt_raw, self.alt_reset_reference)
                    if display_angle is not None:
                        sensor_alt_delta = float(display_angle)
                        print(f"📐 Altitude delta for calibration: {display_angle:.1f}° {display_dir}")
                else:
                    sensor_alt_delta = 0.0
        
        both_connected = self.sensor_az_connected and self.sensor_alt_connected
        
        print(f"🔍 Creating CalibrateDialog with: az_delta={sensor_az_delta}, alt_delta={sensor_alt_delta}")
        
        dlg = CalibrateDialog(
            current_az=float(self.az_motor.current_position),
            current_alt=float(self.alt_motor.current_position),
            theme=self.theme,
            parent=self,
            sensor_az_delta=sensor_az_delta,
            sensor_alt_delta=sensor_alt_delta,
            both_connected=both_connected
        )
        
        if hasattr(dlg, 'calibration_saved'):
            dlg.calibration_saved.connect(self.on_calibration_saved)
        
        if dlg.exec_() == QDialog.Accepted:
            az_val, alt_val = dlg.get_values()
            if az_val is not None and alt_val is not None:
                self.on_calibration_saved(float(az_val), float(alt_val))

    def on_calibration_saved(self, az_val, alt_val):
        with self.az_motor.lock:
            self.az_motor.current_position = float(az_val)
            self.az_motor.target_position = float(az_val)
            self.az_motor.emergency_stop = False

        with self.alt_motor.lock:
            self.alt_motor.current_position = float(alt_val)
            self.alt_motor.target_position = float(alt_val)
            self.alt_motor.emergency_stop = False

        self.update_motor_display(float(az_val), "az")
        self.update_motor_display(float(alt_val), "alt")
        
        direction = get_cardinal_direction(az_val)
        alt_name = get_altitude_name(alt_val)
        
        self.status_label.setText(f"Cal: {direction} ({az_val:.0f}°), {alt_name}")
        self.az_direction.setText(f"Dir: {direction}")
        self.alt_position.setText(f"Pos: {alt_name}")
        
        self.save_positions()
        logger.info(f"Calibration saved: Az={az_val:.1f}°, Alt={alt_val:.1f}°")

    def on_az_manual_start(self, direction):
        if self.halt_btn.text() == "Move":
            return
        step = 10 * direction
        current_time = time.time()
        if current_time - self.last_button_press_time < 0.2:
            return
        self.last_button_press_time = current_time
        self.az_motor.set_step(step)
        if direction > 0:
            self.status_label.setText(f"Manual: Right (↻) - Increasing")
            logger.info(f"Manual AZ right: {step:.1f}°")
        else:
            self.status_label.setText(f"Manual: Left (↺) - Decreasing")
            logger.info(f"Manual AZ left: {step:.1f}°")

    def on_az_manual_stop(self):
        self.status_label.setText("Manual: Stopped")

    def on_alt_manual_start(self, direction):
        if self.halt_btn.text() == "Move":
            return
        step = 5 * direction
        current_time = time.time()
        if current_time - self.last_button_press_time < 0.2:
            return
        self.last_button_press_time = current_time
        
        self.alt_motor.set_step(step)
        
        if direction > 0:
            self.status_label.setText(f"Manual: Alt Up (Δ increases ↻)")
            logger.info(f"Manual ALT up: {step:.1f}°")
        else:
            self.status_label.setText(f"Manual: Alt Down (Δ decreases ↺)")
            logger.info(f"Manual ALT down: {step:.1f}°")
                
    def on_alt_manual_stop(self):
        self.status_label.setText("Manual: Stopped")

    def on_speed_change(self, speed):
        speed_float = float(speed)
        speed_float = max(MANUAL_SPEED_MIN, min(MANUAL_SPEED_MAX, speed_float))
        
        self.az_motor.set_speed(speed_float)
        self.alt_motor.set_speed(speed_float)
        
        self.speed_spin.blockSignals(True)
        self.speed_spin.setValue(speed_float)
        self.speed_spin.blockSignals(False)
        
        logger.debug(f"Speed set to {speed_float:.1f}°/s")

    def toggle_sensor(self):
        if self.sensor_btn.text() == "Connect":
            if hasattr(self, 'socket_server') and self.socket_server:
                self.socket_server.start_server()
            
            self.sensor.start()
            self.sensor_btn.setText("Disconnect")
            self.sensor_btn.setStyleSheet("font-size: 8px; background-color: #ef4444;")
            self.sensor_status.setText("Connecting...")
            self.reset_angle_btn.setEnabled(True)
            self.deltas_restored = False
            logger.info("Sensor connection started")
        else:
            self.sensor.stop()
            self.sensor_btn.setText("Connect")
            self.sensor_btn.setStyleSheet("font-size: 8px; background-color: #10b981;")
            self.sensor_status.setText("Disconnected")
            self.reset_angle_btn.setEnabled(False)
            
            self.sensor_az_name.setText("Sensor-Az (WTSDCL) - Angle Z")
            self.sensor_az_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
            self.sensor_az_angle_x.setText("X: —°")
            self.sensor_az_angle_y.setText("Y: —°")
            self.sensor_az_angle_z.setText("Z: —°")
            
            self.sensor_alt_name.setText("Sensor-Alt (WT901BLE68) - Angle X")
            self.sensor_alt_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
            self.sensor_alt_angle_x.setText("X: —°")
            self.sensor_alt_angle_y.setText("Y: —°")
            self.sensor_alt_angle_z.setText("Z: —°")
            
            self.az_sensor_change.setText("Δ: —")
            self.alt_sensor_change.setText("Δ: —")
            
            self.direction_display.setText("Dir: —")
            self.az_direction.setText("Dir: —")
            self.alt_position.setText("Pos: —")
            self.update_rate_label.setText("Updates: —/—")
            
            self.save_delta_references()
            
            self.sensor_az_connected = False
            self.sensor_alt_connected = False
            self.az_motor.set_sensor_status(False)
            self.alt_motor.set_sensor_status(False)
            
            self.deltas_restored = False
            logger.info("Sensor disconnected")

    def on_sensor_status(self, sensor_index, connected, sensor_type):
        if sensor_index == 0:
            self.sensor_az_connected = connected
            if connected:
                self.sensor_az_name.setStyleSheet(f"color: {self.theme['success_color']}; font-size: 8px; font-weight: bold; border: none;")
                self.sensor_az_name.setText("Sensor-Az (WTSDCL) - Connected (Z)")
                self.sensor_status.setText("AZ Connected - Connecting ALT...")
                logger.info("AZ sensor connected")
            else:
                self.sensor_az_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
                self.sensor_az_name.setText("Sensor-Az (WTSDCL)")
                self.sensor_az_angle_x.setText("X: —°")
                self.sensor_az_angle_y.setText("Y: —°")
                self.sensor_az_angle_z.setText("Z: —°")
                self.az_sensor_change.setText("Δ: —")
                self.deltas_restored = False
                logger.warning("AZ sensor disconnected")
        elif sensor_index == 1:
            self.sensor_alt_connected = connected
            if connected:
                self.sensor_alt_name.setStyleSheet(f"color: {self.theme['success_color']}; font-size: 8px; font-weight: bold; border: none;")
                self.sensor_alt_name.setText("Sensor-Alt (WT901BLE68) - Connected (X)")
                self.sensor_status.setText("Both Sensors Connected")
                
                self.alt_slider.setRange(0, 360)
                self.reset_angle_btn.setEnabled(True)
                logger.info("ALT sensor connected")
                
            else:
                self.sensor_alt_name.setStyleSheet(f"color: {self.theme['text_color']}; font-size: 8px; font-weight: bold; border: none;")
                self.sensor_alt_name.setText("Sensor-Alt (WT901BLE68)")
                self.sensor_alt_angle_x.setText("X: —°")
                self.sensor_alt_angle_y.setText("Y: —°")
                self.sensor_alt_angle_z.setText("Z: —°")
                self.alt_sensor_change.setText("Δ: —")
                
                self.alt_slider.setRange(0, 360)
                
                if not self.sensor_az_connected:
                    self.reset_angle_btn.setEnabled(False)
                
                self.deltas_restored = False
                logger.warning("ALT sensor disconnected")
        
        if self.sensor_az_connected and self.sensor_alt_connected:
            self.sensor_status.setText("Connected (2/2)")
            logger.info("Both sensors connected")
        elif self.sensor_az_connected:
            self.sensor_status.setText("AZ Connected - Connecting ALT...")
        elif self.sensor_alt_connected:
            self.sensor_status.setText("ALT Connected - Connecting AZ...")
        else:
            self.sensor_status.setText("Disconnected")
            
        self.az_motor.set_sensor_status(self.sensor_az_connected)
        self.alt_motor.set_sensor_status(self.sensor_alt_connected)
        
        self.update_button_states(
            self.az_motor.current_position,
            self.alt_motor.current_position
        )

    def on_sensor_data(self, sensor_index, data):
        """Handle incoming sensor data"""
        try:
            if not data or "angle" not in data:
                return
                
            angles = data["angle"]
            angles = [float(a) if a is not None else 0.0 for a in angles]
            current_time = time.time()
            
            if sensor_index == 0:
                self.sensor_az_data = data
                self.last_az_update = current_time
                
                self.sensor_az_angle_x.setText(f"X: {format_angle_with_sign(angles[0])}")
                self.sensor_az_angle_y.setText(f"Y: {format_angle_with_sign(angles[1])}")
                self.sensor_az_angle_z.setText(f"Z: {format_angle_with_sign(angles[2])}")
                
                self.az_motor.set_sensor_status(True, angles)
                motor_az = self.az_motor.current_position
                
                if self.az_reset_reference is not None:
                    continuous = self.az_tracker.update(angles[2])
                    
                    if self.az_display_reference is None:
                        self.az_display_reference = continuous - self.current_az_delta
                        if self.az_display_reference < 0:
                            self.az_display_reference += 360
                    
                    display_az = self.az_tracker.get_display_value(self.az_display_reference)
                    direction_symbol = self.az_tracker.get_direction_symbol(self.az_display_reference)
                    
                    self.current_az_delta = display_az
                    delta_text = f"Δ: {direction_symbol}{display_az:.1f}°"
                    self.az_sensor_change.setText(delta_text)
                    
                    raw_delta = self.az_tracker.get_raw_delta(self.az_display_reference)
                    
                    calibrated_dir, diff = direction_mapper.get_direction_from_delta(raw_delta)
                    if calibrated_dir:
                        if diff < 2:
                            accuracy = "✓"
                        elif diff < 5:
                            accuracy = "~"
                        else:
                            accuracy = "≈"
                        self.direction_display.setText(f"Dir: {calibrated_dir} {accuracy} ({diff:.1f}°)")
                        self.az_direction.setText(f"Dir: {calibrated_dir}")
                    else:
                        self.direction_display.setText(f"Dir: {get_full_direction(motor_az)}")
                        self.az_direction.setText(f"Dir: {get_cardinal_direction(motor_az)}")
                else:
                    self.az_sensor_change.setText("Δ: —")
                    self.direction_display.setText(f"Dir: {get_full_direction(motor_az)}")
                    self.az_direction.setText(f"Dir: {get_cardinal_direction(motor_az)}")
                
                if self.sensor_az_connected and self.sensor_alt_connected and not self.deltas_restored:
                    self.restore_delta_angles()
                
            elif sensor_index == 1:
                self.sensor_alt_data = data
                self.last_alt_update = current_time
                
                self.sensor_alt_angle_x.setText(f"X: {format_angle_with_sign(angles[0])}")
                self.sensor_alt_angle_y.setText(f"Y: {format_angle_with_sign(angles[1])}")
                self.sensor_alt_angle_z.setText(f"Z: {format_angle_with_sign(angles[2])}")
                
                self.alt_motor.set_sensor_status(True, angles)
                motor_alt = self.alt_motor.current_position
                
                if self.alt_reset_reference is not None:
                    display_angle, display_dir = calculate_altitude_delta(angles[0], self.alt_reset_reference)
                    if display_angle is not None:
                        self.current_alt_delta = display_angle
                        delta_text = f"Δ: {display_dir}{display_angle:.1f}°"
                        self.alt_sensor_change.setText(delta_text)
                    else:
                        self.alt_sensor_change.setText("Δ: —")
                else:
                    self.alt_sensor_change.setText("Δ: —")
                
                if is_altitude_within_limits(angles[0], 
                                              direction_mapper.horizon_angle, 
                                              direction_mapper.zenith_angle):
                    self.sensor_alt_angle_x.setStyleSheet("font-size: 8px; font-weight: bold; color: #10b981;")
                else:
                    self.sensor_alt_angle_x.setStyleSheet("font-size: 8px; font-weight: bold; color: #ef4444;")
                
                calibrated_alt, diff = direction_mapper.get_altitude_from_sensor(angles[0])
                if calibrated_alt:
                    if diff < 2:
                        accuracy = "✓"
                    elif diff < 5:
                        accuracy = "~"
                    else:
                        accuracy = "≈"
                    self.alt_position.setText(f"Pos: {calibrated_alt} {accuracy} ({diff:.1f}°)")
                else:
                    self.alt_position.setText(f"Pos: {get_altitude_name(motor_alt)}")
                
                self.update_button_states(
                    self.az_motor.current_position,
                    motor_alt
                )
                
                if self.sensor_az_connected and self.sensor_alt_connected and not self.deltas_restored:
                    self.restore_delta_angles()
                
        except Exception as e:
            logger.error(f"Error updating sensor display: {e}")

    def on_sensor_error(self, msg):
        print(f"DEBUG - Sensor error: {msg}")
        if "Connecting to Sensor-Az" in msg:
            self.sensor_az_name.setText("Sensor-Az (WTSDCL) - Connecting...")
        elif "Connecting to Sensor-Alt" in msg:
            self.sensor_alt_name.setText("Sensor-Alt (WT901BLE68) - Connecting...")
        elif "✅ Sensor-Az connected" in msg:
            self.sensor_az_name.setText("Sensor-Az (WTSDCL) - Connected")
        elif "✅ Sensor-Alt connected" in msg:
            self.sensor_alt_name.setText("Sensor-Alt (WT901BLE68) - Connected")

    def park_all(self):
        if not (self.sensor_az_connected or self.sensor_alt_connected):
            QMessageBox.warning(self, "Sensor Required", 
                               "Cannot park without sensor connection!")
            return

        self.status_label.setText("Parking to North & Zenith...")
        self.status_label.setText(f"Parked at North (0°) & Zenith (90°)")

    def emergency_stop_all(self):
        """Emergency stop all motors"""
        self.az_motor.trigger_emergency_stop()
        self.alt_motor.trigger_emergency_stop()
        self.az_display.setText("HALTED")
        self.alt_display.setText("HALTED")
        self.status_label.setText("🚨 EMERGENCY HALT - Press 'Move' to unlock")
        
        self.halt_btn.setText("Move")
        self.halt_btn.setStyleSheet("background-color: #10b981;")
        self.halt_btn.clicked.disconnect()
        self.halt_btn.clicked.connect(self.unlock_motors)
        
        self.az_left_btn.setEnabled(False)
        self.az_right_btn.setEnabled(False)
        self.alt_up_btn.setEnabled(False)
        self.alt_down_btn.setEnabled(False)
        self.az_slider.setEnabled(False)
        self.alt_slider.setEnabled(False)
        self.speed_spin.setEnabled(False)
        
        logger.warning("EMERGENCY STOP activated")

    def unlock_motors(self):
        self.az_motor.clear_emergency_stop()
        self.alt_motor.clear_emergency_stop()
        
        self.halt_btn.setText("Halt")
        self.halt_btn.setStyleSheet("background-color: #e74c3c;")
        self.halt_btn.clicked.disconnect()
        self.halt_btn.clicked.connect(self.emergency_stop_all)
        
        self.update_button_states(
            self.az_motor.current_position,
            self.alt_motor.current_position
        )
        self.az_slider.setEnabled(True)
        self.alt_slider.setEnabled(True)
        self.speed_spin.setEnabled(True)
        
        self.status_label.setText("Motors unlocked - Ready")
        logger.info("Motors unlocked")

    def update_motor_display(self, value, axis):
        if axis == "az":
            self.az_display.setText(f"Current: {value:.0f}°")
            self.az_slider.setValue(int(round(value)))
        else:
            self.alt_display.setText(f"Current: {value:.0f}°")
            self.alt_slider.setValue(int(round(value % 360.0)))
            
            if self.sensor_alt_connected:
                sensor_alt = motor_to_sensor_alt(
                    value,
                    direction_mapper.horizon_angle,
                    direction_mapper.zenith_angle
                )
                dist_to_horizon = min(abs(sensor_alt - direction_mapper.horizon_angle),
                                      360 - abs(sensor_alt - direction_mapper.horizon_angle))
                dist_to_zenith = min(abs(sensor_alt - direction_mapper.zenith_angle),
                                     360 - abs(sensor_alt - direction_mapper.zenith_angle))
                
                if dist_to_horizon < 1.0:
                    self.alt_position.setText("Pos: Horizon")
                elif dist_to_zenith < 1.0:
                    self.alt_position.setText("Pos: Zenith")
                else:
                    self.alt_position.setText(f"Pos: {value:.0f}°")
            else:
                self.alt_position.setText(f"Pos: {get_altitude_name(value)}")

        self.update_button_states(
            self.az_motor.current_position,
            self.alt_motor.current_position
        )    

    def show_error(self, msg):
        logger.error(f"Motor error: {msg}")
        QMessageBox.critical(self, "Motor Error", msg[:60])

    def update_theme(self, theme_input):
        """
        Update widget theme with new colors dictionary.
        This is called from the parent tab (cam_control.py) when theme changes.
        """
        if isinstance(theme_input, dict):
            self.theme = theme_input
            print(f"🎨 Motor widget updating theme with {len(self.theme)} colors")
        else:
            self.theme = get_theme_colors()
            print(f"⚠️ Motor widget received non-dict theme, using fallback")
        
        self._ensure_theme_complete()
        self._apply_theme_styles()

    def closeEvent(self, event):
        logger.info("Shutting down MotorControlWidget")
        
        self.save_positions()
        self.save_delta_references()
        
        if hasattr(self, 'socket_server') and self.socket_server:
            self.socket_server.stop()
        
        self.az_motor.stop()
        self.alt_motor.stop()
        self.sensor.stop()
        self.health_timer.stop()
        self.delta_update_timer.stop()
        
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        
        if hasattr(self, 'safety'):
            self.safety.stop()
        
        # Clean up GPIO on exit
        if GPIO_AVAILABLE:
            try:
                from gpiozero import Device
                Device.close_all()
                logger.info("GPIO devices cleaned up on exit")
            except:
                pass
        
        event.accept()


# -----------------------------------------------------------------------------
# Standalone Test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    # Clean up GPIO before starting
    cleanup_gpio_pins()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    test_theme = get_theme_colors()
    print(f"✅ Loaded theme colors: {list(test_theme.keys())}")
    
    window = MotorControlWidget(theme=test_theme)
    window.show()
    
    sys.exit(app.exec_())