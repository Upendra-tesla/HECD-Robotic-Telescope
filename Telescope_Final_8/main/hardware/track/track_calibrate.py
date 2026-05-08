#!/usr/bin/env python3
"""
Calibration Visualization for GoTo Window
- Shows calibration data in circular plots
- Real vs Sensor mapping visualization
- Auto-refreshes calibration data
- Uses single global motor.json
"""

import sys
import os
import json
import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont

# --------------------------
# Global Configuration Path - SINGLE FILE
# --------------------------
MAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CONFIG_FILE = os.path.join(MAIN_DIR, "motor.json")

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from parent directory - but avoid circular import by importing specific items
try:
    from track import COLORS, format_angle_with_sign
    from track import converter as main_converter
except ImportError:
    # Fallback if track.py not fully available
    COLORS = {
        'bg': '#0f172a',
        'text': '#f8fafc',
        'grid': '#334155',
        'real_az': '#3b82f6',
        'sensor_az': '#f59e0b',
        'real_alt': '#10b981',
        'sensor_alt': '#ef4444',
        'cardinal': '#fca311',
        'intercardinal': '#94a3b8'
    }
    
    def format_angle_with_sign(angle):
        if angle >= 0:
            return f"+{angle:.1f}°"
        else:
            return f"{angle:.1f}°"
    
    # Create a local converter instance
    class LocalConverter:
        def __init__(self):
            self.az_calibration = {}
            self.alt_calibration = {}
            self.horizon_sensor_value = None
            self.zenith_sensor_value = None
        
        def load_calibration(self):
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r") as f:
                        data = json.load(f)
                    calib = data.get("calibration", {})
                    self.az_calibration = calib.get("azimuth_calibration_delta_32", {})
                    self.alt_calibration = calib.get("altitude_calibration_delta_13", {})
                    self.horizon_sensor_value = self.alt_calibration.get("horizon")
                    self.zenith_sensor_value = self.alt_calibration.get("zenith")
                except:
                    pass
    
    main_converter = LocalConverter()


