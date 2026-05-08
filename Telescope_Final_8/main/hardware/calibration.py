#!/usr/bin/env python3
"""
Calibration Dialog for Motor Control System - SIMPLIFIED
Only calibrates current motor position to target angle
Uses single global motor.json in project root

ADDED: GoTo Tab for PID-controlled motion to target coordinates
REDESIGNED: Clean grid layout with fixed 600x500 window size
"""

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QLabel,
    QPushButton, QHBoxLayout, QVBoxLayout, QGroupBox, QMessageBox,
    QGridLayout, QFrame, QWidget, QTabWidget, QProgressBar, 
    QSlider, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QBrush
import json
import os
import time
import math
import socket
import threading
from collections import deque

# Axis limits
ALT_MIN = -2.0
ALT_MAX = 92.0
AZ_MIN = 0.0
AZ_MAX = 360.0

# Socket configuration
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 65432

# --------------------------
# Global Configuration Path - SINGLE FILE
# --------------------------
MAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(MAIN_DIR, "motor.json")


def get_contrasting_color(bg_color):
    """Return black or white based on background luminance"""
    r, g, b = 0, 0, 0

    if isinstance(bg_color, str):
        bg_color = bg_color.strip()
        if bg_color.startswith('rgb'):
            import re
            numbers = re.findall(r'\d+', bg_color)
            if len(numbers) >= 3:
                r = int(numbers[0])
                g = int(numbers[1])
                b = int(numbers[2])
        elif bg_color.startswith('#'):
            bg_color = bg_color.lstrip('#')
            if len(bg_color) >= 6:
                r = int(bg_color[0:2], 16)
                g = int(bg_color[2:4], 16)
                b = int(bg_color[4:6], 16)
        else:
            return "#FFFFFF"

    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return "#000000" if luminance > 0.5 else "#FFFFFF"


# ============================================================================
# PID Controller Class
# ============================================================================

class PIDController:
    """Discrete PID Controller with anti-windup and derivative filtering"""
    
    def __init__(self, Kp, Ki, Kd, setpoint=0, sample_time=0.05, output_limits=(-1.0, 1.0), name="PID"):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.sample_time = sample_time
        self.output_limits = output_limits
        self.name = name
        
        # Controller state
        self.last_error = 0
        self.integral = 0
        self.last_output = 0
        self.last_time = time.time()
        
        # Derivative filter
        self.deriv_filter = 0.2
        self.last_derivative = 0
        
        # Performance tracking
        self.settling_time = 0
        self.overshoot = 0
        self.max_error = 0
        self.converged = False
        
    def update(self, feedback, current_time=None):
        if current_time is None:
            current_time = time.time()
            
        dt = current_time - self.last_time
        if dt < self.sample_time * 0.5:
            return self.last_output
        
        error = self.setpoint - feedback
        
        # Track max error
        if abs(error) > self.max_error:
            self.max_error = abs(error)
        
        # Check convergence
        if abs(error) < 0.1 and not self.converged:
            self.converged = True
            self.settling_time = current_time - self.last_time + 0.05
        
        # PID terms
        P = self.Kp * error
        
        self.integral += error * dt
        I = self.Ki * self.integral
        
        if dt > 0:
            raw_derivative = (error - self.last_error) / dt
            derivative = self.deriv_filter * raw_derivative + (1 - self.deriv_filter) * self.last_derivative
            self.last_derivative = derivative
        else:
            derivative = 0
        D = self.Kd * derivative
        
        # Calculate output
        output = P + I + D
        
        # Apply limits with anti-windup
        if output > self.output_limits[1]:
            output = self.output_limits[1]
            if self.Ki != 0:
                self.integral = (output - P - D) / self.Ki
        elif output < self.output_limits[0]:
            output = self.output_limits[0]
            if self.Ki != 0:
                self.integral = (output - P - D) / self.Ki
        
        # Track overshoot
        if error * self.last_error < 0:
            if abs(error) > abs(self.overshoot):
                self.overshoot = abs(error)
        
        self.last_error = error
        self.last_output = output
        self.last_time = current_time
        
        return output
    
    def set_setpoint(self, setpoint):
        self.setpoint = setpoint
        self.integral = 0
        self.converged = False
        self.max_error = 0
        self.overshoot = 0
        
    def reset(self):
        self.last_error = 0
        self.integral = 0
        self.last_output = 0
        self.last_derivative = 0
        self.converged = False
        self.max_error = 0
        self.overshoot = 0


# ============================================================================
# GoTo Control Thread
# ============================================================================

