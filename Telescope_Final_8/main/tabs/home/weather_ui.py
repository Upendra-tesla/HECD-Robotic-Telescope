# main/tabs/home/weather_ui.py
"""
Weather UI Module - UI components for weather tab
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QGridLayout
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPixmap


def rgba_color(hex_color, opacity=0.15):
    """Convert hex color to rgba with opacity for 85% transparency"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {opacity})"


def get_contrasting_color(bg_color):
    """Return black or white based on background luminance"""
    bg_color = bg_color.lstrip('#')
    if len(bg_color) == 3:
        bg_color = ''.join([c*2 for c in bg_color])
    
    r = int(bg_color[0:2], 16) / 255.0
    g = int(bg_color[2:4], 16) / 255.0
    b = int(bg_color[4:6], 16) / 255.0
    
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if luminance > 0.5 else "#ffffff"


class MoonPhaseWidget(QWidget):
    """Custom widget to display moon phase using images (moon_00.png to moon_27.png)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(120, 120)
        self.image_label.setScaledContents(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_label)
        
        self.current_image_index = 14  # Default to full moon
        
        # Get correct path to moon images
        # Current file: main/tabs/home/weather_ui.py
        # Moon images should be in: main/tabs/home/home_images/Moon_Phase/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.moon_images_path = os.path.join(current_dir, "home_images", "Moon_Phase")
        
        # Create directory if it doesn't exist
        os.makedirs(self.moon_images_path, exist_ok=True)
        
        self.moon_phase_name_label = None
        self.moon_illumination_label = None
        self.moon_age_label = None
        
    def set_phase(self, image_index, phase_name, illumination, age_days):
        """Set the moon phase using image index (0-27)"""
        self.current_image_index = image_index
        self.load_moon_image(image_index)
        
        if self.moon_phase_name_label:
            self.moon_phase_name_label.setText(phase_name)
        if self.moon_illumination_label:
            self.moon_illumination_label.setText(f"{illumination:.1f}% illuminated")
        if self.moon_age_label:
            self.moon_age_label.setText(f"Age: {age_days:.1f} days")
    
    def load_moon_image(self, image_index):
        """Load moon phase image from file (moon_00.png to moon_27.png)"""
        # Format image name with leading zero (00-27)
        image_path = os.path.join(self.moon_images_path, f"moon_{image_index:02d}.png")
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    120, 120, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                return
        
        # Fallback - create a simple circle with text if image not found
        self.image_label.setText(f"🌙\n{image_index:02d}")
        self.image_label.setStyleSheet("font-size: 48px;")
    
    def set_labels(self, name_label, illumination_label, age_label):
        """Set references to info labels"""
        self.moon_phase_name_label = name_label
        self.moon_illumination_label = illumination_label
        self.moon_age_label = age_label


class WeatherUI:
    """UI Builder for Weather Tab"""
    
    @staticmethod
    def setup_ui(parent, latitude, longitude):
        """
        Setup the user interface with rows and columns - 850×510
        
        Returns:
            tuple: (w_fields, o_fields, planets_label, fact_label, update_label, 
                   space_image_label, moon_widget, loc_label, refresh_btn, loc_btn)
        """
        main_layout = QVBoxLayout(parent)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # === ROW 1: Location Bar and Refresh (height: 40px) ===
        row1 = QFrame()
        row1.setObjectName("row1")
        row1.setFixedHeight(40)
        row1.setFrameStyle(QFrame.NoFrame)
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(5, 5, 5, 5)
        row1_layout.setSpacing(5)
        
        loc_label = QLabel(f"📍 Lat: {latitude:.4f}°, Lon: {longitude:.4f}°")
        loc_label.setFont(QFont("Arial", 10, QFont.Bold))
        row1_layout.addWidget(loc_label)
        
        row1_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedSize(90, 28)
        row1_layout.addWidget(refresh_btn)
        
        loc_btn = QPushButton("⚙️ Set Location")
        loc_btn.setFixedSize(100, 28)
        row1_layout.addWidget(loc_btn)
        
        main_layout.addWidget(row1)
        
        # === ROW 2: Space Fact (height: 60px) ===
        row2 = QFrame()
        row2.setObjectName("row2")
        row2.setFixedHeight(60)
        row2.setFrameStyle(QFrame.NoFrame)
        row2_layout = QVBoxLayout(row2)
        row2_layout.setContentsMargins(5, 5, 5, 5)
        
        fact_title = QLabel("✨ Daily Space Fact")
        fact_title.setFont(QFont("Arial", 10, QFont.Bold))
        fact_title.setAlignment(Qt.AlignCenter)
        row2_layout.addWidget(fact_title)
        
        fact_label = QLabel()
        fact_label.setFont(QFont("Arial", 9))
        fact_label.setAlignment(Qt.AlignCenter)
        fact_label.setWordWrap(True)
        row2_layout.addWidget(fact_label)
        
        main_layout.addWidget(row2)
        
        # === ROW 3: Main Content (height: 410px) ===
        row3 = QFrame()
        row3.setObjectName("row3")
        row3.setFixedHeight(410)
        row3.setFrameStyle(QFrame.NoFrame)
        row3_layout = QHBoxLayout(row3)
        row3_layout.setContentsMargins(5, 5, 5, 5)
        row3_layout.setSpacing(5)
        
        # Column 1: Weather & Sky + Planets (28% width)
        col1 = QFrame()
        col1.setObjectName("col1")
        col1.setFrameStyle(QFrame.NoFrame)
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(5, 5, 5, 5)
        col1_layout.setSpacing(8)
        
        # Weather & Sky section
        weather_title = QLabel("🌤️ Weather & Sky")
        weather_title.setFont(QFont("Arial", 10, QFont.Bold))
        weather_title.setAlignment(Qt.AlignCenter)
        col1_layout.addWidget(weather_title)
        
        # Weather fields in grid
        weather_grid = QGridLayout()
        weather_grid.setSpacing(3)
        
        weather_labels = ["Sky Quality:", "Temperature:", "Humidity:"]
        w_fields = {}
        
        for i, label_text in enumerate(weather_labels):
            label = QLabel(label_text)
            label.setFont(QFont("Arial", 8))
            weather_grid.addWidget(label, i, 0, Qt.AlignRight)
            
            value_label = QLabel("—")
            value_label.setFont(QFont("Arial", 8, QFont.Bold))
            value_label.setWordWrap(True)
            weather_grid.addWidget(value_label, i, 1)
            
            key = label_text.replace(":", "").lower().replace(" ", "_")
            w_fields[key] = value_label
        
        col1_layout.addLayout(weather_grid)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setStyleSheet("background-color: rgba(255,255,255,0.1); max-height: 1px; margin: 5px 0;")
        col1_layout.addWidget(sep1)
        
        # Planets Visible Now section
        planets_title = QLabel("🪐 Planets Visible Now")
        planets_title.setFont(QFont("Arial", 10, QFont.Bold))
        planets_title.setAlignment(Qt.AlignCenter)
        col1_layout.addWidget(planets_title)
        
        # Planet display area
        planets_label = QLabel()
        planets_label.setFont(QFont("Arial", 8))
        planets_label.setAlignment(Qt.AlignLeft)
        planets_label.setWordWrap(True)
        planets_label.setMinimumHeight(120)
        planets_label.setStyleSheet("padding: 4px;")
        col1_layout.addWidget(planets_label)
        
        col1_layout.addStretch()
        row3_layout.addWidget(col1, 28)
        
        # Column 2: Space Updates & Image (44% width)
        col2 = QFrame()
        col2.setObjectName("col2")
        col2.setFrameStyle(QFrame.NoFrame)
        col2_layout = QVBoxLayout(col2)
        col2_layout.setContentsMargins(5, 5, 5, 5)
        col2_layout.setSpacing(5)
        
        space_title = QLabel("🌌 Space Updates")
        space_title.setFont(QFont("Arial", 10, QFont.Bold))
        space_title.setAlignment(Qt.AlignCenter)
        col2_layout.addWidget(space_title)
        
        update_label = QLabel()
        update_label.setFont(QFont("Arial", 8))
        update_label.setAlignment(Qt.AlignCenter)
        update_label.setWordWrap(True)
        update_label.setFixedHeight(60)
        col2_layout.addWidget(update_label)
        
        # Image area
        space_image_label = QLabel()
        space_image_label.setObjectName("space_image_label")
        space_image_label.setAlignment(Qt.AlignCenter)
        space_image_label.setFixedSize(320, 240)
        space_image_label.setStyleSheet("border: none; background: transparent;")
        col2_layout.addWidget(space_image_label, alignment=Qt.AlignCenter)
        
        col2_layout.addStretch()
        row3_layout.addWidget(col2, 44)
        
        # Column 3: Observation & Moon Phase (28% width)
        col3 = QFrame()
        col3.setObjectName("col3")
        col3.setFrameStyle(QFrame.NoFrame)
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(5, 5, 5, 5)
        col3_layout.setSpacing(8)
        
        # Observation section
        obs_title = QLabel("🌙 Sky Observation")
        obs_title.setFont(QFont("Arial", 10, QFont.Bold))
        obs_title.setAlignment(Qt.AlignCenter)
        col3_layout.addWidget(obs_title)
        
        # Observation fields in grid
        obs_grid = QGridLayout()
        obs_grid.setSpacing(3)
        
        obs_labels = ["Sun Position:", "Sky Visibility:", "Recommendation:"]
        o_fields = {}
        
        for i, label_text in enumerate(obs_labels):
            label = QLabel(label_text)
            label.setFont(QFont("Arial", 8))
            obs_grid.addWidget(label, i, 0, Qt.AlignRight)
            
            value_label = QLabel("—")
            value_label.setFont(QFont("Arial", 8, QFont.Bold))
            value_label.setWordWrap(True)
            obs_grid.addWidget(value_label, i, 1)
            
            key = label_text.replace(":", "").lower().replace(" ", "_")
            o_fields[key] = value_label
        
        col3_layout.addLayout(obs_grid)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        sep2.setStyleSheet("background-color: rgba(255,255,255,0.1); max-height: 1px; margin: 5px 0;")
        col3_layout.addWidget(sep2)
        
        # Moon Phase Today section with image
        moon_title = QLabel("🌕 Moon Phase Today")
        moon_title.setFont(QFont("Arial", 10, QFont.Bold))
        moon_title.setAlignment(Qt.AlignCenter)
        col3_layout.addWidget(moon_title)
        
        # Moon phase visualization container
        moon_container = QWidget()
        moon_container.setFixedHeight(180)
        moon_layout = QVBoxLayout(moon_container)
        moon_layout.setContentsMargins(0, 0, 0, 0)
        moon_layout.setSpacing(5)
        
        # Moon phase widget (centered)
        moon_widget = MoonPhaseWidget()
        moon_layout.addWidget(moon_widget, alignment=Qt.AlignCenter)
        
        # Moon phase info
        moon_phase_name_label = QLabel("New Moon")
        moon_phase_name_label.setFont(QFont("Arial", 9, QFont.Bold))
        moon_phase_name_label.setAlignment(Qt.AlignCenter)
        moon_layout.addWidget(moon_phase_name_label)
        
        moon_illumination_label = QLabel("0% illuminated")
        moon_illumination_label.setFont(QFont("Arial", 8))
        moon_illumination_label.setAlignment(Qt.AlignCenter)
        moon_layout.addWidget(moon_illumination_label)
        
        moon_age_label = QLabel("Age: 0 days")
        moon_age_label.setFont(QFont("Arial", 8))
        moon_age_label.setAlignment(Qt.AlignCenter)
        moon_layout.addWidget(moon_age_label)
        
        # Connect labels to moon widget
        moon_widget.set_labels(moon_phase_name_label, moon_illumination_label, moon_age_label)
        
        col3_layout.addWidget(moon_container)
        
        col3_layout.addStretch()
        row3_layout.addWidget(col3, 28)
        
        main_layout.addWidget(row3)
        
        # === ROW 4: Status (height: 10px) ===
        row4 = QFrame()
        row4.setObjectName("row4")
        row4.setFixedHeight(10)
        row4.setFrameStyle(QFrame.NoFrame)
        
        main_layout.addWidget(row4)
        
        return (w_fields, o_fields, planets_label, fact_label, update_label, 
                space_image_label, moon_widget, loc_label, refresh_btn, loc_btn)
    
    @staticmethod
    def apply_theme(widget, theme):
        """Apply theme with 85% transparency to rows and columns"""
        if not theme:
            return
        
        bg_color = theme.get('bg', '#0f172a')
        bg_secondary = theme.get('bg_secondary', '#1e293b')
        text_color = theme.get('text', '#f8fafc')
        accent = theme.get('accent', '#38bdf8')
        button_bg = theme.get('button_bg', '#2563eb')
        
        button_text_color = get_contrasting_color(button_bg)
        
        row_bg = rgba_color(bg_secondary, 0.15)
        col_bg = rgba_color(bg_secondary, 0.15)
        
        stylesheet = f"""
            QWidget {{
                background-color: transparent;
                color: {text_color};
                font-family: 'Arial', sans-serif;
            }}
            
            QFrame#row1, QFrame#row2, QFrame#row3, QFrame#row4 {{
                background-color: {row_bg};
                border: none;
                border-radius: 4px;
            }}
            
            QFrame#col1, QFrame#col2, QFrame#col3 {{
                background-color: {col_bg};
                border: none;
                border-radius: 4px;
            }}
            
            QLabel {{
                color: {text_color};
                background-color: transparent;
                border: none;
                padding: 2px;
            }}
            
            QLabel#space_image_label {{
                background-color: transparent;
                border: none;
                padding: 0;
            }}
            
            QPushButton {{
                background-color: {button_bg};
                color: {button_text_color};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 9px;
            }}
            
            QPushButton:hover {{
                opacity: 0.8;
            }}
            
            QGroupBox {{
                border: none;
                font-weight: bold;
                color: {accent};
            }}
        """
        
        widget.setStyleSheet(stylesheet)