# --------------------------
# Circular Plot Widget (Base)
# --------------------------
class CircularPlot(QWidget):
    """Base class for circular plots (azimuth or altitude)"""
    
    def __init__(self, title, plot_type):
        super().__init__()
        self.setFixedSize(220, 220)
        self.title = title
        self.plot_type = plot_type  # 'azimuth' or 'altitude'
        
        # Data storage
        self.real_points = []      # (angle, label, is_cardinal)
        self.sensor_points = []    # (sensor_value, label, is_cardinal)
        
        # Default ranges
        if plot_type == 'azimuth':
            self.real_range = (0, 360)
            self.sensor_range = (-180, 180)
        else:  # altitude
            self.real_range = (0, 90)
            self.sensor_range = (-180, 180)
    
    def set_data(self, real_points, sensor_points):
        """Set the data points to display"""
        self.real_points = real_points
        self.sensor_points = sensor_points
        self.update()
    
    def _angle_to_point(self, angle, radius_scale=0.8, is_real=True):
        """Convert angle to point on circle"""
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 15
        
        # Adjust radius based on type
        if self.plot_type == 'altitude':
            # For altitude, radius represents elevation (0 at center, 90 at edge)
            if is_real:
                # Real altitude: 0° at edge (horizon), 90° at center (zenith)
                alt_scale = 1.0 - (angle / 90.0)
                r = radius * alt_scale
            else:
                # Sensor altitude: map -180..180 to 0..1 for radius
                norm_angle = (angle + 180) / 360.0
                r = radius * norm_angle
        else:
            # For azimuth, all points on same radius
            r = radius * radius_scale
        
        # Convert angle to radians (0° at top, clockwise)
        theta = math.radians(90 - angle)
        x = center_x + r * math.cos(theta)
        y = center_y - r * math.sin(theta)
        
        return x, y
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QColor(COLORS['bg']))
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 15
        
        # Draw title with high contrast
        painter.setPen(QPen(QColor(COLORS['text']), 1))
        painter.setFont(QFont("Monospace", 8, QFont.Bold))
        painter.drawText(5, 15, self.title)
        
        if self.plot_type == 'azimuth':
            self._draw_azimuth_plot(painter, center_x, center_y, radius)
        else:
            self._draw_altitude_plot(painter, center_x, center_y, radius)
    
    def _draw_azimuth_plot(self, painter, cx, cy, radius):
        """Draw azimuth plot (compass style)"""
        # Draw outer circle
        painter.setPen(QPen(QColor(COLORS['grid']), 1))
        painter.drawEllipse(int(cx - radius), int(cy - radius), 
                          int(2*radius), int(2*radius))
        
        # Draw inner circle for reference
        painter.setPen(QPen(QColor(COLORS['grid']), 1, Qt.DashLine))
        inner_radius = radius * 0.5
        painter.drawEllipse(int(cx - inner_radius), int(cy - inner_radius), 
                          int(2*inner_radius), int(2*inner_radius))
        
        # Draw cardinal direction lines
        painter.setPen(QPen(QColor(COLORS['cardinal']), 1, Qt.DotLine))
        for angle in [0, 90, 180, 270]:  # N, E, S, W
            rad = math.radians(90 - angle)
            x = cx + radius * math.cos(rad)
            y = cy - radius * math.sin(rad)
            painter.drawLine(int(cx), int(cy), int(x), int(y))
        
        # Draw cardinal labels with high contrast
        painter.setPen(QPen(QColor(COLORS['cardinal']), 1))
        painter.setFont(QFont("Monospace", 6, QFont.Bold))
        painter.drawText(int(cx - 3), int(cy - radius + 10), "N")
        painter.drawText(int(cx + radius - 10), int(cy + 3), "E")
        painter.drawText(int(cx - 3), int(cy + radius - 5), "S")
        painter.drawText(int(cx - radius + 5), int(cy + 3), "W")
        
        # Draw real azimuth points (blue) - at inner radius
        if self.real_points:
            painter.setPen(QPen(QColor(COLORS['real_az']), 2))
            painter.setBrush(QBrush(QColor(COLORS['real_az'])))
            for angle, label, is_cardinal in self.real_points:
                x, y = self._angle_to_point(angle, 0.7, True)  # Inner circle for real
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
                
                # Draw label for cardinal points only (to avoid clutter)
                if is_cardinal and label:
                    painter.setPen(QPen(QColor(COLORS['real_az']), 1))
                    painter.setFont(QFont("Monospace", 5, QFont.Bold))
                    painter.drawText(int(x) + 3, int(y) - 3, label[:2])
        
        # Draw sensor azimuth points (orange) - at outer radius
        if self.sensor_points:
            painter.setPen(QPen(QColor(COLORS['sensor_az']), 2))
            painter.setBrush(QBrush(QColor(COLORS['sensor_az'])))
            for sensor_val, label, is_cardinal in self.sensor_points:
                # For sensor values, we plot them directly (they're already in -180..180)
                # But we need to convert to 0-360 for display
                display_angle = sensor_val
                if display_angle < 0:
                    display_angle += 360
                
                x, y = self._angle_to_point(display_angle, 0.9, False)  # Outer circle for sensor
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
                
                # Draw label for cardinal points
                if is_cardinal and label:
                    painter.setPen(QPen(QColor(COLORS['sensor_az']), 1))
                    painter.setFont(QFont("Monospace", 5, QFont.Bold))
                    painter.drawText(int(x) + 3, int(y) - 3, label[:2])
        
        # Draw connecting lines between real and sensor points for cardinal directions
        painter.setPen(QPen(QColor(COLORS['grid']), 1, Qt.DotLine))
        for real_point in self.real_points:
            real_angle, label, is_cardinal = real_point
            if is_cardinal and label:
                # Find matching sensor point
                for sensor_val, s_label, _ in self.sensor_points:
                    if s_label == label:
                        # Draw line connecting them
                        real_x, real_y = self._angle_to_point(real_angle, 0.7, True)
                        sensor_display = sensor_val if sensor_val >= 0 else sensor_val + 360
                        sensor_x, sensor_y = self._angle_to_point(sensor_display, 0.9, False)
                        painter.drawLine(int(real_x), int(real_y), int(sensor_x), int(sensor_y))
                        break
        
        # Draw legend with high contrast text
        self._draw_legend(painter, int(cx + radius - 40), int(cy - radius + 20))
    
    def _draw_altitude_plot(self, painter, cx, cy, radius):
        """Draw altitude plot (elevation style)"""
        # Draw concentric circles for altitude levels
        painter.setPen(QPen(QColor(COLORS['grid']), 1, Qt.DashLine))
        for alt in [30, 60, 90]:
            r = radius * (1.0 - alt/90.0)  # 0° at edge, 90° at center
            painter.drawEllipse(int(cx - r), int(cy - r), int(2*r), int(2*r))
        
        # Draw altitude labels with high contrast
        painter.setPen(QPen(QColor(COLORS['text']), 1))
        painter.setFont(QFont("Monospace", 5, QFont.Bold))
        painter.drawText(int(cx + 3), int(cy - radius + 8), "90°")
        painter.drawText(int(cx + 3), int(cy - int(radius*0.33) + 3), "60°")
        painter.drawText(int(cx + 3), int(cy - int(radius*0.66) + 3), "30°")
        painter.drawText(int(cx + 3), int(cy + 10), "0°")
        
        # Draw real altitude points (green)
        if self.real_points:
            painter.setPen(QPen(QColor(COLORS['real_alt']), 2))
            painter.setBrush(QBrush(QColor(COLORS['real_alt'])))
            for angle, label, is_cardinal in self.real_points:
                x, y = self._angle_to_point(angle, 0.8, True)
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
                
                # Draw label
                if label:
                    painter.setPen(QPen(QColor(COLORS['real_alt']), 1))
                    painter.setFont(QFont("Monospace", 5, QFont.Bold))
                    painter.drawText(int(x) + 3, int(y) - 3, label)
        
        # Draw sensor altitude points (red)
        if self.sensor_points:
            painter.setPen(QPen(QColor(COLORS['sensor_alt']), 2))
            painter.setBrush(QBrush(QColor(COLORS['sensor_alt'])))
            for sensor_val, label, is_cardinal in self.sensor_points:
                x, y = self._angle_to_point(sensor_val, 0.5, False)
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
                
                # Draw label
                if label:
                    painter.setPen(QPen(QColor(COLORS['sensor_alt']), 1))
                    painter.setFont(QFont("Monospace", 5, QFont.Bold))
                    painter.drawText(int(x) + 3, int(y) - 3, label)
        
        # Draw legend with high contrast text
        self._draw_legend(painter, int(cx + radius - 40), int(cy - radius + 20))
    
    def _draw_legend(self, painter, x, y):
        """Draw color legend with high contrast text"""
        legend_y = y
        painter.setFont(QFont("Monospace", 5, QFont.Bold))
        
        # Real points
        painter.setPen(QPen(QColor(COLORS['real_az' if self.plot_type == 'azimuth' else 'real_alt']), 1))
        painter.setBrush(QBrush(QColor(COLORS['real_az' if self.plot_type == 'azimuth' else 'real_alt'])))
        painter.drawEllipse(x, legend_y, 4, 4)
        painter.setPen(QPen(QColor(COLORS['text']), 1))
        painter.drawText(x + 6, legend_y + 3, "Real")
        
        # Sensor points
        painter.setPen(QPen(QColor(COLORS['sensor_az' if self.plot_type == 'azimuth' else 'sensor_alt']), 1))
        painter.setBrush(QBrush(QColor(COLORS['sensor_az' if self.plot_type == 'azimuth' else 'sensor_alt'])))
        painter.drawEllipse(x, legend_y + 10, 4, 4)
        painter.setPen(QPen(QColor(COLORS['text']), 1))
        painter.drawText(x + 6, legend_y + 13, "Sensor")