class GoToControlThread(QThread):
    """Background thread for GoTo motion control"""
    
    position_updated = pyqtSignal(float, float)
    pid_status = pyqtSignal(float, float, float, str)
    motion_status = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int)
    motion_complete = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.moving = False
        self.target_az = 0.0
        self.target_alt = 90.0
        self.current_az = 0.0
        self.current_alt = 90.0
        self.speed_profile = [1.0, 1.25, 1.5]
        self.current_speed = 1.0
        self.acceleration = 0.5
        
        # PID controllers
        self.pid_az = PIDController(Kp=2.5, Ki=0.1, Kd=0.8, name="Azimuth")
        self.pid_alt = PIDController(Kp=3.0, Ki=0.2, Kd=0.5, name="Altitude")
        
        # Socket connection
        self.socket = None
        self.socket_lock = threading.Lock()
        
        # Motion planning
        self.az_direction = 0
        self.az_distance = 0
        self.alt_direction = 0
        self.alt_distance = 0
        self.az_dir_name = ""
        self.alt_dir_name = ""
        
        # Timing
        self.last_update = time.time()
        self.update_interval = 0.05
        
        # Progress tracking
        self.start_az = 0
        self.start_alt = 0
        self.total_az_distance = 0
        self.total_alt_distance = 0
        
        self._connect_socket()
        
    def _connect_socket(self):
        try:
            with self.socket_lock:
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(0.5)
                self.socket.connect((SOCKET_HOST, SOCKET_PORT))
        except:
            self.socket = None
    
    def _send_motor_command(self, az, alt, speed):
        if not self.socket:
            return False
        try:
            with self.socket_lock:
                command = f"{az:.1f},{alt:.1f},{speed:.1f}\n"
                self.socket.send(command.encode())
            return True
        except:
            self.socket = None
            return False
    
    def _calculate_direction(self, current, target, axis_type):
        if axis_type == 'az':
            cw = (target - current) % 360
            ccw = (current - target) % 360
            
            if cw <= ccw:
                return cw, 1, "↻ CW"
            else:
                return ccw, -1, "↺ CCW"
        else:
            distance = target - current
            if distance > 0:
                return abs(distance), 1, "↑ Up"
            else:
                return abs(distance), -1, "↓ Down"
    
    def set_target(self, target_az, target_alt):
        self.target_az = target_az % 360
        self.target_alt = max(ALT_MIN, min(ALT_MAX, target_alt))
        
        # Calculate directions
        self.az_distance, self.az_direction, self.az_dir_name = self._calculate_direction(
            self.current_az, self.target_az, 'az'
        )
        self.alt_distance, self.alt_direction, self.alt_dir_name = self._calculate_direction(
            self.current_alt, self.target_alt, 'alt'
        )
        
        self.start_az = self.current_az
        self.start_alt = self.current_alt
        self.total_az_distance = self.az_distance
        self.total_alt_distance = self.alt_distance
        
        self.pid_az.set_setpoint(self.target_az)
        self.pid_alt.set_setpoint(self.target_alt)
        
        return f"AZ:{self.az_dir_name}({self.az_distance:.0f}°) ALT:{self.alt_dir_name}({self.alt_distance:.0f}°)"
    
    def start_motion(self):
        if self.az_distance < 0.1 and self.alt_distance < 0.1:
            self.motion_complete.emit(True, "Already at target")
            return
        
        self.moving = True
        self.running = True
        self.current_speed = self.speed_profile[0]
        self.last_update = time.time()
        
        self.pid_az.reset()
        self.pid_alt.reset()
        
        if not self.isRunning():
            self.start()
    
    def stop_motion(self):
        self.moving = False
        
    def run(self):
        last_speed_update = time.time()
        
        while self.running and self.moving:
            current_time = time.time()
            dt = current_time - self.last_update
            
            if dt >= self.update_interval:
                # Update PID
                az_output = self.pid_az.update(self.current_az, current_time)
                alt_output = self.pid_alt.update(self.current_alt, current_time)
                
                # Update speed profile
                if current_time - last_speed_update >= 0.5:
                    if abs(self.pid_az.last_error) > 10 or abs(self.pid_alt.last_error) > 10:
                        self.current_speed = min(self.speed_profile[1], self.current_speed + self.acceleration * 0.5)
                    elif abs(self.pid_az.last_error) < 2 and abs(self.pid_alt.last_error) < 2:
                        self.current_speed = self.speed_profile[0]
                    else:
                        self.current_speed = min(self.speed_profile[2], self.current_speed + self.acceleration * 0.5)
                    last_speed_update = current_time
                
                # Update position
                self.current_az = (self.current_az + az_output * self.current_speed * dt * 10) % 360
                self.current_alt = max(ALT_MIN, min(ALT_MAX, 
                    self.current_alt + alt_output * self.current_speed * dt * 10))
                
                self.position_updated.emit(self.current_az, self.current_alt)
                self.pid_status.emit(
                    self.pid_az.Kp * self.pid_az.last_error,
                    self.pid_az.Ki * self.pid_az.integral,
                    self.pid_az.Kd * self.pid_az.last_derivative,
                    "AZ"
                )
                
                # Calculate progress
                remaining_az = abs(self.target_az - self.current_az)
                remaining_az = min(remaining_az, 360 - remaining_az)
                remaining_alt = abs(self.target_alt - self.current_alt)
                
                if self.total_az_distance > 0:
                    az_progress = 100 * (1 - remaining_az / self.total_az_distance)
                else:
                    az_progress = 100
                    
                if self.total_alt_distance > 0:
                    alt_progress = 100 * (1 - remaining_alt / self.total_alt_distance)
                else:
                    alt_progress = 100
                
                progress = int((az_progress + alt_progress) / 2)
                self.progress_updated.emit(progress)
                
                # Check completion
                if remaining_az < 0.1 and remaining_alt < 0.1:
                    self.moving = False
                    self.motion_complete.emit(True, "Motion complete")
                
                self._send_motor_command(self.current_az, self.current_alt, self.current_speed)
                self.last_update = current_time
            
            time.sleep(0.01)
        
        self.running = False
    
    def stop(self):
        self.running = False
        self.moving = False
        if self.socket:
            try:
                with self.socket_lock:
                    self.socket.close()
            except:
                pass
        self.wait()