# --------------------------
# Calibration Tab Widget
# --------------------------
class CalibrationTab(QWidget):
    """Tab for calibration visualization"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        # Auto-refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(2000)  # Update every 2 seconds
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Info panel with improved text contrast
        info_group = QGroupBox("Calibration Info")
        info_group.setStyleSheet(f"""
            QGroupBox {{ 
                color: {COLORS['cardinal']}; 
                font-size: 8px; 
                font-weight: bold;
                border: 1px solid {COLORS['grid']};
                margin-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
                color: {COLORS['cardinal']};
            }}
            QLabel {{ 
                color: {COLORS['text']}; 
                font-size: 9px;
                font-weight: normal;
                background-color: transparent;
                padding: 2px;
            }}
            QLabel[value="true"] {{
                color: {COLORS['real_alt']};
                font-weight: bold;
            }}
        """)
        info_layout = QGridLayout(info_group)
        info_layout.setHorizontalSpacing(10)
        info_layout.setVerticalSpacing(2)
        
        # Get calibration data from global motor.json
        main_converter.load_calibration()
        az_cal = main_converter.az_calibration
        alt_cal = main_converter.alt_calibration
        az_count = len([v for v in az_cal.values() if v is not None])
        
        # Get horizon/zenith values
        horizon = alt_cal.get("horizon", "N/A")
        zenith = alt_cal.get("zenith", "N/A")
        
        # Trained Directions
        dir_label = QLabel("Trained Directions:")
        dir_label.setStyleSheet(f"color: {COLORS['cardinal']}; font-weight: bold;")
        info_layout.addWidget(dir_label, 0, 0)
        
        dir_value = QLabel(f"{az_count}/16")
        dir_value.setStyleSheet(f"color: {COLORS['real_alt']}; font-weight: bold;")
        info_layout.addWidget(dir_value, 0, 1)
        
        # Progress bar for directions
        progress_bar = QLabel("█" * az_count + "░" * (16 - az_count))
        progress_bar.setStyleSheet(f"color: {COLORS['real_alt']}; font-size: 10px;")
        info_layout.addWidget(progress_bar, 0, 2)
        
        # Horizon Sensor
        horizon_label = QLabel("Horizon Sensor:")
        horizon_label.setStyleSheet(f"color: {COLORS['cardinal']}; font-weight: bold;")
        info_layout.addWidget(horizon_label, 1, 0)
        
        if isinstance(horizon, (int, float)):
            horizon_value = QLabel(f"{format_angle_with_sign(horizon)}")
            horizon_value.setStyleSheet(f"color: {COLORS['sensor_alt']}; font-weight: bold;")
        else:
            horizon_value = QLabel(str(horizon))
            horizon_value.setStyleSheet(f"color: {COLORS['grid']};")
        info_layout.addWidget(horizon_value, 1, 1)
        
        # Add mapping arrow for horizon
        horizon_arrow = QLabel("→ 0°")
        horizon_arrow.setStyleSheet(f"color: {COLORS['real_alt']}; font-weight: bold;")
        info_layout.addWidget(horizon_arrow, 1, 2)
        
        # Zenith Sensor
        zenith_label = QLabel("Zenith Sensor:")
        zenith_label.setStyleSheet(f"color: {COLORS['cardinal']}; font-weight: bold;")
        info_layout.addWidget(zenith_label, 2, 0)
        
        if isinstance(zenith, (int, float)):
            zenith_value = QLabel(f"{format_angle_with_sign(zenith)}")
            zenith_value.setStyleSheet(f"color: {COLORS['sensor_alt']}; font-weight: bold;")
        else:
            zenith_value = QLabel(str(zenith))
            zenith_value.setStyleSheet(f"color: {COLORS['grid']};")
        info_layout.addWidget(zenith_value, 2, 1)
        
        # Add mapping arrow for zenith
        zenith_arrow = QLabel("→ 90°")
        zenith_arrow.setStyleSheet(f"color: {COLORS['real_alt']}; font-weight: bold;")
        info_layout.addWidget(zenith_arrow, 2, 2)
        
        # Add sensor range if both are calibrated
        if isinstance(horizon, (int, float)) and isinstance(zenith, (int, float)):
            sensor_range = zenith - horizon
            if abs(sensor_range) > 180:
                if sensor_range > 0:
                    sensor_range -= 360
                else:
                    sensor_range += 360
            
            range_label = QLabel("Sensor Range:")
            range_label.setStyleSheet(f"color: {COLORS['cardinal']}; font-weight: bold;")
            info_layout.addWidget(range_label, 3, 0)
            
            range_value = QLabel(f"{format_angle_with_sign(sensor_range)}")
            range_value.setStyleSheet(f"color: {COLORS['sensor_az']}; font-weight: bold;")
            info_layout.addWidget(range_value, 3, 1)
            
            # Add range note
            range_note = QLabel(f"covers {abs(sensor_range):.0f}° sensor")
            range_note.setStyleSheet(f"color: {COLORS['grid']}; font-size: 7px;")
            info_layout.addWidget(range_note, 3, 2)
        
        layout.addWidget(info_group)
        
        # Plots layout
        plots_layout = QHBoxLayout()
        
        # Azimuth plot
        self.az_plot = CircularPlot("Azimuth (0-360°)", 'azimuth')
        plots_layout.addWidget(self.az_plot)
        
        # Altitude plot
        self.alt_plot = CircularPlot("Altitude (0-90°)", 'altitude')
        plots_layout.addWidget(self.alt_plot)
        
        layout.addLayout(plots_layout)
        
        # Refresh button with better contrast
        refresh_btn = QPushButton("↻ Refresh Calibration Data")
        refresh_btn.clicked.connect(self.update_plots)
        refresh_btn.setFixedHeight(24)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['real_az']};
                color: {COLORS['text']};
                font-size: 9px;
                font-weight: bold;
                border: none;
                border-radius: 3px;
                padding: 3px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['sensor_az']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['real_alt']};
            }}
        """)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        # Initial plot update
        self.update_plots()
    
    def update_plots(self):
        """Update both plots with current calibration data"""
        # Reload calibration data from global motor.json
        main_converter.load_calibration()
        
        # Process azimuth data
        self._update_azimuth_plot()
        
        # Process altitude data
        self._update_altitude_plot()
        
        # Update info display
        self._update_info_display()
    
    def _update_info_display(self):
        """Update the info panel with latest calibration data"""
        # Find the info group box (first child of layout)
        info_group = self.layout().itemAt(0).widget()
        if info_group and isinstance(info_group, QGroupBox):
            # Update the layout content
            layout = info_group.layout()
            
            # Get latest calibration data
            az_cal = main_converter.az_calibration
            alt_cal = main_converter.alt_calibration
            az_count = len([v for v in az_cal.values() if v is not None])
            
            horizon = alt_cal.get("horizon", "N/A")
            zenith = alt_cal.get("zenith", "N/A")
            
            # Update progress bar
            if layout.itemAtPosition(0, 2):
                progress_bar = layout.itemAtPosition(0, 2).widget()
                progress_bar.setText("█" * az_count + "░" * (16 - az_count))
            
            # Update horizon value
            if layout.itemAtPosition(1, 1):
                horizon_widget = layout.itemAtPosition(1, 1).widget()
                if isinstance(horizon, (int, float)):
                    horizon_widget.setText(f"{format_angle_with_sign(horizon)}")
                    horizon_widget.setStyleSheet(f"color: {COLORS['sensor_alt']}; font-weight: bold;")
                else:
                    horizon_widget.setText(str(horizon))
                    horizon_widget.setStyleSheet(f"color: {COLORS['grid']};")
            
            # Update zenith value
            if layout.itemAtPosition(2, 1):
                zenith_widget = layout.itemAtPosition(2, 1).widget()
                if isinstance(zenith, (int, float)):
                    zenith_widget.setText(f"{format_angle_with_sign(zenith)}")
                    zenith_widget.setStyleSheet(f"color: {COLORS['sensor_alt']}; font-weight: bold;")
                else:
                    zenith_widget.setText(str(zenith))
                    zenith_widget.setStyleSheet(f"color: {COLORS['grid']};")
            
            # Update range if both calibrated
            if isinstance(horizon, (int, float)) and isinstance(zenith, (int, float)):
                sensor_range = zenith - horizon
                if abs(sensor_range) > 180:
                    if sensor_range > 0:
                        sensor_range -= 360
                    else:
                        sensor_range += 360
                
                if layout.itemAtPosition(3, 1):
                    range_widget = layout.itemAtPosition(3, 1).widget()
                    range_widget.setText(f"{format_angle_with_sign(sensor_range)}")
    
    def _update_azimuth_plot(self):
        """Update azimuth plot with calibrated directions"""
        az_cal = main_converter.az_calibration
        
        # Real azimuth points (cardinal/intercardinal)
        real_points = []
        sensor_points = []
        
        # Direction mapping (clockwise from north)
        directions = [
            ("north", 0, True),
            ("north-northeast", 22.5, False),
            ("northeast", 45, False),
            ("east-northeast", 67.5, False),
            ("east", 90, True),
            ("east-southeast", 112.5, False),
            ("southeast", 135, False),
            ("south-southeast", 157.5, False),
            ("south", 180, True),
            ("south-southwest", 202.5, False),
            ("southwest", 225, False),
            ("west-southwest", 247.5, False),
            ("west", 270, True),
            ("west-northwest", 292.5, False),
            ("northwest", 315, False),
            ("north-northwest", 337.5, False)
        ]
        
        for dir_name, real_angle, is_cardinal in directions:
            # Add real point
            label = dir_name.upper()[:2] if is_cardinal else ""
            real_points.append((real_angle, label, is_cardinal))
            
            # Add sensor point if calibrated
            if dir_name in az_cal and az_cal[dir_name] is not None:
                sensor_val = az_cal[dir_name]
                sensor_points.append((sensor_val, label, is_cardinal))
        
        self.az_plot.set_data(real_points, sensor_points)
    
    def _update_altitude_plot(self):
        """Update altitude plot with horizon/zenith calibration"""
        alt_cal = main_converter.alt_calibration
        
        # Real altitude points
        real_points = [
            (0, "H", True),      # Horizon
            (45, "M", False),    # Midpoint
            (90, "Z", True)      # Zenith
        ]
        
        # Sensor altitude points
        sensor_points = []
        
        horizon = alt_cal.get("horizon")
        zenith = alt_cal.get("zenith")
        
        if horizon is not None:
            sensor_points.append((horizon, "H", True))
        
        if zenith is not None:
            sensor_points.append((zenith, "Z", True))
        
        # Calculate and add midpoint if both are calibrated
        if horizon is not None and zenith is not None:
            # Handle wrap-around for sensor values
            sensor_range = zenith - horizon
            if abs(sensor_range) > 180:
                if sensor_range > 0:
                    sensor_range -= 360
                else:
                    sensor_range += 360
            
            midpoint = horizon + sensor_range * 0.5
            
            # Normalize to -180..180
            midpoint = midpoint % 360
            if midpoint > 180:
                midpoint -= 360
            elif midpoint < -180:
                midpoint += 360
            
            sensor_points.append((midpoint, "M", False))
        
        self.alt_plot.set_data(real_points, sensor_points)


# For standalone testing
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = CalibrationTab()
    win.show()
    sys.exit(app.exec_())