# ============================================================================
# Simple Direction Indicator
# ============================================================================

class DirectionIndicator(QWidget):
    """Compact visual indicator for motion direction"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.az_direction = 0
        self.alt_direction = 0
        self.az_distance = 0
        self.alt_distance = 0
        self.target_az = 0
        self.target_alt = 90
        self.current_az = 0
        self.current_alt = 90
        
    def set_directions(self, az_dir, alt_dir, az_dist, alt_dist):
        self.az_direction = az_dir
        self.alt_direction = alt_dir
        self.az_distance = az_dist
        self.alt_distance = alt_dist
        self.update()
        
    def set_positions(self, current_az, current_alt, target_az, target_alt):
        self.current_az = current_az
        self.current_alt = current_alt
        self.target_az = target_az
        self.target_alt = target_alt
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = 40
        
        # Draw compass circle
        painter.setPen(QPen(QColor(100, 150, 200), 1))
        painter.setBrush(QBrush(QColor(30, 40, 60, 100)))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Cardinal points
        painter.setPen(QPen(QColor(200, 220, 255), 1))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(center_x - 3, center_y - radius - 2, "N")
        painter.drawText(center_x - 3, center_y + radius + 10, "S")
        painter.drawText(center_x + radius + 5, center_y + 3, "E")
        painter.drawText(center_x - radius - 12, center_y + 3, "W")
        
        # Current position
        if self.current_az is not None:
            az_rad = math.radians(90 - self.current_az)
            pos_x = center_x + radius * 0.6 * math.cos(az_rad)
            pos_y = center_y - radius * 0.6 * math.sin(az_rad)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 255, 0)))
            painter.drawEllipse(int(pos_x) - 4, int(pos_y) - 4, 8, 8)
        
        # Target position
        if self.target_az is not None:
            az_rad = math.radians(90 - self.target_az)
            pos_x = center_x + radius * 0.8 * math.cos(az_rad)
            pos_y = center_y - radius * 0.8 * math.sin(az_rad)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 200, 0)))
            painter.drawEllipse(int(pos_x) - 4, int(pos_y) - 4, 8, 8)


# ============================================================================
# GoTo Tab - Grid Layout
# ============================================================================

class GoToTab(QWidget):
    """GoTo control tab with clean grid layout - 600x500 optimized"""
    
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.goto_thread = GoToControlThread()
        self.current_az = 0.0
        self.current_alt = 90.0
        self.target_az = 0.0
        self.target_alt = 90.0
        self.moving = False
        
        self.setup_ui()
        self.connect_signals()
        self.load_current_position()
        
    def setup_ui(self):
        # Main layout with proper padding
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        
        # ===== ROW 1: Target Coordinates =====
        target_group = QGroupBox("Target Coordinates")
        target_group.setFixedHeight(70)
        target_layout = QGridLayout(target_group)
        target_layout.setContentsMargins(6, 10, 6, 6)
        target_layout.setVerticalSpacing(4)
        target_layout.setHorizontalSpacing(8)
        
        # Azimuth row
        target_layout.addWidget(QLabel("Azimuth:"), 0, 0)
        self.az_spin = QDoubleSpinBox()
        self.az_spin.setRange(AZ_MIN, AZ_MAX)
        self.az_spin.setValue(self.target_az)
        self.az_spin.setSuffix("°")
        self.az_spin.setDecimals(1)
        self.az_spin.setFixedWidth(100)
        self.az_spin.valueChanged.connect(self._on_target_changed)
        target_layout.addWidget(self.az_spin, 0, 1)
        
        # Altitude row
        target_layout.addWidget(QLabel("Altitude:"), 1, 0)
        self.alt_spin = QDoubleSpinBox()
        self.alt_spin.setRange(ALT_MIN, ALT_MAX)
        self.alt_spin.setValue(self.target_alt)
        self.alt_spin.setSuffix("°")
        self.alt_spin.setDecimals(1)
        self.alt_spin.setFixedWidth(100)
        self.alt_spin.valueChanged.connect(self._on_target_changed)
        target_layout.addWidget(self.alt_spin, 1, 1)
        
        # Use current button
        self.use_current_btn = QPushButton("Use Current")
        self.use_current_btn.setFixedSize(90, 28)
        self.use_current_btn.clicked.connect(self._use_current_position)
        target_layout.addWidget(self.use_current_btn, 0, 2, 2, 1, Qt.AlignRight)
        
        main_layout.addWidget(target_group)
        
        # ===== ROW 2: Direction Indicator and Motion Info (2 columns) =====
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        # Column 1: Direction Indicator
        dir_widget = QWidget()
        dir_widget.setFixedWidth(120)
        dir_layout = QVBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(2)
        
        dir_label = QLabel("Direction")
        dir_label.setAlignment(Qt.AlignCenter)
        dir_label.setStyleSheet("font-weight: bold;")
        dir_layout.addWidget(dir_label)
        
        self.direction_indicator = DirectionIndicator()
        dir_layout.addWidget(self.direction_indicator, alignment=Qt.AlignCenter)
        
        info_layout.addWidget(dir_widget)
        
        # Column 2: Motion Information Grid
        motion_group = QGroupBox("Motion Info")
        motion_group.setFixedHeight(120)
        motion_layout = QGridLayout(motion_group)
        motion_layout.setContentsMargins(6, 8, 6, 6)
        motion_layout.setVerticalSpacing(4)
        motion_layout.setHorizontalSpacing(8)
        
        # Current position
        motion_layout.addWidget(QLabel("Current:"), 0, 0)
        self.current_pos_label = QLabel("0.0°, 90.0°")
        self.current_pos_label.setStyleSheet("font-weight: bold;")
        motion_layout.addWidget(self.current_pos_label, 0, 1)
        
        # Target position
        motion_layout.addWidget(QLabel("Target:"), 1, 0)
        self.target_pos_label = QLabel("0.0°, 90.0°")
        self.target_pos_label.setStyleSheet("color: #fca311; font-weight: bold;")
        motion_layout.addWidget(self.target_pos_label, 1, 1)
        
        # Direction
        motion_layout.addWidget(QLabel("Dir:"), 2, 0)
        self.direction_label = QLabel("—")
        self.direction_label.setStyleSheet("color: #fca311;")
        motion_layout.addWidget(self.direction_label, 2, 1)
        
        # Distance
        motion_layout.addWidget(QLabel("Dist:"), 3, 0)
        self.distance_label = QLabel("—")
        motion_layout.addWidget(self.distance_label, 3, 1)
        
        info_layout.addWidget(motion_group)
        main_layout.addLayout(info_layout)
        
        # ===== ROW 3: Speed Profile and PID Tuning (2 columns) =====
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(8)
        
        # Column 1: Speed Profile
        speed_group = QGroupBox("Speed Profile")
        speed_group.setFixedWidth(200)
        speed_layout = QGridLayout(speed_group)
        speed_layout.setContentsMargins(6, 8, 6, 6)
        speed_layout.setVerticalSpacing(4)
        speed_layout.setHorizontalSpacing(6)
        
        # Start speed
        speed_layout.addWidget(QLabel("Start:"), 0, 0)
        self.start_speed_spin = QDoubleSpinBox()
        self.start_speed_spin.setRange(0.5, 2.0)
        self.start_speed_spin.setValue(1.0)
        self.start_speed_spin.setSingleStep(0.1)
        self.start_speed_spin.setFixedWidth(70)
        self.start_speed_spin.valueChanged.connect(self._update_speed_profile)
        speed_layout.addWidget(self.start_speed_spin, 0, 1)
        speed_layout.addWidget(QLabel("x"), 0, 2)
        
        # Cruise speed
        speed_layout.addWidget(QLabel("Cruise:"), 1, 0)
        self.cruise_speed_spin = QDoubleSpinBox()
        self.cruise_speed_spin.setRange(0.5, 2.0)
        self.cruise_speed_spin.setValue(1.25)
        self.cruise_speed_spin.setSingleStep(0.1)
        self.cruise_speed_spin.setFixedWidth(70)
        self.cruise_speed_spin.valueChanged.connect(self._update_speed_profile)
        speed_layout.addWidget(self.cruise_speed_spin, 1, 1)
        speed_layout.addWidget(QLabel("x"), 1, 2)
        
        # Max speed
        speed_layout.addWidget(QLabel("Max:"), 2, 0)
        self.max_speed_spin = QDoubleSpinBox()
        self.max_speed_spin.setRange(0.5, 2.0)
        self.max_speed_spin.setValue(1.5)
        self.max_speed_spin.setSingleStep(0.1)
        self.max_speed_spin.setFixedWidth(70)
        self.max_speed_spin.valueChanged.connect(self._update_speed_profile)
        speed_layout.addWidget(self.max_speed_spin, 2, 1)
        speed_layout.addWidget(QLabel("x"), 2, 2)
        
        # Acceleration
        speed_layout.addWidget(QLabel("Accel:"), 3, 0)
        self.acceleration_spin = QDoubleSpinBox()
        self.acceleration_spin.setRange(0.1, 2.0)
        self.acceleration_spin.setValue(0.5)
        self.acceleration_spin.setSingleStep(0.1)
        self.acceleration_spin.setSuffix("/s")
        self.acceleration_spin.setFixedWidth(70)
        self.acceleration_spin.valueChanged.connect(self._update_speed_profile)
        speed_layout.addWidget(self.acceleration_spin, 3, 1)
        
        settings_layout.addWidget(speed_group)
        
        # Column 2: PID Tuning
        pid_group = QGroupBox("PID Tuning")
        pid_layout = QHBoxLayout(pid_group)
        pid_layout.setContentsMargins(6, 8, 6, 6)
        pid_layout.setSpacing(8)
        
        # Azimuth PID
        az_pid_widget = QWidget()
        az_pid_layout = QGridLayout(az_pid_widget)
        az_pid_layout.setContentsMargins(0, 0, 0, 0)
        az_pid_layout.setVerticalSpacing(2)
        az_pid_layout.setHorizontalSpacing(4)
        
        az_pid_layout.addWidget(QLabel("<b>Azimuth</b>"), 0, 0, 1, 3)
        
        az_pid_layout.addWidget(QLabel("Kp:"), 1, 0)
        self.az_kp_slider = QSlider(Qt.Horizontal)
        self.az_kp_slider.setRange(0, 50)
        self.az_kp_slider.setValue(25)
        self.az_kp_slider.valueChanged.connect(lambda v: self._on_az_pid_changed('kp', v/10))
        az_pid_layout.addWidget(self.az_kp_slider, 1, 1)
        self.az_kp_label = QLabel("2.5")
        self.az_kp_label.setFixedWidth(25)
        az_pid_layout.addWidget(self.az_kp_label, 1, 2)
        
        az_pid_layout.addWidget(QLabel("Ki:"), 2, 0)
        self.az_ki_slider = QSlider(Qt.Horizontal)
        self.az_ki_slider.setRange(0, 50)
        self.az_ki_slider.setValue(10)
        self.az_ki_slider.valueChanged.connect(lambda v: self._on_az_pid_changed('ki', v/100))
        az_pid_layout.addWidget(self.az_ki_slider, 2, 1)
        self.az_ki_label = QLabel("0.10")
        self.az_ki_label.setFixedWidth(25)
        az_pid_layout.addWidget(self.az_ki_label, 2, 2)
        
        az_pid_layout.addWidget(QLabel("Kd:"), 3, 0)
        self.az_kd_slider = QSlider(Qt.Horizontal)
        self.az_kd_slider.setRange(0, 50)
        self.az_kd_slider.setValue(8)
        self.az_kd_slider.valueChanged.connect(lambda v: self._on_az_pid_changed('kd', v/10))
        az_pid_layout.addWidget(self.az_kd_slider, 3, 1)
        self.az_kd_label = QLabel("0.8")
        self.az_kd_label.setFixedWidth(25)
        az_pid_layout.addWidget(self.az_kd_label, 3, 2)
        
        pid_layout.addWidget(az_pid_widget)
        
        # Altitude PID
        alt_pid_widget = QWidget()
        alt_pid_layout = QGridLayout(alt_pid_widget)
        alt_pid_layout.setContentsMargins(0, 0, 0, 0)
        alt_pid_layout.setVerticalSpacing(2)
        alt_pid_layout.setHorizontalSpacing(4)
        
        alt_pid_layout.addWidget(QLabel("<b>Altitude</b>"), 0, 0, 1, 3)
        
        alt_pid_layout.addWidget(QLabel("Kp:"), 1, 0)
        self.alt_kp_slider = QSlider(Qt.Horizontal)
        self.alt_kp_slider.setRange(0, 50)
        self.alt_kp_slider.setValue(30)
        self.alt_kp_slider.valueChanged.connect(lambda v: self._on_alt_pid_changed('kp', v/10))
        alt_pid_layout.addWidget(self.alt_kp_slider, 1, 1)
        self.alt_kp_label = QLabel("3.0")
        self.alt_kp_label.setFixedWidth(25)
        alt_pid_layout.addWidget(self.alt_kp_label, 1, 2)
        
        alt_pid_layout.addWidget(QLabel("Ki:"), 2, 0)
        self.alt_ki_slider = QSlider(Qt.Horizontal)
        self.alt_ki_slider.setRange(0, 50)
        self.alt_ki_slider.setValue(20)
        self.alt_ki_slider.valueChanged.connect(lambda v: self._on_alt_pid_changed('ki', v/100))
        alt_pid_layout.addWidget(self.alt_ki_slider, 2, 1)
        self.alt_ki_label = QLabel("0.20")
        self.alt_ki_label.setFixedWidth(25)
        alt_pid_layout.addWidget(self.alt_ki_label, 2, 2)
        
        alt_pid_layout.addWidget(QLabel("Kd:"), 3, 0)
        self.alt_kd_slider = QSlider(Qt.Horizontal)
        self.alt_kd_slider.setRange(0, 50)
        self.alt_kd_slider.setValue(5)
        self.alt_kd_slider.valueChanged.connect(lambda v: self._on_alt_pid_changed('kd', v/10))
        alt_pid_layout.addWidget(self.alt_kd_slider, 3, 1)
        self.alt_kd_label = QLabel("0.5")
        self.alt_kd_label.setFixedWidth(25)
        alt_pid_layout.addWidget(self.alt_kd_label, 3, 2)
        
        pid_layout.addWidget(alt_pid_widget)
        
        settings_layout.addWidget(pid_group)
        main_layout.addLayout(settings_layout)
        
        # ===== ROW 4: Progress Bar and Controls =====
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setFormat("%p%")
        control_layout.addWidget(self.progress_bar, 2)
        
        # Control buttons
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setFixedSize(70, 28)
        self.preview_btn.clicked.connect(self._preview_motion)
        control_layout.addWidget(self.preview_btn)
        
        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedSize(70, 28)
        self.start_btn.clicked.connect(self._start_motion)
        self.start_btn.setStyleSheet("background-color: #10b981;")
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedSize(70, 28)
        self.stop_btn.clicked.connect(self._stop_motion)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #ef4444;")
        control_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(control_layout)
        
        # ===== ROW 5: PID Status =====
        status_group = QGroupBox("PID Status")
        status_group.setFixedHeight(60)
        status_layout = QGridLayout(status_group)
        status_layout.setContentsMargins(6, 6, 6, 6)
        status_layout.setHorizontalSpacing(15)
        
        # Azimuth status
        status_layout.addWidget(QLabel("Azimuth:"), 0, 0)
        self.az_p_label = QLabel("P:0.00")
        status_layout.addWidget(self.az_p_label, 0, 1)
        self.az_i_label = QLabel("I:0.00")
        status_layout.addWidget(self.az_i_label, 0, 2)
        self.az_d_label = QLabel("D:0.00")
        status_layout.addWidget(self.az_d_label, 0, 3)
        
        # Altitude status
        status_layout.addWidget(QLabel("Altitude:"), 1, 0)
        self.alt_p_label = QLabel("P:0.00")
        status_layout.addWidget(self.alt_p_label, 1, 1)
        self.alt_i_label = QLabel("I:0.00")
        status_layout.addWidget(self.alt_i_label, 1, 2)
        self.alt_d_label = QLabel("D:0.00")
        status_layout.addWidget(self.alt_d_label, 1, 3)
        
        main_layout.addWidget(status_group)
        
        # ===== ROW 6: Status Bar =====
        self.status_bar = QLabel("Ready")
        self.status_bar.setFixedHeight(22)
        self.status_bar.setStyleSheet(f"""
            background-color: rgba(30,41,59,0.8);
            padding: 2px 5px;
            border-radius: 3px;
        """)
        main_layout.addWidget(self.status_bar)
        
    def connect_signals(self):
        self.goto_thread.position_updated.connect(self._on_position_updated)
        self.goto_thread.pid_status.connect(self._on_pid_status)
        self.goto_thread.progress_updated.connect(self.progress_bar.setValue)
        self.goto_thread.motion_complete.connect(self._on_motion_complete)
        self.goto_thread.error_occurred.connect(self._on_error)
        
    def load_current_position(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                current_pos = data.get("current_position", {})
                self.current_az = current_pos.get("azimuth", 0.0)
                self.current_alt = current_pos.get("altitude", 90.0)
                self._update_position_display()
        except:
            pass
            
    def _update_position_display(self):
        self.current_pos_label.setText(f"{self.current_az:.1f}°, {self.current_alt:.1f}°")
        self.target_pos_label.setText(f"{self.target_az:.1f}°, {self.target_alt:.1f}°")
        self.direction_indicator.set_positions(
            self.current_az, self.current_alt,
            self.target_az, self.target_alt
        )
        
    def _on_target_changed(self):
        self.target_az = self.az_spin.value()
        self.target_alt = self.alt_spin.value()
        self._update_position_display()
        
        dir_info = self.goto_thread.set_target(self.target_az, self.target_alt)
        self.direction_label.setText(dir_info)
        self.distance_label.setText(f"AZ:{self.goto_thread.az_distance:.0f}° ALT:{self.goto_thread.alt_distance:.0f}°")
        
        self.direction_indicator.set_directions(
            self.goto_thread.az_direction,
            self.goto_thread.alt_direction,
            self.goto_thread.az_distance,
            self.goto_thread.alt_distance
        )
        
    def _use_current_position(self):
        self.az_spin.setValue(self.current_az)
        self.alt_spin.setValue(self.current_alt)
        
    def _update_speed_profile(self):
        self.goto_thread.speed_profile = [
            self.start_speed_spin.value(),
            self.cruise_speed_spin.value(),
            self.max_speed_spin.value()
        ]
        self.goto_thread.acceleration = self.acceleration_spin.value()
        
    def _on_az_pid_changed(self, term, value):
        if term == 'kp':
            self.goto_thread.pid_az.Kp = value
            self.az_kp_label.setText(f"{value:.1f}")
        elif term == 'ki':
            self.goto_thread.pid_az.Ki = value
            self.az_ki_label.setText(f"{value:.2f}")
        elif term == 'kd':
            self.goto_thread.pid_az.Kd = value
            self.az_kd_label.setText(f"{value:.1f}")
            
    def _on_alt_pid_changed(self, term, value):
        if term == 'kp':
            self.goto_thread.pid_alt.Kp = value
            self.alt_kp_label.setText(f"{value:.1f}")
        elif term == 'ki':
            self.goto_thread.pid_alt.Ki = value
            self.alt_ki_label.setText(f"{value:.2f}")
        elif term == 'kd':
            self.goto_thread.pid_alt.Kd = value
            self.alt_kd_label.setText(f"{value:.1f}")
        
    def _preview_motion(self):
        dir_info = self.goto_thread.set_target(self.target_az, self.target_alt)
        az_time = self.goto_thread.az_distance / self.cruise_speed_spin.value()
        alt_time = self.goto_thread.alt_distance / self.cruise_speed_spin.value()
        est_time = max(az_time, alt_time)
        self.status_bar.setText(f"Preview: {dir_info} | Est: {est_time:.1f}s")
        
    def _start_motion(self):
        if self.moving:
            return
            
        reply = QMessageBox.question(
            self, "Start GoTo",
            f"Move to AZ:{self.target_az:.1f}° ALT:{self.target_alt:.1f}°?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.moving = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.preview_btn.setEnabled(False)
            self.az_spin.setEnabled(False)
            self.alt_spin.setEnabled(False)
            
            self._update_speed_profile()
            self.goto_thread.set_target(self.target_az, self.target_alt)
            self.goto_thread.start_motion()
            self.status_bar.setText("Moving...")
            
    def _stop_motion(self):
        self.goto_thread.stop_motion()
        self._reset_controls()
        self.status_bar.setText("Stopped")
        
    def _on_position_updated(self, az, alt):
        self.current_az = az
        self.current_alt = alt
        self._update_position_display()
        
    def _on_pid_status(self, p, i, d, axis):
        if axis == "AZ":
            self.az_p_label.setText(f"P:{p:.2f}")
            self.az_i_label.setText(f"I:{i:.2f}")
            self.az_d_label.setText(f"D:{d:.2f}")
        else:
            self.alt_p_label.setText(f"P:{p:.2f}")
            self.alt_i_label.setText(f"I:{i:.2f}")
            self.alt_d_label.setText(f"D:{d:.2f}")
            
    def _on_motion_complete(self, success, message):
        self._reset_controls()
        self.status_bar.setText("✓ Complete")
        QMessageBox.information(self, "Complete", message)
        
    def _on_error(self, error_msg):
        self._reset_controls()
        self.status_bar.setText(f"✗ Error")
        QMessageBox.critical(self, "Error", error_msg)
        
    def _reset_controls(self):
        self.moving = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.preview_btn.setEnabled(True)
        self.az_spin.setEnabled(True)
        self.alt_spin.setEnabled(True)
        self.progress_bar.setValue(0)


# ============================================================================
# Main Calibration Dialog
# ============================================================================

class CalibrateDialog(QDialog):
    calibration_saved = pyqtSignal(float, float)

    def __init__(self, current_az, current_alt, theme, parent=None,
                 sensor_az_delta=None, sensor_alt_delta=None, both_connected=False):
        super().__init__(parent)
        self.setWindowTitle("Telescope Control")
        self.setModal(True)
        self.setFixedSize(600, 560)

        self.current_az = current_az
        self.current_alt = current_alt
        self.sensor_az_delta = sensor_az_delta
        self.sensor_alt_delta = sensor_alt_delta
        self.both_connected = both_connected
        self.theme = theme

        self.final_az = current_az
        self.final_alt = current_alt

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setFixedHeight(550)
        
        # Tab 1: Calibration
        self.calibration_tab = self._create_calibration_tab()
        self.tab_widget.addTab(self.calibration_tab, "⚙️ Calibration")
        
        # Tab 2: GoTo
        self.goto_tab = GoToTab(self.theme, self)
        self.tab_widget.addTab(self.goto_tab, "🎯 GoTo")
        
        main_layout.addWidget(self.tab_widget)

    def _create_calibration_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Position comparison frame
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)
        grid = QGridLayout(frame)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(10)

        # Headers
        headers = ["Axis", "Current", "Sensor Δ", "Target"]
        for col, header in enumerate(headers):
            label = QLabel(f"<b>{header}</b>")
            label.setAlignment(Qt.AlignCenter)
            grid.addWidget(label, 0, col)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        grid.addWidget(line, 1, 0, 1, 4)

        # Azimuth row
        grid.addWidget(QLabel("Azimuth:"), 2, 0)
        
        self.current_az_label = QLabel(f"{self.current_az:.1f}°")
        self.current_az_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.current_az_label, 2, 1)

        if self.both_connected and self.sensor_az_delta is not None:
            az_text = f"{self.sensor_az_delta:+.1f}°"
            if self.sensor_az_delta > 0:
                az_text = f"↻{az_text}"
            elif self.sensor_az_delta < 0:
                az_text = f"↺{az_text}"
            self.az_delta_label = QLabel(az_text)
        else:
            self.az_delta_label = QLabel("—")
        self.az_delta_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.az_delta_label, 2, 2)

        self.az_spin = QDoubleSpinBox()
        self.az_spin.setRange(AZ_MIN, AZ_MAX)
        self.az_spin.setValue(self.current_az)
        self.az_spin.setSuffix("°")
        self.az_spin.setDecimals(1)
        self.az_spin.setFixedWidth(90)
        self.az_spin.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.az_spin, 2, 3, Qt.AlignCenter)

        # Altitude row
        grid.addWidget(QLabel("Altitude:"), 3, 0)
        
        self.current_alt_label = QLabel(f"{self.current_alt:.1f}°")
        self.current_alt_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.current_alt_label, 3, 1)

        if self.both_connected and self.sensor_alt_delta is not None:
            self.alt_delta_label = QLabel(f"{self.sensor_alt_delta:+.1f}°")
        else:
            self.alt_delta_label = QLabel("—")
        self.alt_delta_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.alt_delta_label, 3, 2)

        self.alt_spin = QDoubleSpinBox()
        self.alt_spin.setRange(ALT_MIN, ALT_MAX)
        self.alt_spin.setValue(self.current_alt)
        self.alt_spin.setSuffix("°")
        self.alt_spin.setDecimals(1)
        self.alt_spin.setFixedWidth(90)
        self.alt_spin.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.alt_spin, 3, 3, Qt.AlignCenter)

        layout.addWidget(frame)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.use_current_btn = QPushButton("Use Current")
        self.use_current_btn.setFixedSize(100, 28)
        self.use_current_btn.clicked.connect(self._use_current_position)
        btn_layout.addWidget(self.use_current_btn)
        
        if self.both_connected and (self.sensor_az_delta is not None or self.sensor_alt_delta is not None):
            self.use_delta_btn = QPushButton("Apply Deltas")
            self.use_delta_btn.setFixedSize(100, 28)
            self.use_delta_btn.clicked.connect(self._apply_delta_angles)
            btn_layout.addWidget(self.use_delta_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Info label
        self.info_label = QLabel("Set target position and click OK")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self._load_saved_positions()
        
        return widget

    def _apply_styles(self):
        tx = get_contrasting_color(self.theme["window_bg"])
        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {self.theme['window_bg']}; 
                color: {tx}; 
            }}
            QTabWidget::pane {{
                border: 1px solid {self.theme['steel_blue']};
                border-radius: 4px;
                background-color: {self.theme['tab_pane']};
            }}
            QTabBar::tab {{
                background-color: {self.theme['button_bg']};
                color: {self.theme['button_text']};
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }}
            QTabBar::tab:selected {{
                background-color: {self.theme['tab_selected']};
                color: {self.theme['window_bg']};
            }}
            QGroupBox {{
                color: {self.theme.get('accent_gold', '#fca311')};
                border: 1px solid {self.theme.get('steel_blue', '#2a4365')};
                border-radius: 4px;
                margin-top: 8px;
                font-size: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }}
            QFrame {{
                border: 1px solid {self.theme['steel_blue']};
                border-radius: 4px;
                background-color: {self.theme['row_bg']};
            }}
            QPushButton {{ 
                background-color: {self.theme['button_bg']}; 
                color: {self.theme['button_text']};
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {self.theme['button_hover']};
            }}
            QDoubleSpinBox {{ 
                background-color: {self.theme['window_bg']}; 
                color: {tx};
                border: 1px solid {self.theme['steel_blue']};
                border-radius: 3px;
                padding: 2px;
                font-size: 10px;
            }}
            QLabel {{
                color: {tx};
                font-size: 10px;
            }}
            QProgressBar {{
                background-color: {self.theme.get('row_bg', '#1e293b')};
                border-radius: 3px;
                text-align: center;
                font-size: 9px;
            }}
            QProgressBar::chunk {{
                background-color: {self.theme.get('progress_color', '#38bdf8')};
                border-radius: 3px;
            }}
            QSlider::groove:horizontal {{
                background: {self.theme.get('row_bg', '#1e293b')};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.theme.get('button_bg', '#2563eb')};
                width: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }}
        """)

    def _load_saved_positions(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                current_pos = data.get("current_position", {})
                self.az_spin.setValue(current_pos.get("azimuth", self.current_az))
                self.alt_spin.setValue(current_pos.get("altitude", self.current_alt))
            except:
                pass

    def _use_current_position(self):
        self.az_spin.setValue(self.current_az)
        self.alt_spin.setValue(self.current_alt)
        self.info_label.setText("Target set to current position")

    def _apply_delta_angles(self):
        new_az = self.current_az
        new_alt = self.current_alt
        
        if self.sensor_az_delta is not None:
            new_az = (self.current_az + self.sensor_az_delta) % 360
            
        if self.sensor_alt_delta is not None:
            new_alt = self.current_alt + self.sensor_alt_delta
            new_alt = max(ALT_MIN, min(ALT_MAX, new_alt))
        
        self.az_spin.setValue(round(new_az, 1))
        self.alt_spin.setValue(round(new_alt, 1))
        self.info_label.setText("Applied sensor deltas")

    def _accept(self):
        self.final_az = self.az_spin.value()
        self.final_alt = self.alt_spin.value()
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
            else:
                data = {}
            
            if "current_position" not in data:
                data["current_position"] = {}
            
            data["current_position"]["azimuth"] = round(self.final_az, 1)
            data["current_position"]["altitude"] = round(self.final_alt, 1)
            
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except:
            pass
        
        self.calibration_saved.emit(self.final_az, self.final_alt)
        self.accept()

    def get_values(self):
        return self.final_az, self.final_alt